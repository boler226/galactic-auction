# DVO-L3-7F2A91
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /code
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home --uid 1000 appuser
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY labs/devops-lab3/runtime ./lab_runtime
USER appuser
ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION}
EXPOSE 8000
CMD ["uvicorn", "lab_runtime.main:app", "--host", "0.0.0.0", "--port", "8000"]
