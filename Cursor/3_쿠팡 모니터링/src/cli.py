# -*- coding: utf-8 -*-
"""
매주 실행: 엑셀(일간 결제액, WAU) 기반으로 주간 보고서 생성.

사용 예:
  python -m src.cli              # 최근 주차 보고서
  python -m src.cli 2025-27      # 해당 주차
  python -m src.cli --print     # 내용 stdout 출력
"""
import argparse
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description="쿠팡 주간 모니터링 보고서 생성 (엑셀 기반)")
    parser.add_argument("year_week", nargs="?", help="주차 예: 2025-27. 생략 시 최근 주차.")
    parser.add_argument("--print", action="store_true", help="보고서 내용을 stdout에 출력")
    parser.add_argument("--no-file", action="store_true", help="파일 저장 없이 --print 만")
    args = parser.parse_args()

    try:
        from .analyze import run_weekly
    except Exception as e:
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        content, yw = run_weekly(year_week=args.year_week or None)
    except FileNotFoundError as e:
        print(f"설정: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"보고서 생성 실패: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.no_file:
        reports_dir = BASE / "reports"
        reports_dir.mkdir(exist_ok=True)
        path = reports_dir / f"coupang_monitor_{yw}.md"
        path.write_text(content, encoding="utf-8")
        print(f"저장: {path}", file=sys.stderr)

    if args.print or args.no_file:
        print(content)
    else:
        print("위키에 올리려면: Cursor에서 '이번 주 쿠팡 모니터링 위키에 올려줘' 또는 --print 로 내용 확인.", file=sys.stderr)


if __name__ == "__main__":
    main()
