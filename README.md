# Memtion

Mở webcam, theo dõi khuôn mặt + tay + cơ thể, rồi hiện **meme có tư thế / biểu cảm giống bạn nhất** ngay bên cạnh hình camera.

![Demo](docs/images/demo.gif)

📖 **[Hướng dẫn sử dụng](docs/HUONG_DAN.md)**: cài đặt, phím tắt, bảng tư thế → meme của cả 2 pack, mẹo và xử lý sự cố.

```
┌──────────────────────┬──────────────────┐
│   camera (gương)     │      meme        │
│   + overlay debug    │   "Hahaha!"      │
└──────────────────────┴──────────────────┘
```

## Tải bản build sẵn

Vào trang [Releases](https://github.com/QinZinn/Memtion/releases), tải file cho máy bạn (Windows x64,
macOS chip Apple, Linux x64). Không cần cài Python; hướng dẫn mở app có ngay trên trang release.
Muốn chạy từ mã nguồn thì xem phần cài đặt bên dưới.

## Vì sao dùng Python mà không dùng Rust?

Phần khó nhất của app là nhận diện điểm mốc mặt / tay / cơ thể và biểu cảm. **MediaPipe** làm sẵn tất cả việc đó
(478 điểm mặt + 52 "blendshape" biểu cảm như cười, há miệng, nhắm mắt…, 33 điểm cơ thể, 21 điểm mỗi bàn tay và
nhận diện cử chỉ như 👍), chạy realtime trên CPU, nhưng chỉ có bản chính thức cho Python. Bên Rust sẽ phải tự
nạp model ONNX và viết lại toàn bộ khâu tiền/hậu xử lý mà không được thêm gì đáng kể về tốc độ (phần nặng vẫn
nằm trong model). Nên Python là lựa chọn hợp lý.

## Cài đặt (Linux)

Cần Python ≥ 3.11 và một webcam.

