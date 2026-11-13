#!/usr/bin/env bash
# FilmPen — instalador para macOS / Linux
set -e
cd "$(dirname "$0")"

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "[!] Precisas do Python 3.10 ou mais recente: https://www.python.org/downloads/"
  exit 1
fi

echo "[1/3] $($PY --version)"
if [ ! -x .venv/bin/python ]; then
  echo "[2/3] A criar o ambiente virtual em .venv ..."
  "$PY" -m venv .venv
else
  echo "[2/3] Ambiente virtual .venv já existe."
fi
echo "[3/3] A instalar as dependências ..."
.venv/bin/python -m pip install --upgrade pip --disable-pip-version-check -q
.venv/bin/python -m pip install -r requirements.txt --disable-pip-version-check
.venv/bin/python -c "import numpy, PIL; print('      numpy', numpy.__version__, '/ Pillow', PIL.__version__)"
chmod +x start.sh 2>/dev/null || true
echo
echo "Instalação concluída. Para arrancar: ./start.sh"
