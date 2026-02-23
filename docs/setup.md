# 설치 가이드

## 설치 순서 (요약)

1. `pip install -r requirements.txt`
2. PyTorch 설치 (환경에 맞게 cu118 또는 cu126 선택)
3. faiss-gpu 설치: `conda install -c conda-forge faiss-gpu`
4. **numpy<2 고정** (faiss-gpu가 NumPy 1.x로 빌드됨): `pip install "numpy<2"`
5. bge-m3 모델 다운로드

---

## 기본 의존성

```bash
pip install -r requirements.txt
```

(faiss는 conda로 별도 설치 — requirements.txt에 없음)

---

## PyTorch (GPU 가속)

임베딩(bge-m3)을 GPU로 실행하려면 PyTorch CUDA 빌드를 설치합니다. **CUDA 11.8 / 12.x 둘 다 지원**합니다. 환경에 맞게 선택하세요.

### CUDA 12.x

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

### CUDA 11.8

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### CPU 전용 (GPU 미사용)

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 설치 확인

```bash
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"
```

---

## FAISS GPU

FAISS 검색을 GPU로 가속합니다. 앱은 `load_index(use_gpu=True)` 시 자동으로 GPU로 인덱스를 이전합니다.

**conda-forge로만 설치**합니다. pip의 faiss-cpu는 사용하지 않습니다.

```bash
conda install -c conda-forge faiss-gpu
```

### 중요: NumPy 버전

faiss-gpu(conda-forge)는 **NumPy 1.x**로 빌드되어 있습니다. PyTorch 설치 시 numpy가 2.0 이상으로 올라가면 faiss import 시 오류가 납니다.

```text
A module that was compiled using NumPy 1.x cannot be run in NumPy 2.x...
AttributeError: _ARRAY_API not found
```

**해결:** faiss-gpu 설치 후 numpy를 1.x로 고정합니다.

```bash
pip install "numpy<2"
```

### 권장 설치 순서

```bash
pip install -r requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126   # 또는 cu118
conda install -c conda-forge faiss-gpu
pip install "numpy<2"
python scripts/download_bge_m3.py
```

### 확인

```bash
python -c "import faiss; print(faiss.get_num_gpus())"
```

### faiss-cpu (폴백)

GPU가 필요 없으면:

```bash
pip install faiss-cpu
```

(faiss-cpu는 NumPy 2.x와 호환됨)

---

## bge-m3 모델 다운로드

임베딩 탭 사용 전에 모델을 다운로드합니다:

```bash
python scripts/download_bge_m3.py
```

모델은 `models/bge-m3/`에 저장되며, 이후 오프라인에서도 사용 가능합니다.
