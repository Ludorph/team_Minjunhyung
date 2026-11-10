# FeedbackCare 공개 데모 서버 이미지
# 1단계: React 화면 빌드 → 2단계: FastAPI 서버가 API와 빌드된 화면을 함께 제공 (주소 하나)

FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FEEDBACKCARE_DEMO_DATA=1
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY data/ data/
COPY --from=web /web/dist frontend/dist
WORKDIR /app/backend
# 클라우드가 지정하는 PORT 환경변수를 따른다 (없으면 8000)
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
