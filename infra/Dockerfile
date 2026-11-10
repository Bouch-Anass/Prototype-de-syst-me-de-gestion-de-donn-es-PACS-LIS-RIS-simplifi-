FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend/src
WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY frontend/ /app/frontend/
COPY contracts/examples/ /app/contracts/examples/
COPY data/fixtures/ /app/data/fixtures/
COPY data/dicom/study-metadata.json /app/data/dicom/study-metadata.json
COPY infra/start_app.py /app/infra/start_app.py

EXPOSE 8000
CMD ["python", "/app/infra/start_app.py"]
