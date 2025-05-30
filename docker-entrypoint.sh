#!/bin/bash
mode="${1:-http}"
if [ "$mode" = "http" ]; then
    exec uvicorn src.asr_got_reimagined.main:app --host 0.0.0.0 --port 8000
elif [ "$mode" = "stdio" ]; then
    exec python -m src.asr_got_reimagined.main_stdio
elif [ "$mode" = "both" ]; then
    # perhaps run uvicorn in background then stdio?
    exec uvicorn src.asr_got_reimagined.main:app --host 0.0.0.0 --port 8000
fi
