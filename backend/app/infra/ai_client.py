"""외부 AI 연동 (infra 계층) — Anthropic Claude API.

AIClient 는 비즈니스 계층이 의존하는 내부 인터페이스(Target),
ExternalLLMAdapter 는 Claude API(공식 Python SDK)를 이 인터페이스에 맞추는 Adapter 이다.
키가 없거나 호출이 실패하면(5초 타임아웃, 요청 한도, 거절, 형식 오류 등) AIClientError 를 발생시키고,
호출 측(SentimentFilter, ResponseStrategy)은 규칙 기반/템플릿으로 대체(fallback)한다 (NFR-03).
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

import anthropic

from app.infra.config import get_settings

log = logging.getLogger(__name__)

# 정책상 거절(refusal)되면 서버가 같은 요청을 대체 모델로 다시 실행하는 기능 (베타).
# 이 기능을 지원하는 모델에서만 켠다. 그래도 거절되면 AIClientError → 규칙 기반 대체.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-fable-5-2"}
MAX_TOKENS = 4096  # 사고(thinking) 토큰도 포함되므로 넉넉히. 짧은 분류·초안이라 실제 사용량은 훨씬 적다


class AIClientError(Exception):
    """AI 호출 실패(키 없음, 타임아웃, 응답 오류 등)."""


class AIClient(ABC):
    """Adapter 패턴의 Target 인터페이스."""

    @abstractmethod
    def complete(self, prompt: str, system: str | None = None) -> str:
        """텍스트 응답을 돌려준다."""

    def complete_json(self, prompt: str, schema: dict[str, Any], system: str | None = None) -> dict[str, Any]:
        """JSON 객체 응답. 기본 구현은 complete() 결과를 파싱한다 (구조화 출력을 지원하는 Adapter 는 재정의)."""
        return _parse_json(self.complete(prompt, system))


def _parse_json(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise AIClientError(f"JSON 형식 오류: {raw!r}") from e
    if not isinstance(data, dict):
        raise AIClientError(f"JSON 객체가 아님: {raw!r}")
    return data


class ExternalLLMAdapter(AIClient):
    """Adapter 패턴의 Adapter: Claude Messages API → AIClient.complete()/complete_json()."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        effort: str | None = None,
        timeout: float | None = None,
        client: anthropic.Anthropic | None = None,
    ):
        s = get_settings()
        self.api_key = api_key if api_key is not None else s.ai_api_key
        self.model = model or s.ai_model
        self.effort = effort or s.ai_effort
        self.timeout = timeout if timeout is not None else s.ai_timeout
        self._client = client
        if self._client is None and self.api_key:
            # 재시도 0회: 5초 안에 답이 없으면 바로 대체 경로로 간다 (재시도하면 대기 시간이 몇 배로 늘어난다)
            self._client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout, max_retries=0)

    def complete(self, prompt: str, system: str | None = None) -> str:
        return self._request(prompt, system, schema=None)

    def complete_json(self, prompt: str, schema: dict[str, Any], system: str | None = None) -> dict[str, Any]:
        # 구조화 출력(output_config.format): 응답이 스키마에 맞는 JSON 으로 나오도록 API 가 보장한다
        return _parse_json(self._request(prompt, system, schema=schema))

    def _request(self, prompt: str, system: str | None, schema: dict[str, Any] | None) -> str:
        if self._client is None:
            raise AIClientError("FEEDBACKCARE_AI_API_KEY 가 설정되지 않았습니다")
        output_config: dict[str, Any] = {"effort": self.effort}
        if schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "output_config": output_config,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        if self.model in FALLBACK_MODELS:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        try:
            resp = self._client.beta.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise AIClientError("API 키가 올바르지 않습니다") from e
        except anthropic.RateLimitError as e:
            raise AIClientError("요청 한도를 초과했습니다") from e
        except anthropic.APIStatusError as e:
            raise AIClientError(f"API 오류 {e.status_code}: {e.message}") from e
        except anthropic.APITimeoutError as e:
            raise AIClientError(f"응답 시간 초과({self.timeout:g}초)") from e
        except anthropic.APIConnectionError as e:
            raise AIClientError("AI 서버에 연결할 수 없습니다") from e

        if resp.stop_reason == "refusal":
            raise AIClientError("AI 가 요청을 거절했습니다")
        if resp.stop_reason == "max_tokens":
            raise AIClientError("AI 응답이 잘렸습니다(max_tokens)")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise AIClientError("AI 응답이 비어 있습니다")
        log.info("AI 응답 (model=%s, 입력 %d·출력 %d 토큰)", resp.model, resp.usage.input_tokens,
                 resp.usage.output_tokens)
        return text
