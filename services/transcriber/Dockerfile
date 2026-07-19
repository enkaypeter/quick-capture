# Stage 1: Build whisper.cpp with server
FROM ubuntu:24.04 AS builder

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 https://github.com/ggerganov/whisper.cpp.git /whisper

WORKDIR /whisper

RUN cmake -B build \
    -DWHISPER_BUILD_SERVER=ON \
    -DBUILD_SHARED_LIBS=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    && cmake --build build --config Release -j$(nproc)

# Stage 2: Minimal runtime
FROM ubuntu:24.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libcurl4 \
    libgomp1 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the statically-linked server binary
COPY --from=builder /whisper/build/bin/whisper-server /usr/local/bin/whisper-server

# Create model directory
RUN mkdir -p /models

# Download the base.en model
RUN curl -L -o /models/ggml-base.en.bin \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD curl -f http://localhost:8080/ || exit 1

ENTRYPOINT ["whisper-server"]
CMD [ \
    "--model", "/models/ggml-base.en.bin", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--convert", \
    "--language", "en", \
    "--threads", "2" \
]
