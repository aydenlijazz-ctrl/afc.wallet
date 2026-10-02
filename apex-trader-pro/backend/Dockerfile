FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY apex ./apex
# APEX_SERVICE selects which domain routes this Cloud Run service exposes (see apex/main.py)
CMD exec uvicorn apex.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
