# PRSpec 2.0 container: reproducible, non-root, no secrets baked in.
#
#   docker build -t prspec:2.0.0 .
#   docker run --rm prspec:2.0.0 --version
#   # deterministic witness on a read-only client checkout (no key, no network
#   # needed if you also mount an ethereum/EIPs checkout):
#   docker run --rm -v "$PWD/../besu:/src/besu:ro" -v "$PWD/../EIPs:/src/eips:ro" \
#     prspec:2.0.0 witness --eip 1559 -t besu=/src/besu --eips-dir /src/eips
#   # LLM analysis: pass the key at run time, never at build time
#   docker run --rm -e GEMINI_API_KEY -v "$PWD/../besu:/src/besu:ro" \
#     prspec:2.0.0 analyze --eip 1559 --client besu --source-dir /src/besu
#   # fully local model (no code leaves the machine):
#   docker run --rm --network host -e PRSPEC_LOCAL_BASE_URL=http://127.0.0.1:11434/v1 \
#     -v "$PWD/../besu:/src/besu:ro" prspec:2.0.0 --no-cloud analyze -p local \
#     --eip 1559 --client besu --source-dir /src/besu
FROM python:3.13-slim AS build
WORKDIR /build
COPY pyproject.toml README.md requirements.lock ./
COPY src ./src
RUN pip wheel --no-cache-dir --no-deps -w /wheels . \
 && pip wheel --no-cache-dir -r requirements.lock -w /wheels

FROM python:3.13-slim
LABEL org.opencontainers.image.title="PRSpec" \
      org.opencontainers.image.version="2.0.0" \
      org.opencontainers.image.source="https://github.com/Fosurero/PRSpec" \
      org.opencontainers.image.licenses="MIT"
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 prspec \
 && mkdir /work && chown prspec /work
COPY --from=build /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links /wheels prspec==2.0.0 && rm -rf /wheels
USER prspec
WORKDIR /work
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["prspec"]
CMD ["--help"]
