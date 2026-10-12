# Installer UI anti-slop and artwork-safe zones

## Design read

Before code, write one sentence: installer type, audience, visual language and platform. Set three bounded dials:

- composition variance: usually 4-7 for a native installer;
- motion: 1-4, feedback only;
- density: 3-6, enough information to act without obscuring art.

A Windows installer is a compact transactional tool, not a landing page. Borrow critique and token discipline from web design systems, not web page structures.

## Artwork analysis

At the final client size, record:

- source dimensions and exact cover/crop transform;
- logo/title rectangle;
- face/eye rectangles;
- dominant focal subject rectangle;
- one or more low-salience safe rectangles;
- minimum outer margin and DPI scaling behavior.

Controls must remain inside a safe rectangle. Protected rectangles are hard exclusions. If no useful safe rectangle exists, use a narrow bottom rail, a separate native folder dialog, or add a local scrim only behind controls. Never blur, dim or cover the entire artwork merely to make a generic centered panel work.

## Token brief

Create project `DESIGN.md` containing exact values for:

- surface/scrim, text, muted text, accent, accent text, border and error colors;
- body, label, action and status typography;
- 4/8 px spacing rhythm;
- one corner-radius rule;
- control heights and hit targets;
- panel/safe-zone coordinates;
- hover, pressed, disabled, focus, busy, success, refusal and error states.

Run contrast checks. Component text/background combinations must pass WCAG AA when practical for native controls.

## Anti-slop rules

- Keep supplied artwork full-bleed when it is the brand anchor.
- **Tôn trọng tỉ lệ và hướng ảnh gốc (Portrait vs Landscape):** Nếu người dùng cung cấp poster hoặc hình nền dạng dọc (portrait, tỉ lệ 3:4, 2:3, 9:16), **TUYỆT ĐỐI KHÔNG ép crop ngang sang 16:9 (1024×576)** làm cắt cụt mất tiêu đề logo hoặc nhân vật chính. Bắt buộc thiết kế cửa sổ cài đặt theo bố cục dọc tương ứng (ví dụ: `600×800` cho tỉ lệ 3:4, `540×810` cho 2:3, `540×960` cho 9:16) để bảo tồn 100% toàn bộ hình ảnh nghệ thuật gốc. Vùng điều khiển đáy (action rail) đặt gọn ở vùng chân tranh tối màu.
- Do not repeat a game title already present in the image.
- No header bar unless it carries a real window function.
- No centered hero, feature cards, decorative badges, fake versions, weather/location strips, generic glassmorphism or purple/blue glow.
- No arbitrary mixtures of pill buttons, square inputs and heavily rounded panels.
- One action label per intent: `Cài đặt`, `Gỡ cài đặt`, `Chọn thư mục`.
- No decorative progress bar in idle state. Progress exists only while work is running.
- Do not invent technical claims or fake precision.
- Visible copy is short and functional. Diagnostics remain in modal/CLI output.

## Native interaction gate

- Folder field has a visible label and browse control.
- Install is the only primary action. Uninstall is visually secondary.
- Buttons have hover, pressed, disabled and focus states; text never wraps.
- Tab order follows reading order. Enter activates the primary action; Escape closes only when no transaction runs.
- Busy state disables mutation controls and exposes real status/progress.
- Message boxes explain success, refusal and recovery without leaking internal paths.
- DPI test at 100%, 125% and 150%; no clipped Vietnamese text.

## Screenshot pre-flight

Capture the exact compiled candidate, not a mockup. Verify programmatically where possible:

1. client size and crop transform;
2. each interactive rectangle lies inside the chosen safe zone;
3. no interactive rectangle intersects logo/title/face/focal rectangles;
4. minimum control height and margins;
5. no text clipping or wrapped primary CTA;
6. contrast, focus order and disabled/busy states;
7. artwork remains legible and compositionally dominant.

Promotion requires both this visual gate and the transactional install/uninstall gates in `SKILL.md`.

## Locked chassis

These values are the house standard. Do not drift per project:

