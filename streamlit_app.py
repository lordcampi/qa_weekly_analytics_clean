"""Entry point para Streamlit Cloud."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from qa_weekly_analytics.app.streamlit_app import main

main()
