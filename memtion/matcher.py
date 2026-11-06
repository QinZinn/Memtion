"""Load meme rules from TOML, score them against features, smooth over time.

Each meme lists features it wants (`when`) and features it must not have
(`not`), each with a weight. The score is a weighted geometric mean, so it
behaves like a soft AND: a heavily weighted feature that is absent pulls the
score towards zero, a lightly weighted one only lowers it a bit.

    score = priority * exp( sum(w * log(max(v, EPS))) / sum(w) )
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from memtion.features import DEFAULT_THRESHOLDS, FEATURE_NAMES

EPS = 0.02


class ConfigError(ValueError):
    pass


@dataclass
class Meme:
    id: str
    file: Path
    label: str = ""
    when: dict[str, float] = field(default_factory=dict)
    not_: dict[str, float] = field(default_factory=dict)
    priority: float = 1.0

    def score(self, features: dict[str, float]) -> float:
        terms = [(features.get(k, 0.0), w) for k, w in self.when.items()]
        terms += [(1.0 - features.get(k, 0.0), w) for k, w in self.not_.items()]
        total = sum(w for _, w in terms)
        if total <= 0:
            return 0.0
        log_sum = sum(w * math.log(max(v, EPS)) for v, w in terms)
        return self.priority * math.exp(log_sum / total)


@dataclass
class Settings:
    fallback: str | None = None
    min_score: float = 0.5
    smoothing: float = 0.4  # EMA factor per frame (1 = no smoothing)
    hold_frames: int = 4  # frames a new winner must stay on top before switching
    switch_margin: float = 0.05


@dataclass
class Config:
    memes: list[Meme]
    settings: Settings
    thresholds: dict[str, tuple[float, float]]
    name: str = ""
    order: int = 100
    path: Path | None = None

    def by_id(self, meme_id: str) -> Meme:
        for m in self.memes:
            if m.id == meme_id:
                return m
        raise KeyError(meme_id)


def _weights(table: object, where: str) -> dict[str, float]:
    if table is None:
        return {}
    if not isinstance(table, dict):
        raise ConfigError(f"{where} must be a table of feature = weight")
    out = {}
    for name, w in table.items():
        if name not in FEATURE_NAMES:
            raise ConfigError(f"{where}: unknown feature '{name}'. Known: {', '.join(FEATURE_NAMES)}")
        if not isinstance(w, (int, float)) or w < 0:
            raise ConfigError(f"{where}.{name}: weight must be a non-negative number")
        out[name] = float(w)
    return out


def load_config(path: str | Path, check_files: bool = True) -> Config:
    path = Path(path)
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    base = path.parent

    s = data.get("settings", {})
    settings = Settings(
        fallback=s.get("fallback"),
        min_score=float(s.get("min_score", Settings.min_score)),
        smoothing=float(s.get("smoothing", Settings.smoothing)),
        hold_frames=int(s.get("hold_frames", Settings.hold_frames)),
        switch_margin=float(s.get("switch_margin", Settings.switch_margin)),
    )

    thresholds = {}
    for name, pair in data.get("thresholds", {}).items():
        if name not in DEFAULT_THRESHOLDS:
            raise ConfigError(f"[thresholds]: unknown threshold '{name}'")
        if not (isinstance(pair, list) and len(pair) == 2):
            raise ConfigError(f"[thresholds].{name} must be [low, high]")
        thresholds[name] = (float(pair[0]), float(pair[1]))

    memes = []
    seen = set()
    for i, m in enumerate(data.get("meme", [])):
        where = f"meme #{i + 1}"
        if "id" not in m or "file" not in m:
            raise ConfigError(f"{where}: 'id' and 'file' are required")
        if m["id"] in seen:
            raise ConfigError(f"{where}: duplicate id '{m['id']}'")
        seen.add(m["id"])
        where = f"meme '{m['id']}'"
        meme = Meme(
            id=m["id"],
            file=(base / m["file"]).resolve(),
            label=m.get("label", m["id"]),
            when=_weights(m.get("when"), f"{where}.when"),
            not_=_weights(m.get("not"), f"{where}.not"),
            priority=float(m.get("priority", 1.0)),
        )
        if check_files and not meme.file.is_file():
            raise ConfigError(f"{where}: image not found: {meme.file}")
        memes.append(meme)
    if not memes:
        raise ConfigError("no [[meme]] entries found")
    if settings.fallback is not None and settings.fallback not in seen:
        raise ConfigError(f"[settings].fallback '{settings.fallback}' is not a meme id")
    pack = data.get("pack", {})
    return Config(
        memes=memes,
        settings=settings,
        thresholds=thresholds,
        name=str(pack.get("name", path.stem)),
        order=int(pack.get("order", 100)),
        path=path,
    )


def discover_packs(folder: str | Path) -> tuple[list[Config], list[str]]:
    """Load every `*.toml` pack in `folder`, sorted by [pack].order then name.

    Returns (packs, errors); a broken pack is reported instead of stopping the app.
    """
    packs, errors = [], []
    for path in sorted(Path(folder).glob("*.toml")):
        try:
            packs.append(load_config(path))
        except (ConfigError, OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.name}: {exc}")
    packs.sort(key=lambda c: (c.order, c.name))
    return packs, errors


def rank(memes: list[Meme], features: dict[str, float]) -> list[tuple[str, float]]:
    """All memes with their score, best first."""
    scores = [(m.id, m.score(features)) for m in memes]
    return sorted(scores, key=lambda x: x[1], reverse=True)


class Smoother:
    """Exponential smoothing + hysteresis so the meme doesn't flicker."""

    def __init__(self, settings: Settings):
        self.s = settings
        self.ema: dict[str, float] = {}
        self.current: str | None = None
        self._candidate: str | None = None
        self._count = 0

    def update(self, scores: dict[str, float]) -> str | None:
        a = self.s.smoothing
        for k, v in scores.items():
            self.ema[k] = a * v + (1 - a) * self.ema.get(k, v)

        best, best_score = max(self.ema.items(), key=lambda kv: kv[1], default=(None, 0.0))
        if best is None or best_score < self.s.min_score:
            best = self.s.fallback
        if best == self.current:
            self._candidate, self._count = None, 0
            return self.current
        # A new (non-fallback) winner needs a clear lead over the meme on screen.
        contested = self.current is not None and best is not None and best != self.s.fallback
        if contested and best_score < self.ema.get(self.current, 0.0) + self.s.switch_margin:
            self._candidate, self._count = None, 0
            return self.current

        if best == self._candidate:
            self._count += 1
        else:
            self._candidate, self._count = best, 1
        if self.current is None or self._count >= self.s.hold_frames:
            self.current = best
            self._candidate, self._count = None, 0
        return self.current

    def reset(self) -> None:
        self.ema.clear()
        self.current = None
        self._candidate, self._count = None, 0
