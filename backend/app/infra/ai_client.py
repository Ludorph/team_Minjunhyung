"""외부 AI 연동 (infra 계층).

AIClient 는 비즈니스 계층이 의존하는 내부 인터페이스(Target),
ExternalLLMAdapter 는 외부 LLM API 를 이 인터페이스에 맞추는 Adapter 이다.
현재는 스텁: API 키(FEEDBACKCARE_AI_API_KEY)가 없으면 AIClientError 를 발생시키며,
호출 측(SentimentFilter, ResponseStrategy)은 규칙 기반/템플릿으로 대체(fallback)한다.
"""
from abc import ABC, abstractmethod

import httpx

from app.infra.config import get_settings


class AIClientError(Exception):
    """AI 호출 실패(키 없음, 타임아웃, 응답 오류 등)."""


class AIClient(ABC):
    """Adapter 패턴의 Target 인터페이스."""

    @abstractmethod
    def complete(self, prompt: str) -> str: ...


class ExternalLLMAdapter(AIClient):
    """Adapter 패턴의 Adapter: 외부 LLM HTTP API → AIClient.complete()."""

    def __init__(self, api_key: str | None = None, endpoint: str | None = None, timeout: float | None = None):
        s = get_settings()
        self.api_key = api_key if api_key is not None else s.ai_api_key
        self.endpoint = endpoint if endpoint is not None else s.ai_endpoint
        self.timeout = timeout if timeout is not None else s.ai_timeout

    def complete(self, prompt: str) -> str:
        if not self.api_key:
            raise AIClientError("FEEDBACKCARE_AI_API_KEY 가 설정되지 않았습니다 (스텁 모드)")
        if not self.endpoint:
            raise AIClientError("FEEDBACKCARE_AI_ENDPOINT 가 설정되지 않았습니다 (스텁 모드)")
        try:
            # 외부 API 형식({"prompt"} → {"text"})은 가정이며 실제 연동 시 이 부분만 바꾸면 된다.
            r = httpx.post(
                self.endpoint,
                json={"prompt": prompt},
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json()["text"]
        except Exception as e:  # noqa: BLE001 - 모든 외부 오류를 AIClientError 로 변환
            raise AIClientError(str(e)) from e
