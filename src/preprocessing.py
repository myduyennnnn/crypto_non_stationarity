"""
src/preprocessing.py

Từ dữ liệu thô (data/raw/), tạo ra 2 dataset phục vụ phân tích:

  Dataset A — data/processed/crv_full_2021_2024.csv
      CRV đầy đủ 24/7 (không loại ngày nào), có simple return + log return.
      Dùng để phân tích ACF / ADF / event window của riêng CRV, vì CRV
      giao dịch liên tục nên KHÔNG được cắt bớt ngày cuối tuần trước khi
      phân tích tính tự tương quan / tính dừng của chính nó.

  Dataset B — data/processed/crv_sp500_analysis.csv
      CRV ghép với S&P 500 theo NGÀY GIAO DỊCH CHUNG (inner join theo Date),
      có return riêng cho từng tài sản.
      Dùng để SO SÁNH CRV với S&P 500 (benchmark), không dùng dataset này để
      phân tích ACF/ADF riêng cho CRV vì đã bị loại bớt ngày cuối tuần.

Pipeline data-quality áp dụng cho CRV trước khi build Dataset A/B:

    raw data
      -> Date validation
      -> Duplicate check     (chỉ phát hiện + hiển thị chi tiết, KHÔNG tự xóa)
      -> Missing check       (chỉ phát hiện, chưa loại bỏ)
      -> Price validity      (loại dòng giá thiếu/không hợp lệ)
      -> Gap check            (chỉ CẢNH BÁO gap theo calendar-day, KHÔNG fill/
                                nội suy giá — vì nghiên cứu non-stationarity
                                không được tự ý thay đổi chuỗi thời gian gốc)
      -> Sort
      -> Return calculation
      -> Processed data

Với Dataset B, S&P 500 cũng được kiểm tra data-quality riêng (date
validation -> duplicate -> missing -> price validity -> sort) nhưng
KHÔNG chạy gap check, vì S&P 500 không giao dịch cuối tuần / ngày lễ Mỹ
nên không thể áp dụng cùng logic gap của CRV (24/7).

LƯU Ý về return calculation khi có gap: pct_change() / log-return hiện
tính trực tiếp giữa 2 dòng liền kề trong dữ liệu đã sort. Nếu CRV có gap
(ví dụ thiếu 30/07), return của ngày 31/07 sẽ được tính từ giá 29/07 ->
31/07, tức là "nhảy cóc" qua ngày thiếu chứ không phải return 1 ngày
thật sự. Đây là điều cần xử lý cẩn thận sau khi đã chạy data-quality
check để biết thực tế dataset có gap hay không — CHƯA sửa ở phiên bản
này.

Chạy trực tiếp:
    python src/preprocessing.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

EVENT_DATE = pd.Timestamp("2023-07-30")  # Curve Finance exploit


# ---------------------------------------------------------------------------
# DATA QUALITY CHECK PIPELINE
# ---------------------------------------------------------------------------

def check_date_validity(df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    """1. Date validation: đảm bảo cột Date parse được, không có NaT."""
    n_invalid = df[date_col].isna().sum()
    print(f"[1] Date validation: {n_invalid} dòng có Date không hợp lệ (NaT)")
    if n_invalid > 0:
        df = df.dropna(subset=[date_col]).reset_index(drop=True)
        print(f"    -> Đã loại {n_invalid} dòng có Date không hợp lệ")
    return df


def check_duplicates(df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    """
    2. Duplicate check: chỉ PHÁT HIỆN và hiển thị chi tiết các dòng có Date
    trùng lặp, KHÔNG tự động xóa dòng nào ở đây.

    Lý do: nếu Date thật sự bị trùng, hai dòng đó có thể khác nhau ở các cột
    khác (ví dụ giá khác nhau do nguồn dữ liệu khác nhau) — cần xem chi tiết
    trước khi quyết định giữ dòng nào, thay vì mặc định "keep=first" mà chưa
    biết mình đang bỏ đi thông tin gì. Nếu Duplicate = 0 thì không cần xử lý
    gì thêm.
    """
    dup_mask = df.duplicated(subset=[date_col], keep=False)
    n_dup_dates = df.loc[dup_mask, date_col].nunique()
    print(f"[2] Duplicate check: {n_dup_dates} giá trị Date bị trùng lặp")
    if n_dup_dates > 0:
        print("    -> Chi tiết các dòng trùng (cần xem xét thủ công trước khi xử lý):")
        print(df.loc[dup_mask].sort_values(date_col).to_string(index=False))
    else:
        print("    -> PASS, không có Date nào bị trùng")
    return df


def check_missing(df: pd.DataFrame) -> pd.DataFrame:
    """
    3. Missing check: chỉ PHÁT HIỆN và báo cáo giá trị null theo từng cột,
    KHÔNG tự xóa dòng ở bước này. Các dòng có giá thiếu hoặc không hợp lệ
    sẽ được loại bỏ sau, ở bước 4 (check_price_validity), trước khi tính
    return — tách riêng "phát hiện" và "xử lý" để báo cáo methodology rõ ràng.
    """
    missing = df.isna().sum()
    missing = missing[missing > 0]
    print("[3] Missing check (chỉ phát hiện, chưa loại bỏ):")
    if missing.empty:
        print("    -> Không có giá trị thiếu")
    else:
        for col, n in missing.items():
            print(f"    -> Cột '{col}': {n} giá trị thiếu")
    return df


def check_price_validity(df: pd.DataFrame, price_cols: list[str]) -> pd.DataFrame:
    """4. Price validity: giá phải > 0 (loại giá trị âm, bằng 0, hoặc NaN)."""
    print("[4] Price validity check:")
    for col in price_cols:
        if col not in df.columns:
            continue
        invalid_mask = df[col].isna() | (df[col] <= 0)
        n_invalid = int(invalid_mask.sum())
        print(f"    -> Cột '{col}': {n_invalid} giá trị không hợp lệ (<= 0 hoặc NaN)")
        if n_invalid > 0:
            df = df[~invalid_mask].reset_index(drop=True)
            print(f"       Đã loại {n_invalid} dòng có giá không hợp lệ")
    return df


def check_gap(df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    """
    5. Gap check — dành riêng cho CRV.

    CRV là crypto, giao dịch 24/7/365: Thứ 2 -> Chủ nhật đều có thể có
    dữ liệu. Vì vậy KHÔNG được dùng business-day calendar (pd.bdate_range)
    để kiểm tra thiếu ngày như với cổ phiếu/S&P 500.

    Thay vào đó, ta tạo một dải ngày liên tục theo calendar day (freq="D",
    bao gồm cả Thứ 7 / Chủ nhật) rồi so sánh với các ngày thực tế có trong
    dữ liệu để phát hiện gap.
    """
    dates_sorted = df.sort_values(date_col)[date_col]
    full_range = pd.date_range(
        start=dates_sorted.min(),
        end=dates_sorted.max(),
        freq="D",  # calendar day, KHÔNG phải business day
    )
    existing_dates = set(dates_sorted)
    missing_dates = sorted(set(full_range) - existing_dates)

    print(f"[5] Gap check (calendar-day, CRV giao dịch 24/7): {len(missing_dates)} ngày bị thiếu")
    for d in missing_dates[:20]:
        flag = "  <-- gần vùng event 2023-07-30, cần chú ý" if abs((d - EVENT_DATE).days) <= 2 else ""
        print(f"    -> Thiếu: {d.date()}{flag}")
    if len(missing_dates) > 20:
        print(f"    ... và {len(missing_dates) - 20} ngày khác")

    return df


def validate_crv_data(
    df: pd.DataFrame,
    price_cols: list[str] = ("CRV_Close",),
    date_col: str = "Date",
) -> pd.DataFrame:
    """
    Orchestrator: chạy toàn bộ pipeline data-quality cho CRV theo đúng thứ tự:

        raw data -> Date validation -> Duplicate check -> Missing check
        -> Price validity -> Gap check -> Sort -> (Return calculation ở nơi gọi)

    Trả về DataFrame đã qua kiểm tra và đã sort theo Date, sẵn sàng để
    tính return.
    """
    print("\n========== DATA QUALITY CHECK: CRV ==========")
    df = check_date_validity(df, date_col)
    df = check_duplicates(df, date_col)
    df = check_missing(df)
    df = check_price_validity(df, list(price_cols))
    df = check_gap(df, date_col)
    df = df.sort_values(date_col).reset_index(drop=True)  # 6. Sort
    print("===============================================\n")
    return df


def check_event_date(df: pd.DataFrame, date_col: str = "Date") -> None:
    """
    Kiểm tra riêng cho ngày xảy ra sự kiện nghiên cứu (Curve exploit,
    30/07/2023) và 2 ngày liền kề.

    Check này có giá trị cực lớn cho case nghiên cứu vì câu hỏi không
    chỉ là "Dataset có đủ dữ liệu?" mà là "Dataset có dữ liệu đáng tin
    cậy đúng tại vùng xảy ra sự kiện nghiên cứu hay không?"
    """
    print("\n===== EVENT DATE CHECK (Curve exploit 30/07/2023) =====")

    for offset, label in [(-1, "Thứ 7, trước event"), (0, "<- Curve exploit"), (1, "Thứ 2, sau event")]:
        d = EVENT_DATE + pd.Timedelta(days=offset)
        has_data = (df[date_col] == d).any()
        status = "có dữ liệu" if has_data else "⚠️  KHÔNG có dữ liệu"
        print(f"    {d.date()} ({label}): {status}")

    if EVENT_DATE not in df[date_col].values:
        print("Không tìm thấy dữ liệu CRV ngày 30/07/2023.")
    else:
        print("Có dữ liệu CRV ngày 30/07/2023.")
    print("=========================================================\n")


# ---------------------------------------------------------------------------
# RETURN CALCULATION
# ---------------------------------------------------------------------------

def _add_returns(df: pd.DataFrame, price_col: str, prefix: str) -> pd.DataFrame:
    """7. Return calculation: thêm cột simple return và log return cho một cột giá."""
    df[f"{prefix}_simple_return"] = df[price_col].pct_change()
    df[f"{prefix}_log_return"] = np.log(df[price_col] / df[price_col].shift(1))
    return df


# ---------------------------------------------------------------------------
# BUILD DATASETS
# ---------------------------------------------------------------------------

def build_dataset_a() -> pd.DataFrame:
    """Dataset A: CRV đầy đủ 24/7, đã qua data-quality check, có return. Dùng cho ACF/ADF/event window."""
    crv = pd.read_csv(RAW_DIR / "crv_2021_2024.csv", parse_dates=["Date"])

    crv = validate_crv_data(crv, price_cols=["CRV_Close"])
    check_event_date(crv)

    crv = _add_returns(crv, "CRV_Close", "CRV")  # Return calculation -> Processed data

    out_path = PROCESSED_DIR / "crv_full_2021_2024.csv"
    crv.to_csv(out_path, index=False)

    print(f"[Dataset A] Số dòng: {len(crv)} | null return: {crv['CRV_log_return'].isna().sum()}")
    print(f"[Dataset A] Đã lưu: {out_path}")
    return crv


def build_dataset_b() -> pd.DataFrame:
    """Dataset B: CRV + S&P 500 ghép theo ngày giao dịch chung. Dùng để so sánh."""
    crv = pd.read_csv(RAW_DIR / "crv_2021_2024.csv", parse_dates=["Date"])
    sp500 = pd.read_csv(RAW_DIR / "sp500_2021_2024.csv", parse_dates=["Date"])

    crv = validate_crv_data(crv, price_cols=["CRV_Close"])

    # S&P 500 kiểm tra riêng: date validation -> duplicate -> missing ->
    # price validity -> sort. KHÔNG chạy check_gap() cho S&P 500, vì S&P 500
    # không giao dịch cuối tuần / ngày lễ Mỹ — những ngày đó KHÔNG phải là
    # gap, mà là chuyện bình thường của lịch giao dịch chứng khoán.
    print("\n========== DATA QUALITY CHECK: S&P 500 ==========")
    sp500 = check_date_validity(sp500)
    sp500 = check_duplicates(sp500)
    sp500 = check_missing(sp500)
    sp500 = check_price_validity(sp500, ["SP500_Close"])
    sp500 = sp500.sort_values("Date").reset_index(drop=True)
    print("====================================================\n")

    # Inner join: chỉ giữ những ngày CẢ HAI đều có dữ liệu
    # (S&P 500 nghỉ cuối tuần / lễ Mỹ sẽ tự động bị loại khỏi dataset này)
    merged = pd.merge(crv, sp500, on="Date", how="inner")
    merged = merged.sort_values("Date").reset_index(drop=True)

    merged = _add_returns(merged, "CRV_Close", "CRV")
    merged = _add_returns(merged, "SP500_Close", "SP500")

    out_path = PROCESSED_DIR / "crv_sp500_analysis.csv"
    merged.to_csv(out_path, index=False)

    print(f"\n[Dataset B] Số dòng: {len(merged)}")
    print(f"[Dataset B] Đã lưu: {out_path}")

    # Cảnh báo nếu ngày sự kiện hack (30/7/2023, Chủ nhật) bị loại khỏi Dataset B
    if EVENT_DATE not in merged["Date"].values:
        print(
            f"  ⚠️  Lưu ý: ngày {EVENT_DATE.date()} (Curve hack) KHÔNG có trong Dataset B "
            f"vì đây là Chủ nhật (S&P 500 nghỉ). Hãy dùng Dataset A để phân tích event window."
        )

    return merged


def main():
    build_dataset_a()
    build_dataset_b()


if __name__ == "__main__":
    main()