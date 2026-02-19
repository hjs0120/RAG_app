"""bge-m3 모델을 HuggingFace Hub에서 models/bge-m3/ 로 미리 다운로드."""

from __future__ import annotations

import sys
from pathlib import Path

# 프로젝트 루트 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPO_ID = "BAAI/bge-m3"
LOCAL_DIR = PROJECT_ROOT / "models" / "bge-m3"


def main() -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub가 필요합니다: pip install huggingface_hub")
        sys.exit(1)

    print(f"다운로드: {REPO_ID} → {LOCAL_DIR}")
    snapshot_download(
        repo_id=REPO_ID,
        local_dir=str(LOCAL_DIR),
        local_dir_use_symlinks=False,
    )
    print(f"완료: {LOCAL_DIR}")


if __name__ == "__main__":
    main()
