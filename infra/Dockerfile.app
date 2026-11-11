FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend/src
WORKDIR /app/backend

COPY backend/requirements.txt /app/backend/requirements.txt
COPY backend/requirements-dev.txt /app/backend/requirements-dev.txt
COPY simulators/modality/requirements.txt /app/modality-requirements.txt
RUN pip install --no-cache-dir -r requirements-dev.txt -r /app/modality-requirements.txt

COPY backend /app/backend
COPY frontend /app/frontend
COPY contracts /app/contracts
COPY data/fixtures /app/data/fixtures
COPY data/hl7 /app/data/hl7
COPY data/dicom /app/data/dicom
COPY simulators /app/simulators
COPY tests /app/tests
COPY infra/app-entrypoint.sh /app/app-entrypoint.sh

RUN useradd --uid 10001 --create-home app && mkdir -p /app/data/generated && chown -R app:app /app
USER app
ENTRYPOINT ["/bin/sh", "/app/app-entrypoint.sh"]
