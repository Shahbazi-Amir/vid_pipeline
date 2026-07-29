FROM python:3.11.9-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VID_PIPELINE_OUTPUT_ROOT=/data/outputs

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 10001 pipeline
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --upgrade pip && python -m pip install '.[all]'

USER pipeline
VOLUME ["/data/input", "/data/outputs", "/home/pipeline/.cache"]
ENTRYPOINT ["vid-pipeline"]
CMD ["--help"]
