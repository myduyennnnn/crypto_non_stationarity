"""
src/download_data.py

Tải dữ liệu:
    - FTT-USD (FTX Token) từ Yahoo Finance
    - S&P 500 từ FRED
      fallback Yahoo Finance nếu FRED lỗi

Sau khi tải:
    - Không lưu CSV local
    - Chuẩn hóa dữ liệu trong memory
    - Upload trực tiếp lên Supabase

Upload vào Supabase:
    assets
    daily_prices

Cấu trúc Supabase:

assets
    asset_id
    ticker
    asset_name
    asset_type
    data_source
    description
    created_at

daily_prices
    price_id
    asset_id
    trade_date
    open_price
    high_price
    low_price
    close_price
    volume
    created_at

Chạy:
    python src/download_data.py
"""

from pathlib import Path
import math
import os

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# CONFIG
# ============================================================

START_DATE = "2021-01-01"
END_DATE = "2025-01-01"

FTT_TICKER = "FTT-USD"
SP500_TICKER = "^GSPC"

FTT_NAME = "FTX Token"
SP500_NAME = "S&P 500"

BATCH_SIZE = 500


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv(PROJECT_ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Không tìm thấy SUPABASE_URL hoặc "
        "SUPABASE_PUBLISHABLE_KEY trong file .env"
    )


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# ============================================================
# HELPER: FLATTEN YFINANCE COLUMNS
# ============================================================

