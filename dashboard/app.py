"""Dashboard module entrypoint."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard.ui import run_dashboard

run_dashboard()
