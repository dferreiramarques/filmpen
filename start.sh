#!/usr/bin/env bash
# FilmPen — arrancar o servidor (macOS / Linux)
cd "$(dirname "$0")"

PORT="${PORT:-8080}"
TRANSFER="${TRANSFER:-full}"   # full ou 2048
LOOK="${LOOK:-}"               # negative, slide, bw (vazio = o último escolhido)

[ -x .venv/bin/python ] || ./install.sh || exit 1

ARGS=(--port "$PORT" --transfer "$TRANSFER")
[ -n "$LOOK" ] && ARGS+=(--look "$LOOK")

echo "FilmPen a arrancar em http://127.0.0.1:$PORT  (Ctrl+C para parar)"
exec .venv/bin/python -m filmpen run --open "${ARGS[@]}" "$@"
