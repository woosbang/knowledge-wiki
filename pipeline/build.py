"""entries + extracted + topics → site/ 정적 위키 생성.

입력은 오직 wiki/ 아래의 데이터다. 누가(사람/Claude Code/API) 채웠는지는 상관하지 않는다.

두 층을 그린다 (PRD 8절):
  t/<topic>.html  토픽 — 정돈된 본문. 홈·카테고리·검색이 먼저 보여주는 것
  d/<slug>.html   원본 문서 — 근거. 그대로 보존되고 토픽에서 링크로 도달한다
  raw/<slug>.html 원본 HTML 그대로 — 추출이 깨져도 내용은 남는다
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config, extract, scan, topics as topics_mod
from .models import Entry, Topic


def load_taxonomy() -> dict[str, Any]:
    if not config.TAXONOMY_PATH.exists():
        return {"categories": [], "rules": {}}
    return yaml.safe_load(config.TAXONOMY_PATH.read_text(encoding="utf-8")) or {}


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(config.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["site_title"] = config.SITE_TITLE
    env.globals["site_description"] = config.SITE_DESCRIPTION
    env.globals["built_at"] = date.today().isoformat()
    return env


def _topic_view(t: Topic, by_slug: dict[str, Entry]) -> dict[str, Any]:
    """템플릿이 쓰는 토픽 뷰. 근거 문서 객체와 정렬용 날짜를 붙인다."""
    srcs = topics_mod.valid_sources(t, by_slug)
    return {
        "id": t.id,
        "title": t.title,
        "category": t.category,
        "subcategory": t.subcategory,
        "summary": t.summary,
        "tags": t.tags,
        "mode": t.mode,
        "locked": t.locked,
        "synthesized_at": t.synthesized_at,
        "synthesized_by": t.synthesized_by,
        "sources": srcs,
        "updated": topics_mod.updated_on(t, by_slug),
        "stale": topics_mod.needs_synthesis(t, by_slug) or topics_mod.is_stale_locked(t, by_slug),
    }


def _group(topic_views: list[dict], loose: list[Entry], taxonomy: dict) -> list[dict[str, Any]]:
    """카테고리 정의 순서대로 토픽과 '토픽 미배정 문서'를 묶는다."""
    by_cat_t: dict[str, list[dict]] = defaultdict(list)
    by_cat_d: dict[str, list[Entry]] = defaultdict(list)
    for tv in topic_views:
        by_cat_t[tv["category"] or "misc"].append(tv)
    for e in loose:
        by_cat_d[e.category or "misc"].append(e)

    defined = {c["id"]: c for c in taxonomy.get("categories", [])}
    groups: list[dict[str, Any]] = []

    def make(cid: str, meta: dict) -> dict[str, Any]:
        ts = sorted(by_cat_t.pop(cid, []), key=lambda v: v["title"])
        ds = sorted(by_cat_d.pop(cid, []), key=lambda e: e.title)
        return {**meta, "topics": ts, "loose": ds, "count": len(ts) + len(ds)}

    for cid, meta in sorted(defined.items(), key=lambda kv: kv[1].get("order", 500)):
        groups.append(make(cid, meta))
    for cid in sorted(set(by_cat_t) | set(by_cat_d)):
        groups.append(make(cid, {
            "id": cid, "name": cid, "order": 1000, "undefined": True,
            "blurb": "taxonomy.yaml 에 정의되지 않은 카테고리입니다.",
        }))
    return groups


def _subgroups(group: dict[str, Any]) -> list[dict[str, Any]]:
    defined = {s["id"]: s for s in group.get("subcategories") or []}
    buckets: dict[str, list[dict]] = defaultdict(list)
    for tv in group["topics"]:
        buckets[tv["subcategory"] or ""].append(tv)

    out: list[dict[str, Any]] = []
    for sid, meta in defined.items():
        if buckets.get(sid):
            out.append({**meta, "topics": buckets.pop(sid)})
    for sid, ts in buckets.items():
        if ts:
            out.append({"id": sid or "_", "name": sid or "그 외", "topics": ts})
    return out


def _topic_body(t: Topic, by_slug: dict[str, Entry], root: str) -> tuple[str, list[dict[str, Any]]]:
    """mode 에 따라 본문을 고른다. synthesized 인데 .md 가 아직 없으면 mirror 처럼 그린다."""
    if t.mode == "synthesized":
        md = topics_mod.load_md(t.id)
        if md is not None:
            return topics_mod.render_markdown(md, by_slug, root)
    primary = by_slug.get(t.primary) or next(iter(topics_mod.valid_sources(t, by_slug)), None)
    if primary is None:
        return "<p>근거 문서가 없습니다.</p>", []
    data = extract.load_extracted(primary.slug) or {}
    return data.get("html", ""), primary.headings or data.get("headings", [])


def _search_index(topic_views: list[dict], entries: list[Entry]) -> list[dict[str, Any]]:
    """토픽을 먼저, 원본 문서를 뒤에. 검색 JS 는 kind 로 링크 경로를 정한다."""
    rows: list[dict[str, Any]] = []
    for tv in topic_views:
        text = ""
        if tv["mode"] == "synthesized":
            text = topics_mod.MEMO_RE.sub("", topics_mod.load_md(tv["id"]) or "")
        if not text and tv["sources"]:
            text = (extract.load_extracted(tv["sources"][0].slug) or {}).get("text", "")
        rows.append({
            "kind": "topic", "slug": tv["id"], "title": tv["title"],
            "category": tv["category"], "tags": tv["tags"], "summary": tv["summary"],
            "status": "active", "body": text[:4000],
        })
    for e in entries:
        data = extract.load_extracted(e.slug) or {}
        rows.append({
            "kind": "doc", "slug": e.slug, "title": e.title,
            "category": e.category, "tags": e.tags, "summary": e.summary,
            "status": e.status, "body": (data.get("text") or "")[:4000],
        })
    return rows


def build() -> dict[str, Any]:
    taxonomy = load_taxonomy()
    entries = [e for e in scan.load_entries() if e.status != "draft"]
    by_slug = {e.slug: e for e in entries}

    all_topics = topics_mod.load_topics()
    topics_mod.sync_modes(all_topics, by_slug)
    all_topics = [t for t in all_topics if topics_mod.valid_sources(t, by_slug)]
    by_topic = {t.id: t for t in all_topics}
    topic_views = [_topic_view(t, by_slug) for t in all_topics]
    covered = {e.slug for t in all_topics for e in topics_mod.valid_sources(t, by_slug)}
    loose = [e for e in entries if e.slug not in covered]   # 토픽 미배정 — 감추지 않고 따로 보여준다

    env = _env()
    if config.SITE_DIR.exists():
        shutil.rmtree(config.SITE_DIR)
    for sub in ("t", "d", "c", "raw"):
        (config.SITE_DIR / sub).mkdir(parents=True, exist_ok=True)

    groups = _group(topic_views, loose, taxonomy)

    # 홈
    recent = sorted(topic_views, key=lambda v: v["updated"], reverse=True)[:8]
    (config.SITE_DIR / "index.html").write_text(
        env.get_template("index.html").render(
            root="", groups=[g for g in groups if g["count"]], recent=recent,
            total_topics=len(topic_views), total_docs=len(entries),
        ),
        encoding="utf-8",
    )

    # 카테고리 페이지
    for group in groups:
        if not group["count"]:
            continue
        (config.SITE_DIR / "c" / f"{group['id']}.html").write_text(
            env.get_template("category.html").render(
                root="../", group=group, subgroups=_subgroups(group), groups=groups
            ),
            encoding="utf-8",
        )

    # 토픽 페이지
    for t in all_topics:
        body, headings = _topic_body(t, by_slug, "../")
        tv = next(v for v in topic_views if v["id"] == t.id)
        (config.SITE_DIR / "t" / f"{t.id}.html").write_text(
            env.get_template("topic.html").render(
                root="../", topic=tv, body=body, headings=headings, groups=groups,
                category=next((g for g in groups if g["id"] == t.category), None),
            ),
            encoding="utf-8",
        )

    # 원본 문서 페이지 + 원본 사본
    for entry in entries:
        data = extract.load_extracted(entry.slug)
        if data is None:
            continue
        related = [by_slug[s] for s in entry.related if s in by_slug]
        successor = by_slug.get(entry.superseded_by) if entry.superseded_by else None
        topic = by_topic.get(entry.topic) if entry.topic else None
        (config.SITE_DIR / "d" / f"{entry.slug}.html").write_text(
            env.get_template("doc.html").render(
                root="../",
                entry=entry,
                body=data["html"],
                headings=entry.headings or data.get("headings", []),
                related=related,
                successor=successor,
                topic=topic,
                groups=groups,
                category=next((g for g in groups if g["id"] == entry.category), None),
            ),
            encoding="utf-8",
        )
        src = config.ROOT / entry.source
        if src.exists():
            shutil.copy2(src, config.SITE_DIR / "raw" / f"{entry.slug}.html")

    # 검색 인덱스 + 정적 자산
    (config.SITE_DIR / "search-index.json").write_text(
        json.dumps(_search_index(topic_views, entries), ensure_ascii=False), encoding="utf-8"
    )
    if config.ASSETS_DIR.exists():
        shutil.copytree(config.ASSETS_DIR, config.SITE_DIR / "assets", dirs_exist_ok=True)
    (config.SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")

    return {
        "topics": len(all_topics),
        "documents": len(entries),
        "categories": sum(1 for g in groups if g["count"]),
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }
