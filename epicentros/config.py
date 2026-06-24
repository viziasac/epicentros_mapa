from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"

CSV_MARKETPLACE = DATA_DIR / "base_epicentros_marketplace.csv"
CSV_EPICENTROS = DATA_DIR / "clientes_gemelos_epicentro.csv"

# Fallback si los CSV siguen en la raíz del proyecto
if not CSV_MARKETPLACE.is_file():
    CSV_MARKETPLACE = ROOT_DIR / "base_epicentros_marketplace.csv"
if not CSV_EPICENTROS.is_file():
    CSV_EPICENTROS = ROOT_DIR / "clientes_gemelos_epicentro.csv"

GRID_SIZE_M = 500

PARTNERS = {
    "Red Bull": "rb",
    "BAT": "bat",
    "Queirolo": "queirolo",
    "Piscano": "piscano",
    "Pernod Ricard": "pernod",
}

SEGMENTO_ESTABLE = "Estable"
SEGMENTO_INESTABLE = "Inestable"
SEGMENTO_NO_COMPRADOR = "No Comprador"

DEFAULT_UMBRAL_PCT = 0.30
DEFAULT_MIN_PARTNERS_ESTABLES = 1
DEFAULT_NR_MARKETPLACE = 0.0
DEFAULT_NR_BACKUS = 0.0
MIN_CLIENTES_GRILLA = 2
DEFAULT_MAX_GRILLAS = 8_000

COLOR_GRILLA = {
    "fuerte_epicentro": "#2563eb",
    "fuerte_sin_epicentro": "#16a34a",
    "debil_epicentro": "#ea580c",
    "debil_sin_epicentro": "#dc2626",
}

COLOR_POC = {
    "epicentro": "#2563eb",
    "gemelo": "#6b7280",
}

MAX_GRILLAS_RENDER = 12_000
