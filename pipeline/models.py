"""wiki/entries/<slug>.json 의 스키마.

이 스키마는 Claude Code(슬래시 커맨드)와 API 스크립트가 공유하는 계약이다.
누가 채웠든 build 는 이 파일만 읽는다.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATUSES = ("active", "draft", "outdated", "superseded")
LEVELS = ("beginner", "intermediate", "advanced")


@dataclass
class Overlap:
    """다른 문서와 내용이 겹친다는 지적. 자동 삭제는 하지 않고 리포트만 한다."""

    slug: str
    reason: str = ""
    severity: str = "low"  # low | medium | high


@dataclass
class Entry:
    # --- scan/extract 가 채우는 기계적 사실 ---
    slug: str
    source: str                      # ROOT 기준 상대경로 (docs/xxx.html)
    source_hash: str = ""            # 본문 해시. 바뀌면 재분류 대상.
    title: str = ""
    doc_date: str = ""               # 원본 파일 mtime (YYYY-MM-DD)
    word_count: int = 0
    headings: list[dict[str, Any]] = field(default_factory=list)

    # --- AI(또는 사람)가 채우는 판단 ---
    category: str = ""               # taxonomy.yaml 의 카테고리 id
    subcategory: str = ""
    tags: list[str] = field(default_factory=list)
    summary: str = ""                # 2~3문장. 목록/검색에 노출된다.
    key_points: list[str] = field(default_factory=list)
    level: str = "intermediate"
    related: list[str] = field(default_factory=list)      # 관련 문서 slug
    supersedes: list[str] = field(default_factory=list)   # 이 문서가 대체하는 문서
    superseded_by: str = ""                               # 이 문서를 대체한 문서
    overlaps: list[dict[str, Any]] = field(default_factory=list)
    status: str = "active"
    notes: str = ""                  # 사람이 남기는 메모. AI 가 덮어쓰지 않는다.

    # --- 이력 ---
    classified_at: str = ""
    classified_by: str = ""          # claude-code | api | manual
    classifier_hash: str = ""        # 분류 시점의 source_hash

    @property
    def needs_classification(self) -> bool:
        """분류가 없거나, 분류 이후 원본이 바뀌었으면 True."""
        if not self.category or not self.summary:
            return True
        return self.classifier_hash != self.source_hash

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Entry":
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def load(cls, path: Path) -> "Entry":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
