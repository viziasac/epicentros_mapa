from __future__ import annotations

import pandas as pd

from epicentros.config import PARTNERS
from epicentros.scoring import (
    aggregate_grids,
    assign_grid,
    compute_client_scores,
    filter_grids_by_color,
    limit_grids_for_render,
    partner_prefixes,
)


def apply_geo_filters(
    df: pd.DataFrame,
    canal: str = "Todos",
    gerencia: str = "Todas",
    solo_listado: bool = False,
    segmento_partner: str = "Todos",
    partner_prefix: str | None = None,
) -> pd.DataFrame:
    out = df
    if canal != "Todos":
        out = out[out["canal"] == canal]
    if gerencia != "Todas":
        out = out[out["gerencia"] == gerencia]
    if solo_listado:
        out = out[out["es_poc"] == 1]
    if segmento_partner != "Todos" and partner_prefix:
        col = f"{partner_prefix}_segmento_resumen"
        if col in out.columns:
            out = out[out[col].astype(str).str.strip() == segmento_partner]
    return out


def clamp_min_partners(n_partners: int, current: int | None = None) -> int:
    """Evita error de slider cuando se pasa de N partners a 1 (ej. solo Red Bull)."""
    if n_partners < 1:
        return 1
    value = current if current is not None else 1
    return max(1, min(value, n_partners))


def run_pipeline(
    df: pd.DataFrame,
    partners_sel: list[str],
    min_partners_estables: int,
    umbral_pct: float,
    umbral_nr_mp: float,
    umbral_nr_backus: float,
    max_grillas: int,
    colores_grilla: tuple[str, ...] = (),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, float, float]:
    prefixes = partner_prefixes(partners_sel)
    min_partners_estables = clamp_min_partners(len(prefixes), min_partners_estables)

    scored = compute_client_scores(df, prefixes, min_partners_estables)
    scored, paso_lat, paso_lon = assign_grid(scored)

    grid_full = aggregate_grids(
        scored,
        umbral_pct=umbral_pct,
        umbral_nr_marketplace=umbral_nr_mp,
        umbral_nr_backus=umbral_nr_backus,
    )
    grid_full = filter_grids_by_color(grid_full, list(colores_grilla) or None)
    grid_render = limit_grids_for_render(grid_full, max_grillas=max_grillas)

    return scored, grid_full, grid_render, paso_lat, paso_lon
