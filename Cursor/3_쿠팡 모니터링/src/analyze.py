# -*- coding: utf-8 -*-
"""주차별 쿠팡 결제액·WAU(Android+IOS) 분석 및 위키용 보고서 생성. 데이터는 엑셀에서 로드."""
import pandas as pd
from pathlib import Path
from .config import load_config, get_paths
from .excel_loader import load_payment_df, load_wau_df
from .news_collector import collect_coupang_news, news_to_markdown


def _str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "nan"):
        return "-"
    return str(v).strip()


def build_weekly_report(year_week: str, payment_df: pd.DataFrame, users_df: pd.DataFrame, news_md: str) -> str:
    lines = [
        f"# 쿠팡 모니터링 주간 보고 ({year_week})",
        "",
        "## 1. 쿠팡 결제액 (주차별, 일간 집계)",
        "",
    ]
    pay_row = payment_df[payment_df["year_week"].astype(str) == str(year_week)]
    if not pay_row.empty:
        row = pay_row.iloc[0]
        amount = _str(row.get("payment_amount_억", ""))
        note = _str(row.get("note", ""))
        lines.append(f"- **해당 주({year_week}) 결제액**: {amount}억 원")
        if note != "-":
            lines.append(f"- 비고: {note}")
    else:
        lines.append(f"- 해당 주({year_week}) 결제액 데이터 없음 (엑셀에 해당 기간 일간 데이터가 있는지 확인)")
    lines.extend(["", "| 주차 | 주 시작일 | 결제액(억) | 비고 |", "|------|-----------|------------|------|"])
    for _, r in payment_df.tail(12).iterrows():
        wl = _str(r.get("week_label")) if "week_label" in r else _str(r.get("week_start"))
        lines.append(f"| {wl} | {_str(r.get('week_start'))} | {_str(r.get('payment_amount_억'))} | {_str(r.get('note'))} |")
    lines.append("")

    lines.extend(["## 2. 쿠팡 WAU (Android+IOS 사용자 수, 주간)", ""])
    users_row = users_df[users_df["year_week"].astype(str) == str(year_week)]
    if not users_row.empty:
        row = users_row.iloc[0]
        u = _str(row.get("active_users_만", ""))
        note = _str(row.get("note", ""))
        lines.append(f"- **해당 주({year_week}) WAU(Android+IOS)**: {u}만 명")
        if note != "-":
            lines.append(f"- 비고: {note}")
    else:
        lines.append(f"- 해당 주({year_week}) WAU 데이터 없음 (쿠팡 WAU 모니터링.xlsx 에 해당 주 데이터 추가 후 확인)")
    lines.extend(["", "| 주차 | 주 시작일 | WAU(Android+IOS, 만 명) | 비고 |", "|------|-----------|--------------------------|------|"])
    for _, r in users_df.tail(12).iterrows():
        wl = _str(r.get("week_label")) if "week_label" in r else _str(r.get("week_start"))
        lines.append(f"| {wl} | {_str(r.get('week_start'))} | {_str(r.get('active_users_만'))} | {_str(r.get('note'))} |")
    lines.append("")
    lines.extend(["", "---", "", news_md])
    return "\n".join(lines)


def run_weekly(year_week: str = None):
    """
    엑셀에서 결제액·WAU 로드 후 해당 주차 보고서 생성.
    반환: (마크다운 문자열, year_week)
    """
    config = load_config()
    paths = get_paths(config)
    base_dir = Path(__file__).resolve().parent.parent
    payment_df = load_payment_df(base_dir, paths.get("payment_excel"))
    users_df = load_wau_df(base_dir, paths.get("wau_excel"))

    if not year_week and not payment_df.empty:
        year_week = str(payment_df["year_week"].iloc[-1])
    if not year_week and not users_df.empty:
        year_week = str(users_df["year_week"].iloc[-1])
    if not year_week:
        year_week = "2025-27"  # 기본값

    news_result = collect_coupang_news(config, paths["news_cache_dir"], year_week)
    news_md = news_to_markdown(news_result)
    content = build_weekly_report(year_week, payment_df, users_df, news_md)
    return content, year_week
