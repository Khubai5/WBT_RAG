FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    TOKENIZERS_PARALLELISM=false \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    ANONYMIZED_TELEMETRY=false

WORKDIR /app
RUN useradd --create-home --uid 10001 wbt && chown wbt:wbt /app
COPY requirements.txt ./
# CPU-only PyTorch avoids installing CUDA libraries on a web server.
RUN pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt
COPY --chown=wbt:wbt . .
USER wbt
# No API key is required or used during this step. Models and the validated
# Chroma snapshot become part of the image and survive a fresh container.
RUN python -m src.deployment prepare
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8501')+'/_stcore/health',timeout=4)"
CMD ["python", "-m", "src.deployment", "serve"]
