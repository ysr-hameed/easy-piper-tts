FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY piper /app/piper

COPY piper-web/app.py /app/app.py

WORKDIR /app

ENV PIPER_HOME=/app/piper
ENV LD_LIBRARY_PATH=/app/piper/lib
ENV ESPEAK_DATA_PATH=/app/piper/lib/espeak-ng-data

EXPOSE 8765

CMD ["python3", "app.py"]
