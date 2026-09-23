"""Phase 2 — Anthropic API 로 무인 분류.

Claude Code 슬래시 커맨드와 **같은 지침 파일**(pipeline/prompts/classify.md)을 쓴다.
따라서 둘 중 무엇으로 돌려도 결과 스키마와 기준이 같다.

필요: uv sync --extra api  +  환경변수 ANTHROPIC_API_KEY
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from . import config, extract, scan
from .models import Entry

PROMPT_PATH = Path(__file__).parent / "prompts" / "classify.md"

# 본문이 길면 앞부분과 목차만으로도 분류에는 충분하다. 토큰 낭비를 줄인다.
MAX_BODY_CHARS = 12000

TOOL_SCHEMA = {
    "name": "record_classification",
    "description": "문서 한 건의 분류 결과를 기록한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "subcategory": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
            "summary": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
            "level": {"type": "string", "enum": ["beginner", "intermediate", "advanced"]},
            "related": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            "overlaps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "slug": {"type": "string"},
                        "reason": {"type": "string"},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                    "required": ["slug", "reason", "severity"],
                },
            },
            "status": {"type": "string", "enum": ["active", "draft", "outdated", "superseded"]},
            "supersedes": {"type": "array", "items": {"type": "string"}},
            "superseded_by": {"type": "string"},
        },
        "required": ["category", "tags", "summary", "key_points", "level", "status"],
    },
}


def _context() -> str:
    taxonomy = config.TAXONOMY_PATH.read_text(encoding="utf-8")
    index = config.INDEX_PATH.read_text(encoding="utf-8") if config.INDEX_PATH.exists() else "{}"
    return (
        "## 카테고리 체계 (wiki/taxonomy.yaml)\n```yaml\n" + taxonomy + "\n```\n\n"
        "## 기존 문서 목록 (wiki/index.json)\n```json\n" + index + "\n```\n"
    )


def _document_block(slug: str) -> str:
    data = extract.load_extracted(slug)
    if data is None:
        raise FileNotFoundError(f"추출 캐시 없음: {slug} — 먼저 `wiki scan` 을 실행하세요.")
    headings = "\n".join(f"{'  ' * (h['level'] - 2)}- {h['text']}" for h in data["headings"])
    return (
        f"## 분류 대상 문서\n\n"
        f"- slug: `{slug}`\n- 제목: {data['title']}\n\n"
        f"### 목차\n{headings or '(없음)'}\n\n"
        f"### 본문\n{data['text'][:MAX_BODY_CHARS]}\n"
    )


def classify_one(client: Any, slug: str, model: str, shared_context: str) -> dict[str, Any]:
    message = client.messages.create(
        model=model,
        max_tokens=2000,
        system=[
            {"type": "text", "text": PROMPT_PATH.read_text(encoding="utf-8")},
            {"type": "text", "text": shared_context, "cache_control": {"type": "ephemeral"}},
        ],
        tools=[TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "record_classification"},
        messages=[{"role": "user", "content": _document_block(slug)}],
    )
    for block in message.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input)
    raise RuntimeError(f"분류 결과를 받지 못했습니다: {slug}")


def apply_result(slug: str, result: dict[str, Any]) -> Entry:
    path = config.ENTRIES_DIR / f"{slug}.json"
    entry = Entry.load(path)
    entry.category = result.get("category", "misc")
    entry.subcategory = result.get("subcategory", "")
    entry.tags = result.get("tags", [])
    entry.summary = result.get("summary", "")
    entry.key_points = result.get("key_points", [])
    entry.level = result.get("level", "intermediate")
    entry.related = result.get("related", [])
    entry.overlaps = result.get("overlaps", [])
    entry.status = result.get("status", "active")
    entry.supersedes = result.get("supersedes", [])
    entry.superseded_by = result.get("superseded_by", "")
    entry.classified_at = date.today().isoformat()
    entry.classified_by = "api"
    entry.classifier_hash = entry.source_hash  # 재분류 스킵 기준
    entry.save(path)
    return entry


def classify_pending(
    slugs: list[str] | None = None, model: str = "claude-sonnet-5", dry_run: bool = False
) -> list[str]:
    from anthropic import Anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 없습니다.")

    entries = scan.load_entries()
    targets = [e.slug for e in entries if e.needs_classification]
    if slugs:
        targets = [s for s in slugs if s in {e.slug for e in entries}]

    if not targets:
        return []

    client = Anthropic()
    shared = _context()
    done: list[str] = []

    for slug in targets:
        result = classify_one(client, slug, model, shared)
        if dry_run:
            print(json.dumps({slug: result}, ensure_ascii=False, indent=2))
        else:
            apply_result(slug, result)
        done.append(slug)

    if not dry_run:
        scan.write_index(scan.load_entries())
    return done
