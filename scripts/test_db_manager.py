"""Phase 2 검증: db_manager load/append/remove 동작 테스트.

사용법:
  python scripts/test_db_manager.py

필수: output/rules.index, output/rules_meta.jsonl 존재 (임베딩 탭에서 먼저 생성)
또는: --output-dir 경로 지정
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db.db_manager import (
    load_index,
    save_index,
    append_chunks,
    remove_chunks,
    rebuild_index,
)
from src.core.faiss_index import search
from src.core.embedding_bge import encode_query


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 2 db_manager 검증")
    ap.add_argument("--output-dir", type=str, default=str(PROJECT_ROOT / "output"))
    args = ap.parse_args()

    output_dir = Path(args.output_dir)
    idx_path = output_dir / "rules.index"
    meta_path = output_dir / "rules_meta.jsonl"

    print("=== Phase 2 db_manager 검증 ===\n")

    # 1. load_index
    if idx_path.exists() and meta_path.exists():
        print("1. load_index() ...")
        index, meta_list = load_index(idx_path, meta_path)
        print(f"   OK: index.ntotal={index.ntotal}, meta 수={len(meta_list)}")
    else:
        print(f"1. load_index() - 스킵 (파일 없음: {idx_path})")
        print("   임베딩 탭에서 먼저 FAISS를 생성한 뒤 다시 실행하세요.")
        return 0

    # 2. 검색 테스트 (기준선)
    query = "검사 주기"
    q_emb = encode_query(query)
    results = search(index, q_emb, meta_list, top_k=3)
    print(f"\n2. 검색 테스트 (쿼리: '{query}'):")
    for rank, (idx, score, meta) in enumerate(results, 1):
        cid = meta.get("chunk_id", idx)
        print(f"   [{rank}] {cid} score={score:.4f}")

    # 3. append_chunks (테스트용 chunk 1개)
    test_chunk = {
        "doc_id": "test_doc",
        "article": "999",
        "section": "테스트",
        "paragraph": "0",
        "chunk_index": 1,
        "text": "이것은 Phase 2 db_manager append 테스트용 chunk입니다. 검사 주기는 매년 1회 실시합니다.",
        "meta": {"pages": [99]},
    }
    print("\n3. append_chunks() ...")
    append_chunks([test_chunk], idx_path, meta_path)
    print("   OK: 1개 chunk 추가 완료")

    # 4. 재로드 후 검색 (추가된 chunk 포함 여부)
    index2, meta_list2 = load_index(idx_path, meta_path)
    results2 = search(index2, q_emb, meta_list2, top_k=5)
    print(f"\n4. 추가 후 검색 (top-5):")
    found_test = False
    for rank, (idx, score, meta) in enumerate(results2, 1):
        cid = meta.get("chunk_id", idx)
        txt_preview = (meta.get("text") or meta.get("full_text") or "")[:60]
        print(f"   [{rank}] {cid} score={score:.4f} | {txt_preview}...")
        if "Phase 2" in (meta.get("full_text") or meta.get("text") or ""):
            found_test = True
    if found_test:
        print("   OK: 추가된 chunk가 검색 결과에 포함됨")
    else:
        print("   참고: 추가 chunk가 top-5에 없을 수 있음 (의미 유사도에 따라)")

    # 5. remove_chunks (방금 추가한 chunk 제거)
    test_chunk_id = "test_doc_999_테스트_0_1"
    print(f"\n5. remove_chunks(['{test_chunk_id}']) ...")
    remove_chunks([test_chunk_id], idx_path, meta_path)
    print("   OK: chunk 제거 및 인덱스 재구성 완료")

    # 6. 재로드 후 검색 (제거된 chunk가 없는지)
    index3, meta_list3 = load_index(idx_path, meta_path)
    remaining_ids = {m.get("chunk_id") for m in meta_list3}
    if test_chunk_id not in remaining_ids:
        print("   OK: 제거된 chunk가 meta에서 제외됨")
    else:
        print("   경고: 제거 대상 chunk_id가 여전히 meta에 존재")

    print("\n=== Phase 2 검증 완료 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
