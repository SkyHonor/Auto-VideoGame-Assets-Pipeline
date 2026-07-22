#!/bin/sh
# One-shot init: pull the LLM used for prompt expansion from the OFFICIAL Ollama
# registry, then exit. Runs against the already-running `ollama` service.
set -e

MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"
HOST="${OLLAMA_HOST:-http://ollama:11434}"

echo "[ollama-init] waiting for ollama server at ${HOST} ..."
until curl -sf "${HOST}/api/tags" >/dev/null 2>&1; do
  sleep 2
done

echo "[ollama-init] pulling model: ${MODEL}"
curl -sf -X POST "${HOST}/api/pull" -d "{\"name\":\"${MODEL}\"}" >/dev/null

echo "[ollama-init] model ${MODEL} is ready."
