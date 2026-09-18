# Khảo sát tính phi ổn định (Non-Stationarity) của FTT trong khủng hoảng thanh khoản

**Case study:** FTX sụp đổ (02–11/11/2022) — phân tích FTT (FTX Token) và so sánh với S&P 500.

---

## 1. Giới thiệu

Project khảo sát tính **phi ổn định (Non-Stationarity)** của giá và lợi suất tài sản tài chính trong bối cảnh xảy ra một cú sốc lớn trên thị trường crypto.

Case study được lựa chọn là **FTX sụp đổ vào tháng 11/2022**, với FTT (FTX Token) là tài sản trọng tâm và S&P 500 được sử dụng làm benchmark đại diện cho thị trường chứng khoán Mỹ.

FTT được lựa chọn vì token này có mối liên hệ trực tiếp với hệ sinh thái FTX và từng đóng vai trò quan trọng trong bảng cân đối của Alameda Research. Trong giai đoạn FTX gặp khủng hoảng thanh khoản, giá FTT giảm mạnh, tạo ra một case phù hợp để khảo sát sự thay đổi của hành vi chuỗi thời gian trước, trong và sau cú sốc.

### Sự kiện nghiên cứu

- **02/11/2022:** Báo cáo về bảng cân đối của Alameda Research được công bố, cho thấy Alameda nắm giữ lượng FTT lớn.
- **06/11/2022:** Binance công bố kế hoạch bán lượng FTT đang nắm giữ, làm gia tăng áp lực bán và lo ngại về thanh khoản.
- **08/11/2022:** FTX tạm dừng việc rút tiền của khách hàng.
- **11/11/2022:** FTX và nhiều công ty liên quan nộp đơn xin phá sản.

Khoảng thời gian **02–11/11/2022** được sử dụng làm event window trọng tâm để quan sát biến động của FTT.

---

## 2. Mục tiêu nghiên cứu

Project tập trung trả lời các câu hỏi:

1. Chuỗi giá FTT có biểu hiện tính phi ổn định như thế nào trong giai đoạn 2021–2024?
2. Lợi suất của FTT có ổn định hơn chuỗi giá hay không?
3. Cấu trúc tự tương quan (autocorrelation) của FTT thay đổi như thế nào quanh sự kiện FTX sụp đổ?
4. Mức độ biến động của FTT thay đổi như thế nào trước, trong và sau khủng hoảng?
5. Hành vi của FTT trong giai đoạn khủng hoảng khác như thế nào so với S&P 500?
6. Sự kiện FTX sụp đổ có tạo ra thay đổi rõ rệt trong đặc điểm của chuỗi lợi suất FTT hay không?

---

## 3. Dữ liệu

### 3.1. Nguồn và cách truy cập

- Dữ liệu được lưu trữ trong **Supabase** (PostgreSQL), gồm hai bảng: `assets` (thông tin tài sản, trong đó có cột `data_source` ghi nguồn dữ liệu gốc) và `daily_prices` (giá lịch sử theo ngày).
- Toàn bộ notebook preprocessing đọc **trực tiếp từ Supabase**, không dùng file CSV local, không gọi lại API bên ngoài trong lúc phân tích.
- Không tạo thêm bảng raw/matched/dataset mới trên Supabase; mọi dữ liệu trung gian chỉ tồn tại trong memory (Pandas).

### 3.2. FTT

| | |
|---|---|
| **Ticker** | `FTT-USD` |
| **Tên** | FTX Token |
| **Loại** | Crypto, giao dịch 24/7 |
| **Tần suất** | Daily |
| **Khoảng thời gian** | 01/01/2021 – 31/12/2024 |

### 3.3. S&P 500

| | |
|---|---|
| **Ticker** | `^GSPC` |
| **Tên** | S&P 500 Index |
| **Loại** | Chỉ số chứng khoán, theo lịch giao dịch Mỹ (không giao dịch cuối tuần/ngày lễ) |
| **Tần suất** | Daily |
| **Khoảng thời gian** | 01/01/2021 – 31/12/2024 |

### 3.4. Cấu trúc bảng `daily_prices` (đọc từ Supabase)

