"""wiki CLI.

  uv run wiki scan        docs/ 를 읽어 추출 캐시와 entry 골격을 갱신
  uv run wiki status      AI 가 할 일 — 분류가 필요한 문서, 합성이 필요한 토픽
  uv run wiki audit       중복/노후/토픽 리포트를 생성
  uv run wiki build       site/ 정적 위키 생성
  uv run wiki sync        scan → audit → build 를 한 번에
  uv run wiki serve       site/ 를 로컬에서 띄운다

  토픽 (PRD 8절)
  uv run wiki topic-init <id> --title … --category … --sources a b   토픽 생성 + 근거 배정
  uv run wiki topic-add  <id> <slug>…                                기존 토픽에 근거 추가
  uv run wiki synth-done <id> [--by claude-code]                     본문(.md) 쓴 뒤 해시 기록 + 검사

  (선택) API 무인 실행 — uv sync --extra api
  uv run wiki classify    미분류 문서를 Anthropic API 로 분류
  uv run wiki synthesize  합성이 필요한 토픽을 Anthropic API 로 작성
"""

from __future__ import annotations

import argparse
import json
import sys

from . import audit as audit_mod
from . import build as build_mod
from . import config, scan
from . import topics as topics_mod
from .models import Topic


def _by_slug():
    return {e.slug: e for e in scan.load_entries()}


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
    by_slug = {e.slug: e for e in entries}
    pending = [e for e in entries if e.needs_classification]

    all_topics = topics_mod.load_topics()
    topics_mod.sync_modes(all_topics, by_slug)
    topic_ids = {t.id for t in all_topics}
    synth = [t for t in all_topics if topics_mod.needs_synthesis(t, by_slug)]
    unassigned = [e for e in entries if not e.needs_classification and (not e.topic or e.topic not in topic_ids)]

    if args.json:
        print(json.dumps({
            "classify": [{
                "slug": e.slug, "title": e.title, "source": e.source,
                "extracted": str((config.EXTRACTED_DIR / f"{e.slug}.json").relative_to(config.ROOT)),
                "reason": "신규" if not e.category else "원본 변경",
            } for e in pending],
            "assign_topic": [{"slug": e.slug, "title": e.title, "category": e.category} for e in unassigned],
            "synthesize": [{
                "id": t.id, "title": t.title, "sources": t.sources,
                "extracted": [str((config.EXTRACTED_DIR / f"{s}.json").relative_to(config.ROOT)) for s in t.sources],
                "md": str(topics_mod.md_path(t.id).relative_to(config.ROOT)),
                "has_md": topics_mod.load_md(t.id) is not None,
                "reason": "본문 없음" if topics_mod.load_md(t.id) is None else "근거 또는 지침 변경",
            } for t in synth],
            "topics": [{"id": t.id, "title": t.title, "category": t.category, "sources": t.sources}
                       for t in all_topics],
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"문서 {len(entries)}개 · 분류 필요 {len(pending)}개 · 토픽 미배정 {len(unassigned)}개 "
          f"· 토픽 {len(all_topics)}개 · 합성 필요 {len(synth)}개")
    for e in pending:
        print(f"  · 분류  {e.slug} — {e.title}  [{'신규' if not e.category else '원본 변경'}]")
    for e in unassigned:
        print(f"  · 배정  {e.slug} — {e.title}")
    for t in synth:
        print(f"  · 합성  {t.id} — {t.title}  (근거 {len(t.sources)})")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    report = audit_mod.run()
    print(f"리포트: {(config.REPORTS_DIR / 'health.md').relative_to(config.ROOT)}")
    print(f"  분류 필요 {len(report['unclassified'])} · "
          f"중복 의심 {len(report['duplicate_candidates'])} · "
          f"노후 {len(report['stale'])} · 고아 {len(report['orphans'])} · "
          f"토픽 합성 필요 {len(report['topics_pending'])} · "
          f"토픽 미배정 {len(report['unassigned'])} · "
          f"검사 경고 {len(report['topic_problems'])}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    result = build_mod.build()
    print(f"빌드 완료 → {config.SITE_DIR.relative_to(config.ROOT)}  "
          f"(토픽 {result['topics']} · 문서 {result['documents']} · 카테고리 {result['categories']})")
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


# ── 토픽 ─────────────────────────────────────────────────────────────────

def _assign(topic: Topic, slugs: list[str], by_slug) -> list[str]:
    """entry.topic 을 채운다. 다른 토픽에 이미 속해 있으면 옮긴다."""
    moved = []
    for slug in slugs:
        e = by_slug.get(slug)
        if e is None:
            print(f"  ! `{slug}` — entry 없음 (건너뜀)", file=sys.stderr)
            continue
        if e.topic and e.topic != topic.id:
            old = topics_mod.topic_path(e.topic)
            if old.exists():
                t_old = Topic.load(old)
                t_old.sources = [s for s in t_old.sources if s != slug]
                t_old.save(old)
                moved.append(f"{slug}: {e.topic} → {topic.id}")
        e.topic = topic.id
        e.save(config.ENTRIES_DIR / f"{slug}.json")
        if slug not in topic.sources:
            topic.sources.append(slug)
    return moved


def cmd_topic_init(args: argparse.Namespace) -> int:
    path = topics_mod.topic_path(args.id)
    if path.exists() and not args.force:
        print(f"이미 있는 토픽: {args.id}  (덮어쓰려면 --force, 근거만 추가하려면 topic-add)", file=sys.stderr)
        return 1
    by_slug = _by_slug()
    topic = Topic(
        id=args.id, title=args.title, category=args.category,
        subcategory=args.subcategory or "", summary=args.summary or "",
        tags=args.tags or [], primary=args.primary or (args.sources[0] if args.sources else ""),
    )
    moved = _assign(topic, args.sources, by_slug)
    topic.mode = topics_mod.resolve_mode(topic, by_slug)
    topic.save(path)
    scan.write_index(scan.load_entries())
    print(f"토픽 생성: {topic.id}  mode={topic.mode}  근거 {len(topic.sources)}")
    for m in moved:
        print(f"  ↪ {m}")
    if topic.mode == "synthesized":
        print(f"  → 본문을 써야 한다: {topics_mod.md_path(topic.id).relative_to(config.ROOT)}")
    return 0


def cmd_topic_add(args: argparse.Namespace) -> int:
    path = topics_mod.topic_path(args.id)
    if not path.exists():
        print(f"없는 토픽: {args.id}", file=sys.stderr)
        return 1
    by_slug = _by_slug()
    topic = Topic.load(path)
    moved = _assign(topic, args.slugs, by_slug)
    topic.mode = topics_mod.resolve_mode(topic, by_slug)
    topic.save(path)
    scan.write_index(scan.load_entries())
    print(f"토픽 갱신: {topic.id}  mode={topic.mode}  근거 {len(topic.sources)}")
    for m in moved:
        print(f"  ↪ {m}")
    if topics_mod.needs_synthesis(topic, by_slug):
        print(f"  → 재합성 필요: {topics_mod.md_path(topic.id).relative_to(config.ROOT)}")
    return 0


def cmd_synth_done(args: argparse.Namespace) -> int:
    path = topics_mod.topic_path(args.id)
    if not path.exists():
        print(f"없는 토픽: {args.id}", file=sys.stderr)
        return 1
    if topics_mod.load_md(args.id) is None:
        print(f"본문이 없다: {topics_mod.md_path(args.id).relative_to(config.ROOT)}", file=sys.stderr)
        return 1
    by_slug = _by_slug()
    topic = Topic.load(path)
    if topic.locked and not args.force:
        print(f"잠긴 토픽이다: {args.id}  (사람이 잠갔다면 --force 로만 기록한다)", file=sys.stderr)
        return 1
    topic = topics_mod.mark_synthesized(topic, by_slug, by=args.by)
    problems = topics_mod.check_topic(topic, by_slug)
    print(f"기록 완료: {topic.id}  synth_hash={topic.synth_hash}  by={topic.synthesized_by}")
    if problems:
        print("검사 경고:")
        for p in problems:
            print(f"  - {p}")
        return 2
    print("검사 통과: 인용 · 코드 · 분량")
    return 0


# ── API 경로 ─────────────────────────────────────────────────────────────

def cmd_classify(args: argparse.Namespace) -> int:
    try:
        from .classify_api import classify_pending
    except ImportError as exc:
        print(f"anthropic 패키지가 필요합니다: uv sync --extra api  ({exc})", file=sys.stderr)
        return 1
    done = classify_pending(slugs=args.slug, model=args.model, dry_run=args.dry_run)
    print(f"분류 완료 {len(done)}개")
    return 0


def cmd_synthesize(args: argparse.Namespace) -> int:
    try:
        from .synthesize_api import synthesize_pending
    except ImportError as exc:
        print(f"anthropic 패키지가 필요합니다: uv sync --extra api  ({exc})", file=sys.stderr)
        return 1
    done = synthesize_pending(ids=args.id, model=args.model, dry_run=args.dry_run)
    print(f"합성 완료 {len(done)}개")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wiki", description="knowledge-wiki 파이프라인")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="docs/ 스캔 및 본문 추출")
    p.add_argument("--force", action="store_true", help="변경이 없어도 전부 다시 추출")
    p.set_defaults(func=cmd_scan, json=False)

    p = sub.add_parser("status", help="AI 가 할 일 (분류 / 토픽 배정 / 합성)")
    p.add_argument("--json", action="store_true", help="JSON 으로 출력 (AI 가 읽기 좋게)")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("audit", help="중복/노후/토픽 리포트 생성")
    p.set_defaults(func=cmd_audit, json=False)

    p = sub.add_parser("build", help="site/ 생성")
    p.set_defaults(func=cmd_build, json=False)

    p = sub.add_parser("sync", help="scan + audit + build")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_sync, json=False)

    p = sub.add_parser("serve", help="로컬 미리보기 서버")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve, json=False)

    p = sub.add_parser("topic-init", help="토픽 생성 + 근거 문서 배정")
    p.add_argument("id")
    p.add_argument("--title", required=True)
    p.add_argument("--category", required=True)
    p.add_argument("--subcategory")
    p.add_argument("--summary")
    p.add_argument("--tags", nargs="*")
    p.add_argument("--sources", nargs="+", required=True, help="근거 문서 slug")
    p.add_argument("--primary", help="충돌 시 기준 문서 (기본: 첫 근거)")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_topic_init)

    p = sub.add_parser("topic-add", help="기존 토픽에 근거 문서 추가")
    p.add_argument("id")
    p.add_argument("slugs", nargs="+")
    p.set_defaults(func=cmd_topic_add)

    p = sub.add_parser("synth-done", help="본문(.md) 작성 후 synth_hash 기록 + 신뢰 검사")
    p.add_argument("id")
    p.add_argument("--by", default="claude-code", choices=["claude-code", "api", "manual"])
    p.add_argument("--force", action="store_true", help="잠긴 토픽에도 기록")
    p.set_defaults(func=cmd_synth_done)

    p = sub.add_parser("classify", help="Anthropic API 로 자동 분류 (Phase 3)")
    p.add_argument("--slug", action="append", help="특정 문서만 (반복 지정 가능)")
    p.add_argument("--model", default="claude-sonnet-5")
    p.add_argument("--dry-run", action="store_true", help="호출 결과를 저장하지 않고 출력만")
    p.set_defaults(func=cmd_classify, json=False)

    p = sub.add_parser("synthesize", help="Anthropic API 로 토픽 본문 작성 (Phase 5c)")
    p.add_argument("--id", action="append", help="특정 토픽만 (반복 지정 가능)")
    p.add_argument("--model", default="claude-sonnet-5")
    p.add_argument("--dry-run", action="store_true", help="결과를 저장하지 않고 출력만")
    p.set_defaults(func=cmd_synthesize, json=False)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
