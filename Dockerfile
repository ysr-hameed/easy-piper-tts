FROM python:3.12-slim AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

RUN curl -fsSL https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz \
    -o piper.tar.gz && \
    mkdir -p /app/piper && \
    tar xzf piper.tar.gz -C /app/piper && \
    rm piper.tar.gz

RUN mkdir -p /app/piper/models && \
    curl -fsSL https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/rohan/medium/hi_IN-rohan-medium.onnx \
    -o /app/piper/models/hi_IN-rohan-medium.onnx && \
    curl -fsSL https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/rohan/medium/hi_IN-rohan-medium.onnx.json \
    -o /app/piper/models/hi_IN-rohan-medium.onnx.json && \
    curl -fsSL https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx \
    -o /app/piper/models/hi_IN-pratham-medium.onnx && \
    curl -fsSL https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json \
    -o /app/piper/models/hi_IN-pratham-medium.onnx.json && \
    curl -fsSL https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx \
    -o /app/piper/models/hi_IN-priyamvada-medium.onnx && \
    curl -fsSL https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium.onnx.json \
    -o /app/piper/models/hi_IN-priyamvada-medium.onnx.json

RUN ln -sf hi_IN-rohan-medium.onnx /app/piper/models/hi_IN-medium.onnx && \
    ln -sf hi_IN-rohan-medium.onnx.json /app/piper/models/hi_IN-medium.onnx.json

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/piper /app/piper

COPY piper-web/app.py /app/app.py

WORKDIR /app

ENV PIPER_HOME=/app/piper
ENV LD_LIBRARY_PATH=/app/piper/lib
ENV ESPEAK_DATA_PATH=/app/piper/lib/espeak-ng-data

EXPOSE 8765

CMD ["python3", "app.py"]