```text
price_id
asset_id
trade_date
open_price
high_price
low_price
close_price
volume
created_at
```

`close_price` là biến giá chính dùng để tính return cho toàn bộ nghiên cứu. OHLC được kiểm tra logic khi đủ dữ liệu, nhưng không được tự điền nếu thiếu.

---

## 4. Quy trình xử lý dữ liệu (Preprocessing)

Thực hiện trong `01_preprocessing_supabase.ipynb`, gồm 2 phần, 18 bước:

### Nguyên tắc

- Không fill, forward-fill, backward-fill hoặc interpolate giá.
- Không tạo thêm ngày giao dịch giả cho FTT; không coi cuối tuần/ngày lễ của S&P 500 là missing.
- Outlier chỉ được **gắn cờ để tham khảo**, không tự động xóa — kể cả khi biên độ lớn, vì với FTT biến động cực đoan quanh sự kiện sập sàn có thể là tín hiệu thật.
- Không tạo dataframe tổng hợp/so sánh (ví dụ merge FTT với S&P 500) ở cuối notebook preprocessing — việc join theo ngày giao dịch chung, nếu cần cho phân tích/trực quan hóa, do notebook phía sau tự thực hiện, để tránh mỗi người dùng một bản merge khác nhau.

### PHẦN 1 — Kiểm tra chất lượng dữ liệu (trên dữ liệu thô)

| Bước | Nội dung |
|---|---|
| 01 | Load dữ liệu từ Supabase |
| 02 | Kiểm tra schema / datatype |
| 03 | Kiểm tra khoảng thời gian |
| 04 | Kiểm tra duplicate |
| 05 | Kiểm tra missing / null |
| 06 | Kiểm tra missing trading days / gap (riêng FTT, do giao dịch 24/7) |
| 07 | Kiểm tra OHLC consistency |
| 08 | Kiểm tra giá trị bất hợp lệ (Close NaN/Inf/≤0) |
| 09 | Kiểm tra outlier trên return (sơ bộ, kèm biểu đồ chẩn đoán) |
| 10 | Quality report tổng hợp |

### PHẦN 2 — Tiền xử lý

| Bước | Nội dung |
|---|---|
| 11 | Sort theo `trade_date` |
| 12 | Xóa duplicate nếu thực sự tồn tại (đã xác nhận ở bước 04) |
| 13 | Loại dòng `close_price` không hợp lệ nếu thực sự tồn tại (đã xác nhận ở bước 08) |
| 14 | KHÔNG fill giá |
| 15 | KHÔNG interpolate giá |
| 16 | KHÔNG xóa outlier chỉ vì nó "lớn" — chỉ gắn lại cờ đã phát hiện ở bước 09 |
| 17 | Tính simple return và log return, sau khi dữ liệu đã qua các bước trên |
| 18 | Kiểm tra lại dữ liệu cuối cùng |

### Output

- `ftt_processed`: FTT đầy đủ 2021–2024, đã có `FTT_simple_return`, `FTT_log_return`, `FTT_outlier_iqr`, `FTT_outlier_zscore`. Dùng cho ACF/ADF, rolling volatility và event window.
- `sp500_processed`: S&P 500 đã chuẩn hóa tương tự, dùng làm benchmark so sánh.
- Cả hai chỉ tồn tại trong memory của notebook, không ghi lại lên Supabase, không xuất CSV.

---
Dưới đây là phần nội dung tiếp nối mục 4 được biên soạn lại **ngắn gọn, mạch lạc và chuẩn hóa kỹ thuật**, liên kết trực tiếp với đầu ra (`ftt_processed`, `sp500_processed`) từ khâu tiền xử lý:

---
## 5. Trực quan hóa dữ liệu (`02_visualization.ipynb`)

Sử dụng trực tiếp `ftt_processed` và `sp500_processed` sau bước tiền xử lý để trực quan hóa dữ liệu, phân tích biến động giá và quan sát phản ứng của thị trường quanh sự kiện FTX.

### 5.1. Thiết lập khoảng thời gian sự kiện

Xác định ba khoảng thời gian chính:

