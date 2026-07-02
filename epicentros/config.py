from pathlib import Path
import os

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
CACHE_DIR = ROOT_DIR / ".cache"

GRID_SIZE_M = 400
PARQUET_NAME = f"base_epicentros_full_grid{GRID_SIZE_M}m.parquet"

# Parquet incluido en repo (deploy Streamlit Cloud sin secrets)
PARQUET_BUNDLED = DATA_DIR / PARQUET_NAME

CSV_FULL = DATA_DIR / "base_epicentros_full.csv"
if not CSV_FULL.is_file():
    CSV_FULL = ROOT_DIR / "base_epicentros_full.csv"

# Parquet local generado o en raíz (desarrollo)
PARQUET_LOCAL = ROOT_DIR / PARQUET_NAME
PARQUET_FULL = PARQUET_BUNDLED if PARQUET_BUNDLED.is_file() else PARQUET_LOCAL

ENV_DATA_URL = "EPICENTROS_DATA_URL"

PARTNERS = {
    "Red Bull": "rb",
    "BAT": "bat",
    "Queirolo": "queirolo",
    "Piscano": "piscano",
    "Pernod Ricard": "pernod",
}

COMPRADOR_L3M = "Comprador L3M"
NO_COMPRADOR_L3M = "No Comprador L3M"

DEFAULT_UMBRAL_PCT_COMPRADORES = 0.10
DEFAULT_MIN_PARTNERS_COMPRADORES = 1
DEFAULT_UMBRAL_POP = 0.50
DEFAULT_UMBRAL_PCT_POP = 0.30
MIN_CLIENTES_GRILLA = 2
DEFAULT_MAX_GRILLAS = 8_000

COLOR_GRILLA = {
    "verde": "#16a34a",
    "azul": "#2563eb",
    "celeste": "#06b6d4",
    "naranja": "#ea580c",
    "rojo": "#dc2626",
}

ETIQUETA_GRILLA = {
    "verde": "Verde — compradores",
    "azul": "Azul — compradores + epicentro",
    "celeste": "Celeste — epicentro + POP alto",
    "naranja": "Naranja — POP alto sin epicentro",
    "rojo": "Rojo",
}

COLOR_POC = "#2563eb"
MAX_GRILLAS_RENDER = 12_000


def data_setup_hint() -> str:
    return (
        f"Coloca `{PARQUET_NAME}` en `data/`, un CSV en la raíz, "
        "o configura `EPICENTROS_DATA_URL` / secrets `[data] parquet_url`."
    )
