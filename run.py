"""
FraudShield — Master Cross-Platform CLI Launcher.

Provides unified commands for:
  setup       Install dependencies and prepare environment
  train-fast  Run fast training pipeline (<3 min on CPU)
  train       Run full production training run (requires confirmation)
  demo        Train if artifacts missing, then launch server & UI
  test        Execute pytest test suite

Usage:
  python run.py [COMMAND] [OPTIONS]
  (Defaults to 'demo' if no command specified)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import ARTIFACTS_DIR, CHAMPION_MODEL_FILE, DATA_PROCESSED_DIR, METRICS_FILE


def run_command(cmd: list[str], env: dict[str, str] | None = None) -> int:
    """Execute command in subprocess with streaming output."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    # Ensure UTF-8 output on Windows
    full_env["PYTHONIOENCODING"] = "utf-8"
    full_env["PYTHONUTF8"] = "1"

    print(f"\n[FraudShield] Executing: {' '.join(cmd)}")
    try:
        res = subprocess.run(cmd, env=full_env, cwd=str(PROJECT_ROOT))
        return res.returncode
    except KeyboardInterrupt:
        print("\n[FraudShield] Interrupted by user.")
        return 130
    except Exception as exc:
        print(f"\n[FraudShield] Error executing command: {exc}")
        return 1


def cmd_setup(args: argparse.Namespace) -> int:
    """Install required Python dependencies."""
    print("=" * 60)
    print("FraudShield Environment Setup")
    print("=" * 60)
    req_file = PROJECT_ROOT / "requirements.txt"
    if not req_file.exists():
        print(f"[Error] requirements.txt not found at {req_file}")
        return 1

    cmd = [sys.executable, "-m", "pip", "install", "-r", str(req_file)]
    code = run_command(cmd)
    if code == 0:
        print("\n[Success] All FraudShield dependencies installed successfully!")
    return code


def cmd_train_fast(args: argparse.Namespace) -> int:
    """Execute fast training pipeline (<3 minutes on laptop CPU)."""
    print("=" * 60)
    print("FraudShield — Fast Training Run (<3 minutes)")
    print("=" * 60)
    train_script = PROJECT_ROOT / "src" / "train.py"
    if not train_script.exists():
        print("[Notice] src/train.py is scheduled for Phase 3. Generating sample data and EDA for Phase 1...")
        cmd = [sys.executable, "-c", "from src.data import load_ledgersim, generate_eda_summary; df = load_ledgersim(fast=True); generate_eda_summary(df)"]
        return run_command(cmd)

    cmd = [sys.executable, str(train_script), "--fast"]
    return run_command(cmd)


def cmd_train(args: argparse.Namespace) -> int:
    """Execute full production training run."""
    print("=" * 60)
    print("FraudShield — Full Production Training Pipeline")
    print("=" * 60)
    train_script = PROJECT_ROOT / "src" / "train.py"
    if not train_script.exists():
        print("[Notice] src/train.py is scheduled for Phase 3. Training pause rule will apply.")
        return 0

    cmd = [sys.executable, str(train_script)]
    return run_command(cmd)


def cmd_demo(args: argparse.Namespace) -> int:
    """Launch FastAPI server serving the live scoring API and UI."""
    print("=" * 60)
    print("FraudShield — Operations Desk & Demo Server")
    print("=" * 60)

    # Check if artifacts exist; if missing, train-fast first
    if not (CHAMPION_MODEL_FILE.exists() and METRICS_FILE.exists()):
        print("\n[Notice] Required training artifacts not found.")
        print("[Notice] Running fast training pipeline first so demo has real data...")
        train_code = cmd_train_fast(args)
        if train_code != 0:
            print("[Warning] Pre-training step returned non-zero code.")

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)

    api_script = PROJECT_ROOT / "api" / "main.py"
    if not api_script.exists():
        print(f"[Notice] api/main.py is scheduled for Phase 5. Server will launch once backend is built.")
        return 0

    print(f"\n[Starting Server] Serving FraudDesk at http://{host}:{port}")
    cmd = [sys.executable, "-m", "uvicorn", "api.main:app", "--host", str(host), "--port", str(port)]
    return run_command(cmd)


def cmd_test(args: argparse.Namespace) -> int:
    """Run pytest test suite."""
    print("=" * 60)
    print("FraudShield Verification Test Suite")
    print("=" * 60)
    test_args = args.pytest_args if hasattr(args, "pytest_args") and args.pytest_args else []
    cmd = [sys.executable, "-m", "pytest"] + test_args
    return run_command(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="FraudShield Launcher",
        description="Single entrypoint for FraudShield training, testing, and demonstration.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # setup
    subparsers.add_parser("setup", help="Install required dependencies")

    # train-fast
    subparsers.add_parser("train-fast", help="Run fast training pipeline (<3 min)")

    # train
    subparsers.add_parser("train", help="Run full production training run")

    # demo
    demo_parser = subparsers.add_parser("demo", help="Train if needed and launch demo server")
    demo_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default 127.0.0.1)")
    demo_parser.add_argument("--port", type=int, default=8000, help="Port (default 8000)")

    # test
    test_parser = subparsers.add_parser("test", help="Execute pytest test suite")
    test_parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Arguments passed directly to pytest")

    parsed = parser.parse_args()

    # Default to demo if no subcommand specified
    cmd_name = parsed.command or "demo"

    commands = {
        "setup": cmd_setup,
        "train-fast": cmd_train_fast,
        "train": cmd_train,
        "demo": cmd_demo,
        "test": cmd_test,
    }

    handler = commands.get(cmd_name)
    if handler:
        sys.exit(handler(parsed))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

