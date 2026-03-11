#!/bin/bash
# Restart LinkedIn Job Matcher - Telegram Bot
# Usage: ./scripts/restart_bot.sh

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "========================================"
echo "LinkedIn Job Matcher - Bot Restart"
echo "========================================"
echo ""

# Kill any existing bot processes
echo "Stopping existing bot processes..."
pkill -9 -f "run_telegram_bot.py" 2>/dev/null && echo "  ✓ Killed existing bot processes" || echo "  ✓ No existing bot processes found"

# Wait for processes to fully terminate
sleep 2

# Verify all processes are killed
if pgrep -f "run_telegram_bot.py" > /dev/null 2>&1; then
    echo "  ⚠ Warning: Bot processes still running, force killing..."
    pkill -9 -f "run_telegram_bot.py" 2>/dev/null
    sleep 1
fi

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

echo ""
echo "Starting Telegram Bot..."

# Start bot in background with output logging
nohup python "$SCRIPT_DIR/run_telegram_bot.py" > "$PROJECT_ROOT/bot_output.log" 2>&1 &
BOT_PID=$!

echo "  ✓ Bot started with PID: $BOT_PID"
echo ""

# Wait for service to initialize
echo "Waiting for bot to initialize..."
sleep 3

# Check if bot is still running
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo ""
    echo "✅ Bot started successfully!"
    echo ""
    echo "Service:"
    echo "  📱 Telegram Bot - Running (PID: $BOT_PID)"
    echo ""
    echo "Logs:"
    echo "  tail -f $PROJECT_ROOT/bot_output.log"
    echo ""
    echo "Stop:"
    echo "  pkill -f run_telegram_bot.py"
    echo ""
else
    echo ""
    echo "❌ Bot failed to start!"
    echo ""
    echo "Error log:"
    echo "----------------------------------------"
    tail -20 "$PROJECT_ROOT/bot_output.log"
    echo "----------------------------------------"
    exit 1
fi
