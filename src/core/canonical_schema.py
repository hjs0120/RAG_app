"""Canonical JSON 스키마 — 문서 유형에 독립적인 RAG 기반 구조."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CanonicalSource:
    """문서 출처 메타데이터."""
    file_name: str
    organization: str | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"file_name": self.file_name}
        if self.organization is not None:
            d["organization"] = self.organization
        if self.version is not None:
            d["version"] = self.version
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> CanonicalSource | None:
        if d is None or not isinstance(d, dict):
            return None
        fn = d.get("file_name")
        if fn is None:
            return None
        return cls(
            file_name=str(fn),
            organization=d.get("organization"),
            version=d.get("version"),
        )


@dataclass
class CanonicalLocation:
    """물리/논리 위치."""
    physical_page: int | None = None
    logical_page: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.physical_page is not None:
            d["physical_page"] = self.physical_page
        if self.logical_page is not None:
            d["logical_page"] = self.logical_page
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> CanonicalLocation | None:
        if d is None or not isinstance(d, dict):
            return None
        pp = d.get("physical_page")
        lp = d.get("logical_page")
        if pp is None and lp is None:
            return None
        return cls(
            physical_page=int(pp) if pp is not None else None,
            logical_page=int(lp) if lp is not None else None,
        )


@dataclass
class CanonicalStructureItem:
    """계층 구조 항목 (장/절/조/항)."""
    level: int
    type: str  # "chapter" | "section" | "article" | "paragraph" | ...
    label: str

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "type": self.type, "label": self.label}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> CanonicalStructureItem | None:
        if d is None or not isinstance(d, dict):
            return None
        level = d.get("level")
        t = d.get("type")
        label = d.get("label")
        if level is None or t is None or label is None:
            return None
        return cls(level=int(level), type=str(t), label=str(label))


@dataclass
class CanonicalContent:
    """본문 내용."""
    text: str
    language: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"text": self.text}
        if self.language is not None:
            d["language"] = self.language
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> CanonicalContent | None:
        if d is None or not isinstance(d, dict):
            return None
        text = d.get("text")
        if text is None:
            return None
        return cls(text=str(text), language=d.get("language"))


@dataclass
class CanonicalRecord:
    """Canonical JSON 최상위 레코드."""

    doc_id: str
    doc_type: str
    content: CanonicalContent
    source: CanonicalSource | None = None
    location: CanonicalLocation | None = None
    structure: list[CanonicalStructureItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type,
            "content": self.content.to_dict(),
        }
        if self.source is not None:
            d["source"] = self.source.to_dict()
        if self.location is not None:
            d["location"] = self.location.to_dict()
        if self.structure:
            d["structure"] = [s.to_dict() for s in self.structure]
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CanonicalRecord:
        doc_id = d.get("doc_id")
        doc_type = d.get("doc_type")
        content = CanonicalContent.from_dict(d.get("content"))

        if doc_id is None:
            raise ValueError("doc_id is required")
        if doc_type is None:
            raise ValueError("doc_type is required")
        if content is None:
            raise ValueError("content.text is required")

        source = CanonicalSource.from_dict(d.get("source"))
        location = CanonicalLocation.from_dict(d.get("location"))

        structure: list[CanonicalStructureItem] = []
        for item in d.get("structure") or []:
            si = CanonicalStructureItem.from_dict(item)
            if si is not None:
                structure.append(si)

        return cls(
            doc_id=str(doc_id),
            doc_type=str(doc_type),
            content=content,
            source=source,
            location=location,
            structure=structure,
        )
