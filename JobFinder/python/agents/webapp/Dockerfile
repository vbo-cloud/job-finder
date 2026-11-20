# Build context: JobFinder/python/
# docker build -f agents/webapp/Dockerfile -t webapp .
FROM python:3.12-slim
WORKDIR /app
COPY agents/webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agents/webapp/ .
COPY shared/ ./shared/
COPY migrations/ ./migrations/
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
