<h1>DRUG RECOMMENDATION</h1>
Xây dựng hệ thống hỗ trợ người dùng tra cứu và tham khảo thông tin thuốc nhanh chóng, thuận tiện.
Hệ thống phát triển theo hướng xử lý ngôn ngữ tự nhiên(NLP) tạo nên tảng cho việc phân tích và phát triển các mô hình gợi ý trong thực tế.


<h2>Tính năng chính</h2>
<li>Nhập mô tả triệu chứng để nhận gợi ý danh sách thuốc liên quan.</li>
<li>Xem các thông tin chi tiết thuốc (chi định, chống chỉ định, tác dụng phụ).</li>
<li>Lưu thuốc đã tra cứu để tham khảo sau.</li>
<li>Xem lại lịch sử gợi ý.</li>
<li>Quản trị viên có thể quản lý dữ liệu thuốc, thống kê dữ liệu và theo dõi hoạt động</li>

<h2>Kiến trúc hệ thống</h2>
Hệ thống được thiết kế gồm 3 thành phần chính:
<li><b>Giao diện web (Front-end):</b> Xây dựng bằng Flask + HTML/CSS/JS, cho phép người dùng nhập triệu chứng và nhận gợi ý</li>
<li><b>Xử lý dữ liệu và mô hình gợi ý(Back-end):</b> Thu thập dữ liệu từ các nguồn uy tín(bằng Selenium/BeautifulSoup + Requests), tiền xử lý văn bản, vector hóa bằng TF-IDF và áp dụng các mô hình học máy (Logistic Regression, Random Forest).</li>
<li><b>Cơ sở dữ liệu (Database): </b> Lưu trữ thông tin thuốc, dữ liệu triệu chứng, lịch sử tìm kiếm và danh sách thuốc đã lưu</li>
<p><img width="981" height="441" alt="Usecase-System Structure drawio" src="https://github.com/user-attachments/assets/68d6dd8f-0983-432e-bb2c-ee4a4320ac46" /></p>

<h2>Cài đặt và chạy thử</h2>
<p><strong>Clone repository về máy:</strong></p>
<pre><code class="language-bash">
git clone https://github.com/username/drug-recommendation.git
cd drug-recommendation
</code></pre>

<p><strong>Cài đặt thư viện cần thiết:</strong></p>
<pre><code class="language-bash">
pip install -r requirements.txt
</code></pre>

<p><strong>Chạy ứng dụng:</strong></p>
<pre><code class="language-bash">
python app.py
</code></pre>

<p>Truy cập ứng dụng tại: <a href="http://localhost:5000" target="_blank">http://localhost:5000</a></p>


<h2>Kết quả</h2>
<li>Thu thập dữ liệu từ hai nguồn: Nhà Thuốc Long Châu và Điều Trị.</li>
<li>Tiền xử lý dữ liệu: làm sạch, chuẩn hóa, loại bỏ cột trùng, hợp nhất các bộ dữ liệu, trực quan hóa (WordCloud, Heatmap, Histogram).</li>
<li>Huấn luyện mô hình Logistic Regression và Random Forest, đánh giá bằng Accuracy, F1-Macro, F1-Weighted.</li>
<li>Hoàn thiện website với đầy đủ chức năng người dùng và quản trị.</li>
<p><img width="945" height="525" alt="image" src="https://github.com/user-attachments/assets/82645419-b36a-40c4-bab4-e57a9326f6dd" /></p>