- client `1024 x 576` (landscape 16:9) or portrait matching poster (e.g. `600 x 800` for 3:4, `540 x 810` for 2:3), `FormBorderStyle.None`;
- `Cài` and `Gỡ` adjacent, same Y, 0-24px gap;
- build/version in a fixed-width right-aligned cell (e.g. `STEAM BUILD  <buildid>` lấy chính xác từ `appmanifest_<appid>.acf` trường `buildid`, TUYỆT ĐỐI không bịa năm/placeholder như `STEAM BUILD 2026`; chỉ 1 dòng đơn nhất, omit redundant `v1.0` hay `Bản dịch...`), never `AutoSize` on the right edge;
- drag empty artwork only; controls keep the default pointer; no `Cursor.SizeAll` on parents;
- `ShowInTaskbar=true` and native `WS_MINIMIZEBOX`;
- signature `Syrin.online`, rainbow phase `0.045`, bottom-right, 8px inner margin, MUST be clickable to open `https://syrin.online/` with hand cursor on hover;
- action rail scrim: MUST have translucent glass effect (~70-75% opacity dark glass) letting underlying artwork show through, NEVER a solid opaque flat black box;
- no second footer, no chart cards, no dashboard chrome, no web kit copy;
- **Zero-Clutter (Không thêm chữ dài dòng)**: Tuyệt đối không thêm các hộp text tĩnh dài dòng ("Sẵn sàng cài đặt...", "Tự động sao lưu và hỗ trợ gỡ cài đặt sạch sẽ..."). Giữ giao diện tối giản, chỉ đường dẫn + duyệt + Cài/Gỡ + Steam Build ID. Hướng dẫn chi tiết chỉ hiện ở modal MessageBox sau khi cài đặt thành công;
- **Bảo vệ Logo & Focal Artwork**: Nếu ảnh nền gốc đã có sẵn logo/title to (như `LOST & FOUND`), tuyệt đối KHÔNG đặt dock/panel đè lên logo đó. Phải khảo sát vùng an toàn (thường là dải bottom-rail góc dưới) để toàn bộ logo, bàn tay, nhân vật chính lộ diện 100%;
- **WinForms GDI+ Ampersand Quirk**: Mọi `Label` chứa text có ký tự `&` (tên game, đường dẫn) phải luôn đặt `UseMnemonic = false` để tránh GDI+ nuốt mất dấu `&`;
- **WinExe Console Handling**: Khi hỗ trợ CLI test/preview trên WinExe (.NET), gọi `Console.OutputEncoding` phải bọc trong `try/catch` hoặc gọi Win32 `AttachConsole(-1)` để tránh crash handle invalid.

## Standalone PyInstaller / Python Chassis Performance Rule

When bundling a single-file Python/Tkinter installer (`--onefile`):

1. **Eliminate Dependency Bloat & Defender Scan Delay**:
   - PyInstaller auto-detects site-packages and can bundle SciPy, NumPy, PIL, OpenSSL, win32, causing >1,000 files and 75 MB extracted to `%TEMP%`.
   - Windows Defender Real-Time Protection scans every extracted file, inducing a 5-6 second delay before the GUI appears.
   - Use native `tk.PhotoImage` for PNG images (standard library in Python 3.4+ / Tk 8.6+) instead of importing `PIL` (`_avif.pyd` alone is 7.5MB).
   - Explicitly add `--exclude-module` for `numpy`, `scipy`, `PIL`, `ssl`, `_ssl`, `matplotlib`, `pandas`, `torch`, `win32com`, `win32gui`, `psutil`, `charset_normalizer`.
   - Optimize multi-res `app.ico` with PNG compression (<50KB instead of 560KB uncompressed BMPs).
   - Keeps total extracted files <40 files, reducing window visibility latency from 5.6s to <0.08s (instant startup).
2. **Instant Window Display**:
   - Apply `WS_EX_APPWINDOW` via `ctypes` directly on parent hwnd without calling `wm_withdraw()`/`wm_deiconify()` to eliminate startup flicker.
   - Text elements drawn directly on `tk.Canvas` have 100% native transparency over the blended glass background.

Start from `templates/InstallerChassis.cs` plus `templates/installer-gui-layout.example.json`. Do not rewrite the shell. Fill `installer-gui-layout.json`, then run `scripts/verify_installer_gui_layout.py <layout.json> --csharp Program.cs --screenshot <compiled-gui.png>` before promotion. A screenshot without this JSON+PNG gate is not proof. Existing installers that drifted (wrong rainbow phase, missing chassis numbers) are repaired to this lock; do not leave old EXEs on 0.041 or a second footer.

## Proven compact pattern

Use when the supplied image already includes strong branding:

- locked 1024x576 chassis above;
- full-bleed `cover` artwork;
- compact dark local scrim/panel in the lowest-salience safe zone;
- one build label, one folder row, two actions;
- actual status/progress appears only during a transaction;
- signature in the bottom-right, never over title/faces.

The lazier safe alternative is a bottom action rail plus a native folder dialog. Prefer it when a panel would cover the title or faces. The chassis numbers still apply.
