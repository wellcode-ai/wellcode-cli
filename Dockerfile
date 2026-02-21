FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

ENV WELLCODE_DATA_DIR=/data

EXPOSE 8787

CMD ["wellcode", "serve", "--host", "0.0.0.0", "--port", "8787"]
