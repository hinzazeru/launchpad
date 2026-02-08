#!/bin/bash
#
# LaunchPad 💸 Web App Startup Script
#
# Usage:
#   ./run_webapp.sh              # Development mode (backend + frontend)
#   ./run_webapp.sh --production # Production mode (serves built React app)
#   ./run_webapp.sh --build      # Build frontend and run in production mode
#   ./run_webapp.sh --help       # Show help
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
MODE="development"
PORT=8000
FRONTEND_PORT=5173
BUILD_FIRST=false
BACKEND_PID=""
FRONTEND_PID=""
CLEANUP_DONE=false

# PID file for tracking processes
PID_FILE="$SCRIPT_DIR/.webapp.pid"

# Cleanup function - ensures all processes are stopped
cleanup() {
    if [ "$CLEANUP_DONE" = true ]; then
        return
    fi
    CLEANUP_DONE=true

    echo ""
    echo -e "${YELLOW}Shutting down services...${NC}"

    # Kill backend if running
    if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo -e "  ${BLUE}Stopping backend (PID: $BACKEND_PID)...${NC}"
        kill -TERM "$BACKEND_PID" 2>/dev/null || true
        # Wait up to 5 seconds for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
                break
            fi
            sleep 0.5
        done
        # Force kill if still running
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            echo -e "  ${YELLOW}Force killing backend...${NC}"
            kill -9 "$BACKEND_PID" 2>/dev/null || true
        fi
        echo -e "  ${GREEN}Backend stopped${NC}"
    fi

    # Kill frontend if running
    if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
        echo -e "  ${BLUE}Stopping frontend (PID: $FRONTEND_PID)...${NC}"
        kill -TERM "$FRONTEND_PID" 2>/dev/null || true
        # Wait up to 5 seconds for graceful shutdown
        for i in {1..10}; do
            if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
                break
            fi
            sleep 0.5
        done
        # Force kill if still running
        if kill -0 "$FRONTEND_PID" 2>/dev/null; then
            echo -e "  ${YELLOW}Force killing frontend...${NC}"
            kill -9 "$FRONTEND_PID" 2>/dev/null || true
        fi
        echo -e "  ${GREEN}Frontend stopped${NC}"
    fi

    # Clean up any orphaned processes on our ports
    cleanup_port $PORT "backend"
    if [ "$MODE" = "development" ]; then
        cleanup_port $FRONTEND_PORT "frontend"
    fi

    # Remove PID file
    rm -f "$PID_FILE"

    echo -e "${GREEN}All services stopped cleanly${NC}"
}

# Cleanup a specific port
cleanup_port() {
    local port=$1
    local service=$2
    local pids=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo -e "  ${YELLOW}Cleaning up orphaned $service processes on port $port...${NC}"
        echo "$pids" | xargs kill -9 2>/dev/null || true
    fi
}

# Check if a port is in use
check_port() {
    local port=$1
    local service=$2
    if lsof -ti:$port &>/dev/null; then
        local pid=$(lsof -ti:$port | head -1)
        echo -e "${YELLOW}Warning: Port $port is already in use (PID: $pid)${NC}"
        read -p "Kill existing process? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cleanup_port $port $service
            sleep 1
        else
            echo -e "${RED}Cannot start $service - port $port in use${NC}"
            exit 1
        fi
    fi
}

# Wait for a service to be healthy
wait_for_service() {
    local url=$1
    local service=$2
    local max_attempts=${3:-30}
    local attempt=1

    echo -ne "  ${BLUE}Waiting for $service to be ready...${NC}"

    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e " ${GREEN}Ready!${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        ((attempt++))
    done

    echo -e " ${RED}Failed!${NC}"
    return 1
}

# Set up signal handlers
setup_signal_handlers() {
    trap cleanup EXIT
    trap 'cleanup; exit 130' INT
    trap 'cleanup; exit 143' TERM
    trap 'cleanup; exit 1' HUP
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --production|-p)
            MODE="production"
            shift
            ;;
        --build|-b)
            MODE="production"
            BUILD_FIRST=true
            shift
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --frontend-port)
            FRONTEND_PORT="$2"
            shift 2
            ;;
        --help|-h)
            echo "LaunchPad 💸 Web App"
            echo ""
            echo "Usage: ./run_webapp.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --production, -p     Run in production mode (serves built React app)"
            echo "  --build, -b          Build frontend first, then run in production mode"
            echo "  --port PORT          Specify backend port (default: 8000)"
            echo "  --frontend-port PORT Specify frontend port (default: 5173, dev mode only)"
            echo "  --help, -h           Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_webapp.sh              # Dev mode: API on :8000, React on :5173"
            echo "  ./run_webapp.sh --production # Prod mode: everything on :8000"
            echo "  ./run_webapp.sh --build      # Build React, then run prod mode"
            echo "  ./run_webapp.sh --port 3000  # Use custom port"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check for Python virtual environment
