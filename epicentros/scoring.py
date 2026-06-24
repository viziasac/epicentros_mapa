from __future__ import annotations

import numpy as np
import pandas as pd

from epicentros.config import (
    COLOR_GRILLA,
    GRID_SIZE_M,
    MAX_GRILLAS_RENDER,
    MIN_CLIENTES_GRILLA,
    PARTNERS,
    SEGMENTO_ESTABLE,
)


def partner_prefixes(selected_partners: list[str]) -> list[str]:
    return [PARTNERS[p] for p in selected_partners if p in PARTNERS]


def _grid_step(lat_mean: float) -> tuple[float, float]:
    paso_lat = GRID_SIZE_M / 111_320
    paso_lon = paso_lat / np.cos(np.radians(lat_mean))
    return paso_lat, paso_lon


def assign_grid(df: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    paso_lat, paso_lon = _grid_step(df["latitud"].mean())
    out = df.copy()
    out["grid_lat"] = (out["latitud"] / paso_lat).round() * paso_lat
    out["grid_lon"] = (out["longitud"] / paso_lon).round() * paso_lon
    return out, paso_lat, paso_lon


def compute_client_scores(
    df: pd.DataFrame,
    prefixes: list[str],
    min_partners_estables: int,
) -> pd.DataFrame:
    if not prefixes:
        raise ValueError("Selecciona al menos un partner.")

    estable_flags = []
    nr_partner_cols = []

    for p in prefixes:
        seg_col = f"{p}_segmento_resumen"
        if seg_col not in df.columns:
            raise KeyError(f"Columna requerida no encontrada: {seg_col}")
        seg = df[seg_col].fillna("No Comprador").astype(str).str.strip()
        estable_flags.append((seg == SEGMENTO_ESTABLE).astype(int))
        nr_partner_cols.append(df[f"{p}_nr_l3m"])

    estable_mat = np.column_stack(estable_flags)

    out = df.copy()
    out["n_partners_sel"] = len(prefixes)
    out["partners_estables"] = estable_mat.sum(axis=1)
    out["nr_partners_sel_l3m"] = np.column_stack(nr_partner_cols).sum(axis=1)
    out["cumple_umbral_estables"] = (
        out["partners_estables"] >= min_partners_estables
    ).astype(int)
    return out


def _grilla_es_fuerte(
    grid: pd.DataFrame,
    umbral_pct: float,
    umbral_nr_marketplace: float,
    umbral_nr_backus: float,
) -> pd.Series:
    por_pct = grid["pct_cumplen"] >= umbral_pct
    por_mp = (
        grid["nr_marketplace"] >= umbral_nr_marketplace
        if umbral_nr_marketplace > 0
        else pd.Series(False, index=grid.index)
    )
    por_backus = (
        grid["nr_backus"] >= umbral_nr_backus
        if umbral_nr_backus > 0
        else pd.Series(False, index=grid.index)
    )
    return por_pct | por_mp | por_backus


def aggregate_grids(
    df: pd.DataFrame,
    umbral_pct: float,
    umbral_nr_marketplace: float,
    umbral_nr_backus: float,
) -> pd.DataFrame:
    grid = df.groupby(["grid_lat", "grid_lon"], as_index=False).agg(
        total_clientes=("cliente_id", "count"),
        clientes_cumplen=("cumple_umbral_estables", "sum"),
        nr_marketplace=("total_soles_marketplace_l3m", "sum"),
        nr_backus=("total_soles_backus_l3m", "sum"),
        nr_partners=("nr_partners_sel_l3m", "sum"),
        pocs_listado=("es_poc", "sum"),
        pocs_epicentro=("es_epicentro", "sum"),
        pocs_gemelo=("es_gemelo", "sum"),
    )

    grid = grid[grid["total_clientes"] >= MIN_CLIENTES_GRILLA].copy()
    grid["pct_cumplen"] = grid["clientes_cumplen"] / grid["total_clientes"]

    base_fuerte = _grilla_es_fuerte(
        grid, umbral_pct, umbral_nr_marketplace, umbral_nr_backus
    )
    # Epicentro + Gemelo = POC del listado
    tiene_poc = grid["pocs_listado"] >= 1

    grid["color_grilla"] = np.select(
        [
            base_fuerte & tiene_poc,
            base_fuerte & ~tiene_poc,
            ~base_fuerte & tiene_poc,
        ],
        [
            COLOR_GRILLA["fuerte_epicentro"],
            COLOR_GRILLA["fuerte_sin_epicentro"],
            COLOR_GRILLA["debil_epicentro"],
        ],
        default=COLOR_GRILLA["debil_sin_epicentro"],
    )

    grid["etiqueta_zona"] = np.select(
        [
            base_fuerte & tiene_poc,
            base_fuerte & ~tiene_poc,
            ~base_fuerte & tiene_poc,
        ],
        [
            "Fuerte + POC",
            "Fuerte sin POC",
            "Débil + POC",
        ],
        default="Débil sin POC",
    )

    return grid


def filter_grids_by_color(grid: pd.DataFrame, colores_sel: list[str] | None) -> pd.DataFrame:
    if not colores_sel:
        return grid
    return grid[grid["etiqueta_zona"].isin(colores_sel)].copy()


def limit_grids_for_render(
    grid: pd.DataFrame, max_grillas: int = MAX_GRILLAS_RENDER
) -> pd.DataFrame:
    if len(grid) <= max_grillas:
        return grid

    out = grid.copy()
    out["_prioridad"] = (
        out["nr_marketplace"]
        + out["nr_backus"] * 0.1
        + out["pct_cumplen"] * 100
        + out["pocs_listado"] * 10
    )
    return (
        out.sort_values("_prioridad", ascending=False)
        .head(max_grillas)
        .drop(columns="_prioridad")
    )
