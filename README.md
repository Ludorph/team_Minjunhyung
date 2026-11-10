# FeedbackCare — 중소기업용 고객 피드백 감정 분석 및 대응 지원 시스템

설계 과제(PBL2)용 **실행 가능한 프로젝트 골격**입니다. 폴더·클래스·테이블 구조는
`PBL2_설계/diagrams` 의 PlantUML 설계(03 도메인, 04 서비스·패턴, 06 패키지, 09 ERD, 10 화면 흐름)를 그대로 따릅니다.
핵심 비즈니스 로직(우선순위 공식, 상태 전이, CSV 검증, 분석 파이프라인)은 실제로 동작하며,
외부 AI 연동은 스텁(Adapter)으로 두고 규칙 기반 분석기/템플릿으로 대체(fallback)합니다.

- Backend: FastAPI + SQLAlchemy 2 + SQLite
- Frontend: React (Vite, JS/JSX), axios, 순수 CSS

## 1. 폴더 구조

```
team_Minjunhyung/
├─ data/sample_feedback.csv          # 가상 피드백 20건 (CSV 업로드 테스트용)
├─ backend/
│  ├─ requirements.txt, pytest.ini
│  ├─ app/
│  │  ├─ main.py                     # FastAPI 진입점 (테이블 생성·시드)
│  │  ├─ presentation/               # 표현 계층
│  │  │  ├─ routers/ auth.py, feedbacks.py, drafts.py, dashboard.py
│  │  │  ├─ schemas.py               # pydantic DTO
│  │  │  └─ deps.py                  # DB 세션·현재 사용자 의존성
│  │  ├─ business/                   # 비즈니스 계층
│  │  │  ├─ services/                # feedback/analysis/response/dashboard(+auth) 서비스
│  │  │  ├─ pipeline/                # base.py(Filter, Pipeline, FeedbackContext), filters.py
│  │  │  ├─ analyzers/               # 감정 분석기(LLM/규칙), 주제 분류기
│  │  │  ├─ priority/                # calculator.py, decorators.py
│  │  │  ├─ response/                # strategies.py (답변 전략)
│  │  │  └─ state/                   # feedback_state.py
│  │  ├─ persistence/                # 영속 계층: database.py, models.py, repositories.py, seed.py
│  │  └─ infra/                      # config.py, ai_client.py, security.py
│  └─ tests/                         # pytest
└─ frontend/
   ├─ package.json, vite.config.js (/api → :8000 프록시), index.html
   └─ src/
      ├─ main.jsx, App.jsx (해시 라우팅), router.js, styles.css
      ├─ api/client.js               # axios REST 클라이언트
      ├─ components/                 # Nav, Badges(배지·태그·막대 차트)
      └─ pages/                      # Login, Dashboard, FeedbackList, FeedbackDetail, FeedbackNew, Upload, Accuracy
```

## 2. 3계층 ↔ 폴더 매핑 (06_development_package.puml)

| 계층 | 패키지(설계) | 폴더 | 역할 |
|---|---|---|---|
| 표현 (Presentation) | `presentation (routers, schemas)` | `backend/app/presentation/` + `frontend/` | REST API, 요청/응답 DTO, React SPA |
| 비즈니스 (Business) | `business` → services, pipeline, analyzers, priority, response, state | `backend/app/business/*` | 유스케이스 처리, 분석·우선순위·답변·상태 규칙 |
| 영속 (Persistence) | `persistence (models, repositories)` | `backend/app/persistence/` | ORM 모델(ERD), Repository, 시드 |
| 인프라 (Infra) | `infra (ai_client, config)` | `backend/app/infra/` | 설정, 외부 AI Adapter, 비밀번호 해시 |

의존 방향: presentation → services → (pipeline, response, state, persistence), analyzers/response → infra.

## 3. 디자인 패턴 ↔ 파일 매핑 (04_class_service_patterns.puml)

| 패턴 | 역할 | 클래스 | 파일 |
|---|---|---|---|
| Pipe-Filter | Pipe/데이터 | `FeedbackContext` | `business/pipeline/base.py` |
| | Filter 인터페이스 / 실행기 | `Filter`, `Pipeline` | `business/pipeline/base.py` |
| | ConcreteFilter | `ValidationFilter`, `CleansingFilter`, `SentimentFilter`, `TopicFilter`, `PriorityFilter` | `business/pipeline/filters.py` |
| | 조립·실행 | `AnalysisService` | `business/services/analysis_service.py` |
| Strategy (감정 분석) | Strategy | `SentimentAnalyzer` | `business/analyzers/base.py` |
| | ConcreteStrategy | `LLMSentimentAnalyzer`, `RuleBasedSentimentAnalyzer` | `business/analyzers/llm_analyzer.py`, `rule_based_analyzer.py` |
| Adapter | Target / Adapter | `AIClient`, `ExternalLLMAdapter` | `infra/ai_client.py` |
| Decorator | Component / ConcreteComponent | `PriorityItem`, `BasePriorityItem` | `business/priority/decorators.py` |
| | Decorator / ConcreteDecorator | `TagDecorator`, `UrgentTagDecorator`("긴급"), `VipTagDecorator`("VIP") | `business/priority/decorators.py` |
| Strategy (답변) | Strategy / ConcreteStrategy | `ResponseStrategy`, `ApologyStrategy`, `GuidanceStrategy`, `ThanksStrategy` | `business/response/strategies.py` |
| | 선택기 / 사용처 | `StrategySelector`, `ResponseService` | `business/response/strategies.py`, `business/services/response_service.py` |
| State | State / ConcreteState | `FeedbackState`, `PendingState`, `InProgressState`, `DoneState` | `business/state/feedback_state.py` |
| | Context | `Feedback` (status 컬럼) | `persistence/models.py` |

