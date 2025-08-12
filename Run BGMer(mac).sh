#!/usr/bin/env bash
set -euo pipefail

# スクリプトのあるフォルダへ移動（どこから実行してもOK）
cd "$(dirname "$0")"

APP_NAME="BGMer"
VENV_DIR=".venv"

echo "[1/4] Python を確認..."
PYBIN="/opt/homebrew/bin/python3.11"
if [ ! -x "$PYBIN" ]; then
  PYBIN="$(command -v python3 || true)"
fi
if [ -z "${PYBIN:-}" ]; then
  echo "Python が見つかりません。Homebrew で 'brew install python@3.11' を実行してください。"
  exit 1
fi
echo "  -> ${PYBIN}"

echo "[2/4] 仮想環境(arm64)を作成..."
/usr/bin/arch -arm64 "$PYBIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install -U pip setuptools wheel

echo "[3/4] 依存をインストール..."
if [ -f requirements.txt ]; then
  pip install -r requirements.txt
else
  echo "requirements.txt が見つかりません。BGMer のルートで実行してください。"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "⚠️  ffmpeg が見つかりません。音声合成の結合で必要です。'brew install ffmpeg' を推奨します（続行は可能）。"
fi

echo "[4/4] アプリを起動..."
exec python app.py
