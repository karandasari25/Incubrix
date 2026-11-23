FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir .
COPY app /app/app
COPY connectors /app/connectors
COPY frontend /app/frontend
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
