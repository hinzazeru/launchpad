#!/usr/bin/env python3
"""Run the FastAPI backend server.

Usage:
    python run_api.py                  # Development mode (default)
    python run_api.py --production     # Production mode (serves React build)
    python run_api.py --port 8080      # Custom port
"""

import argparse
import os
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run Resume Targeter API server")
    parser.add_argument(
        "--production",
        action="store_true",
        help="Run in production mode (serves React build, no hot-reload)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the server on (default: 8000)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)"
    )
    args = parser.parse_args()

    # Set production environment variable
    if args.production:
        os.environ["PRODUCTION"] = "true"
        print("🚀 Starting in PRODUCTION mode...")
        print(f"   Serving React build from frontend/dist/")
    else:
        os.environ["PRODUCTION"] = "false"
        print("🔧 Starting in DEVELOPMENT mode...")
        print(f"   Frontend: http://localhost:5173 (run `npm run dev` in frontend/)")

    print(f"   API: http://{args.host}:{args.port}")
    print(f"   Docs: http://{args.host}:{args.port}/docs")
    print()

    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=not args.production,
        log_level="info"
    )


if __name__ == "__main__":
    main()
