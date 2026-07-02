"""Auditoría completa — local y simulación Streamlit Cloud."""
from __future__ import annotations

import shutil
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


def _has_dataset() -> bool:
    from epicentros.config import CSV_FULL, PARQUET_BUNDLED, PARQUET_LOCAL
    from epicentros.data import _remote_data_url

    if _remote_data_url():
        return True
    return any(p.is_file() for p in (PARQUET_BUNDLED, PARQUET_LOCAL, CSV_FULL))


def main() -> None:
    print("=== Auditoría Epicentros ===\n")

    def repo_layout():
        required = [
            "streamlit_app.py",
            "mapa_epicentros.py",
            "requirements.txt",
            "data/base_epicentros_full_grid400m.parquet",
            "epicentros/config.py",
            "epicentros/data.py",
            "epicentros/filters.py",
            "epicentros/grid.py",
            "epicentros/mapa.py",
            "epicentros/pipeline.py",
            "epicentros/scoring.py",
        ]
        for rel in required:
            assert (ROOT / rel).is_file(), f"Falta: {rel}"

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

    def streamlit_entry():
        entry = ROOT / "streamlit_app.py"
        compile(entry.read_text(encoding="utf-8"), str(entry), "exec")

    check("Layout del repo", repo_layout)
    check("Imports y módulos", imports)
    check("Lógica de color", logica_color)
    check("Entry point streamlit_app", streamlit_entry)

    if not _has_dataset():
        print("  SKIP Datos (sin parquet/CSV)")
        print("\n=== OK parcial ===")
        return

    def data():
        from epicentros.config import PARTNERS
        from epicentros.data import load_full_dataset

        df = load_full_dataset()
        assert len(df) > 100_000
        assert "grid_id" in df.columns
        for p in PARTNERS.values():
            assert f"{p}_flag_comprador_l3m" in df.columns
            assert f"{p}_pop" in df.columns

    def cloud_sim():
        """Solo parquet en data/ — igual que Streamlit Cloud."""
        from epicentros.config import PARQUET_BUNDLED
        from epicentros.data import load_full_dataset
        from epicentros.pipeline import run_pipeline

        assert PARQUET_BUNDLED.is_file()
        csv_candidates = list(ROOT.glob("base_epicentros_full.csv")) + list(
            (ROOT / "data").glob("base_epicentros_full.csv")
        )
        backups = []
        for p in csv_candidates:
            if p.is_file():
                bak = p.with_suffix(p.suffix + ".audit_bak")
                shutil.move(p, bak)
                backups.append((bak, p))
        try:
            df = load_full_dataset()
            assert len(df) > 0
            _, _, grid, _, _ = run_pipeline(
                df.head(8_000), ["Red Bull", "BAT"], 1, 0.10, 0.50, 0.30, 600, ()
            )
            assert not grid.empty
        finally:
            for bak, orig in backups:
                shutil.move(bak, orig)

    def mapa_render():
        from epicentros.data import load_full_dataset
        from epicentros.mapa import build_map
        from epicentros.pipeline import run_pipeline

        df = load_full_dataset().head(8_000)
        scored, _, grid, pl, po = run_pipeline(
            df, list(["Red Bull"]), 1, 0.10, 0.50, 0.30, 400, ()
        )
        build_map(scored, grid, pl, po, ["Red Bull"], 1, 0.1, 0.3, 0.5, False)

    check("Carga de datos", data)
    check("Simulación Streamlit Cloud", cloud_sim)
    check("Render mapa Folium", mapa_render)
    print("\n=== OK — listo para local y Streamlit Cloud ===")


if __name__ == "__main__":
    main()
