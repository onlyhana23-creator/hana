# -*- coding: utf-8 -*-
"""
쿠팡 일간 결제액 / WAU 엑셀에서 데이터 로드.
- 결제액: 일간 → 주차별 합계(억 원)
- WAU: Android+IOS 사용자 수만 사용 (주간)
"""
from pathlib import Path
import re
import pandas as pd


# 결제액 엑셀: 시트 '주요지표', 헤더 5행(0-indexed), 데이터 6행부터.
# 컬럼 0=기간, 1=순 결제금액(원), 4=총 결제횟수(회), 5=총 결제자(명)
PAYMENT_SHEET = "주요지표"
PAYMENT_HEADER_ROW = 5
PAYMENT_DATE_COL = 0
PAYMENT_AMOUNT_COL = 1
PAYMENT_COUNT_COL = 4   # 총 결제횟수(회)
PAYMENT_USERS_COL = 5  # 총 결제자(명)

# WAU 엑셀: 첫 시트, 헤더 행에 'Android+IOS 사용자 수', '날짜' 포함. 데이터는 그 다음 행부터
WAU_DATE_COL_NAME = "날짜"
WAU_ANDROID_IOS_COL_NAME = "Android+IOS 사용자 수"


def _to_numeric(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return None
    if isinstance(s, (int, float)):
        return float(s) if not pd.isna(s) else None
    s = str(s).strip().replace(",", "")
    if not s or s in ("-", "nan", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _week_label(week_start_str: str) -> str:
    """week_start 'YYYY-MM-DD' → 'YY/MM/DD 주차'"""
    if not week_start_str or pd.isna(week_start_str):
        return ""
    s = str(week_start_str).strip()
    if len(s) >= 10:
        y, m, d = s[:4], s[5:7], s[8:10]
        return f"{y[2:]}/{m}/{d} 주차"
    return s


def load_payment_daily_from_excel(path: Path, days: int = 30) -> pd.DataFrame:
    """
    일간 결제 raw 로드: 일자, 순 결제금액, 총 결제횟수, 총 결제자, 직전일 대비 증가율(3지표).
    최근 days 일만 반환.
    """
    if not path.exists():
        return pd.DataFrame(columns=[
            "date", "순_결제금액_원", "총_결제횟수", "총_결제자_명",
            "순_결제금액_전일대비", "총_결제횟수_전일대비", "총_결제자_전일대비"
        ])

    df = pd.read_excel(path, sheet_name=PAYMENT_SHEET, header=None)
    if df.shape[0] <= PAYMENT_HEADER_ROW:
        return pd.DataFrame(columns=[
            "date", "순_결제금액_원", "총_결제횟수", "총_결제자_명",
            "순_결제금액_전일대비", "총_결제횟수_전일대비", "총_결제자_전일대비"
        ])

    data = df.iloc[PAYMENT_HEADER_ROW:, [PAYMENT_DATE_COL, PAYMENT_AMOUNT_COL, PAYMENT_COUNT_COL, PAYMENT_USERS_COL]].copy()
    data.columns = ["date", "순_결제금액_원", "총_결제횟수", "총_결제자_명"]
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for c in ["순_결제금액_원", "총_결제횟수", "총_결제자_명"]:
        data[c] = data[c].apply(_to_numeric)
    data = data.dropna(subset=["순_결제금액_원", "총_결제횟수", "총_결제자_명"])

    data = data.tail(days).reset_index(drop=True)

    for col, pct_col in [
        ("순_결제금액_원", "순_결제금액_전일대비"),
        ("총_결제횟수", "총_결제횟수_전일대비"),
        ("총_결제자_명", "총_결제자_전일대비"),
    ]:
        prev = data[col].shift(1)
        data[pct_col] = None
        mask = prev.notna() & (prev != 0)
        data.loc[mask, pct_col] = ((data.loc[mask, col] - prev[mask]) / prev[mask] * 100).round(2)

    data["date"] = data["date"].dt.strftime("%Y-%m-%d")
    return data


def load_payment_from_excel(path: Path) -> pd.DataFrame:
    """
    '쿠팡 일간 결제액 모니터링.xlsx' 로드.
    일간 순 결제금액을 주차별로 합산해 year_week, week_start, week_label, payment_amount_억 반환.
    """
    if not path.exists():
        return pd.DataFrame(columns=["year_week", "week_start", "week_label", "payment_amount_억", "note"])

    df = pd.read_excel(path, sheet_name=PAYMENT_SHEET, header=None)
    if df.shape[0] <= PAYMENT_HEADER_ROW:
        return pd.DataFrame(columns=["year_week", "week_start", "week_label", "payment_amount_억", "note"])

    data = df.iloc[PAYMENT_HEADER_ROW:]
    data = data.rename(columns={PAYMENT_DATE_COL: "date", PAYMENT_AMOUNT_COL: "amount"})
    data = data[["date", "amount"]].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"])
    data["amount"] = data["amount"].apply(_to_numeric)
    data = data.dropna(subset=["amount"])

    data["week_start_dt"] = data["date"].dt.to_period("W-MON").dt.start_time
    data["year_week"] = data["week_start_dt"].dt.strftime("%Y-%W").str.replace("-W", "-", regex=False)

    weekly = data.groupby("week_start_dt", as_index=False).agg(
        year_week=("year_week", "first"),
        payment_amount_억=("amount", lambda x: round(x.sum() / 100_000_000, 1)),
    )
    weekly["week_start"] = weekly["week_start_dt"].dt.strftime("%Y-%m-%d")
    weekly["week_label"] = weekly["week_start"].apply(_week_label)
    weekly["note"] = ""
    return weekly[["year_week", "week_start", "week_label", "payment_amount_억", "note"]]


def load_wau_from_excel(path: Path) -> pd.DataFrame:
    """
    '쿠팡 WAU 모니터링.xlsx' 로드.
    Android+IOS 사용자 수만 사용. 시트는 첫 번째 시트, 헤더 행에서 '날짜', 'Android+IOS 사용자 수' 컬럼 찾기.
    """
    if not path.exists():
        return pd.DataFrame(columns=["year_week", "week_start", "week_label", "active_users_만", "note"])

    xl = pd.ExcelFile(path)
    sheet = xl.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet, header=None)

    # 헤더 행 찾기 (날짜, Android+IOS 사용자 수 포함된 행)
    header_row = None
    date_col = None
    aios_col = None
    for r in range(min(15, len(df))):
        row = df.iloc[r]
        for c in range(len(row)):
            v = str(row.iloc[c]).strip() if pd.notna(row.iloc[c]) else ""
            if v == WAU_DATE_COL_NAME:
                date_col = c
            if v == WAU_ANDROID_IOS_COL_NAME:
                aios_col = c
        if date_col is not None and aios_col is not None:
            header_row = r
            break

    if header_row is None or date_col is None or aios_col is None:
        return pd.DataFrame(columns=["year_week", "week_start", "week_label", "active_users_만", "note"])

    data = df.iloc[header_row + 1 :, [date_col, aios_col]].copy()
    data = data.rename(columns={data.columns[0]: "date_str", data.columns[1]: "users"})
    data["users"] = data["users"].apply(_to_numeric)
    data = data.dropna(subset=["users"])

    # 날짜 파싱: "2025-06-30 ~ 2025-07-06" → 주 시작일 2025-06-30
    def parse_week_start(s):
        if pd.isna(s):
            return None
        s = str(s).strip()
        m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
        if m:
            return m.group(1)
        return None

    data["week_start"] = data["date_str"].apply(parse_week_start)
    data = data.dropna(subset=["week_start"])
    data["year_week"] = pd.to_datetime(data["week_start"]).dt.strftime("%Y-%W").str.replace("-W", "-", regex=False)
    data["week_label"] = data["week_start"].apply(_week_label)
    data["active_users_만"] = (data["users"] / 10_000).round(1)
    data["note"] = ""

    out = data[["year_week", "week_start", "week_label", "active_users_만", "note"]].drop_duplicates(subset=["year_week"])
    return out.sort_values("week_start").reset_index(drop=True)


def load_payment_df(base_dir: Path, excel_path: str = None) -> pd.DataFrame:
    """설정 또는 기본 경로로 결제액 엑셀 로드 후 주차별 DataFrame 반환."""
    base_dir = Path(base_dir)
    path = base_dir / (excel_path or "쿠팡 일간 결제액 모니터링.xlsx")
    return load_payment_from_excel(path)


def load_wau_df(base_dir: Path, excel_path: str = None) -> pd.DataFrame:
    """설정 또는 기본 경로로 WAU 엑셀 로드 후 주차별 DataFrame 반환 (Android+IOS만)."""
    base_dir = Path(base_dir)
    path = base_dir / (excel_path or "쿠팡 WAU 모니터링.xlsx")
    return load_wau_from_excel(path)


def load_payment_daily_df(base_dir: Path, excel_path: str = None, days: int = 30) -> pd.DataFrame:
    """일간 결제 데이터 로드 (최근 days일, 전일대비 증가율 포함)."""
    base_dir = Path(base_dir)
    path = base_dir / (excel_path or "쿠팡 일간 결제액 모니터링.xlsx")
    return load_payment_daily_from_excel(path, days=days)
