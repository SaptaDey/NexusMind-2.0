#!/bin/bash
mode="${1:-http}"
if [ "$mode" = "http" ]; then
    exec uvicorn src.asr_got_reimagined.main:app --host 0.0.0.0 --port 8000
elif [ "$mode" = "stdio" ]; then
    exec python -m src.asr_got_reimagined.main_stdio
elif [ "$mode" = "both" ]; then
    # Run uvicorn in background and then stdio in foreground
    uvicorn src.asr_got_reimagined.main:app --host 0.0.0.0 --port 8000 &
    HTTP_PID=$!
    # Wait a moment for HTTP server to start
    sleep 2
    # Run stdio in foreground
    python -m src.asr_got_reimagined.main_stdio
    # If stdio exits, kill the HTTP server
    kill $HTTP_PID
fi