* **Cửa sổ sự kiện (`EVENT_WINDOW`):** `02/11/2022 – 11/11/2022`, từ thời điểm thông tin bị rò rỉ đến khi FTX nộp đơn phá sản.
* **Mốc sự kiện chính (`EVENT_DATE`):** `08/11/2022`, thời điểm FTX dừng cho khách hàng rút tiền.
* **Cửa sổ quan sát (`VIEW_WINDOW`):** `01/10/2022 – 31/12/2022`, dùng để quan sát diễn biến trước và sau sự kiện.

### 5.2. Phân tích giá đóng cửa

Vẽ biểu đồ giá đóng cửa của FTT và S&P 500 trong giai đoạn 2021–2024. Cửa sổ sự kiện được đánh dấu trên biểu đồ để dễ quan sát sự thay đổi bất thường của giá và khả năng xuất hiện **điểm gãy cấu trúc (Structural Break)**.

### 5.3. Phân tích Log Return

Vẽ Log Return hàng ngày của FTT và S&P 500 cùng đường tham chiếu `y = 0`. Qua biểu đồ, quan sát mức độ biến động của lợi suất, đặc biệt là các giai đoạn biến động mạnh và hiện tượng **cụm biến động (Volatility Clustering)**.

### 5.4. Thống kê mô tả và phân phối

Tính các chỉ số thống kê gồm `n`, `mean`, `std`, `skew`, `kurtosis`, `min` và `max` bằng hàm `describe_return`. Đồng thời, sử dụng Histogram với `bins=80` để quan sát hình dạng phân phối và kiểm tra hiện tượng **đuôi dày (Fat Tails)**.

### 5.5. Phóng to cửa sổ sự kiện

Lọc dữ liệu FTT trong khoảng `01/10/2022 – 31/12/2022` và vẽ chi tiết giá đóng cửa cùng Log Return. Mốc `08/11/2022` được đánh dấu trên biểu đồ để dễ quan sát sự thay đổi của giá và biến động sau sự kiện.

---

## 6. Kiểm định tính dừng: ACF & ADF Test (`03_acf_adf_test.ipynb`)

Thực hiện kiểm định tính dừng của chuỗi thời gian và xác định bậc tích hợp $I(d)$ của dữ liệu.

### 6.1. Kiểm định tự tương quan ACF

Sử dụng `plot_acf` với `lags=40` trên giá đóng cửa và Log Return của FTT và S&P 500. Kết quả ACF được dùng để quan sát mức độ phụ thuộc của giá trị hiện tại vào các giá trị trong quá khứ và đánh giá dấu hiệu của chuỗi dừng hoặc không dừng.

### 6.2. Kiểm định nghiệm đơn vị ADF

Sử dụng hàm `adf_test` với `adfuller(..., autolag="AIC")` để kiểm định tính dừng của chuỗi. Kết quả được đánh giá dựa trên thống kê ADF, các giá trị tới hạn và `p-value` với mức ý nghĩa $\alpha = 0.05$.

* $H_0$: Chuỗi có nghiệm đơn vị, không dừng.
* $H_1$: Chuỗi không có nghiệm đơn vị, dừng.

### 6.3. Kiểm định ADF theo từng giai đoạn

Đối với FTT, dữ liệu được chia thành hai giai đoạn quanh ngày `08/11/2022`: trước sự kiện (`trade_date < 2022-11-08`) và từ ngày sự kiện trở đi (`trade_date >= 2022-11-08`). Sau đó, thực hiện ADF riêng cho từng giai đoạn và tính độ lệch chuẩn (`std`) để đánh giá tính dừng của Log Return và sự thay đổi mức độ biến động trước và sau sự kiện.

## 7. Yêu cầu môi trường

Cần file `.env` ở thư mục gốc project với:

```env
SUPABASE_URL=...
SUPABASE_PUBLISHABLE_KEY=...
```

---

## 8. Cấu trúc project


```text
01_preprocessing_supabase.ipynb   # Kiểm tra và tiền xử lý dữ liệu từ Supabase
02_visualization.ipynb            # Trực quan hóa dữ liệu và phân tích giai đoạn FTX
03_acf_adf_test.ipynb              # Phân tích ACF và kiểm định ADF
```