def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    yfinance đôi khi trả về MultiIndex columns.

    Ví dụ:
        ('Close', 'FTT-USD')

    sẽ được đưa về:
        'Close'
    """

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    return df


# ============================================================
# HELPER: NORMALIZE DATE
# ============================================================

def _normalize_date(
    df: pd.DataFrame,
    column: str = "Date"
) -> pd.DataFrame:
    """
    Chuẩn hóa Date về datetime không timezone.
    """

    df = df.copy()

    df[column] = pd.to_datetime(
        df[column],
        errors="coerce"
    )

    # Xử lý timezone nếu có
    if hasattr(df[column].dt, "tz") and df[column].dt.tz is not None:
        df[column] = df[column].dt.tz_localize(None)

    # Loại bỏ ngày không hợp lệ
    df = df.dropna(subset=[column])

    return df


# ============================================================
# HELPER: CLEAN NUMERIC COLUMNS
# ============================================================

def _clean_numeric_columns(
    df: pd.DataFrame,
    columns: list[str]
) -> pd.DataFrame:
    """
    Chuyển các cột số sang numeric.

    Giá trị không hợp lệ:
        NaN
        +inf
        -inf

    sẽ được chuyển thành None sau bước chuẩn bị record.
    """

    df = df.copy()

    for col in columns:

        if col not in df.columns:
            df[col] = None

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        )

    return df


# ============================================================
# DOWNLOAD FTT
# ============================================================

def download_ftt() -> pd.DataFrame:

    print("Đang tải FTT-USD từ Yahoo Finance...")

    # --------------------------------------------------------
    # Kiểm tra ticker
    # --------------------------------------------------------

    try:

        info = yf.Ticker(FTT_TICKER).info

        long_name = (
            info.get("longName")
            or info.get("shortName")
            or ""
        ).lower()

        print(
            f"  Tên theo Yahoo Finance: {long_name!r}"
        )

    except Exception as e:

        print(
            f"  Không kiểm tra được tên ticker: {e}"
        )

    # --------------------------------------------------------
    # Download
    # --------------------------------------------------------

    ftt = yf.download(
        FTT_TICKER,
        start=START_DATE,
        end=END_DATE,
        interval="1d",
        auto_adjust=False,
        progress=False,
    )

    if ftt.empty:
        raise RuntimeError(
            "Không tải được dữ liệu FTT-USD từ Yahoo Finance."
        )

    # --------------------------------------------------------
    # Flatten + reset index
    # --------------------------------------------------------

    ftt = _flatten_columns(ftt)

    ftt = ftt.reset_index()

    # --------------------------------------------------------
    # Kiểm tra columns
    # --------------------------------------------------------

    required_columns = [
        "Date",
        "Open",
        "High",
        "Low",
        "Close",
        "Volume",
    ]

    missing_columns = [
        col
        for col in required_columns
        if col not in ftt.columns
    ]

    if missing_columns:
        raise RuntimeError(
            "Dữ liệu FTT thiếu các cột: "
            + ", ".join(missing_columns)
        )

    # --------------------------------------------------------
    # Chọn columns
    # --------------------------------------------------------

    ftt = ftt[required_columns]

    # --------------------------------------------------------
    # Rename
    # --------------------------------------------------------

    ftt = ftt.rename(
        columns={
            "Open": "open_price",
            "High": "high_price",
            "Low": "low_price",
            "Close": "close_price",
            "Volume": "volume",
        }
    )

    # --------------------------------------------------------
    # Normalize date
    # --------------------------------------------------------

    ftt = _normalize_date(ftt)

    # --------------------------------------------------------
    # Numeric
    # --------------------------------------------------------

    numeric_columns = [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    ]

    ftt = _clean_numeric_columns(
        ftt,
        numeric_columns
    )

    # --------------------------------------------------------
    # Remove invalid rows
    # --------------------------------------------------------

    ftt = (
        ftt
        .dropna(subset=["close_price"])
        .drop_duplicates(subset=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Info
    # --------------------------------------------------------

    print(
        f"  Số dòng: {len(ftt)}"
    )

    print(
        f"  Khoảng ngày: "
        f"{ftt['Date'].min().date()} -> "
        f"{ftt['Date'].max().date()}"
    )

    print(
        f"  Null close: "
        f"{ftt['close_price'].isna().sum()}"
    )

    return ftt


# ============================================================
# DOWNLOAD S&P 500
# ============================================================

def download_sp500() -> tuple[pd.DataFrame, str]:

    print("\nĐang tải S&P 500 từ FRED...")

    sp500 = None
    data_source = "FRED"

    # --------------------------------------------------------
    # Ưu tiên FRED
    # --------------------------------------------------------

    try:

        from pandas_datareader import data as web

        sp500 = web.DataReader(
            "SP500",
            "fred",
            START_DATE,
            END_DATE,
        )

        if sp500.empty:
            raise RuntimeError(
                "FRED trả về dữ liệu rỗng."
            )

        sp500 = sp500.reset_index()

        # ----------------------------------------------------
        # Chuẩn hóa tên Date
        # ----------------------------------------------------

        if "DATE" in sp500.columns:
            sp500 = sp500.rename(
                columns={
                    "DATE": "Date"
                }
            )

        # ----------------------------------------------------
        # Rename close
        # ----------------------------------------------------

        sp500 = sp500.rename(
            columns={
                "SP500": "close_price"
            }
        )

        # ----------------------------------------------------
        # FRED chỉ có Close
        # ----------------------------------------------------

        sp500["open_price"] = None
        sp500["high_price"] = None
        sp500["low_price"] = None
        sp500["volume"] = None

        sp500 = sp500[
            [
                "Date",
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "volume",
            ]
        ]

        print(
            "  Lấy S&P 500 từ FRED thành công."
        )

    # --------------------------------------------------------
    # Fallback Yahoo Finance
    # --------------------------------------------------------

    except Exception as e:

        print(
            f"  FRED lỗi: {e}"
        )

        print(
            "  Chuyển sang Yahoo Finance (^GSPC)..."
        )

        data_source = "Yahoo Finance"

        sp_raw = yf.download(
            SP500_TICKER,
            start=START_DATE,
            end=END_DATE,
            interval="1d",
            auto_adjust=False,
            progress=False,
        )

        if sp_raw.empty:
            raise RuntimeError(
                "Không tải được S&P 500 từ "
                "FRED hoặc Yahoo Finance."
            )

        sp_raw = _flatten_columns(sp_raw)

        sp_raw = sp_raw.reset_index()

        required_columns = [
            "Date",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        missing_columns = [
            col
            for col in required_columns
            if col not in sp_raw.columns
        ]

        if missing_columns:
            raise RuntimeError(
                "Dữ liệu S&P 500 từ Yahoo thiếu các cột: "
                + ", ".join(missing_columns)
            )

        sp500 = sp_raw[required_columns]

        sp500 = sp500.rename(
            columns={
                "Open": "open_price",
                "High": "high_price",
                "Low": "low_price",
                "Close": "close_price",
                "Volume": "volume",
            }
        )

        print(
            "  Lấy S&P 500 từ Yahoo Finance thành công."
        )

    # --------------------------------------------------------
    # Normalize date
    # --------------------------------------------------------

    sp500 = _normalize_date(sp500)

    # --------------------------------------------------------
    # Numeric
    # --------------------------------------------------------

    numeric_columns = [
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    ]

    sp500 = _clean_numeric_columns(
        sp500,
        numeric_columns
    )

    # --------------------------------------------------------
    # Remove invalid rows
    # --------------------------------------------------------

    sp500 = (
        sp500
        .dropna(subset=["close_price"])
        .drop_duplicates(subset=["Date"])
        .sort_values("Date")
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # Info
    # --------------------------------------------------------

    print(
        f"  Số dòng: {len(sp500)}"
    )

    print(
        f"  Khoảng ngày: "
        f"{sp500['Date'].min().date()} -> "
        f"{sp500['Date'].max().date()}"
    )

    print(
        f"  Null close: "
        f"{sp500['close_price'].isna().sum()}"
    )

    return sp500, data_source


# ============================================================
# GET / CREATE ASSET
# ============================================================

def get_or_create_asset(
    ticker: str,
    asset_name: str,
    asset_type: str,
    data_source: str,
    description: str
):
    """
    Tìm asset trong bảng assets.

    Nếu chưa có thì tạo mới.

    Trả về asset_id.
    """

    print(
        f"\nKiểm tra asset: {ticker}"
    )

    # --------------------------------------------------------
    # Tìm asset hiện có
    # --------------------------------------------------------

    response = (
        supabase
        .table("assets")
        .select(
            "asset_id, ticker, asset_name"
        )
        .eq("ticker", ticker)
        .limit(1)
        .execute()
    )

    if response.data:

        asset = response.data[0]

        print(
            f"  Đã tồn tại: "
            f"{asset['ticker']} "
            f"(asset_id={asset['asset_id']})"
        )

        return asset["asset_id"]

    # --------------------------------------------------------
    # Asset chưa tồn tại -> tạo mới
    # --------------------------------------------------------

    response = (
        supabase
        .table("assets")
        .insert(
            {
                "ticker": ticker,
                "asset_name": asset_name,
                "asset_type": asset_type,
                "data_source": data_source,
                "description": description,
            }
        )
        .execute()
    )

    if not response.data:
        raise RuntimeError(
            f"Không thể tạo asset {ticker}."
        )

    asset = response.data[0]

    print(
        f"  Đã tạo asset mới: "
        f"{asset['ticker']} "
        f"(asset_id={asset['asset_id']})"
    )

    return asset["asset_id"]


# ============================================================
# CLEAN VALUE FOR JSON / SUPABASE
# ============================================================

def _clean_value(value):
    """
    Đảm bảo giá trị có thể serialize thành JSON.

    Xử lý:
        NaN
        +inf
        -inf
        NaT
        pandas NA

    thành None.

    Các giá trị hợp lệ được giữ nguyên.
    """

    # --------------------------------------------------------
    # None
    # --------------------------------------------------------

    if value is None:
        return None

    # --------------------------------------------------------
    # Timestamp / datetime
    # --------------------------------------------------------

    if isinstance(value, pd.Timestamp):

        if pd.isna(value):
            return None

        return value

    # --------------------------------------------------------
    # Numeric
    # --------------------------------------------------------

    if isinstance(value, (int, float)):

        if isinstance(value, float):

            if not math.isfinite(value):
                return None

        return value

    # --------------------------------------------------------
    # Pandas NA / NaN
    # --------------------------------------------------------

    try:

        if pd.isna(value):
            return None

    except (TypeError, ValueError):
        pass

    return value


# ============================================================
# PREPARE DAILY PRICES
# ============================================================

def prepare_daily_prices(
    df: pd.DataFrame,
    asset_id
) -> list:
    """
    Chuyển DataFrame thành records phù hợp
    với bảng daily_prices.

    Không gửi price_id vì Supabase tự sinh.

    Date:
        YYYY-MM-DD

    NaN / inf:
        None
    """

    data = df.copy()

    # --------------------------------------------------------
    # Trade date
    # --------------------------------------------------------

    data["trade_date"] = (
        data["Date"]
        .dt
        .strftime("%Y-%m-%d")
    )

    # --------------------------------------------------------
    # Asset ID
    # --------------------------------------------------------

    data["asset_id"] = asset_id

    # --------------------------------------------------------
    # Columns cần upload
    # --------------------------------------------------------

    upload_columns = [
        "asset_id",
        "trade_date",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "volume",
    ]

    records = (
        data[upload_columns]
        .to_dict(orient="records")
    )

    # --------------------------------------------------------
    # Clean từng value
    # --------------------------------------------------------

    cleaned_records = []

    for record in records:

        cleaned_record = {
            key: _clean_value(value)
            for key, value in record.items()
        }

        cleaned_records.append(
            cleaned_record
        )

    return cleaned_records


# ============================================================
# VALIDATE RECORDS
# ============================================================

def validate_records(
    records: list,
    ticker: str
):
    """
    Kiểm tra record trước khi upload.

    Đảm bảo không còn:
        NaN
        +inf
        -inf
    """

    invalid_records = []

    for index, record in enumerate(records):

        for key, value in record.items():

            if isinstance(value, float):

                if not math.isfinite(value):

                    invalid_records.append(
                        {
                            "index": index,
                            "column": key,
                            "value": value,
                        }
                    )

    if invalid_records:

        print(
            f"\nPhát hiện {len(invalid_records)} "
            f"giá trị không hợp lệ trong {ticker}."
        )

        print(
            "Ví dụ:"
        )

        for item in invalid_records[:5]:

            print(
                f"  row={item['index']}, "
                f"column={item['column']}, "
                f"value={item['value']}"
            )

        raise ValueError(
            f"Records của {ticker} vẫn chứa "
            f"giá trị NaN/inf trước khi upload."
        )


# ============================================================
# UPLOAD DAILY PRICES
# ============================================================

def upload_daily_prices(
    records: list,
    ticker: str
):

    print(
        f"\nUpload {ticker} -> daily_prices..."
    )

    total = len(records)

    if total == 0:

        print(
            f"  Không có dữ liệu để upload {ticker}."
        )

        return

    # --------------------------------------------------------
    # Validate trước khi upload
    # --------------------------------------------------------

    validate_records(
        records,
        ticker
    )

    # --------------------------------------------------------
    # Upload theo batch
    # --------------------------------------------------------

    for i in range(
        0,
        total,
        BATCH_SIZE
    ):

        batch = records[
            i:i + BATCH_SIZE
        ]

        try:

            (
                supabase
                .table("daily_prices")
                .upsert(
                    batch,
                    on_conflict="asset_id,trade_date"
                )
                .execute()
            )

        except Exception as e:

            print(
                f"\n  Upload lỗi tại batch "
                f"{i + 1}-{min(i + BATCH_SIZE, total)}"
            )

            raise RuntimeError(
                f"Không thể upload {ticker}: {e}"
            ) from e

        uploaded = min(
            i + BATCH_SIZE,
            total
        )

        print(
            f"  Đã xử lý "
            f"{uploaded}/{total}"
        )

    print(
        f"  Upload {ticker} hoàn tất."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 65)
    print("DOWNLOAD + UPLOAD DATA — FTT & S&P 500")
    print("=" * 65)

    # --------------------------------------------------------
    # 1. Download
    # --------------------------------------------------------

    ftt = download_ftt()

    sp500, sp500_source = download_sp500()

    # --------------------------------------------------------
    # 2. Get / create assets
    # --------------------------------------------------------

    ftt_asset_id = get_or_create_asset(
        ticker=FTT_TICKER,
        asset_name=FTT_NAME,
        asset_type="crypto",
        data_source="Yahoo Finance",
        description=(
            "FTX Token (FTT), "
            "native token của hệ sinh thái FTX."
        )
    )

    sp500_asset_id = get_or_create_asset(
        ticker=SP500_TICKER,
        asset_name=SP500_NAME,
        asset_type="index",
        data_source=sp500_source,
        description=(
            "S&P 500 Index, "
            "benchmark thị trường chứng khoán Mỹ."
        )
    )

    # --------------------------------------------------------
    # 3. Prepare records
    # --------------------------------------------------------

    print("\nChuẩn bị dữ liệu để upload...")

    ftt_records = prepare_daily_prices(
        ftt,
        ftt_asset_id
    )

    sp500_records = prepare_daily_prices(
        sp500,
        sp500_asset_id
    )

    print(
        f"  FTT records: {len(ftt_records)}"
    )

    print(
        f"  S&P 500 records: {len(sp500_records)}"
    )

    # --------------------------------------------------------
    # 4. Upload FTT
    # --------------------------------------------------------

    upload_daily_prices(
        ftt_records,
        FTT_TICKER
    )

    # --------------------------------------------------------
    # 5. Upload S&P 500
    # --------------------------------------------------------

    upload_daily_prices(
        sp500_records,
        SP500_TICKER
    )

    # --------------------------------------------------------
    # DONE
    # --------------------------------------------------------

    print("\n" + "=" * 65)
    print("HOÀN TẤT")
    print("=" * 65)

    print(
        f"""
FTT:
    Asset ID: {ftt_asset_id}
    Records:  {len(ftt_records)}
    Source:   Yahoo Finance

S&P 500:
    Asset ID: {sp500_asset_id}
    Records:  {len(sp500_records)}
    Source:   {sp500_source}

Dữ liệu đã được upload trực tiếp lên Supabase:
    assets
    daily_prices
"""
    )


if __name__ == "__main__":
    main()

