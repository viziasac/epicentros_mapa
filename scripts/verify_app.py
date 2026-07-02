"""Auditoría local del proyecto Epicentros."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  OK  {name}")
    except Exception as exc:
        print(f"  FAIL {name}: {exc}")
        raise


def _has_local_dataset() -> bool:
    from epicentros.config import CSV_FULL, PARQUET_FULL
    from epicentros.data import _remote_data_url

    if _remote_data_url():
        return True
    return CSV_FULL.is_file() or PARQUET_FULL.is_file()


def main() -> None:
    print("=== Auditoría Epicentros ===\n")

    def imports():
        from epicentros.config import ETIQUETA_GRILLA, GRID_SIZE_M, PARTNERS

        assert GRID_SIZE_M == 400
        assert len(ETIQUETA_GRILLA) == 5
        assert len(PARTNERS) == 5
        import epicentros.filters  # noqa: F401
        import epicentros.grid  # noqa: F401

    def logica_color():
        import pandas as pd
        from epicentros.config import ETIQUETA_GRILLA
        from epicentros.scoring import _color_grid

        pct_c = pd.Series([0.5, 0.5, 0.1, 0.1, 0.1, 0.5, 0.1, 0.1, 0.1, 0.5])
        pct_p = pd.Series([0.1, 0.1, 0.5, 0.1, 0.5, 0.1, 0.1, 0.5, 0.5, 0.5])
        n_e = pd.Series([0, 1, 1, 0, 0, 1, 0, 0, 1, 1])

        _, etiquetas, _ = _color_grid(pct_c, pct_p, n_e, 0.3, 0.3)
        assert etiquetas.iloc[0] == ETIQUETA_GRILLA["verde"]
        assert etiquetas.iloc[1] == ETIQUETA_GRILLA["azul"]
        assert etiquetas.iloc[2] == ETIQUETA_GRILLA["celeste"]
        assert etiquetas.iloc[7] == ETIQUETA_GRILLA["naranja"]

    check("Imports y módulos", imports)
    check("Lógica de color", logica_color)

    if not _has_local_dataset():
        print("  SKIP Datos (sin CSV/parquet local ni URL remota)")
        print("\n=== OK parcial — configura datos para prueba completa ===")
        return

    def data():
        from epicentros.data import load_full_dataset
        from epicentros.config import PARTNERS

        df = load_full_dataset()
        assert len(df) > 0
        assert "grid_id" in df.columns
        assert "flag_epicentro" in df.columns
        for p in PARTNERS.values():
            assert f"{p}_flag_comprador_l3m" in df.columns
            assert f"{p}_pop" in df.columns

    def colores_cinco():
        from epicentros.config import ETIQUETA_GRILLA, PARTNERS
        from epicentros.data import load_full_dataset
        from epicentros.scoring import aggregate_grids, compute_client_metrics, partner_prefixes

        df = load_full_dataset().head(25_000)
        prefixes = partner_prefixes(list(PARTNERS.keys()))
        df = compute_client_metrics(df, prefixes, 1, 0.50)
        grid = aggregate_grids(df, 0.10, 0.30)
        assert len(grid) > 0
        assert "intensidad" in grid.columns
        labels = set(grid["etiqueta_zona"].unique())
        assert labels.issubset(set(ETIQUETA_GRILLA.values()))

    def solo_red_bull():
        from epicentros.data import load_full_dataset
        from epicentros.mapa import build_map
        from epicentros.pipeline import run_pipeline

        df = load_full_dataset().head(12_000)
        scored, _, grid_render, pl, po = run_pipeline(
            df, ["Red Bull"], 1, 0.10, 0.50, 0.30, 400, ()
        )
        assert scored["n_partners_sel"].max() == 1
        build_map(scored, grid_render, pl, po, ["Red Bull"], 1, 0.1, 0.3, 0.5, False)

    check("Datos + grid_id", data)
    check("5 colores", colores_cinco)
    check("Solo Red Bull", solo_red_bull)
    print("\n=== OK — listo para streamlit run streamlit_app.py ===")


if __name__ == "__main__":
    main()
