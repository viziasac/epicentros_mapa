"""Punto de entrada para Streamlit Community Cloud."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).resolve().parent / "mapa_epicentros.py"), run_name="__main__")
