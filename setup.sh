#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR/app"

uv venv --clear
source .venv/bin/activate
uv pip install -r requirements.txt
python3 app.py &
sleep 1
open http://localhost:8000/
wait