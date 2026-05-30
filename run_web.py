#!/usr/bin/env python3
"""
Запуск веб-сервера Table Tennis Analyzer.

    python run_web.py
    python run_web.py --port 8080 --reload
"""

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Table Tennis Analyzer Web")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Table Tennis Analyzer")
    print(f"  http://{args.host}:{args.port}")
    print(f"{'='*60}\n")

    uvicorn.run(
        "web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()