PYTHON_CMD="python3"
check_venv() {
    if [ -d "venv" ]; then
        echo -e "${BLUE}Activating Python virtual environment...${NC}"
        source venv/bin/activate
        PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
    else
        echo -e "${YELLOW}Warning: No venv found. Using system Python.${NC}"
    fi
}

# Check dependencies
check_dependencies() {
    echo -e "${BLUE}Checking dependencies...${NC}"

    # Check Python (use -x for path, command -v for command name)
    if [[ "$PYTHON_CMD" == /* ]]; then
        # It's an absolute path
        if [ ! -x "$PYTHON_CMD" ]; then
            echo -e "${RED}Error: Python not found at $PYTHON_CMD${NC}"
            exit 1
        fi
    else
        # It's a command name
        if ! command -v "$PYTHON_CMD" &> /dev/null; then
            echo -e "${RED}Error: Python 3 is not installed${NC}"
            exit 1
        fi
    fi

    # Check if FastAPI is installed
    if ! "$PYTHON_CMD" -c "import fastapi" 2>/dev/null; then
        echo -e "${YELLOW}FastAPI not found. Installing dependencies...${NC}"
        "$PYTHON_CMD" -m pip install -r requirements.txt
    fi

    # Check Node.js for development mode
    if [ "$MODE" = "development" ]; then
        if ! command -v node &> /dev/null; then
            echo -e "${RED}Error: Node.js is not installed (required for development mode)${NC}"
            exit 1
        fi

        if [ ! -d "frontend/node_modules" ]; then
            echo -e "${YELLOW}Installing frontend dependencies...${NC}"
            (cd frontend && npm install)
        fi
    fi

    echo -e "${GREEN}Dependencies OK${NC}"
}

# Build frontend
build_frontend() {
    echo -e "${BLUE}Building frontend...${NC}"
    (cd frontend && npm run build)
    echo -e "${GREEN}Frontend build complete!${NC}"
}

# Run in development mode
run_development() {
    echo -e "${GREEN}Starting in DEVELOPMENT mode...${NC}"
    echo ""

    # Check ports before starting
    check_port $PORT "backend"
    check_port $FRONTEND_PORT "frontend"

    # Start backend in background
    echo -e "${BLUE}Starting backend server...${NC}"
    "$PYTHON_CMD" run_api.py --port "$PORT" &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$PID_FILE"

    # Wait for backend to be ready
    if ! wait_for_service "http://localhost:$PORT/api/health" "Backend API" 30; then
        echo -e "${RED}Backend failed to start${NC}"
        cleanup
        exit 1
    fi

    # Start frontend in background
    echo -e "${BLUE}Starting frontend dev server...${NC}"
    (cd frontend && npm run dev -- --port $FRONTEND_PORT) &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" >> "$PID_FILE"

    # Wait for frontend to be ready
    if ! wait_for_service "http://localhost:$FRONTEND_PORT" "Frontend" 30; then
        echo -e "${RED}Frontend failed to start${NC}"
        cleanup
        exit 1
    fi

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║            All services started successfully!          ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Frontend:${NC}     http://localhost:$FRONTEND_PORT"
    echo -e "  ${CYAN}Backend API:${NC}  http://localhost:$PORT"
    echo -e "  ${CYAN}API Docs:${NC}     http://localhost:$PORT/docs"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
    echo ""

    # Wait for either process to exit
    wait
}

# Run in production mode
run_production() {
    # Check if frontend build exists
    if [ ! -d "frontend/dist" ]; then
        echo -e "${RED}Error: Frontend build not found at frontend/dist/${NC}"
        echo -e "${YELLOW}Run with --build flag to build first, or run 'npm run build' in frontend/${NC}"
        exit 1
    fi

    echo -e "${GREEN}Starting in PRODUCTION mode...${NC}"
    echo ""

    # Check port before starting
    check_port $PORT "server"

    # Start server
    echo -e "${BLUE}Starting production server...${NC}"
    "$PYTHON_CMD" run_api.py --production --port "$PORT" &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$PID_FILE"

    # Wait for server to be ready
    if ! wait_for_service "http://localhost:$PORT/api/health" "Server" 30; then
        echo -e "${RED}Server failed to start${NC}"
        cleanup
        exit 1
    fi

    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║            Production server running!                  ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${CYAN}Web App:${NC}   http://localhost:$PORT"
    echo -e "  ${CYAN}API Docs:${NC}  http://localhost:$PORT/docs"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""

    # Wait for process to exit
    wait $BACKEND_PID
}

# Main
main() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          LaunchPad 💸 Web App         ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    echo ""

    # Set up cleanup handlers
    setup_signal_handlers

    check_venv
    check_dependencies

    if [ "$BUILD_FIRST" = true ]; then
        build_frontend
    fi

    if [ "$MODE" = "production" ]; then
        run_production
    else
        run_development
    fi
}

main
