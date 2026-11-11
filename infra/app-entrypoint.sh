#!/bin/sh
set -eu

postgres_password=$(cat /run/secrets/postgres_password)
export DATABASE_URL="postgresql+psycopg://app:${postgres_password}@postgres:5432/pacs_lis_ris"
export HL7_SERVICE_SECRET="$(cat /run/secrets/hl7_service_secret)"
export ORTHANC_USERNAME=demo
export ORTHANC_PASSWORD="$(python -c 'import json; print(json.load(open("/run/secrets/orthanc.secret.json"))["RegisteredUsers"]["demo"])')"

cd /app/backend
python -m alembic -c alembic.ini upgrade head
exec "$@"
