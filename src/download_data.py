"""
src/download_data.py

Tải dữ liệu THÔ (raw) cho:
  - CRV-USD  (Curve DAO Token) từ Yahoo Finance
  - S&P 500  từ FRED (nguồn chính thức), tự động fallback sang Yahoo Finance
    (^GSPC) nếu FRED lỗi/không truy cập được.

Output:
  data/raw/crv_2021_2024.csv
  data/raw/sp500_2021_2024.csv

Chạy trực tiếp:
    python src/download_data.py
"""

from pathlib import Path

import pandas as pd
import yfinance as yf

# =========================
# CONFIG
# =========================

START_DATE = "2021-01-01"
END_DATE = "2025-01-01"  # lấy dư 1 ngày để chắc chắn có đủ đến 31/12/2024

CRV_TICKER = "CRV-USD"
CRV_EXPECTED_NAME = "curve"  # dùng để kiểm tra không nhầm sang crvUSD

# Xác định thư mục gốc của project (crypto_non_stationarity/) dù chạy từ đâu
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """yfinance đôi khi trả về MultiIndex cột -> chuẩn hóa về cột đơn."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def download_crv() -> pd.DataFrame:
    """Tải dữ liệu CRV-USD (Curve DAO Token) và kiểm tra đúng ticker."""
    print("Đang tải CRV-USD từ Yahoo Finance...")

    # --- Kiểm tra tên đầy đủ để chắc chắn KHÔNG lấy nhầm crvUSD (CRVUSD-USD) ---
    try:
        info = yf.Ticker(CRV_TICKER).info
        long_name = (info.get("longName") or info.get("shortName") or "").lower()
        print(f"  Tên đầy đủ theo Yahoo Finance: {long_name!r}")
        if CRV_EXPECTED_NAME not in long_name:
            print(
                f"CẢNH BÁO: tên trả về không chứa 'curve'. "
                f"Hãy kiểm tra lại xem có bị nhầm ticker không (CRV-USD vs CRVUSD-USD)."
            )
    except Exception as e:
        print(f" Không kiểm tra được tên ticker ({e}). Tiếp tục tải nhưng hãy tự soát lại.")

    crv = yf.download(
        CRV_TICKER,
        start=START_DATE,
        end=END_DATE,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )

    if crv.empty:
        raise RuntimeError("Không tải được dữ liệu CRV-USD. Kiểm tra lại kết nối mạng / ticker.")

    crv = _flatten_columns(crv).reset_index()
    crv = crv[["Date", "Open", "High", "Low", "Close", "Volume"]]
    crv = crv.rename(columns={"Close": "CRV_Close", "Volume": "CRV_Volume"})

    crv["Date"] = pd.to_datetime(crv["Date"])
    if crv["Date"].dt.tz is not None:
        crv["Date"] = crv["Date"].dt.tz_localize(None)

    print(f"  Số dòng: {len(crv)} | Khoảng ngày: {crv['Date'].min().date()} -> {crv['Date'].max().date()}")
    print(f"  Giá trị null: {crv['CRV_Close'].isna().sum()}")

    return crv


def download_sp500() -> pd.DataFrame:
    """Tải S&P 500 từ FRED (ưu tiên), fallback sang Yahoo Finance (^GSPC) nếu lỗi."""
    print("\nĐang tải S&P 500 từ FRED...")

    sp500 = None
    try:
        from pandas_datareader import data as web

        sp500 = web.DataReader("SP500", "fred", START_DATE, END_DATE)
        sp500 = sp500.reset_index().rename(columns={"DATE": "Date", "SP500": "SP500_Close"})
        print("  Lấy dữ liệu từ FRED thành công.")
    except Exception as e:
        print(f"  ⚠️  FRED lỗi ({e}). Chuyển sang Yahoo Finance (^GSPC)...")
        sp_raw = yf.download("^GSPC", start=START_DATE, end=END_DATE, progress=False)
        sp_raw = _flatten_columns(sp_raw).reset_index()
        sp500 = sp_raw[["Date", "Close"]].rename(columns={"Close": "SP500_Close"})
        print("  Lấy dữ liệu từ Yahoo Finance thành công (fallback).")

    sp500["Date"] = pd.to_datetime(sp500["Date"])
    if sp500["Date"].dt.tz is not None:
        sp500["Date"] = sp500["Date"].dt.tz_localize(None)

    # FRED để trống (NaN) vào các ngày thị trường Mỹ nghỉ lễ giữa tuần -> loại các dòng NaN thật sự
    sp500 = sp500.dropna(subset=["SP500_Close"])

    print(f"  Số dòng: {len(sp500)} | Khoảng ngày: {sp500['Date'].min().date()} -> {sp500['Date'].max().date()}")

    return sp500


def main():
    crv = download_crv()
    sp500 = download_sp500()

    crv_path = RAW_DIR / "crv_2021_2024.csv"
    sp500_path = RAW_DIR / "sp500_2021_2024.csv"

    crv.to_csv(crv_path, index=False)
    sp500.to_csv(sp500_path, index=False)

    print(f"\n Đã lưu: {crv_path}")
    print(f" Đã lưu: {sp500_path}")


if __name__ == "__main__":
    main()
