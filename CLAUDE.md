# CLAUDE.md — FeedbackCare

중소기업용 고객 피드백 감정 분석 및 대응 지원 시스템 (팀 TeamMinJunhyung, 저장소 `team_Minjunhyung`).
근거 문서: 요구사항 정의서 v1.1 (FR-01~05 필수, EX-01~08 선택, NFR-01~03), 시스템 설계서 v1.1. 모든 문서는 `docs/` 아래 분류 폴더에 있고 색인은 `docs/README.md`.
팀 코딩 규칙 전문은 `docs/coding-rules.md` — 이 파일은 그 요약이며, 다르면 coding-rules.md가 우선이다.

## 실행·검사 명령

| 목적 | 위치 | 명령 |
|---|---|---|
| 백엔드 실행 (:8000, API 문서 /docs) | `backend` | `.venv\Scripts\python -m uvicorn app.main:app --port 8000` |
| 프론트 실행 (:5173, /api → :8000 프록시) | `frontend` | `npm run dev` |
| 테스트 | `backend` | `.venv\Scripts\python -m pytest` |
| Python 스타일 (PEP 8, ruff) | `backend` | `.venv\Scripts\python -m ruff check app tests` |
| 프론트 스타일 (ESLint) | `frontend` | `npm run lint` |
| 프론트 빌드 | `frontend` | `npm run build` |

작업을 끝내기 전에 위 검사 4개(테스트, ruff, lint, build)를 모두 통과시킨다.
DB는 `backend/feedbackcare.db`(SQLite, 커밋 금지). 테이블 구조를 바꿨으면 이 파일을 지우고 재시작하면 시드(계정·등급 가중치·주제)와 함께 다시 만들어진다.

## 아키텍처 규칙

- 3계층: `backend/app/presentation`(routers·schemas) → `business/services` → `business/{pipeline, analyzers, priority, response, state}` → `persistence`(models·repositories). `infra`는 AI 클라이언트·설정·보안.
- 라우터는 서비스만 호출한다(DB 직접 조회 금지). `persistence`는 `business`를 import하지 않는다.
- 분석은 파이프-필터: `ValidationFilter → CleansingFilter → SentimentFilter → TopicFilter → PriorityFilter` (`business/pipeline/filters.py`). 필터는 `process(ctx)` 하나만 구현한다.
- 외부 AI는 `infra/ai_client.py`의 `AIClient`로만 호출하고 타임아웃 5초. 실패하면 규칙 기반 분석(`analyzer=RULE`)·템플릿 답변(`is_ai_generated=False`)으로 대체한다 (NFR-03).
- 업로드는 저장까지만 동기로 처리하고 분석은 `BackgroundTasks`로 넘긴다 (업로드 응답 1초, NFR-02).

## 패턴별 코드 위치

| 패턴 | 위치 | 내용 |
|---|---|---|
| Pipe-Filter | `business/pipeline/` | `Filter`, `Pipeline`, `FeedbackContext`, 필터 5개 |
| Strategy | `business/analyzers/` | 감정 분석기 `LLMSentimentAnalyzer` ↔ `RuleBasedSentimentAnalyzer` |
| Strategy | `business/priority/calculator.py` | `PriorityRule` (`WeightedProductRule` 기본, `WeightedSumRule` 대안) |
| Strategy | `business/response/strategies.py` | 답변 톤 `Apology/Guidance/ThanksStrategy`, `StrategySelector` |
| Decorator | `business/priority/decorators.py` | `UrgentTagDecorator`(긴급), `VipTagDecorator`(VIP) |
| State | `business/state/feedback_state.py` | `PendingState → InProgressState → DoneState`, 완료 후 재오픈 |
| Adapter | `infra/ai_client.py` | `AIClient`, `ExternalLLMAdapter` (현재 스텁) |

새 분석기·규칙·톤·태그·상태는 기존 클래스를 고치지 않고 클래스를 추가한다.

## 업무 규칙 (바꾸려면 요구사항 정의서부터 수정)

- **우선순위 (FR-03, AI로 계산 금지):** P = (부정 강도 × 10) × 등급 가중치(VIP 1.5 / REGULAR 1.0 / NEW 0.8 / 미확인 1.0) × (1 + min(경과 시간, 72h) / 72). P ≥ 15 이면 '긴급'. 계산 인자는 `priority_scores`에 저장해 화면에 근거로 표시한다.
- **상태 (FR-05):** PENDING -start→ IN_PROGRESS -complete→ DONE -reopen→ IN_PROGRESS. 그 외 전이는 `InvalidTransitionError`(409). 완료는 확정된 답변 초안이 있어야 가능 (Human-in-the-Loop, FR-04). 모든 전이는 `status_histories`에 기록.
- **AI 결과 표시 (운영계획서 13절):** AI가 만든 감정 분석·답변 초안은 화면에서 `SourceBadge`로 "AI 생성 / 규칙·템플릿 대체"를 표시하고, 담당자가 고친 초안은 "담당자 수정"으로 구분한다.
- 데이터는 가상 피드백만 사용한다 (`data/sample_feedback.csv`). 실제 개인정보 금지.

## 코딩 규칙 요약

- Python: PEP 8 (줄 길이 120, 팀 합의), snake_case / PascalCase / UPPER_SNAKE, 예외는 `...Error`, 공개 함수 타입 힌트 필수, `print` 대신 `logging`.
- 프론트: ESLint recommended + react, 작은따옴표·세미콜론 없음·2칸, `===`만, API 호출은 `src/api/client.js`로만.
- 주석·docstring은 한국어로 "왜"를 쓰고, 패턴 역할 클래스는 docstring에 역할을 적는다.
- 이름은 앱 FeedbackCare, 팀 TeamMinJunhyung, 저장소 `team_Minjunhyung`, 환경변수 `FEEDBACKCARE_*`만 쓴다. 이전 프로젝트명은 코드·파일·화면·문서 어디에도 쓰지 않는다.
- 비밀 정보는 `.env`(커밋 금지)로만.

## Git

- 브랜치 `feature/<요구사항ID>-<설명>` → Pull Request → 상대방 리뷰 → `main`. `main` 직접 push·`--force` 금지.
- 커밋 메시지: `[FR-03] 무엇을 했는지`.

## AI 사용 규칙

- AI가 만든 코드는 사람이 읽고 수정·검증한 뒤 커밋한다.
- 주요 프롬프트·응답 요지·채택/수정/폐기 이유·검증 결과를 주차별 AI 활용 로그에 기록한다.
- 설계나 규칙이 바뀌면 같은 PR에서 이 파일과 `docs/coding-rules.md`, 시스템 설계서를 함께 갱신한다.

## 설계서 v1.1과 코드 이름 대응 (13주차에 정리 예정)

| 설계서 v1.1 | 현재 코드 |
|---|---|
| `api/`, `service/`, `repository/`, `external/` | `presentation/`, `business/services/`, `persistence/`, `infra/` |
| `ResponseState` | `FeedbackState` |
| `Response` (테이블 RESPONSE) | `ResponseDraft` (`response_drafts`) |
| `GuideStrategy`, `DefaultPriorityRule` | `GuidanceStrategy`, `WeightedProductRule` |
| `TaggedResult`, `BaseResult` | `PriorityItem`, `BasePriorityItem` |
| `CollectFilter`, `CleanFilter` | `ValidationFilter`, `CleansingFilter` |
| 완료 상태에서 종료 | 완료 → 재오픈 허용 |
