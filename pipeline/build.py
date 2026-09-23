"""entries + extracted → site/ 정적 위키 생성.

입력은 오직 wiki/ 아래의 데이터다. 누가(사람/Claude Code/API) 채웠는지는 상관하지 않는다.
"""

from __future__ import annotations

import json
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import config, extract, scan
from .models import Entry


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


def _group(entries: list[Entry], taxonomy: dict) -> list[dict[str, Any]]:
    """카테고리 정의 순서대로 문서를 묶는다. 정의에 없는 카테고리는 뒤에 붙인다."""
    by_cat: dict[str, list[Entry]] = defaultdict(list)
    for e in entries:
        by_cat[e.category or "misc"].append(e)

    defined = {c["id"]: c for c in taxonomy.get("categories", [])}
    groups: list[dict[str, Any]] = []

    for cid, meta in sorted(defined.items(), key=lambda kv: kv[1].get("order", 500)):
        docs = sorted(by_cat.pop(cid, []), key=lambda e: e.title)
        groups.append({**meta, "documents": docs, "count": len(docs)})

    for cid, docs in sorted(by_cat.items()):
        groups.append({
            "id": cid,
            "name": cid,
            "blurb": "taxonomy.yaml 에 정의되지 않은 카테고리입니다.",
            "order": 1000,
            "undefined": True,
            "documents": sorted(docs, key=lambda e: e.title),
            "count": len(docs),
        })
    return groups


def _subgroups(group: dict[str, Any]) -> list[dict[str, Any]]:
    defined = {s["id"]: s for s in group.get("subcategories") or []}
    buckets: dict[str, list[Entry]] = defaultdict(list)
    for e in group["documents"]:
        buckets[e.subcategory or ""].append(e)

    out: list[dict[str, Any]] = []
    for sid, meta in defined.items():
        if buckets.get(sid):
            out.append({**meta, "documents": buckets.pop(sid)})
    for sid, docs in buckets.items():
        if not docs:
            continue
        out.append({"id": sid or "_", "name": meta_name(sid), "documents": docs})
    return out


def meta_name(sid: str) -> str:
    return sid or "그 외"


def _search_index(entries: list[Entry]) -> list[dict[str, Any]]:
    rows = []
    for e in entries:
        data = extract.load_extracted(e.slug) or {}
        text = (data.get("text") or "")[:4000]
        rows.append({
            "slug": e.slug,
            "title": e.title,
            "category": e.category,
            "tags": e.tags,
            "summary": e.summary,
            "status": e.status,
            "body": text,
        })
    return rows


def build() -> dict[str, Any]:
    taxonomy = load_taxonomy()
    entries = [e for e in scan.load_entries() if e.status != "draft"]
    env = _env()

    if config.SITE_DIR.exists():
        shutil.rmtree(config.SITE_DIR)
    (config.SITE_DIR / "d").mkdir(parents=True, exist_ok=True)
    (config.SITE_DIR / "c").mkdir(parents=True, exist_ok=True)
    (config.SITE_DIR / "raw").mkdir(parents=True, exist_ok=True)

    groups = _group(entries, taxonomy)
    by_slug = {e.slug: e for e in entries}

    # 홈
    recent = sorted(entries, key=lambda e: e.doc_date, reverse=True)[:8]
    (config.SITE_DIR / "index.html").write_text(
        env.get_template("index.html").render(
            root="",
            groups=[g for g in groups if g["count"]],
            recent=recent,
            total=len(entries),
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

    # 문서 페이지 + 원본 사본
    for entry in entries:
        data = extract.load_extracted(entry.slug)
        if data is None:
            continue
        related = [by_slug[s] for s in entry.related if s in by_slug]
        successor = by_slug.get(entry.superseded_by) if entry.superseded_by else None
        (config.SITE_DIR / "d" / f"{entry.slug}.html").write_text(
            env.get_template("doc.html").render(
                root="../",
                entry=entry,
                body=data["html"],
                headings=entry.headings or data.get("headings", []),
                related=related,
                successor=successor,
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
        json.dumps(_search_index(entries), ensure_ascii=False), encoding="utf-8"
    )
    if config.ASSETS_DIR.exists():
        shutil.copytree(config.ASSETS_DIR, config.SITE_DIR / "assets", dirs_exist_ok=True)
    (config.SITE_DIR / ".nojekyll").write_text("", encoding="utf-8")

    return {
        "documents": len(entries),
        "categories": sum(1 for g in groups if g["count"]),
        "built_at": datetime.now().isoformat(timespec="seconds"),
    }
