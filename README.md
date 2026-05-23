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

## Ảnh demo
1. **Giao diện trang chủ**
<img width="1894" height="1005" alt="image" src="https://github.com/user-attachments/assets/9e479cdc-e9bd-448b-87ce-9edce05a2717" />



2. **Giao diện khi thực hiện phân tích**
<img width="1891" height="1007" alt="image" src="https://github.com/user-attachments/assets/b2ef5039-e0bf-4689-ba36-44edebe7ad27" />



3. **Giao diện khi xem chi tiết thông tin thuốc**
<img width="680" height="917" alt="image" src="https://github.com/user-attachments/assets/ec1bbe6c-1e06-4beb-82f6-d048b3c1fb81" />



## Kết quả thực nghiệm

### So sánh mô hình gợi ý

Kết quả dưới đây được trích từ notebook huấn luyện/đánh giá trong `Modeling/Modeling_Finetune_PhoBERT_final.ipynb`.

| Mô hình | Hit@1 | Hit@3 | Hit@5 | MRR@5 | Precision@5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| TF-IDF | 0.467 | 0.592 | 0.623 | 0.533 | 0.493 |
| BiLSTM | 0.824 | 0.882 | 0.882 | 0.843 | 0.800 |
| BiGRU | 0.765 | 0.941 | 0.941 | 0.843 | 0.776 |
| TextCNN | 0.765 | 0.824 | 0.824 | 0.794 | 0.800 |
| TF-IDF + SVD | 0.824 | 0.941 | 0.941 | 0.873 | 0.788 |
| PhoBERT | 0.824 | 0.882 | 0.882 | 0.853 | 0.812 |

### Log huấn luyện PhoBERT

| Epoch | Train loss | Val loss | Best val |
| --- | ---: | ---: | ---: |
| 1 | 3.1840 | 2.6387 | 2.6387 |
| 2 | 2.5637 | 2.5072 | 2.5072 |
| 3 | 2.4595 | 2.4560 | 2.4560 |
| 4 | 2.3734 | 2.4781 | 2.4560 |
| 5 | 2.3208 | 2.4341 | 2.4341 |
| 6 | 2.2716 | 2.4558 | 2.4341 |
| 7 | 2.2328 | 2.4659 | 2.4341 |
| 8 | 2.2095 | 2.4746 | 2.4341 |

## Cấu trúc thư mục

| Thư mục / tệp | Vai trò | Nội dung chính |
| --- | --- | --- |
| `crawlData_AnKhang/` | Crawl dữ liệu An Khang | Notebook crawl link và crawl chi tiết thuốc, file CSV dữ liệu thô và file lỗi/fix. |
| `crawlData_DieuTri/` | Crawl dữ liệu Điều Trị | Notebook lấy link, crawl dữ liệu và thư mục chứa link danh mục. |
| `crawlData_LongChau/` | Crawl dữ liệu Long Châu | Notebook crawl danh mục/thuốc, file JSON và CSV dữ liệu thô. |
| `crawlData_MinhChau/` | Crawl dữ liệu Minh Châu | Notebook crawl link và dữ liệu thuốc, các file CSV trung gian và đã làm sạch. |
| `crawlData_Pharmacity/` | Crawl dữ liệu Pharmacity | Notebook crawl link/thuốc và các file CSV lỗi, demo, dữ liệu cuối. |
| `preprocessData_All/` | Hợp nhất và chuẩn hoá dữ liệu | Notebook EDA, mapping danh mục, merge dữ liệu và file CSV hợp nhất cuối cùng. |
| `preprocessData_AnKhang/` | Tiền xử lý riêng An Khang | Dữ liệu đã làm sạch/chuẩn hoá cho nguồn An Khang. |
| `preprocessData_DieuTri/` | Tiền xử lý riêng Điều Trị | Dữ liệu đã chuẩn hoá cho nguồn Điều Trị. |
| `preprocessData_LongChau/` | Tiền xử lý riêng Long Châu | Dữ liệu đã chuẩn hoá cho nguồn Long Châu. |
| `preprocessData_MinhChau/` | Tiền xử lý riêng Minh Châu | Dữ liệu đã chuẩn hoá cho nguồn Minh Châu. |
| `preprocessData_Pharmacity/` | Tiền xử lý riêng Pharmacity | Dữ liệu đã chuẩn hoá cho nguồn Pharmacity. |
| `Modeling/` | Huấn luyện mô hình | Notebook fine-tune PhoBERT và các file model `.pth` đã lưu. |
| `Web/` | Ứng dụng Flask | Mã nguồn web, database SQLite, templates, static assets và logic gợi ý thuốc. |
| `requirements.txt` | Phụ thuộc Python | Danh sách thư viện cần cài đặt để chạy pipeline và web app. |
| `README.md` | Tài liệu dự án | Hướng dẫn tổng quan, cài đặt, chạy và mô tả các thành phần. |

### Cấu trúc tổng quan

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

## Tác giả

- Dự án: DrugRecommandation
- Mô tả: Hệ thống gợi ý thuốc tiếng Việt dựa trên triệu chứng


