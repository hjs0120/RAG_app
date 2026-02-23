"""Phase 1 수동 검증 — Canonical Schema, Validator, Citation Formatter.

실행: python scripts/test_canonical_phase1.py

검증 항목:
1. canonical_schema.CanonicalRecord.from_dict() → to_dict() 왕복 직렬화
2. canonical_validator.validate(records) → 오류 없이 통과
3. citation_formatter.format_citation(record) → "p.7, 제 1 장 총칙 > 제 101조" 형태
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# rag 패키지 __init__이 faiss 등을 로드하므로, citation_formatter만 직접 로드
from src.core.canonical_schema import (
    CanonicalRecord,
    CanonicalSource,
    CanonicalLocation,
    CanonicalStructureItem,
    CanonicalContent,
)
from src.core.canonical_validator import validate as canonical_validate

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "src.rag.citation_formatter",
    ROOT / "src" / "rag" / "citation_formatter.py",
)
_cf_mod = importlib.util.module_from_spec(_spec)
_cf_mod.__package__ = "src.rag"
sys.modules["src.rag.citation_formatter"] = _cf_mod
_spec.loader.exec_module(_cf_mod)
format_citation = _cf_mod.format_citation


# 기존 문서(이동식 해양구조물 규칙_2024-7-92.pdf) 기반 수동 변환 10개 레코드
MANUAL_CANONICAL_RECORDS = [
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {
            "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
            "organization": "KR",
            "version": "2024",
        },
        "location": {"physical_page": 7},
        "structure": [
            {"level": 1, "type": "chapter", "label": "제 1 장 총칙"},
        ],
        "content": {"text": "제 1 장 총칙", "language": "ko"},
    },
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {
            "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
            "organization": "KR",
            "version": "2024",
        },
        "location": {"physical_page": 7},
        "structure": [
            {"level": 1, "type": "chapter", "label": "제 1 장 총칙"},
            {"level": 2, "type": "section", "label": "제 1 절 일반사항"},
        ],
        "content": {"text": "제 1 절 일반사항", "language": "ko"},
    },
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {
            "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
            "organization": "KR",
            "version": "2024",
        },
        "location": {"physical_page": 7},
        "structure": [
            {"level": 1, "type": "chapter", "label": "제 1 장 총칙"},
            {"level": 2, "type": "section", "label": "제 1 절 일반사항"},
            {"level": 3, "type": "article", "label": "제 101조"},
        ],
        "content": {"text": "101. 적용", "language": "ko"},
    },
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {
            "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
            "organization": "KR",
            "version": "2024",
        },
        "location": {"physical_page": 7},
        "structure": [
            {"level": 1, "type": "chapter", "label": "제 1 장 총칙"},
            {"level": 2, "type": "section", "label": "제 1 절 일반사항"},
            {"level": 3, "type": "article", "label": "제 101조"},
            {"level": 4, "type": "paragraph", "label": "1항"},
        ],
        "content": {
            "text": "1. 이 규칙은 우리 선급에 등록하고자 하는 또는 우리 선급에 등록된 이동식 해양구조물의 설계, 제조, 설치 및 검사에 대하여 적용한다.",
            "language": "ko",
        },
    },
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {
            "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
            "organization": "KR",
            "version": "2024",
        },
        "location": {"physical_page": 7},
        "structure": [
            {"level": 1, "type": "chapter", "label": "제 1 장 총칙"},
            {"level": 2, "type": "section", "label": "제 1 절 일반사항"},
            {"level": 3, "type": "article", "label": "제 101조"},
            {"level": 4, "type": "paragraph", "label": "2항"},
        ],
        "content": {
            "text": "2. 이 규칙은 우리 선급의 최소요건이며, 특정 기국은 이 요건을 초과하는 규정을 가질 수 있다.",
            "language": "ko",
        },
    },
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {
            "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
            "organization": "KR",
            "version": "2024",
        },
        "location": {"physical_page": 7},
        "structure": [
            {"level": 1, "type": "chapter", "label": "제 1 장 총칙"},
            {"level": 2, "type": "section", "label": "제 1 절 일반사항"},
            {"level": 3, "type": "article", "label": "제 102조"},
        ],
        "content": {"text": "102. 구조물의 형식 구조물의 형식은 다음과 같이 분류한다.", "language": "ko"},
    },
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {
            "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
            "organization": "KR",
            "version": "2024",
        },
        "location": {"physical_page": 8},
        "structure": [
            {"level": 1, "type": "chapter", "label": "제 1 장 총칙"},
            {"level": 2, "type": "section", "label": "제 1 절 일반사항"},
            {"level": 3, "type": "article", "label": "제 103조"},
        ],
        "content": {"text": "103. 적용제외 다음 사항에 대하여는 이 규칙을 적용하지 아니한다.", "language": "ko"},
    },
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {
            "file_name": "이동식 해양구조물 규칙_2024-7-92.pdf",
            "organization": "KR",
            "version": "2024",
        },
        "location": {"physical_page": 8},
        "structure": [
            {"level": 1, "type": "chapter", "label": "제 1 장 총칙"},
            {"level": 2, "type": "section", "label": "제 1 절 일반사항"},
            {"level": 3, "type": "article", "label": "제 105조"},
            {"level": 4, "type": "paragraph", "label": "1항"},
        ],
        "content": {
            "text": "1. 만재흘수선 표시를 하는 모든 구조물은 1966년의 만재흘수선에 관한 국제협약의 관련규정에 적합하여야 한다.",
            "language": "ko",
        },
    },
    # structure 없음 — citation은 "p.7"만
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "source": {"file_name": "이동식 해양구조물 규칙_2024-7-92.pdf"},
        "location": {"physical_page": 9},
        "content": {"text": "본문 중 분류 불가 블록 예시", "language": "ko"},
    },
    # 최소 필드만
    {
        "doc_id": "MOUS_RULE_2024",
        "doc_type": "regulation",
        "content": {"text": "필수 필드만 있는 레코드", "language": "ko"},
    },
]


def main() -> None:
    print("=" * 60)
    print("Phase 1 수동 검증: Canonical Schema, Validator, Citation Formatter")
    print("=" * 60)

    # 1. from_dict → to_dict 왕복 직렬화
    print("\n[1] from_dict / to_dict 왕복 직렬화")
    records: list[CanonicalRecord] = []
    for i, d in enumerate(MANUAL_CANONICAL_RECORDS):
        try:
            rec = CanonicalRecord.from_dict(d)
            back = rec.to_dict()
            # 필수 필드만 비교 (순서 무관)
            assert back.get("doc_id") == d.get("doc_id")
            assert back.get("doc_type") == d.get("doc_type")
            assert back.get("content", {}).get("text") == d.get("content", {}).get("text")
            records.append(rec)
            print(f"  [OK] 레코드 {i + 1}: 직렬화 OK")
        except Exception as e:
            print(f"  [FAIL] 레코드 {i + 1}: {e}")
            raise

    # 2. canonical_validator 검증
    print("\n[2] canonical_validator.validate(records)")
    errors = canonical_validate(records)
    if errors:
        for idx, msg in errors:
            print(f"  [FAIL] 레코드 {idx + 1}: {msg}")
        raise SystemExit(1)
    print("  [OK] 모든 레코드 검증 통과")

    # 3. citation_formatter 출력
    print("\n[3] citation_formatter.format_citation(record)")
    for i, rec in enumerate(records):
        cite = format_citation(rec)
        print(f"  [{i + 1}] {repr(cite)}")

    # 기대 출력 샘플 확인
    expected_sample = "p.7, 제 1 장 총칙 > 제 1 절 일반사항 > 제 101조 > 1항"
    sample_cite = format_citation(records[3])  # 4번째 레코드 (101조 1항)
    assert expected_sample == sample_cite, f"Expected {expected_sample!r}, got {sample_cite!r}"
    print(f"\n  [OK] 기대 형식 확인: {sample_cite}")

    # structure 없을 경우 "p.9"만
    no_struct_cite = format_citation(records[8])
    assert no_struct_cite == "p.9", f"Expected 'p.9', got {no_struct_cite!r}"
    print(f"  [OK] structure 없음: {no_struct_cite}")

    # location 없을 경우 ""
    no_loc_cite = format_citation(records[9])
    assert no_loc_cite == "", f"Expected '', got {no_loc_cite!r}"
    print(f"  [OK] location 없음: {no_loc_cite}")

    print("\n" + "=" * 60)
    print("Phase 1 수동 검증 완료 - 모든 항목 통과")
    print("=" * 60)


if __name__ == "__main__":
    main()
