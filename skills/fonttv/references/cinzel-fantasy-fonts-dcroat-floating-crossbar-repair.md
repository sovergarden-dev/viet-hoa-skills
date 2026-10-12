# Cinzel Fantasy Fonts — Dcroat / dcroat Floating Crossbar Repair

Phạm vi: route A, recipe riêng cho họ Cinzel; tọa độ chỉ đúng với bản font đã đo. Kết quả vẫn phải qua các gate trong `quality-gates.md`; Cinzel là OFL, kiểm Reserved Font Name trước khi phân phối bản đã sửa.

## 1. Hiện Tượng Lỗi (The Overline Defect)

Họ font `Cinzel` (bao gồm `Cinzel-Regular`, `Cinzel-Medium`, `Cinzel-SemiBold`, `Cinzel-Bold`, `Cinzel-ExtraBold`, `Cinzel-Black` và `CINZELDECORATIVE`) do Google Fonts phát hành rất phổ biến trong các game fantasy RPG phương Tây.

Tuy nhiên, định nghĩa glyph `Dcroat` (U+0110 `Đ`) và `dcroat` (U+0111 `đ`) trong các font này bị lỗi typography nghiêm trọng:
- Component thanh ngang (`uni0304` - macron) bị đặt ở tọa độ `y = 795..860`, nằm lơ lửng phía trên đỉnh đầu chữ D (vượt qua cả `cap-height` là 700).
- Chữ `Đ` bị biến dạng thành $\bar{D}$ (chữ D có dấu gạch ngang trên đỉnh đầu như chữ D âm vực / macron) thay vì dấu gạch ngang cắt ngang thân đứng.

## 2. Quy Trình Sửa Đổi Bằng `fontTools`

### A. Đối với Cinzel Standard (`Cinzel-*`)
Các font Cinzel tiêu chuẩn xây dựng `Dcroat` và `dcroat` dưới dạng glyph composite ghép từ glyph `D` (hoặc `d`) và component `uni0304`.

```python
import io
from fontTools.ttLib import TTFont

def fix_cinzel_standard(font_bytes: bytes) -> bytes:
    f = TTFont(io.BytesIO(font_bytes))
    glyf = f["glyf"]
    
    # 1. Dcroat (Đ hoa): đưa thanh ngang về giữa thân đứng
    if "Dcroat" in glyf:
        g = glyf["Dcroat"]
        for comp in g.components:
            if comp.glyphName == "uni0304":
                comp.x = -185
                comp.y = -350  # Dời xuống ~350 units, đưa thanh ngang về y ~ 380
        g.recalcBounds(glyf)
        
    # 2. dcroat (đ thường): đưa thanh ngang về giữa thân chữ thường
    if "dcroat" in glyf:
        g = glyf["dcroat"]
        for comp in g.components:
            if comp.glyphName == "uni0304":
                comp.x = -185
                comp.y = -415  # Đưa thanh ngang về y ~ 320
        g.recalcBounds(glyf)
        
    buf = io.BytesIO()
    f.save(buf)
    return buf.getvalue()
```

### B. Đối với Cinzel Decorative (`CINZELDECORATIVE-*`)
Font `CINZELDECORATIVE` không dùng component mà vẽ thanh ngang bằng contour vector độc lập trong `Dcroat`.

```python
def fix_cinzel_decorative(font_bytes: bytes) -> bytes:
    f = TTFont(io.BytesIO(font_bytes))
    glyf = f["glyf"]
    if "Dcroat" in glyf:
        g = glyf["Dcroat"]
        if g.numberOfContours > 0:
            coords = g.coordinates
            # Contour đầu tiên (hoặc contour thanh ngang) được dịch chuyển tọa độ
            for i in range(g.endPtsOfContours[0] + 1):
                coords[i] = (coords[i][0] - 330, coords[i][1] - 420)
            g.recalcBounds(glyf)
    buf = io.BytesIO()
    f.save(buf)
    return buf.getvalue()
```

## 3. Tiêu Chuẩn Kiểm Định (QA Verification)
Sau khi can thiệp, chạy script kiểm tra bounding box của glyph `Dcroat`:
```python
coords = g.getCoordinates(glyf)[0]
ys = [p[1] for p in coords]
assert max(ys) <= 701, f"Lỗi: Thanh ngang vẫn nằm vọt trần (yMax = {max(ys)} > 701)!"
```
- Bắt buộc `yMax <= 701` (bằng đỉnh đầu chữ D hoa).
- Thanh ngang phải nằm cân đối cắt chính giữa thân đứng ở `y ~ 380`.
