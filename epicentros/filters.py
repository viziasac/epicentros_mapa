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
    mask = pd.Series(True, index=df.index)

    if canal != "Todos":
        mask &= df["canal"] == canal
    if gerencias:
        mask &= df["gerencia"].isin(gerencias)
    if solo_epicentro:
        mask &= df["es_epicentro"] == 1
    if segmento_comprador != "Todos" and partner_prefix:
        col = f"{partner_prefix}_flag_comprador_l3m"
        if col in df.columns:
            mask &= df[col].astype(str).str.strip() == segmento_comprador

    if mask.all():
        return df
    return df.loc[mask]