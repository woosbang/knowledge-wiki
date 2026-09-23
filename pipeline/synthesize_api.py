"""Phase 5c — Anthropic API 로 토픽 본문 무인 작성.

Claude Code 슬래시 커맨드와 **같은 지침 파일**(pipeline/prompts/synthesize.md)을 쓴다.

필요: uv sync --extra api  +  환경변수 ANTHROPIC_API_KEY

※ 아직 실제 API 호출로 검증하지 않았다. 처음 쓸 때는 --dry-run 으로 출력을 먼저 본다.
"""

from __future__ import annotations

import json
import os
from typing import Any

from . import config, extract, scan
from . import topics as topics_mod
from .models import Topic

# 근거 하나당 본문 상한. 넘으면 앞부분 + 목차만 준다 (토큰 낭비 방지)
MAX_SOURCE_CHARS = 16000


def _source_block(slug: str, by_slug) -> str:
    data = extract.load_extracted(slug)
    e = by_slug[slug]
    if data is None:
        raise FileNotFoundError(f"추출 캐시 없음: {slug} — 먼저 `wiki scan` 을 실행하세요.")
    headings = "\n".join(f"{'  ' * (h['level'] - 2)}- {h['text']}" for h in data["headings"])
    return (
        f"### 근거 문서 `{slug}`\n"
        f"- 제목: {data['title']}\n- 날짜: {e.doc_date}\n- 상태: {e.status}\n"
        f"- 요약: {e.summary}\n\n"
        f"#### 목차\n{headings or '(없음)'}\n\n"
        f"#### 본문\n{data['text'][:MAX_SOURCE_CHARS]}\n"
    )


def _user_message(topic: Topic, by_slug) -> str:
    meta = json.dumps(topic.to_dict(), ensure_ascii=False, indent=2)
    old = topics_mod.load_md(topic.id)
    parts = [
        "## 토픽 메타데이터 (wiki/topics/<id>.json)\n```json\n" + meta + "\n```\n",
        "## 근거 문서들\n",
        *[_source_block(s, by_slug) for s in topic.sources if s in by_slug],
    ]
    if old:
        parts.append("## 기존 본문 (재합성 — memo 블록은 반드시 옮길 것)\n```markdown\n" + old + "\n```\n")
    parts.append("위 지침대로 `wiki/topics/<id>.md` 의 내용만 Markdown 으로 출력하라. 코드 펜스로 감싸지 말 것.")
    return "\n".join(parts)


def synthesize_one(client: Any, topic: Topic, by_slug, model: str) -> str:
    message = client.messages.create(
        model=model,
        max_tokens=8000,
        system=[{"type": "text", "text": topics_mod.PROMPT_PATH.read_text(encoding="utf-8"),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _user_message(topic, by_slug)}],
    )
    text = "".join(getattr(b, "text", "") for b in message.content).strip()
    # 모델이 그래도 펜스로 감쌌으면 벗긴다
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip() + "\n"


def synthesize_pending(
    ids: list[str] | None = None, model: str = "claude-sonnet-5", dry_run: bool = False
) -> list[str]:
    from anthropic import Anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY 환경변수가 없습니다.")

    by_slug = {e.slug: e for e in scan.load_entries()}
    all_topics = topics_mod.load_topics()
    topics_mod.sync_modes(all_topics, by_slug)
    targets = [t for t in all_topics if topics_mod.needs_synthesis(t, by_slug)]
    if ids:
        targets = [t for t in all_topics if t.id in set(ids) and not t.locked]
    if not targets:
        return []

    client = Anthropic()
    done: list[str] = []
    for t in targets:
        md = synthesize_one(client, t, by_slug, model)
        md = topics_mod.preserve_memo(topics_mod.load_md(t.id), md)
        if dry_run:
            print(f"===== {t.id} =====\n{md}")
        else:
            topics_mod.md_path(t.id).write_text(md, encoding="utf-8")
            topics_mod.mark_synthesized(t, by_slug, by="api")
            for p in topics_mod.check_topic(t, by_slug):
                print(f"  ⚠ {t.id}: {p}")
        done.append(t.id)
    return done
