"""Launch the Prediction Wallet web UI (FastAPI + browser)."""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

PORT = 8765
URL = f"http://localhost:{PORT}"


def main():
    root = Path(__file__).parent
    print(f"Starting Prediction Wallet UI on {URL} ...")
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "api.main:app",
            "--host", "0.0.0.0",
            "--port", str(PORT),
            "--reload",
        ],
        cwd=str(root),
    )
    time.sleep(1.5)
    webbrowser.open(URL)
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
