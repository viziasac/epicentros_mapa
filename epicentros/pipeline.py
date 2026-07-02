from __future__ import annotations

import pandas as pd

from epicentros.grid import grid_step
from epicentros.scoring import (
    aggregate_grids,
    compute_client_metrics,
    filter_grids_by_color,
    limit_grids_for_render,
    partner_prefixes,
)


def clamp_min_partners(n_partners: int, current: int | None = None) -> int:
    if n_partners < 1:
        return 1
    value = current if current is not None else 1
    return max(1, min(value, n_partners))


def run_pipeline(
    df: pd.DataFrame,
    partners_sel: list[str],
    min_partners_compradores: int,
    umbral_pct: float,
    umbral_pop: float,
    umbral_pct_pop: float,
    max_grillas: int,
    colores_grilla: tuple[str, ...] = (),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float, float]:
    prefixes = partner_prefixes(partners_sel)
    min_partners_compradores = clamp_min_partners(
        len(prefixes), min_partners_compradores
    )

    scored = compute_client_metrics(
        df, prefixes, min_partners_compradores, umbral_pop
    )

    paso_lat, paso_lon = grid_step(float(scored["latitud"].mean()))

    grid_full = aggregate_grids(scored, umbral_pct, umbral_pct_pop)
    grid_full = filter_grids_by_color(grid_full, list(colores_grilla) or None)
    grid_render = limit_grids_for_render(grid_full, max_grillas=max_grillas)

    return scored, grid_full, grid_render, paso_lat, paso_lon
