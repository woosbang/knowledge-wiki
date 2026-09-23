"""docs/ 를 훑어 entries/ 와 동기화한다.

여기서는 '기계적으로 알 수 있는 것'만 채운다. 분류·요약은 AI 단계의 몫.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from . import config, extract
from .models import Entry


@dataclass
class ScanResult:
    new: list[str]
    changed: list[str]
    unchanged: list[str]
    orphaned: list[str]   # entries 는 있는데 docs 에서 사라진 문서

    @property
    def needs_ai(self) -> list[str]:
        return self.new + self.changed


def slugify(name: str) -> str:
    """파일명 → URL 슬러그. 한글은 그대로 살린다(가독성 우선)."""
    s = name.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^\w가-힣\-]+", "", s, flags=re.UNICODE)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _source_files() -> list[Path]:
    if not config.DOCS_DIR.exists():
        return []
    return sorted(
        p for p in config.DOCS_DIR.rglob("*.html")
        if p.is_file() and not p.name.startswith(("_", "."))
    )


def scan(force: bool = False) -> ScanResult:
    """docs/ 를 읽어 추출 캐시와 entry 골격을 갱신한다."""
    config.ENTRIES_DIR.mkdir(parents=True, exist_ok=True)

    new: list[str] = []
    changed: list[str] = []
    unchanged: list[str] = []
    seen: set[str] = set()
    slug_owner: dict[str, Path] = {}

    for path in _source_files():
        slug = slugify(path.stem)
        if slug in slug_owner:  # 슬러그 충돌 — 파일명 해시를 붙여 분리
            slug = f"{slug}-{hashlib.sha1(str(path).encode()).hexdigest()[:6]}"
        slug_owner[slug] = path
        seen.add(slug)

        digest = file_hash(path)
        entry_path = config.ENTRIES_DIR / f"{slug}.json"
        is_new = not entry_path.exists()
        entry = Entry(slug=slug, source="") if is_new else Entry.load(entry_path)

        if not is_new and entry.source_hash == digest and not force:
            unchanged.append(slug)
            if extract.load_extracted(slug) is not None:
                continue  # 캐시까지 멀쩡하면 건너뛴다

        data = extract.extract_file(path, slug)
        extract.write_extracted(data)

        entry.slug = slug
        entry.source = path.relative_to(config.ROOT).as_posix()
        entry.source_hash = digest
        entry.title = entry.title if entry.title and not is_new else data["title"]
        entry.headings = data["headings"]
        entry.word_count = data["word_count"]
        entry.doc_date = date.fromtimestamp(path.stat().st_mtime).isoformat()
        entry.save(entry_path)

        if is_new:
            new.append(slug)
        elif slug not in unchanged:
            changed.append(slug)

    orphaned = sorted(
        p.stem for p in config.ENTRIES_DIR.glob("*.json") if p.stem not in seen
    )

    return ScanResult(
        new=sorted(new),
        changed=sorted(changed),
        unchanged=sorted(unchanged),
        orphaned=orphaned,
    )


def load_entries(include_orphans: bool = False) -> list[Entry]:
    entries: list[Entry] = []
    for path in sorted(config.ENTRIES_DIR.glob("*.json")):
        entry = Entry.load(path)
        if not include_orphans and not (config.ROOT / entry.source).exists():
            continue
        entries.append(entry)
    return entries


def write_index(entries: list[Entry]) -> Path:
    """사람과 AI 가 한 번에 훑어볼 수 있는 요약 인덱스."""
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(entries),
        "documents": [
            {
                "slug": e.slug,
                "title": e.title,
                "category": e.category,
                "subcategory": e.subcategory,
                "tags": e.tags,
                "status": e.status,
                "summary": e.summary,
                "doc_date": e.doc_date,
                "needs_classification": e.needs_classification,
            }
            for e in entries
        ],
    }
    config.INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.INDEX_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return config.INDEX_PATH
