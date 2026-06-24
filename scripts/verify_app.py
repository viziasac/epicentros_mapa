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


def main() -> None:
    print("=== Auditoría Epicentros ===\n")

    def imports():
        from epicentros.config import DEFAULT_MIN_PARTNERS_ESTABLES, PARTNERS
        from epicentros.pipeline import clamp_min_partners

        assert DEFAULT_MIN_PARTNERS_ESTABLES == 1
        assert clamp_min_partners(1, 5) == 1
        assert clamp_min_partners(5, 10) == 5
        assert len(PARTNERS) == 5

    def data():
        from epicentros.data import load_full_dataset
        from epicentros.config import PARTNERS

        df = load_full_dataset()
        assert len(df) > 0
        for p in PARTNERS.values():
            assert f"{p}_segmento_resumen" in df.columns

    def solo_red_bull():
        from epicentros.data import load_full_dataset
        from epicentros.pipeline import run_pipeline

        df = load_full_dataset().head(15_000)
        scored, grid_full, grid_render, pl, po = run_pipeline(
            df,
            ["Red Bull"],
            min_partners_estables=1,
            umbral_pct=0.30,
            umbral_nr_mp=0,
            umbral_nr_backus=0,
            max_grillas=500,
        )
        assert scored["n_partners_sel"].max() == 1
        from epicentros.mapa import build_map

        build_map(scored, grid_render, pl, po, ["Red Bull"], 1, show_pocs=False)

    def scoring_nr_zero():
        from epicentros.data import load_full_dataset
        from epicentros.scoring import aggregate_grids, assign_grid, compute_client_scores, partner_prefixes
        from epicentros.config import PARTNERS

        df = load_full_dataset().head(10_000)
        df = compute_client_scores(df, partner_prefixes(list(PARTNERS.keys())), 1)
        df, _, _ = assign_grid(df)
        strict = aggregate_grids(df, 0.99, 0, 0)
        assert strict["etiqueta_zona"].str.contains("Fuerte").sum() < len(strict)

    check("Imports", imports)
    check("Datos", data)
    check("Solo Red Bull", solo_red_bull)
    check("NR=0 no pinta todo verde", scoring_nr_zero)
    print("\n=== OK — streamlit run mapa_epicentros.py ===")


if __name__ == "__main__":
    main()
