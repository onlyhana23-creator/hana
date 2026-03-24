# -*- coding: utf-8 -*-
"""설정 로드."""
from pathlib import Path
import os
import yaml

BASE = Path(__file__).resolve().parent.parent


def load_config():
    config_path = BASE / "config.yaml"
    example_path = BASE / "config.example.yaml"
    path_to_load = config_path if config_path.exists() else example_path
    if not path_to_load.exists():
        return {}
    with open(path_to_load, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # config.example.yaml 의 naver_search 등 보조 설정 반영 (config에 없거나 비어 있을 때)
    if example_path.exists() and example_path != path_to_load:
        try:
            with open(example_path, "r", encoding="utf-8") as ef:
                example = yaml.safe_load(ef) or {}
            for key in ("naver_search", "confluence"):
                ex = example.get(key) or {}
                if not ex:
                    continue
                cur = data.setdefault(key, {})
                for k, v in ex.items():
                    if v and (not cur.get(k)):
                        cur[k] = v
        except Exception:
            pass
    if os.getenv("CONFLUENCE_SPACE_KEY"):
        data.setdefault("confluence", {})["space_key"] = os.getenv("CONFLUENCE_SPACE_KEY")
    if os.getenv("NAVER_CLIENT_ID"):
        data.setdefault("naver_search", {})["client_id"] = os.getenv("NAVER_CLIENT_ID")
    if os.getenv("NAVER_CLIENT_SECRET"):
        data.setdefault("naver_search", {})["client_secret"] = os.getenv("NAVER_CLIENT_SECRET")
    return data


def get_paths(config):
    """데이터 파일 경로. 엑셀 파일명은 config 또는 기본값 사용."""
    paths = (config.get("paths") or {}).copy()
    paths.setdefault("payment_excel", "cp_payment.xlsx")
    paths.setdefault("wau_excel", "cp_wau.xlsx")
    paths.setdefault("news_cache_dir", "data/news_cache")
    result = {}
    for k, v in paths.items():
        if k == "news_cache_dir" and isinstance(v, str) and not Path(v).is_absolute():
            result[k] = BASE / v
        elif k.endswith("_excel"):
            result[k] = v  # 파일명만 저장, base_dir과 조합해 사용
        else:
            result[k] = BASE / v if isinstance(v, str) and not Path(v).is_absolute() else v
    return result
