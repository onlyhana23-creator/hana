# -*- coding: utf-8 -*-
"""쿠팡 관련 뉴스 수집 (네이버 뉴스 검색 API)."""
import os
import re
import html
import json
from urllib.parse import urlparse
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
import requests

NAVER_NEWS_URL = "https://openapi.naver.com/v1/search/news.json"
RECENT30D_CACHE_FILE = "coupang_news_recent30d.json"
RECENT2W_CACHE_FILE = "coupang_news_recent2w.json"

# 쿠팡 혜택·와우 멤버십 관련만 포함 (최소 하나 포함)
INCLUDE_KEYWORDS = ("혜택", "멤버십", "와우", "변경", "개편", "조정", "무료배송", "회원혜택")


def _strip_html(text):
    """HTML 태그 제거 후 html.unescape 적용."""
    if not text or not isinstance(text, str):
        return ""
    s = re.sub(r"<[^>]+>", "", text.strip())
    return html.unescape(s).strip()


def _normalize_url(url):
    """URL 정규화: trailing slash 제거 후 scheme+netloc+path만 사용, 중복 비교용 키 반환."""
    if not url or not isinstance(url, str):
        return ""
    s = url.strip()
    s = s.rstrip("/")
    try:
        p = urlparse(s)
        base = f"{p.scheme}://{p.netloc}{p.path}" if p.scheme and p.netloc else s
        return base.lower()
    except Exception:
        return s.lower()


def _normalize_title(title):
    """제목 정규화: 공백·특수문자 정리 후 중복 비교용 키 반환."""
    if not title or not isinstance(title, str):
        return ""
    s = re.sub(r"\s+", " ", title.strip())
    return s[:100] if len(s) > 100 else s


