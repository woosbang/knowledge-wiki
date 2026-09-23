"""wiki CLI.

  uv run wiki scan      docs/ 를 읽어 추출 캐시와 entry 골격을 갱신
  uv run wiki status    AI 분류가 필요한 문서를 보여준다
  uv run wiki audit     중복/노후/미분류 리포트를 생성
  uv run wiki build     site/ 정적 위키 생성
  uv run wiki sync      scan → audit → build 를 한 번에
  uv run wiki serve     site/ 를 로컬에서 띄운다
  uv run wiki classify  (선택) Anthropic API 로 무인 분류
"""

from __future__ import annotations

import argparse
import json
import sys

from . import audit as audit_mod
from . import build as build_mod
from . import config, scan


def cmd_scan(args: argparse.Namespace) -> int:
    result = scan.scan(force=args.force)
    scan.write_index(scan.load_entries())
    print(f"신규 {len(result.new)} · 변경 {len(result.changed)} · 유지 {len(result.unchanged)}")
    for slug in result.new:
        print(f"  + {slug}")
    for slug in result.changed:
        print(f"  ~ {slug}")
    for slug in result.orphaned:
        print(f"  ! {slug} (원본 없음)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    entries = scan.load_entries()
    pending = [e for e in entries if e.needs_classification]
    print(f"문서 {len(entries)}개 · 분류 필요 {len(pending)}개")
    if args.json:
        print(json.dumps(
            [{"slug": e.slug,
              "title": e.title,
              "source": e.source,
              "extracted": str((config.EXTRACTED_DIR / f"{e.slug}.json").relative_to(config.ROOT)),
              "reason": "신규" if not e.category else "원본 변경"}
             for e in pending],
            ensure_ascii=False, indent=2,
        ))
    else:
        for e in pending:
            why = "신규" if not e.category else "원본 변경"
            print(f"  · {e.slug} — {e.title}  [{why}]")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    report = audit_mod.run()
    print(f"리포트: {(config.REPORTS_DIR / 'health.md').relative_to(config.ROOT)}")
    print(f"  분류 필요 {len(report['unclassified'])} · "
          f"중복 의심 {len(report['duplicate_candidates'])} · "
          f"노후 {len(report['stale'])} · 고아 {len(report['orphans'])}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    result = build_mod.build()
    print(f"빌드 완료 → {config.SITE_DIR.relative_to(config.ROOT)}  "
          f"(문서 {result['documents']} · 카테고리 {result['categories']})")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    cmd_scan(args)
    cmd_audit(args)
    return cmd_build(args)


def cmd_serve(args: argparse.Namespace) -> int:
    import functools
    import http.server
    import socketserver

    if not config.SITE_DIR.exists():
        print("site/ 가 없습니다. 먼저 `uv run wiki build` 를 실행하세요.", file=sys.stderr)
        return 1
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(config.SITE_DIR))
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        print(f"http://127.0.0.1:{args.port}/  (Ctrl+C 로 종료)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print()
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    try:
        from .classify_api import classify_pending
    except ImportError as exc:
        print(f"anthropic 패키지가 필요합니다: uv sync --extra api  ({exc})", file=sys.stderr)
        return 1
    done = classify_pending(slugs=args.slug, model=args.model, dry_run=args.dry_run)
    print(f"분류 완료 {len(done)}개")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wiki", description="knowledge-wiki 파이프라인")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="docs/ 스캔 및 본문 추출")
    p.add_argument("--force", action="store_true", help="변경이 없어도 전부 다시 추출")
    p.set_defaults(func=cmd_scan, json=False)

    p = sub.add_parser("status", help="분류가 필요한 문서 목록")
    p.add_argument("--json", action="store_true", help="JSON 으로 출력 (AI 가 읽기 좋게)")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("audit", help="중복/노후 리포트 생성")
    p.set_defaults(func=cmd_audit, json=False)

    p = sub.add_parser("build", help="site/ 생성")
    p.set_defaults(func=cmd_build, json=False)

    p = sub.add_parser("sync", help="scan + audit + build")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_sync, json=False)

    p = sub.add_parser("serve", help="로컬 미리보기 서버")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve, json=False)

    p = sub.add_parser("classify", help="Anthropic API 로 자동 분류 (Phase 2)")
    p.add_argument("--slug", action="append", help="특정 문서만 (반복 지정 가능)")
    p.add_argument("--model", default="claude-sonnet-5")
    p.add_argument("--dry-run", action="store_true", help="호출 결과를 저장하지 않고 출력만")
    p.set_defaults(func=cmd_classify, json=False)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
