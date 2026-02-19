# 설치 가이드

## 설치 내역역

### 명령어
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

### 설치확인 명렁어
```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"

2.10.0+cu126
True
12.6
```

###  pip 사항항
```bash
torch                 2.10.0+cu126
torchaudio            2.10.0+cu126
torchvision           0.25.0+cu126
```

## 기본 의존성

```bash
pip install -r requirements.txt
```

## PyTorch CUDA (GPU 가속)

임베딩(bge-m3)을 GPU로 실행하려면 PyTorch CUDA 빌드를 별도 설치합니다.

### CUDA 12.x (권장)

```bash
pip install torch torchvision torchaudio
```

(최신 PyPI torch는 CUDA 12를 기본으로 제공하는 경우가 많음)

### CUDA 11.8

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### CPU 전용 (GPU 미사용)

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

## bge-m3 모델 다운로드

임베딩 탭 사용 전, 로컬에 모델을 미리 다운로드합니다:

```bash
python scripts/download_bge_m3.py
```

모델은 `models/bge-m3/`에 저장되며, 이후 오프라인에서도 사용 가능합니다.

## FAISS GPU (선택, 검색 속도 향상)

FAISS 검색을 GPU로 가속하려면 faiss-gpu를 사용합니다. **Windows에서는 pip 미지원**이므로 conda로 설치합니다:

```bash
conda install conda-forge::faiss-gpu
```

설치 시 기존 faiss-cpu가 faiss-gpu로 대체됩니다. CUDA 환경이 있어야 합니다.
