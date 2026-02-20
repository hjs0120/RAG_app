"""Ollama API 클라이언트 — generate, health_check, 에러 처리."""

from __future__ import annotations

import requests

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_NUM_CTX = 4096

OLLAMA_NOT_RUNNING_MSG = (
    "Ollama가 실행되지 않았습니다. "
    "Ollama를 설치하고 실행한 후 다시 시도하세요. (https://ollama.com)"
)


class OllamaClient:
    """Ollama HTTP API 클라이언트."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")

    def health_check(self) -> bool:
        """
        Ollama 서버 연결 확인.
        Returns:
            True: 정상, False: 연결 실패
        """
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except (requests.RequestException, ConnectionError):
            return False

    def list_models(self) -> list[str]:
        """
        Ollama에 설치된 모델 목록 조회.
        Returns:
            모델 이름 리스트 (예: ["qwen2.5:7b-instruct", "llama3:latest"])
        """
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            data = r.json()
            models = data.get("models") or []
            return [m.get("name", "") for m in models if m.get("name")]
        except (requests.RequestException, ConnectionError, KeyError, TypeError):
            return []

    def generate(
        self,
        prompt: str,
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        num_ctx: int = DEFAULT_NUM_CTX,
    ) -> str:
        """
        /api/generate로 텍스트 생성 (non-streaming).
        Returns:
            생성된 텍스트
        Raises:
            RuntimeError: Ollama 미실행 또는 API 오류
        """
        if not self.health_check():
            raise RuntimeError(OLLAMA_NOT_RUNNING_MSG)

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }

        try:
            r = requests.post(url, json=payload, timeout=300)
            r.raise_for_status()
            data = r.json()
            return data.get("response", "").strip()
        except requests.RequestException as e:
            raise RuntimeError(
                f"Ollama API 호출 실패: {e}\n{OLLAMA_NOT_RUNNING_MSG}"
            ) from e
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"Ollama 응답 파싱 실패: {e}") from e

    def generate_chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str = DEFAULT_MODEL,
        temperature: float = DEFAULT_TEMPERATURE,
        num_ctx: int = DEFAULT_NUM_CTX,
    ) -> str:
        """
        /api/chat로 텍스트 생성. instruct 모델(qwen2.5 등)에 적합.
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
        """
        if not self.health_check():
            raise RuntimeError(OLLAMA_NOT_RUNNING_MSG)

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
            },
        }

        try:
            r = requests.post(url, json=payload, timeout=300)
            r.raise_for_status()
            data = r.json()
            msg = data.get("message") or {}
            return (msg.get("content") or "").strip()
        except requests.RequestException as e:
            raise RuntimeError(
                f"Ollama API 호출 실패: {e}\n{OLLAMA_NOT_RUNNING_MSG}"
            ) from e
        except (KeyError, TypeError) as e:
            raise RuntimeError(f"Ollama 응답 파싱 실패: {e}") from e

    def load_model(self, model: str = DEFAULT_MODEL) -> None:
        """
        Ollama 서버에서 모델을 메모리에 미리 로드.
        최소한의 chat 요청을 보내 모델 로딩을 트리거합니다.
        """
        if not self.health_check():
            raise RuntimeError(OLLAMA_NOT_RUNNING_MSG)
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "."}],
            "stream": False,
            "options": {"num_predict": 1},
        }
        try:
            r = requests.post(url, json=payload, timeout=120)
            r.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(
                f"Ollama 모델 로드 실패: {e}\n{OLLAMA_NOT_RUNNING_MSG}"
            ) from e
