# -*- coding: utf-8 -*-
"""
쿠팡 모니터링 대시보드 Flask 앱.
실행: python app.py → http://localhost:5000
"""
import os
import socket
from pathlib import Path
from flask import Flask, render_template, jsonify, request, send_file

# .env 파일이 있으면 DATABASE_URL 등 환경 변수 로드
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.config import load_config, get_paths
from src.excel_loader import (
    load_payment_daily_df,
    load_payment_df,
    load_wau_df,
)
from src.news_collector import collect_coupang_news, collect_coupang_news_recent_2w
from models import db

app = Flask(__name__, static_folder="static", template_folder="templates")
BASE = Path(__file__).resolve().parent

# DB 연결 (DATABASE_URL 있으면 Neon PostgreSQL, 없으면 로컬 sqlite)
database_url = os.environ.get("DATABASE_URL")
if database_url:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif database_url.startswith("postgresql://") and "+" not in database_url.split("://")[0]:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + str(BASE / "local.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


def _get_paths():
    config = load_config()
    return get_paths(config)


def _local_ips_and_port():
    """이 PC의 로컬 IP 목록과 서버 포트. 팀원 접속용 주소 표시에 사용."""
    port = int(os.environ.get("PORT", 5000))
    ips = []
    try:
        # 외부로 나가는 기본 IP가 로컬 LAN IP인 경우가 많음
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
        except Exception:
            pass
        finally:
            s.close()
        # 모든 네트워크 인터페이스의 IPv4 주소
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    if not ips:
        ips = ["127.0.0.1"]
    return {"port": port, "ips": ips, "urls": [f"http://{ip}:{port}" for ip in ips]}


@app.route("/api/server-info")
def api_server_info():
    """접속 주소 안내용: port, ips, urls."""
    return jsonify(_local_ips_and_port())


@app.route("/")
def index():
    return render_template("dashboard.html")


def _week_label_from_date(date_str: str) -> str:
    """YYYY-MM-DD → 해당 주 월요일 YY/MM/DD 주차."""
    try:
        from datetime import datetime
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        # Monday = 0, so subtract weekday and add (Monday)
        from datetime import timedelta
        monday = d - timedelta(days=d.weekday())
        y, m, day = monday.year, monday.month, monday.day
        return f"{str(y)[2:]}/{m:02d}/{day:02d} 주차"
    except Exception:
        return date_str


@app.route("/api/payment/daily")
def api_payment_daily():
    """일간 결제: 최근 30일, 순 결제금액/총 결제횟수/총 결제자, 직전일 대비 증가율. 주간 그룹용 week_label 포함."""
    paths = _get_paths()
    days = int(__import__("flask").request.args.get("days", 30))
    df = load_payment_daily_df(BASE, paths.get("payment_excel"), days=days)
    rows = []
    for _, r in df.iterrows():
        date_str = r["date"]
        rows.append({
            "date": date_str,
            "week_label": _week_label_from_date(date_str),
            "순_결제금액_원": r["순_결제금액_원"],
            "총_결제횟수": r["총_결제횟수"],
            "총_결제자_명": r["총_결제자_명"],
            "순_결제금액_WoW": r.get("순_결제금액_WoW"),
            "총_결제횟수_WoW": r.get("총_결제횟수_WoW"),
            "총_결제자_WoW": r.get("총_결제자_WoW"),
        })
    return jsonify({"data": rows})


@app.route("/api/payment/weekly")
def api_payment_weekly():
    """주차별 결제 합계. week_label = YY/MM/DD 주차."""
    paths = _get_paths()
    df = load_payment_df(BASE, paths.get("payment_excel"))
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "year_week": r["year_week"],
            "week_start": r["week_start"],
            "week_label": r.get("week_label", ""),
            "payment_amount_억": r["payment_amount_억"],
        })
    return jsonify({"data": rows})


@app.route("/api/wau/weekly")
def api_wau_weekly():
    """주차별 WAU(Android+IOS). week_label = YY/MM/DD 주차."""
    paths = _get_paths()
    df = load_wau_df(BASE, paths.get("wau_excel"))
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "year_week": r["year_week"],
            "week_start": r["week_start"],
            "week_label": r.get("week_label", ""),
            "active_users_만": r["active_users_만"],
        })
    return jsonify({"data": rows})


@app.route("/api/news")
def api_news():
    """최근 2주 쿠팡 뉴스 (URL/제목 기준 중복 제거, HTML 제거). 날짜, 기사제목, 링크."""
    config = load_config()
    paths = _get_paths()
    result = collect_coupang_news_recent_2w(config, paths["news_cache_dir"])
    items = result.get("items", [])
    rows = [{"title": x.get("title", ""), "link": x.get("link", ""), "date": x.get("date", "")} for x in items]
    out = {"data": rows}
    if result.get("message"):
        out["message"] = result["message"]
    return jsonify(out)


def _excel_path(which: str):
    """which: 'payment' | 'wau'"""
    paths = _get_paths()
    name = paths.get("payment_excel") if which == "payment" else paths.get("wau_excel")
    path = BASE / (name or ("쿠팡 일간 결제액 모니터링.xlsx" if which == "payment" else "쿠팡 WAU 모니터링.xlsx"))
    return path


@app.route("/api/excel/download/<which>")
def api_excel_download(which):
    """엑셀 다운로드. which: payment | wau"""
    if which not in ("payment", "wau"):
        return jsonify({"error": "invalid type"}), 400
    path = _excel_path(which)
    if not path.exists():
        return jsonify({"error": "파일 없음"}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


@app.route("/api/excel/upload", methods=["POST"])
def api_excel_upload():
    """엑셀 업로드. form 필드: payment (결제액 파일), wau (WAU 파일). 각각 선택 가능."""
    paths = _get_paths()
    payment_name = paths.get("payment_excel") or "쿠팡 일간 결제액 모니터링.xlsx"
    wau_name = paths.get("wau_excel") or "쿠팡 WAU 모니터링.xlsx"
    saved = []
    if "payment" in request.files:
        f = request.files["payment"]
        if f and f.filename and f.filename.lower().endswith(".xlsx"):
            path = BASE / payment_name
            f.save(path)
            saved.append("payment")
    if "wau" in request.files:
        f = request.files["wau"]
        if f and f.filename and f.filename.lower().endswith(".xlsx"):
            path = BASE / wau_name
            f.save(path)
            saved.append("wau")
    return jsonify({"ok": True, "saved": saved})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
