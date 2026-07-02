"""Entry point para Streamlit Cloud. Redirige al módulo real de la app."""
import sys
from pathlib import Path

# Asegurar que src/ esté en el path
_REPO_ROOT = Path(__file__).resolve().parent
_SRC_PATH = _REPO_ROOT / "src"
if str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))

from qa_weekly_analytics.app.streamlit_app import main

if __name__ == "__main__":
    main()