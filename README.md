# DrugRecommandation

Hệ thống gợi ý thuốc tiếng Việt dựa trên triệu chứng, kết hợp dữ liệu thu thập từ nhiều nhà thuốc, tiền xử lý dữ liệu và mô hình PhoBERT fine-tune để tìm thuốc phù hợp. Dự án gồm pipeline crawl dữ liệu, chuẩn hoá dữ liệu, huấn luyện mô hình và triển khai web Flask để tra cứu, lưu lịch sử và quản trị thuốc.

## Mục tiêu dự án

- Gợi ý thuốc từ mô tả triệu chứng đầu vào.
- Tổng hợp dữ liệu thuốc từ nhiều nguồn khác nhau.
- Cung cấp giao diện web để tìm kiếm, xem chi tiết và lưu thuốc yêu thích.
- Hỗ trợ tài khoản người dùng, lịch sử tìm kiếm và trang quản trị.

## Tính năng chính

- Tìm kiếm thuốc theo triệu chứng bằng mô hình PhoBERT và embedding.
- Xem chi tiết thuốc: thành phần, chỉ định, chống chỉ định, tác dụng phụ, cách dùng.
- Lưu và quản lý danh sách thuốc đã lưu.
- Lưu lịch sử tìm kiếm và cho phép tìm lại truy vấn cũ.
- Đăng ký, đăng nhập, cập nhật hồ sơ cá nhân, đổi mật khẩu.
- Trang quản trị để quản lý thuốc, người dùng và thống kê hệ thống.

## Kiến trúc tổng quan

1. **Crawl dữ liệu**: thu thập dữ liệu từ nhiều nguồn nhà thuốc.
2. **Preprocess dữ liệu**: làm sạch, chuẩn hoá và hợp nhất dữ liệu.
3. **Modeling**: fine-tune PhoBERT và xây dựng vector biểu diễn thuốc.
4. **Web app**: triển khai giao diện Flask để người dùng tra cứu và quản trị.

## Cấu trúc thư mục

```text
DrugRecommandation/
├── crawlData_AnKhang/
├── crawlData_DieuTri/
├── crawlData_LongChau/
├── crawlData_MinhChau/
├── crawlData_Pharmacity/
├── Modeling/
├── preprocessData_All/
├── preprocessData_AnKhang/
├── preprocessData_DieuTri/
├── preprocessData_LongChau/
├── preprocessData_MinhChau/
├── preprocessData_Pharmacity/
├── Web/
├── requirements.txt
└── README.md
```

## Công nghệ sử dụng

- Python
- Flask
- Pandas, NumPy
- PyTorch
- Transformers, PhoBERT
- FAISS
- scikit-learn
- SQLite
- Selenium, BeautifulSoup

## Dữ liệu và mô hình

### Dữ liệu

- Dữ liệu nguồn được crawl từ nhiều nhà thuốc và website dược phẩm.
- Dữ liệu sau hợp nhất và mapping nằm trong `preprocessData_All/`.
- File mặc định mà web app sử dụng là:
  - `preprocessData_All/merged_drug_data_mapped(2).csv`

### Mô hình

- Mô hình mặc định:
  - `Modeling/phobert_finetuned(3)_latest.pth`
- Web app sẽ nạp mô hình PhoBERT fine-tune để sinh embedding và tính mức độ phù hợp giữa triệu chứng và thuốc.

## Hướng dẫn cài đặt

### 1. Tạo môi trường ảo

Trên Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Cài đặt thư viện

```powershell
pip install -r requirements.txt
```

### 3. Kiểm tra file dữ liệu và model

Đảm bảo tồn tại các file mặc định sau:

- `preprocessData_All/merged_drug_data_mapped(2).csv`
- `Modeling/phobert_finetuned(3)_latest.pth`
- `Web/database/` sẽ tự tạo nếu chưa có

## Cấu hình môi trường

Các biến môi trường tuỳ chọn:

- `FLASK_SECRET_KEY`: khoá bí mật cho Flask session.
- `DRUG_DATASET_PATH`: đường dẫn tới file CSV dữ liệu thuốc.
- `DRUG_PHOBERT_PATH`: đường dẫn tới file model `.pth`.
- `DRUG_MAX_LENGTH`: độ dài token tối đa khi mã hoá văn bản, mặc định `128`.

Ví dụ trên PowerShell:

```powershell
$env:FLASK_SECRET_KEY="your-secret-key"
$env:DRUG_DATASET_PATH="D:\OU\KhoaLuanTotNghiep\DrugRecommandation\preprocessData_All\merged_drug_data_mapped(2).csv"
$env:DRUG_PHOBERT_PATH="D:\OU\KhoaLuanTotNghiep\DrugRecommandation\Modeling\phobert_finetuned(3)_latest.pth"
$env:DRUG_MAX_LENGTH="128"
```

## Chạy ứng dụng web

Từ thư mục `Web/`:

```powershell
cd Web
python app.py
```

Sau đó mở trình duyệt tại:

```text
http://127.0.0.1:5000
```

Hoặc theo cấu hình mặc định của app:

- host: `0.0.0.0`
- port: `5000`

## Chức năng web

- Trang chủ và tìm kiếm thuốc theo triệu chứng.
- Đăng nhập và đăng ký tài khoản.
- Xem lịch sử tìm kiếm.
- Lưu thuốc yêu thích.
- Xem chi tiết thuốc.
- Trang cá nhân và đổi mật khẩu.
- Trang quản trị cho thuốc, người dùng và thống kê.

## Cơ sở dữ liệu

- Web app sử dụng SQLite.
- File database mặc định nằm tại:
  - `Web/database/simple_app.db`
- Database sẽ được khởi tạo tự động qua `Web/init.py`.

## Ghi chú

- Đây là dự án phục vụ nghiên cứu/đồ án, nên dữ liệu và model có thể cần cập nhật lại nếu thay đổi nguồn crawl hoặc cấu trúc cột.
- Nếu bạn muốn chạy trên máy khác, hãy kiểm tra lại đúng đường dẫn dataset và model trong phần biến môi trường.
- Có thể bổ sung ảnh demo giao diện vào README để trang GitHub trực quan hơn.