def fetch_naver_news(query: str, client_id: str, client_secret: str, display: int = 20, sort: str = "date"):
    """네이버 뉴스 검색. 성공 시 items 리스트, 실패 시 예외 발생(원인 파악용)."""
    if not client_id or not client_secret:
        return []
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    params = {"query": query, "display": min(display, 100), "sort": sort}
    r = requests.get(NAVER_NEWS_URL, headers=headers, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("items", [])


def collect_coupang_news(config: dict, cache_dir: Path, year_week: str):
    naver = config.get("naver_search") or {}
    cid = naver.get("client_id") or os.getenv("NAVER_CLIENT_ID")
    csec = naver.get("client_secret") or os.getenv("NAVER_CLIENT_SECRET")
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"coupang_news_{year_week.replace('-', '_')}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    items = []
    for q in ["쿠팡", "쿠팡 결제", "쿠팡 로켓배송", "쿠팡 이벤트"]:
        items.extend(fetch_naver_news(q, cid or "", csec or "", display=15, sort="date"))
    # 중복 제거: URL(link) 기준 1건만 유지. URL 없으면 제목 기준.
    seen_url = set()
    seen_title = set()
    unique = []
    for x in items:
        link = (x.get("link") or "").strip()
        t = (x.get("title") or "").strip()
        key = link if link else t
        if not key:
            continue
        if link and link in seen_url:
            continue
        if not link and t in seen_title:
            continue
        if link:
            seen_url.add(link)
        else:
            seen_title.add(t)
        unique.append({"title": t, "link": link or x.get("link"), "description": (x.get("description") or "").strip(), "pubDate": x.get("pubDate")})
    result = {"year_week": year_week, "collected_at": datetime.now().isoformat(), "items": unique[:50]}
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return result


def _is_benefit_or_membership_related(title: str, description: str) -> bool:
    """쿠팡 혜택 변경·와우 멤버십 관련이면 True. 단순 브랜드·행사 광고는 False."""
    text = (title or "") + " " + (description or "")
    if not text.strip():
        return False
    has_include = any(k in text for k in INCLUDE_KEYWORDS)
    # 혜택/멤버십/와우/변경 등 관련 키워드가 있어야 포함
    if not has_include:
        return False
    # 광고·홍보만 있으면 제외 (관련 키워드와 함께 있어도 광고성 강하면 제외하지 않음)
    if "광고" in text or "홍보" in text:
        if "혜택" not in text and "멤버십" not in text and "변경" not in text:
            return False
    return True


def _filter_benefit_membership_only(items: list) -> list:
    """혜택·와우 멤버십 관련 기사만 남기고 단순 광고/행사는 제외."""
    return [x for x in items if _is_benefit_or_membership_related(
        (x.get("title") or "").strip(),
        (x.get("description") or "").strip()
    )]


def _parse_pubdate(pubdate_str):
    """pubDate 문자열을 datetime으로 파싱. 실패 시 None."""
    if not pubdate_str or not isinstance(pubdate_str, str):
        return None
    s = pubdate_str.strip()
    try:
        return parsedate_to_datetime(s)
    except Exception:
        try:
            return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None


def collect_coupang_news_recent_30d(config: dict, cache_dir: Path):
    """
    최근 30일 간 쿠팡 관련 뉴스 수집.
    display=100, sort=date 로 요청 후 pubDate 기준 30일 이내만 필터, URL/제목 중복 제거.
    """
    naver = config.get("naver_search") or {}
    cid = naver.get("client_id") or os.getenv("NAVER_CLIENT_ID")
    csec = naver.get("client_secret") or os.getenv("NAVER_CLIENT_SECRET")
    cache_dir = Path(cache_dir)
    if os.environ.get("VERCEL"):
        cache_dir = Path("/tmp/news_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / RECENT30D_CACHE_FILE

    if not cid or not csec:
        return {"items": [], "message": "config.yaml에 네이버 검색 API client_id, client_secret을 설정하면 최근 30일 뉴스가 표시됩니다."}

    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            collected = datetime.fromisoformat(data.get("collected_at", "2000-01-01"))
            if (datetime.now() - collected).total_seconds() < 3600:
                return data
        except Exception:
            pass

    raw_items = []
    try:
        for q in ["쿠팡 혜택 변경", "와우 멤버십", "쿠팡 와우 혜택", "쿠팡 멤버십 변경", "쿠팡 회원 혜택"]:
            raw_items.extend(fetch_naver_news(q, cid, csec, display=50, sort="date"))
    except Exception as e:
        return {"items": [], "message": "뉴스 API 오류: " + str(e)}

    items = _filter_benefit_membership_only(raw_items)
    use_fallback = len(items) == 0
    if use_fallback:
        items = raw_items  # 필터 결과 0건이면 필터 없이 최근 뉴스 사용

    cutoff = (datetime.now() - timedelta(days=30)).date()
    seen_url = set()
    seen_title = set()
    unique = []
    for x in items:
        link = (x.get("link") or "").strip()
        t = (x.get("title") or "").strip()
        pub = _parse_pubdate(x.get("pubDate"))
        if pub is not None:
            pub_date = pub.date() if hasattr(pub, "date") else pub
            if hasattr(pub_date, "year") and pub_date < cutoff:
                continue
        if not t and not link:
            continue
        if link and link in seen_url:
            continue
        if not link and t in seen_title:
            continue
        if link:
            seen_url.add(link)
        else:
            seen_title.add(t)
        unique.append({"title": t, "link": link or x.get("link"), "description": (x.get("description") or "").strip(), "pubDate": x.get("pubDate")})

    result = {"collected_at": datetime.now().isoformat(), "items": unique[:50]}
    if use_fallback and result["items"]:
        result["message"] = "혜택·와우 멤버십 관련 기사가 없어 최근 쿠팡 뉴스를 표시합니다."
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return result


def collect_coupang_news_recent_2w(config: dict, cache_dir: Path):
    """
    최근 2주 간 쿠팡 관련 뉴스 수집.
    HTML 태그 제거, URL/제목 정규화로 중복 제거, 날짜 YYYY-MM-DD 포맷.
    """
    naver = config.get("naver_search") or {}
    cid = naver.get("client_id") or os.getenv("NAVER_CLIENT_ID")
    csec = naver.get("client_secret") or os.getenv("NAVER_CLIENT_SECRET")
    cache_dir = Path(cache_dir)
    if os.environ.get("VERCEL"):
        cache_dir = Path("/tmp/news_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / RECENT2W_CACHE_FILE

    if not cid or not csec:
        return {"items": [], "message": "config.yaml에 네이버 검색 API client_id, client_secret을 설정하면 최근 2주 뉴스가 표시됩니다."}

    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            collected = datetime.fromisoformat(data.get("collected_at", "2000-01-01"))
            if (datetime.now() - collected).total_seconds() < 3600:
                return data
        except Exception:
            pass

    raw_items = []
    try:
        for q in ["쿠팡 혜택 변경", "와우 멤버십", "쿠팡 와우 혜택", "쿠팡 멤버십 변경", "쿠팡 회원 혜택"]:
            raw_items.extend(fetch_naver_news(q, cid, csec, display=50, sort="date"))
    except Exception as e:
        return {"items": [], "message": "뉴스 API 오류: " + str(e)}

    items = _filter_benefit_membership_only(raw_items)
    use_fallback = len(items) == 0
    if use_fallback:
        items = raw_items

    cutoff = (datetime.now() - timedelta(days=14)).date()
    seen_url = set()
    seen_title = set()
    unique = []
    for x in items:
        raw_link = (x.get("link") or "").strip()
        raw_title = (x.get("title") or "").strip()
        raw_desc = (x.get("description") or "").strip()
        title = _strip_html(raw_title)
        desc = _strip_html(raw_desc)
        link = _strip_html(raw_link) or raw_link
        url_key = _normalize_url(link)
        title_key = _normalize_title(title) if title else ""
        pub = _parse_pubdate(x.get("pubDate"))
        if pub is not None:
            pub_date = pub.date() if hasattr(pub, "date") else pub
            if hasattr(pub_date, "year") and pub_date < cutoff:
                continue
        if not title and not link:
            continue
        if url_key and url_key in seen_url:
            continue
        if title_key and title_key in seen_title:
            continue
        if url_key:
            seen_url.add(url_key)
        if title_key:
            seen_title.add(title_key)
        date_str = pub.strftime("%Y-%m-%d") if pub else ""
        unique.append({
            "title": title,
            "link": link or x.get("link"),
            "description": desc,
            "pubDate": x.get("pubDate"),
            "date": date_str,
        })

    result = {"collected_at": datetime.now().isoformat(), "items": unique[:50]}
    if use_fallback and result["items"]:
        result["message"] = "혜택·와우 멤버십 관련 기사가 없어 최근 쿠팡 뉴스를 표시합니다."
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return result


def news_to_markdown(news_result: dict) -> str:
    if not news_result or not news_result.get("items"):
        return "해당 주차 쿠팡 혜택·와우 멤버십 관련 뉴스가 수집되지 않았습니다. (네이버 검색 API 설정 시 표시됩니다.)"
    lines = ["### 쿠팡 혜택·와우 멤버십 뉴스 (결제액·이슈 연관 참고)", ""]
    for item in news_result["items"][:20]:
        title = (item.get("title") or "").replace("|", "\\|")
        link = item.get("link") or ""
        pub = item.get("pubDate") or ""
        lines.append(f"- **{title}**  ")
        if link:
            lines.append(f"  - 링크: {link}")
        if pub:
            lines.append(f"  - 일자: {pub}")
        lines.append("")
    return "\n".join(lines)
