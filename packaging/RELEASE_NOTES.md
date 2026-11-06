Bản build sẵn của Memtion, **không cần cài Python**. Đã kèm model MediaPipe và 2 pack meme (Meme gốc, Blob).

| Hệ điều hành | File |
|---|---|
| Windows 10/11 (64-bit) | `Memtion-…-windows-x64.zip` |
| macOS 11+ chip Apple (M1 trở lên) | `Memtion-…-macos-arm64.zip` |
| Linux x86_64 (glibc ≥ 2.35, ví dụ Ubuntu 22.04+) | `Memtion-…-linux-x64.tar.gz` |

Chưa có bản cho Mac chip Intel vì MediaPipe không phát hành bản cho nền tảng đó.

### Windows
Giải nén, mở thư mục `memtion`, chạy `memtion.exe`. Nếu SmartScreen cảnh báo (app chưa ký số): **More info → Run anyway**.

### macOS
Giải nén ra `Memtion.app`. App chưa được Apple ký nên lần đầu macOS sẽ chặn, mở Terminal chạy:
```bash
xattr -dr com.apple.quarantine ~/Downloads/Memtion.app
```
rồi mở app và bấm **Cho phép** khi được hỏi quyền dùng camera.

### Linux
```bash
sudo apt install libegl1 libgles2   # Debian/Ubuntu; MediaPipe cần các thư viện này
```
```bash
tar -xzf Memtion-*-linux-x64.tar.gz && ./memtion/memtion
```

### Phím tắt
`p` đổi pack · `c` hiệu chỉnh mặt (nên bấm 1 lần khi mới ngồi vào) · `d` debug · `s` chụp màn hình · `q` thoát

Muốn thêm pack meme riêng: đặt file `.toml` vào `%APPDATA%\memtion\packs` (Windows), `~/Library/Application Support/memtion/packs` (macOS) hoặc `~/.config/memtion/packs` (Linux). Chạy `memtion --list` để xem các pack đang có.

📖 Hướng dẫn đầy đủ (kèm ảnh và bảng tư thế → meme): https://github.com/QinZinn/Memtion/blob/main/docs/HUONG_DAN.md
