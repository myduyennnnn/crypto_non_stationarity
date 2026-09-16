# Khảo sát tính phi ổn định (Non-Stationarity) của CRV trong khủng hoảng thanh khoản

Case study: Curve Finance bị hack (30/07/2023) — so sánh CRV (Curve DAO Token) với S&P 500.

## Cấu trúc project

```
crypto_non_stationarity/
│
├── data/
│   ├── raw/
│   │   ├── crv_2021_2024.csv        # CRV thô, đầy đủ 24/7
│   │   └── sp500_2021_2024.csv      # S&P 500 thô, chỉ ngày thị trường mở cửa
│   │
│   └── processed/
│       ├── crv_full_2021_2024.csv   # Dataset A: CRV full + return (dùng cho ACF/ADF/event window)
│       ├── crv_sp500_analysis.csv   # Dataset B: CRV + S&P 500 matched (dùng để so sánh)
│       ├── adf_summary.csv          # Bảng tổng hợp kết quả ADF (xuất ra sau khi chạy notebook 03)
│       └── plots/                   # Các biểu đồ được lưu tự động (.png)
│
├── notebooks/
│   ├── 01_data_check.ipynb          # Kiểm tra chất lượng dữ liệu, null, event window
│   ├── 02_visualization.ipynb       # Time series, histogram
│   └── 03_acf_adf.ipynb             # ACF plot + kiểm định ADF + bảng so sánh
│
├── src/
│   ├── download_data.py             # Tải dữ liệu thô CRV (Yahoo) + S&P 500 (FRED, fallback Yahoo)
│   ├── preprocessing.py             # Tạo Dataset A và Dataset B
│   └── stationarity.py              # Hàm vẽ time series/histogram/ACF + chạy ADF test
│
└── README.md
```

## Vì sao có 2 dataset (A và B)?

- **CRV giao dịch 24/7**, còn **S&P 500 chỉ có giá vào ngày thị trường Mỹ mở cửa** (nghỉ cuối tuần, lễ).
- Ngày Curve Finance bị hack — **30/07/2023 là Chủ nhật** — S&P 500 không có dữ liệu ngày này.
- Nếu chỉ dùng dataset đã ghép (matched theo ngày S&P 500 có giao dịch) để phân tích CRV, bạn sẽ:
  1. Làm sai lệch ACF/ADF của CRV (chuỗi bị cắt khúc giả tạo do loại bỏ cuối tuần).
  2. Bỏ lỡ đúng ngày xảy ra sự kiện khi phân tích event window.

→ **Dataset A** (CRV đầy đủ) dùng để phân tích ACF/ADF/event window của riêng CRV.
→ **Dataset B** (CRV + S&P 500 matched) chỉ dùng ở bước so sánh cuối cùng giữa hai loại tài sản.

## Cách chạy

```bash
# 1. Cài thư viện
pip install yfinance pandas numpy matplotlib statsmodels pandas-datareader --break-system-packages

# 2. Tải dữ liệu thô
python src/download_data.py

# 3. Xử lý thành 2 dataset
python src/preprocessing.py

# 4. Mở notebooks theo thứ tự 01 -> 02 -> 03
jupyter notebook notebooks/
```

## Lưu ý quan trọng

- **CRV-USD** (Curve DAO Token) khác hoàn toàn với **CRVUSD-USD** (stablecoin crvUSD của Curve).
  `download_data.py` có bước kiểm tra tên đầy đủ (`longName`) để cảnh báo nếu lấy nhầm ticker.
- Nếu FRED (`pandas_datareader`) bị lỗi kết nối, script tự động chuyển sang lấy S&P 500 qua
  Yahoo Finance (`^GSPC`) — không cần can thiệp thủ công.
- Sự kiện mốc: **Curve Finance bị hack ngày 30/07/2023** (lỗ hổng reentrancy trong Vyper),
  gây sụt giảm TVL từ ~3.7 tỷ USD xuống ~2.1 tỷ USD trong 24 giờ, và đe dọa thanh lý cưỡng bức
  khoản vay CRV của nhà sáng lập Curve trên Aave — minh họa rủi ro lan tỏa hệ thống (contagion risk).