```bash
sudo apt install libegl1 libgles2 libgl1   # MediaPipe cần các thư viện OpenGL/EGL này (Ubuntu/Debian)
```

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -e .
```

Lần chạy đầu tiên sẽ tự tải các model MediaPipe (~30 MB) vào thư mục `models/`. Muốn tải trước:

```bash
memtion --download-models
```

## Chạy

```bash
memtion            # hoặc: python -m memtion
```

| Phím | Tác dụng |
|------|----------|
| `q` / `Esc` | thoát |
| `p` | đổi pack meme (Meme gốc ↔ Blob) |
| `d` | bật/tắt overlay debug (điểm mốc, điểm số từng meme, giá trị đặc trưng) |
| `c` | **hiệu chỉnh**: nhìn thẳng với mặt bình thường ~1 giây, app sẽ lấy đó làm mốc "trung tính" |
| `m` | bật/tắt lật gương |
| `s` | lưu ảnh chụp màn hình vào `screenshots/` |

Nên bấm `c` một lần sau khi ngồi vào chỗ: webcam laptop thường đặt cao hơn mắt nên khi bạn nhìn màn hình,
đầu hơi cúi sẵn; hiệu chỉnh xong thì "cúi đầu" / "ngẩng đầu" mới được tính đúng.

Một số tuỳ chọn:

```bash
memtion --pack blob         # bắt đầu với pack Blob
memtion --list              # xem các pack và meme
memtion --camera 1          # dùng webcam khác (/dev/video1)
memtion --fast              # pose model "lite": nhanh hơn trên máy yếu
memtion --debug             # mở sẵn overlay debug
memtion --camera clip.mp4   # chạy trên file video
memtion --image anh.jpg --out ketqua.jpg   # phân tích 1 ảnh, in điểm số, lưu ảnh kết quả
```

## Các pack meme

App có 2 pack, bấm `p` để đổi:

- **Meme gốc** (`packs/default.toml`, ảnh trong `Sample_Meme/`): 20 meme, thiên về tư thế tay và cơ thể (bảng bên dưới).
- **Blob** (`packs/blob.toml`, ảnh trong `Blob_Meme/`): 31 mặt vẽ tay, thiên về biểu cảm khuôn mặt: cười, khóc,
  há miệng, chu môi, phồng má, mím môi, nhíu mày, nghiêng/cúi đầu, ngón cái lên/xuống, ló mặt từ mép khung hình…
  Vài meme không có biểu cảm tương ứng đo được (lè lưỡi, đeo kính, hề, bó hoa) nên được gán cho tư thế gần nghĩa
  nhất; xem `label` và luật trong file.

### Pack "Meme gốc"

| id | Làm thế này | Meme |
|----|-------------|------|
| `break_free` | giơ cả hai tay lên cao quá đầu | người bẻ xích |
| `thumbs_up` | giơ ngón cái 👍 | mèo like |
| `pointing` | chỉ tay (ngón trỏ duỗi, các ngón khác co), há miệng | wojak chỉ tay |
| `shocked` | hai tay ôm đầu, há miệng, mở to mắt | anh ôm đầu sốc |
| `crying` | hai tay che má/mắt, nhíu mày buồn | hải ly khóc |
| `sweet` | hai tay chống cằm + cười | Angela dễ thương |
| `choking` | tay ôm cổ, nhắm/nheo mắt, nhăn mặt | anh tự bóp cổ |
| `phone_call` | một tay áp lên tai | anh nghe điện thoại |
| `smug` | một tay đặt lên đầu/sau gáy, mỉm cười | thỏ hồng tự tin |
| `hug` | khoanh tay / tự ôm mình, mỉm cười | ôm gối |
| `thinking_side` | tay chống cằm + quay mặt sang bên | mèo suy tư |
| `thinking` | tay chống cằm (+ nhìn lên trên) | khỉ suy tư |
| `reading` | cúi đầu nhìn xuống thứ đang cầm trước ngực | chó đọc giấy |
| `laughing` | cười to, há miệng | Jerry cười |
| `grin` | cười tươi, miệng khép | nhân vật pixel cười |
| `content` | nhắm mắt + ngẩng mặt lên | chó phê |
| `confused` | nghiêng đầu, không cười | chó "?" |
| `lone_wolf` | quay mặt sang bên, tay để xa mặt | sói cô độc |
| `defeated` | vai nghiêng (dựa tường) + cúi đầu | ngựa dựa tường |
| `blank_stare` | mặt buồn / không làm gì đặc biệt (meme mặc định) | Spongebob đội mũ |

## Tuỳ chỉnh

Toàn bộ luật nằm trong các file [`packs/*.toml`](packs/), **không cần sửa code**:

```toml
[[meme]]
id = "laughing"
file = "Sample_Meme/....jpg"
label = "Hahaha!"
priority = 1.05
when = { smile = 1.0, mouth_open = 1.0 }   # cần có
not  = { hand_chin = 0.5 }                 # không được có (ví dụ)
```

- Mỗi đặc trưng có giá trị 0..1. Điểm của meme = `priority` × trung bình nhân có trọng số của các đặc trưng
  trong `when` (và `1 - giá trị` của các đặc trưng trong `not`). Thiếu một đặc trưng nặng ký → điểm gần 0.
- Meme có điểm cao nhất (sau khi làm mượt theo thời gian) sẽ được hiện; nếu không meme nào đạt `min_score`
  thì hiện meme `fallback`.
- **Thêm meme mới**: chép ảnh vào thư mục ảnh của pack, thêm một khối `[[meme]]`. Bật `--debug` để xem đặc trưng
  nào sáng lên khi bạn làm tư thế đó rồi đưa vào `when`.
- **Thêm pack mới**: tạo một file `.toml` (có bảng `[pack]` với `name`) trong `packs/`, hoặc trong thư mục cấu hình
  người dùng nếu bạn dùng bản build sẵn: `~/.config/memtion/packs` (Linux),
  `~/Library/Application Support/memtion/packs` (macOS), `%APPDATA%\memtion\packs` (Windows).
- `tests/test_packs.py` kiểm tra mỗi biểu cảm chọn đúng meme của nó với khoảng cách điểm rõ ràng; thêm kịch bản
  vào đó khi bạn thêm meme để bắt các luật "giẫm chân" lên nhau.
- Ngưỡng của đặc trưng (ví dụ cười bao nhiêu thì tính là cười) chỉnh trong bảng `[thresholds]`.

Danh sách đặc trưng có trong phần đầu `packs/default.toml`; định nghĩa chi tiết trong `memtion/features.py`.

## Cấu trúc code

```
memtion/
  detector.py   MediaPipe (mặt, cơ thể, tay + cử chỉ)  ->  Observation (numpy thuần)
  features.py   Observation  ->  các đặc trưng có tên, giá trị 0..1
  matcher.py    đọc memes.toml, chấm điểm meme, làm mượt + chống nhấp nháy
  render.py     vẽ khung meme, chữ tiếng Việt, overlay debug
  cli.py        vòng lặp webcam, phím tắt, chọn pack, chế độ --image
  models.py     tải model MediaPipe
  paths.py      đường dẫn tài nguyên / thư mục người dùng (chạy từ mã nguồn hoặc bản build)
packs/          mỗi file .toml là một pack: luật ánh xạ tư thế -> meme
packaging/      spec PyInstaller + ghi chú release
tests/          pytest (test tích hợp chạy trên các ảnh meme có người thật)
.github/workflows/build.yml   test -> build 3 hệ điều hành -> release
```

```bash
pip install -e ".[dev]"
```

```bash
pytest
```

## Build và phát hành

Workflow [`.github/workflows/build.yml`](.github/workflows/build.yml) chạy mỗi lần push:

1. **Test**: ruff + pytest (kể cả test tích hợp với model thật) trên Ubuntu.
2. **Build**: PyInstaller trên Windows, macOS (Apple Silicon) và Linux. Mỗi bản build được chạy thử ngay trên
   runner (`--list` và nhận diện một ảnh mẫu phải ra `shocked`) rồi đóng gói thành file tải về trong mục Artifacts.
3. **Release**: đính các file trên vào một GitHub Release, theo một trong hai cách:
   - Push một tag `v*`:

     ```bash
     git tag v0.2.0
     ```

     ```bash
     git push origin v0.2.0
     ```

   - Hoặc trên GitHub: **Actions → Build → Run workflow**, chọn branch `main`, điền `release_tag` (ví dụ `v0.2.0`).
     Workflow sẽ tự tạo tag trên commit đó.

Build thử trên máy mình:

```bash
pip install -e . pyinstaller && python -m memtion --download-models && pyinstaller packaging/memtion.spec --noconfirm
```

Kết quả nằm ở `dist/memtion/` (hoặc `dist/Memtion.app` trên macOS).

## Gỡ lỗi

- **`libEGL.so.1: cannot open shared object file`**: cài `libegl1 libgles2` như ở trên.
- **Không mở được camera**: kiểm tra `ls /dev/video*`, thử `--camera 1`, và đảm bảo user thuộc nhóm `video`.
- **Cửa sổ không hiện trên Wayland**: thử `QT_QPA_PLATFORM=xcb memtion`.
- **Meme nhảy lung tung / quá nhạy**: tăng `hold_frames` hoặc giảm `smoothing` trong `[settings]`.
- **Một tư thế khó nhận**: bật `d`, xem đặc trưng nào thiếu, rồi hạ trọng số hoặc chỉnh `[thresholds]`.
