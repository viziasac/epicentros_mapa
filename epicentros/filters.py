from __future__ import annotations

import pandas as pd


def apply_geo_filters(
    df: pd.DataFrame,
    canal: str = "Todos",
    gerencias: tuple[str, ...] = (),
    solo_epicentro: bool = False,
    segmento_comprador: str = "Todos",
    partner_prefix: str | None = None,
) -> pd.DataFrame:
    out = df
    if canal != "Todos":
        out = out[out["canal"] == canal]
    if gerencias:
        out = out[out["gerencia"].isin(gerencias)]
    if solo_epicentro:
        out = out[out["es_epicentro"] == 1]
    if segmento_comprador != "Todos" and partner_prefix:
        col = f"{partner_prefix}_flag_comprador_l3m"
        if col in out.columns:
            out = out[out[col].astype(str).str.strip() == segmento_comprador]
    return out
