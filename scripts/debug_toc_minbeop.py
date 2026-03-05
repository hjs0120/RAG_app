"""민법 PDF TOC/본문 시작 디버그 — 추출 과정 단계별 확인.

사용법:
  python scripts/debug_toc_minbeop.py "data/민법(법률)(제20432호)(20260101).pdf"
  python scripts/debug_toc_minbeop.py "D:/경로/민법.pdf"
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    if len(sys.argv) < 2:
        print("사용법: python scripts/debug_toc_minbeop.py <PDF경로>")
        print("예: python scripts/debug_toc_minbeop.py data/민법(법률)(제20432호)(20260101).pdf")
        return

    pdf_path = Path(sys.argv[1])
    if not pdf_path.is_file():
        print(f"파일 없음: {pdf_path}")
        return

    import fitz
    from src.core.extract_pdf_raw import extract_raw, _extract_lines_with_style
    from src.core.toc_detector import (
        detect_toc_start,
        apply_toc_filter,
        _is_body_start_candidate,
        _is_toc_entry_line,
    )

    print("=" * 70)
    print(f"PDF: {pdf_path.name}")
    print("=" * 70)

    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"총 페이지: {total_pages}")
    doc.close()

    # 1. TOC 필터 적용 전 raw 라인 추출 (rebuild 전 단계와 동일)
    lines = _extract_lines_with_style(
        pdf_path,
        exclude_header_footer=True,
        header_footer_margin_ratio=0.08,
    )
    print(f"\n[1] _extract_lines_with_style 결과: {len(lines)} 라인")

    # 2. 차례/본문 후보 위치 찾기
    toc_idx, body_idx = detect_toc_start(lines)
    print(f"\n[2] detect_toc_start:")
    print(f"    차례(차례) 라인 인덱스: {toc_idx}")
    print(f"    본문 시작 라인 인덱스: {body_idx}")

    if body_idx is not None and body_idx < len(lines):
        first_line = lines[body_idx]
        print(f"    본문 시작 첫 줄: p{first_line.get('page')} | {first_line.get('text', '')[:80]}")
    else:
        print("    본문 시작 없음 (body_idx=None)")

    # 3. 25~45페이지 구간 라인 상세 (본문 시작 인근)
    print("\n[3] 25~45페이지 구간 라인 (본문 시작 인근):")
    for i, ln in enumerate(lines):
        pg = ln.get("page", 0)
        if pg < 25 or pg > 45:
            continue
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        is_toc = _is_toc_entry_line(text)
        is_cand = _is_body_start_candidate(text)
        flags = []
        if is_cand:
            flags.append("본문후보")
        if is_toc:
            flags.append("목차항목")
        flag_str = " [" + ", ".join(flags) + "]" if flags else ""
        marker = " << 본문시작" if i == body_idx else ""
        print(f"  [{i:5d}] p{pg:3d} | {text[:70]}{'...' if len(text)>70 else ''}{flag_str}{marker}")

    # 4. 1~5페이지 라인 (목차 "차 례" 확인용)
    print("\n[4a] 1~5페이지 라인 (목차 확인):")
    for i, ln in enumerate(lines):
        pg = ln.get("page", 0)
        if pg < 1 or pg > 5:
            continue
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        has_cha = "차" in text and "례" in text
        print(f"  [{i:5d}] p{pg} | {text[:75]}{' ...' if len(text)>75 else ''}  {' <-차례' if has_cha else ''}")

    # 5. 차례 구간 라인 (toc_idx 주변)
    if toc_idx is not None:
        print("\n[5] 차례 구간 라인 (인덱스 toc_idx 주변):")
        start = max(0, toc_idx - 2)
        end = min(len(lines), toc_idx + 15)
        for i in range(start, end):
            ln = lines[i]
            text = (ln.get("text") or "").strip()
            if not text:
                continue
            pg = ln.get("page", 0)
            is_toc = _is_toc_entry_line(text)
            is_cand = _is_body_start_candidate(text)
            flags = []
            if is_cand:
                flags.append("본문후보")
            if is_toc:
                flags.append("목차항목")
            flag_str = " [" + ", ".join(flags) + "]" if flags else ""
            marker = " << 차례" if i == toc_idx else (" << 본문시작" if i == body_idx else "")
            print(f"  [{i:5d}] p{pg:3d} | {text[:70]}{'...' if len(text)>70 else ''}{flag_str}{marker}")

    # 6. extract_raw(after_toc=True) 결과의 첫 블록
    blocks = extract_raw(
        pdf_path,
        doc_id="debug",
        after_toc=True,
        exclude_header_footer=True,
    )
    print(f"\n[6] extract_raw(after_toc=True) 결과: {len(blocks)} 블록")
    if blocks:
        for i, blk in enumerate(blocks[:8]):
            print(f"    [{i}] p{blk.get('page')} | {(blk.get('text') or '')[:60]}")
        if len(blocks) > 8:
            print(f"    ... 외 {len(blocks)-8}개")

    # 7. extract_raw(after_toc=False) 시 31페이지 근처 블록
    blocks_full = extract_raw(
        pdf_path,
        doc_id="debug",
        after_toc=False,
        exclude_header_footer=True,
    )
    p31 = [b for b in blocks_full if b.get("page") in (30, 31, 32)]
    print(f"\n[7] extract_raw(after_toc=False) - 30~32페이지 블록: {len(p31)}개")
    for b in p31[:15]:
        print(f"    p{b.get('page')} | {(b.get('text') or '')[:65]}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
