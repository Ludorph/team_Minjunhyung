# 팀 코딩 규칙 — FeedbackCare (TeamMinJunhyung)

- 버전: v1.0 (2026-11-10, 12주차)
- 근거: 운영계획서 7절 "팀 코딩 규칙을 문서화하고 AI 지시 문서에 반영. 자바 이외 언어는 해당 언어의 표준 스타일 가이드 적용", ch08 구현(코드 작성 규칙)
- 적용: 이 저장소의 모든 코드. 규칙의 요약은 루트 `CLAUDE.md`에 반영되어 있으며, 둘이 다르면 이 문서를 기준으로 고친다.

## 1. 공통

| 항목 | 규칙 |
|---|---|
| 인코딩 / 줄바꿈 | UTF-8, LF (`.gitattributes`로 강제 — Windows에서도 LF로 커밋) |
| 들여쓰기 | Python 공백 4칸, JavaScript·JSX 공백 2칸, 탭 금지 |
| 주석 | 한국어. 코드가 "무엇"을 하는지가 아니라 "왜" 그렇게 했는지를 쓴다. 근거가 요구사항이면 ID를 붙인다 (예: `# UC-03 E1: 등급 누락 시 기본값 1.0`) |
| 패턴 표시 | 디자인 패턴의 역할을 맡은 클래스는 docstring 첫 줄에 역할을 적는다 (예: `"""State 패턴의 ConcreteState: 처리중."""`) |
| 비밀 정보 | API 키·비밀번호는 코드와 저장소에 넣지 않는다. `.env`(커밋 금지) 또는 환경변수 `FEEDBACKCARE_*`로만 주입 |
| 프로젝트 이름 | 앱 FeedbackCare, 팀 TeamMinJunhyung, 저장소 `team_Minjunhyung`만 쓴다. 이전 프로젝트명은 코드·파일·화면·문서에 쓰지 않는다 |

## 2. Python (백엔드) — PEP 8

| 항목 | 규칙 | 예 |
|---|---|---|
| 모듈·함수·변수 | `snake_case` | `feedback_service.py`, `elapsed_hours()` |
| 클래스 | `PascalCase` | `PriorityCalculator`, `InProgressState` |
| 상수 | `UPPER_SNAKE_CASE` | `URGENT_THRESHOLD = 15.0` |
| 예외 클래스 | 이름 끝에 `Error` | `InvalidTransitionError`, `PipelineAbortError` |
| 내부용 | 앞에 `_` | `_reject()`, `_SALT` |
| 줄 길이 | **120자** (PEP 8 권장 79자 대신 팀 합의 — 한글 docstring·주석 가독성 때문) | |
| import 순서 | 표준 라이브러리 → 외부 패키지 → `app` 내부, 그룹 사이 빈 줄 | ruff `I` 규칙이 자동 정렬 |
| 타입 힌트 | 공개 함수·메서드의 인자와 반환값에 필수 (ruff `ANN001`·`ANN201`로 검사). 예외: FastAPI 라우터는 `response_model`로 반환 형식을 명시하므로 반환 타입 생략 허용, 테스트 함수는 생략 허용 | `def calculate(self, neg: float, grade: str \| None, hours: float) -> PriorityScore:` |
| 출력 | `print` 금지, `logging` 사용 | `log.info("AI 초안 생성 실패 → 템플릿 사용: %s", e)` |
| 예외 처리 | `except Exception`은 외부 AI 호출 경계(분석기·답변 전략)에서만 허용하고 반드시 로그를 남긴다. 업무 규칙 위반은 전용 예외로 던진다 | |

### 계층 규칙 (3계층 + 분석부 파이프-필터)

```
presentation (routers, schemas, deps)
   ↓ 서비스만 호출
business/services
   ↓
business/pipeline · analyzers · priority · response · state
   ↓
persistence (models, repositories)        infra (ai_client, config, security)
```

- `presentation`은 DB를 직접 조회하지 않고 `services`만 호출한다.
- `persistence`는 `business`를 import하지 않는다 (상태 전이 규칙이 `state/`에 있는 이유).
- 외부 AI는 `infra/ai_client.py`의 `AIClient`를 통해서만 호출하고, 실패·타임아웃(5초) 시 규칙 기반 분석·템플릿 답변으로 대체한다 (NFR-03).
- 새 분석기·우선순위 규칙·답변 톤·태그·상태는 **기존 클래스를 고치지 않고 클래스를 추가**한다 (OCP).

