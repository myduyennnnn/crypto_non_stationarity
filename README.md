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

## 5. Yêu cầu môi trường

Cần file `.env` ở thư mục gốc project với:

```env
SUPABASE_URL=...
SUPABASE_PUBLISHABLE_KEY=...
```

---

## 6. Cấu trúc project

```text
01_preprocessing_supabase.ipynb   # Notebook preprocessing chính thức (theo quy trình ở mục 4)
```

> Lưu ý: notebook preprocessing chỉ dừng ở việc tạo `ftt_processed` / `sp500_processed`. Việc trực quan hóa, ACF/ADF, rolling volatility, event study và merge dữ liệu để so sánh (nếu cần) được thực hiện ở (các) notebook phân tích tiếp theo, không nằm trong phạm vi file này.