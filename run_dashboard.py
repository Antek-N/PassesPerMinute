"""
Streamlit application entry point.

Sets up the system path to include the `src` directory, resolving import issues
in the Streamlit Cloud environment, and launches the main dashboard.
"""
import sys
from pathlib import Path

current_dir = Path(__file__).parent
src_path = current_dir / "src"
sys.path.append(str(src_path))

from passes_per_minute.streamlit_app import main

if __name__ == "__main__":
    main()