## 3. JavaScript / React (프론트엔드) — ESLint recommended

| 항목 | 규칙 |
|---|---|
| 문자열 / 세미콜론 | 작은따옴표, 세미콜론 없음 |
| 비교 | `===`, `!==`만 사용 |
| 컴포넌트 파일 | `PascalCase.jsx`, 화면 하나당 `src/pages/` 파일 하나 (S01~S07) |
| 공용 컴포넌트 | `src/components/` (배지·태그·차트 등) |
| API 호출 | 화면에서 axios를 직접 쓰지 않고 `src/api/client.js`의 함수만 사용 |
| Hooks | `react-hooks` 규칙 준수 (`useEffect` 의존성 누락 금지) |
| AI 결과 표시 | AI가 만든 값(감정 분석, 답변 초안)은 반드시 `SourceBadge`로 "AI 생성 / 규칙·템플릿 대체"를 표시한다 (운영계획서 13절) |

## 4. API · DB 명명

| 대상 | 규칙 | 예 |
|---|---|---|
| REST 경로 | `/api/` + 복수형 명사, 동작은 HTTP 메서드로 | `POST /api/feedbacks/upload`, `PATCH /api/feedbacks/{id}/status` |
| JSON 필드 | `snake_case` | `analyzed_rows`, `is_ai_generated` |
| 테이블 / 컬럼 | `snake_case`, 테이블은 복수형 | `priority_scores.time_weight` |
| 코드값 | 영문 대문자 | `PENDING`, `IN_PROGRESS`, `DONE`, `VIP` |
| 스키마 변경 | `models.py`·`schemas.py` 변경 PR은 상대방 확인 후 병합하고, 병합 후 각자 로컬 `feedbackcare.db`를 지우고 재시작 | |

## 5. 테스트

- 새 기능·버그 수정은 **정상 케이스 1개 + 예외 케이스 1개 이상**의 테스트를 함께 추가한다 (운영계획서 7절).
- 파일 이름은 `backend/tests/test_<대상>.py`, 함수 이름은 `test_<행동>_<기대결과>` 형태를 권장한다.
- 외부 AI가 필요한 테스트는 실제 API 대신 가짜 `AIClient`(테스트 더블)를 주입한다.
- PR 전에 아래 4개 명령이 모두 통과해야 한다.

| 검사 | 명령 (위치) |
|---|---|
| 백엔드 테스트 | `.venv\Scripts\python -m pytest` (backend) |
| Python 스타일 | `.venv\Scripts\python -m ruff check app tests` (backend) |
| 프론트 스타일 | `npm run lint` (frontend) |
| 프론트 빌드 | `npm run build` (frontend) |

## 6. Git 규칙

| 항목 | 규칙 |
|---|---|
| 브랜치 | `main`은 항상 시연 가능한 상태. 작업은 `feature/<요구사항ID>-<짧은설명>`, 버그는 `fix/<ID>-<설명>` (예: `feature/FR-02-ai`) |
| 커밋 메시지 | `[요구사항ID] 무엇을 했는지` 한 줄 (예: `[FR-05] 대시보드 일별 추이 차트 추가`). 여러 요구사항이면 `[FR-02][FR-04]` |
| 병합 | Pull Request → 상대방 리뷰 1회 이상 → `main` 병합. `main`에 직접 push 금지, `--force` 금지 |
| 커밋 금지 | `.venv/`, `node_modules/`, `*.db`, `.env`, `dist/` (`.gitignore`로 차단) |

## 7. AI 사용 규칙 (운영계획서 13절)

- AI가 만든 코드·문서는 사람이 읽고 수정·검증한 뒤 커밋한다. 이해하지 못한 코드는 커밋하지 않는다.
- 주요 프롬프트, 응답 요지, 채택·수정·폐기 이유, 검증 방법과 결과를 주차별 AI 활용 로그에 기록한다.
- 설계(시스템 설계서)나 이 규칙이 바뀌면 같은 PR에서 `CLAUDE.md`도 함께 고친다.
