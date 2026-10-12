# Fixtures Directory Notice

Thư mục này được sử dụng làm fixture cho các bài kiểm thử tự động của toolchain.

**Lưu ý quan trọng về bản quyền:**
- Các tệp dữ liệu game thương mại thực tế (như phông chữ bên thứ ba, tệp nhị phân `.font`, file game gốc) **TUYỆT ĐỐI KHÔNG ĐƯỢC PHÂN PHỐI** trong kho mã nguồn mở này.
- Các bài kiểm tra yêu cầu tài nguyên game thực tế sẽ tự động chuyển sang chế độ `skipTest` khi biến môi trường `VIETHOA_FIXTURE_ROOT` không được thiết lập.
- Để chạy kiểm thử đầy đủ trên dữ liệu của bạn, hãy thiết lập:
  ```bash
  export VIETHOA_FIXTURE_ROOT="/path/to/your/unpacked/assets"
  ```
