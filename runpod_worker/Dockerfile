FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV WAN_MOCK=1
ENV WAN_REPO_DIR=/opt/Wan2.2
ENV WAN_MODEL_DIR=/workspace/models/Wan2.2-Animate-14B
ENV WAN_AUTO_DOWNLOAD=1
ENV HF_HOME=/workspace/hf
ENV PIP_ROOT_USER_ACTION=ignore
ENV MAX_JOBS=2
ENV TORCH_CUDA_ARCH_LIST=12.0

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    ninja-build \
    git \
    ffmpeg \
    ca-certificates \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY runpod_worker/requirements.txt /app/requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && python3 -m pip install --no-cache-dir -r /app/requirements.txt

RUN python3 -m pip install --no-cache-dir \
    torch==2.8.0 torchvision==0.23.0 torchaudio==2.8.0 \
    --index-url https://download.pytorch.org/whl/cu128

RUN git clone --depth 1 https://github.com/Wan-Video/Wan2.2.git "$WAN_REPO_DIR" \
    && sed -i '/flash_attn/d;/flash-attn/d' "$WAN_REPO_DIR/requirements.txt" \
    && python3 -m pip install --no-cache-dir -r "$WAN_REPO_DIR/requirements.txt" \
    && python3 -m pip install --no-cache-dir --no-build-isolation -r "$WAN_REPO_DIR/requirements_animate.txt" moviepy \
    && python3 -m pip install --no-cache-dir flash-attn --no-build-isolation

COPY runpod_worker/ /app/

CMD ["python3", "-u", "/app/handler.py"]
