"""물리 7페이지 파이프라인 디버그 — 제 1 장 총칙, 제 1 절 일반사항 추적.

V3: extract_pdf_raw + rule_marine_regulation 사용.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.extract_pdf_raw import extract_raw
from src.core.rule_marine_regulation import map_to_canonical


def _find(blocks_or_records, keywords, label, is_canonical: bool = False):
    hits = []
    for i, item in enumerate(blocks_or_records):
        if is_canonical:
            t = item.content.text if hasattr(item, "content") else ""
            page = item.location.physical_page if item.location else 0
        else:
            t = item.get("text", "")
            page = item.get("page", 0)
        for k in keywords:
            if k in t:
                hits.append((i, page, t[:70]))
                break
    print(f"  [{label}] {len(hits)} items")
    for i, p, t in hits[:10]:
        print(f"    [{i}] p{p}: {t}")
    return hits


def main():
    data_dir = ROOT / "data"
    pdf_candidates = list(data_dir.glob("*.pdf")) if data_dir.exists() else []
    pdf_path = pdf_candidates[0] if pdf_candidates else ROOT / "이동식 해양구조물 규칙_2024.pdf"
    if not pdf_path.exists():
        print("PDF 없음")
        return

    kw = ["제 1 장", "총칙", "제 1 절", "일반사항", "101."]

    # Raw (after_toc=False)
    raw_no_toc = extract_raw(
        pdf_path,
        doc_id="MOUS_RULE_2024",
        after_toc=False,
        exclude_header_footer=True,
    )
    print("\n--- Raw (after_toc=False) ---")
    _find(raw_no_toc, kw, "raw_no_toc")

    # Raw (after_toc=True)
    raw = extract_raw(
        pdf_path,
        doc_id="MOUS_RULE_2024",
        after_toc=True,
        exclude_header_footer=True,
    )
    print("\n--- Raw (after_toc=True) ---")
    _find(raw, kw, "raw")
    if raw:
        print("  First 5 blocks:")
        for i, blk in enumerate(raw[:5]):
            print(f"    [{i}] p{blk.get('page')} {str(blk.get('text',''))[:60]}")

    # Canonical
    canonical = map_to_canonical(raw, {"file_name": pdf_path.name})
    print("\n--- Canonical ---")
    _find(canonical, kw, "canonical", is_canonical=True)

    page7 = [r for r in canonical if r.location and r.location.physical_page == 7]
    print(f"\n--- Page 7 canonical: {len(page7)} records ---")
    for i, rec in enumerate(page7[:15]):
        t = (rec.content.text or "")[:50]
        struct = " > ".join(s.label for s in rec.structure[:2]) if rec.structure else ""
        print(f"  [{i}] {struct} | {t}")


if __name__ == "__main__":
    main()
