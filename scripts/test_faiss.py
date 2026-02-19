"""FAISS 인덱스 생성/로드/검색 테스트 — CPU/GPU 동작 확인."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    import faiss
    import numpy as np

    print("=== FAISS 테스트 ===")

    # GPU 사용 가능 여부
    try:
        n_gpus = faiss.get_num_gpus() if hasattr(faiss, "get_num_gpus") else 0
        print(f"FAISS GPU 개수: {n_gpus}")
    except Exception as e:
        print(f"GPU 확인 실패: {e}")
        n_gpus = 0

    # 소규모 인덱스 생성
    d = 1024  # bge-m3 차원
    n = 10
    np.random.seed(42)
    embeddings = np.random.randn(n, d).astype(np.float32)
    # L2 정규화 (IndexFlatIP 내적 = cosine)
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(d)
    index.add(embeddings)
    print(f"인덱스 생성: {n} vectors, dim={d}")

    # GPU 전환 시도
    from src.core.faiss_index import _index_to_gpu_if_available

    index_gpu = _index_to_gpu_if_available(index)
    on_gpu = index_gpu != index
    print(f"검색에 GPU 사용: {on_gpu}")

    # 검색 테스트
    query = np.random.randn(1, d).astype(np.float32)
    faiss.normalize_L2(query)
    scores, indices = index_gpu.search(query, 3)
    print(f"검색 결과 (top-3): indices={indices[0].tolist()}, scores={scores[0].tolist()}")

    # load_index 통합 테스트 (임시 파일 사용)
    import tempfile
    from src.core.faiss_index import create_index, save_index, load_index, search
    from src.core.embedding_bge import encode_query

    output_dir = Path(tempfile.mkdtemp())
    meta_list = [{"chunk_id": f"c{i}", "text": f"chunk {i}"} for i in range(n)]
    idx_path, meta_path = save_index(index, meta_list, output_dir, stem="test")
    print(f"저장: {idx_path}")

    loaded_index, loaded_meta = load_index(idx_path, meta_path)
    print(f"로드 완료, 검색 GPU 사용: {on_gpu}")

    # 실제 임베딩으로 검색 (모델 필요)
    try:
        q_emb = encode_query("테스트 쿼리")
        results = search(loaded_index, q_emb, loaded_meta, top_k=3)
        print(f"encode_query + search 결과: {len(results)}건")
    except FileNotFoundError as e:
        print(f"bge-m3 미다운로드로 encode 건너뜀: {e}")
    except Exception as e:
        print(f"encode/search 오류: {e}")

    print("=== 테스트 완료 ===")


if __name__ == "__main__":
    main()
