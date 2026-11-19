#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
exec uvicorn handoff.main:app --reload --host 127.0.0.1 --port 8000
