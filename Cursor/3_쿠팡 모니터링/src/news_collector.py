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

# 네이버 뉴스 검색 쿼리 (중복은 수집 후 URL/제목으로 제거)
NEWS_SEARCH_QUERIES = [
    "쿠팡 실적",
    "쿠팡 매출",
    "쿠팡 이용자",
    "쿠팡 AI",
    "쿠팡 물류",
    "쿠팡 배송 정책",
    "쿠팡 무료배송",
    "와우 멤버십",
    "쿠팡 와우",
    "쿠팡 멤버십",
    "쿠팡 혜택 변경",
    "쿠팡 경영",
    "쿠팡 분기",
    "쿠팡 신사업",
    "쿠팡 로켓배송",
    "쿠팡 회원 혜택",
    "쿠팡 개편",
]

# Positive: 실적·지표 / 멤버십·배송 / 반응·시장 / 기술·미래 (하나라도 있으면 후보)
_POSITIVE_METRICS = (
    "실적",
    "매출",
    "영업이익",
    "거래액",
    "이용자",
    "MAU",
    "WAU",
    "경영",
    "분기",
    "분기실적",
    "GMV",
)
_POSITIVE_MEMBERSHIP = (
    "혜택",
    "멤버십",
    "와우",
    "무료배송",
    "배송",
    "로켓배송",
    "배송비",
    "개편",
    "조정",
    "회원혜택",
    "회원",
    "배송정책",
)
_POSITIVE_REACTION = (
    "소비자",
    "시장",
    "시민단체",
    "논란",
    "반발",
    "비판",
    "환영",
    "여론",
    "반응",
)
_POSITIVE_TECH = (
    "AI",
    "인공지능",
    "자동화",
    "물류",
    "로봇",
    "신사업",
    "투자",
    "기술",
)

# Negative: 제목에 경쟁사가 두드러지는데 쿠팡이 제목에 없을 때
_COMPETITOR_IN_TITLE = (
    "컬리",
    "이마트",
    "롯데마트",
    "홈플러스",
    "SSG",
    "이마트몰",
    "SSG닷컴",
    "네이버쇼핑",
)

_EMPTY_MEANINGFUL_MSG = (
    "유의미 뉴스 선정 기준에 맞는 기사가 최근 기간 내에 없습니다. "
    "(칼럼·타사 위주·위클립 등은 제외됩니다.)"
)


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


def _should_exclude_news(title_plain: str, body_plain: str) -> bool:
    """Negative filter. 제목 위주 휴리스틱."""
    t = title_plain or ""
    full = (title_plain or "") + " " + (body_plain or "")
    if re.search(r"\[[^\]]*칼럼[^\]]*\]", t):
        return True
    if "사설" in t:
        return True
    if "위클립" in t or "[위클립]" in t:
        return True
    if "휴무" in t and "쿠팡" not in t:
        return True
    if any(c in t for c in _COMPETITOR_IN_TITLE) and "쿠팡" not in t:
        return True
    if "쿠팡" not in full and "로켓" not in full and "와우" not in full:
        return True
    return False


def _has_coupang_brand_context(body_plain: str) -> bool:
    """쿠팡·로켓·와우 등 브랜드 맥락이 본문(제목+요약)에 있는지."""
    text = body_plain or ""
    if "쿠팡" in text:
        return True
    if "로켓" in text:
        return True
    if "와우" in text:
        return True
    return False


def _matches_positive_signal(body_plain: str) -> bool:
    """Positive OR: 실적·멤버십/배송·반응·기술 중 하나."""
    text = body_plain or ""
    groups = (
        _POSITIVE_METRICS,
        _POSITIVE_MEMBERSHIP,
        _POSITIVE_REACTION,
        _POSITIVE_TECH,
    )
    for grp in groups:
        if any(k in text for k in grp):
            return True
    return False


def _is_meaningful_coupang_news(raw_title: str, raw_description: str) -> bool:
    """유의미 뉴스 선정: Negative 제외 → 쿠팡 연관 → Positive OR."""
    title = _strip_html(raw_title or "")
    desc = _strip_html(raw_description or "")
    full = title + " " + desc
    if not full.strip():
        return False
    if _should_exclude_news(title, full):
        return False
    if not _has_coupang_brand_context(full):
        return False
    if not _matches_positive_signal(full):
        return False
    if "광고" in full or "홍보" in full:
        if not any(k in full for k in ("혜택", "멤버십", "실적", "매출", "배송", "와우", "쿠팡")):
            return False
    return True


def _filter_meaningful_items(items: list) -> list:
    return [
        x
        for x in items
        if _is_meaningful_coupang_news(
            (x.get("title") or "").strip(),
            (x.get("description") or "").strip(),
        )
    ]


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
    for q in ["쿠팡", "쿠팡 결제", "쿠팡 로켓배송", "쿠팡 이벤트", "쿠팡 실적", "와우 멤버십"]:
        items.extend(fetch_naver_news(q, cid or "", csec or "", display=15, sort="date"))
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
    unique = _filter_meaningful_items(unique)
    result = {"year_week": year_week, "collected_at": datetime.now().isoformat(), "items": unique[:50]}
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return result


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
        for q in NEWS_SEARCH_QUERIES:
            raw_items.extend(fetch_naver_news(q, cid, csec, display=50, sort="date"))
    except Exception as e:
        return {"items": [], "message": "뉴스 API 오류: " + str(e)}

    items = _filter_meaningful_items(raw_items)

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
    if not result["items"]:
        result["message"] = _EMPTY_MEANINGFUL_MSG
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
        for q in NEWS_SEARCH_QUERIES:
            raw_items.extend(fetch_naver_news(q, cid, csec, display=50, sort="date"))
    except Exception as e:
        return {"items": [], "message": "뉴스 API 오류: " + str(e)}

    items = _filter_meaningful_items(raw_items)

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
    if not result["items"]:
        result["message"] = _EMPTY_MEANINGFUL_MSG
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return result


def news_to_markdown(news_result: dict) -> str:
    if not news_result or not news_result.get("items"):
        return "해당 주차 쿠팡 관련 유의미 뉴스가 수집되지 않았습니다. (네이버 검색 API 설정 시 표시됩니다.)"
    lines = ["### 쿠팡 관련 유의미 뉴스 (실적·멤버십·배송·시장반응·기술 등)", ""]
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