## 4. 핵심 비즈니스 규칙

- **우선순위** `P = (negIntensity × 10) × gradeWeight × timeWeight` (`business/priority/calculator.py`)
  - negIntensity: 감정이 NEGATIVE일 때 강도(0~1), 아니면 0
  - gradeWeight: `grade_weights` 테이블 (VIP 1.5, REGULAR 1.0, NEW 0.8, 미지정·알 수 없음 1.0)
  - timeWeight: `1 + min(경과시간, 72)/72` (1.0~2.0) → 최대 P = 30
  - P ≥ 15 → `UrgentTagDecorator`("긴급"), VIP 고객 → `VipTagDecorator`("VIP")
  - 예) 강도 0.9, VIP, 24시간 → 9 × 1.5 × 1.333 = **18.0 → 긴급**
- **상태 전이**: 미처리(PENDING) –start→ 처리중(IN_PROGRESS) –complete→ 완료(DONE) –reopen→ 처리중.
  그 외 전이는 `InvalidTransitionError`(API 409). complete 는 확정된 답변 초안이 있어야 하며, 모든 전이는 `status_histories` 에 기록됩니다.
- **CSV 업로드** (`POST /api/feedbacks/upload`): 확장자·인코딩·헤더(`customer_name,grade,source,written_at,content`) 오류 → 400 + 메시지.
  행 단위 오류(등급/출처/날짜/내용 누락)는 `error_rows` 로 집계하고 정상 행만 저장 → **202 + batch_id** 응답 후 `BackgroundTasks` 로 분석.
- **AI 대체 경로**: `FEEDBACKCARE_AI_API_KEY` 가 없으면 `ExternalLLMAdapter` 가 `AIClientError` 를 던지고,
  `SentimentFilter` 는 `RuleBasedSentimentAnalyzer`(한국어 감성 사전)로, `ResponseStrategy` 는 템플릿으로 대체합니다.
  (키와 `FEEDBACKCARE_AI_ENDPOINT` 를 지정하면 `{"prompt"}` → `{"text"}` 형식의 HTTP 호출을 시도하는 스텁입니다.)
- **시드** (앱 시작 시, 멱등): grade_weights, topics(품질·배송·가격·서비스·기타), 사용자 `agent1/agent1234`(AGENT), `admin1/admin1234`(ADMIN)

> **인증은 과제용 스텁입니다.** 비밀번호는 `hashlib.sha256`(고정 salt)로 해시하고, 로그인 시 무작위 토큰을 서버 메모리에 보관합니다
> (서버 재시작 시 재로그인 필요). 운영 시 bcrypt/argon2 + JWT 등으로 교체해야 합니다.

## 5. 주요 API

| 메서드 | 경로 | 화면 |
|---|---|---|
| POST | `/api/auth/login`, GET `/api/auth/me` | S01 |
| GET | `/api/dashboard/summary` (감정·주제·상태별 건수, 긴급 건수, 일별 추이) | S02 |
| GET | `/api/feedbacks?status=&sentiment=&topic=&date_from=&date_to=&urgent=` (우선순위 내림차순) | S03 |
| GET | `/api/feedbacks/{id}`, PATCH `/api/feedbacks/{id}/status` `{action}`, POST `/api/feedbacks/{id}/analyze` | S04 |
| POST | `/api/feedbacks/{id}/drafts`, PATCH `/api/drafts/{id}`, PATCH `/api/drafts/{id}/confirm` | S04 |
| POST | `/api/feedbacks` | S05 |
| POST | `/api/feedbacks/upload`, GET `/api/feedbacks/batches/{id}` | S06 |
| PUT | `/api/feedbacks/{id}/gold-label`, GET `/api/dashboard/accuracy` (관리자) | S07 |

전체 명세는 서버 실행 후 http://127.0.0.1:8000/docs 에서 확인할 수 있습니다.

## 6. 실행 방법

### Backend (Python 3.12+; 3.14 확인)
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload --port 8000   # http://127.0.0.1:8000/docs
pytest                                       # 테스트
```
DB 파일은 `backend/feedbackcare.db` 에 생성됩니다(삭제하면 초기화). 환경변수:
`FEEDBACKCARE_DB_URL`, `FEEDBACKCARE_AI_API_KEY`, `FEEDBACKCARE_AI_ENDPOINT`, `FEEDBACKCARE_AI_TIMEOUT`(기본 5초).

### Frontend (Node 18+)
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173  (/api 는 :8000 으로 프록시)
npm run build    # dist/ 생성
```

### 빠른 확인 순서
1. 백엔드·프론트엔드 실행 → `agent1 / agent1234` 로그인
2. CSV 업로드 화면에서 `data/sample_feedback.csv` 업로드 → 목록에서 우선순위·긴급/VIP 태그 확인
3. 상세 화면에서 초안 생성 → 확정 → 상태 변경(처리 시작 → 완료)
4. `admin1` 로 로그인하면 정확도 검증(S07) 메뉴에서 정답 라벨 입력·일치율 확인
