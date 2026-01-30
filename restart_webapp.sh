#!/bin/bash
#
# restart_webapp.sh
# Kills existing processes on ports 8000/5173 and restarts the webapp
# Handles cases where no processes are running without errors.
#

# Kill process on port 8000 (Backend)
PID_BACKEND=$(lsof -t -i:8000 2>/dev/null)
if [ -n "$PID_BACKEND" ]; then
    echo -e "\033[0;33mKilling existing process on port 8000 (PID: $PID_BACKEND)...\033[0m"
    kill -9 $PID_BACKEND 2>/dev/null || true
else
    echo "No process found on port 8000."
fi

# Kill process on port 5173 (Frontend)
PID_FRONTEND=$(lsof -t -i:5173 2>/dev/null)
if [ -n "$PID_FRONTEND" ]; then
    echo -e "\033[0;33mKilling existing process on port 5173 (PID: $PID_FRONTEND)...\033[0m"
    kill -9 $PID_FRONTEND 2>/dev/null || true
else
    echo "No process found on port 5173."
fi

echo -e "\033[0;32mCleanup complete. Starting web app...\033[0m"
./run_webapp.sh "$@"
