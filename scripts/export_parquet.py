"""Exporta parquet listo para desplegar en Streamlit Cloud."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from epicentros.config import GRID_SIZE_M, PARQUET_BUNDLED, PARQUET_LOCAL
from epicentros.data import load_full_dataset


def main() -> None:
    print(f"Cargando dataset y generando grilla {GRID_SIZE_M}m…")
    df = load_full_dataset()
    for out in (PARQUET_LOCAL, PARQUET_BUNDLED):
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out, index=False)
        mb = out.stat().st_size / (1024 * 1024)
        print(f"OK: {out} ({mb:.1f} MB, {len(df):,} filas)")


if __name__ == "__main__":
    main()
