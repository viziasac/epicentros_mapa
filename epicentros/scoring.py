from __future__ import annotations

import numpy as np
import pandas as pd

from epicentros.config import (
    COLOR_GRILLA,
    COMPRADOR_L3M,
    ETIQUETA_GRILLA,
    MAX_GRILLAS_RENDER,
    MIN_CLIENTES_GRILLA,
    PARTNERS,
)


def partner_prefixes(selected_partners: list[str]) -> list[str]:
    return [PARTNERS[p] for p in selected_partners if p in PARTNERS]


def compute_client_metrics(
    df: pd.DataFrame,
    prefixes: list[str],
    min_partners_compradores: int,
    umbral_pop: float,
) -> pd.DataFrame:
    if not prefixes:
        raise ValueError("Selecciona al menos un partner.")

    comprador_flags = []
    pop_cols = []

    for p in prefixes:
        flag_col = f"{p}_flag_comprador_l3m"
        pop_col = f"{p}_pop"
        if flag_col not in df.columns:
            raise KeyError(f"Columna requerida no encontrada: {flag_col}")
        flags = df[flag_col].fillna("").astype(str).str.strip()
        comprador_flags.append((flags == COMPRADOR_L3M).astype(np.int8))
        pop_cols.append(df[pop_col].to_numpy(dtype=float))

    comprador_mat = np.column_stack(comprador_flags)
    pop_mat = np.column_stack(pop_cols)

    out = df.copy()
    n = len(prefixes)
    out["n_partners_sel"] = n
    out["partners_compradores"] = comprador_mat.sum(axis=1)
    out["pop_promedio"] = pop_mat.mean(axis=1)
    out["cumple_comprador"] = (
        out["partners_compradores"] >= min_partners_compradores
    ).astype(np.int8)
    out["cumple_pop_alto"] = (out["pop_promedio"] >= umbral_pop).astype(np.int8)
    return out


def _color_grid(
    pct_compradores: pd.Series,
    pct_pop_alto: pd.Series,
    n_epicentros: pd.Series,
    umbral_pct: float,
    umbral_pct_pop: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    tiene_epic = n_epicentros >= 1
    sin_epic = n_epicentros == 0
    fuerte_comp = pct_compradores >= umbral_pct
    fuerte_pop = pct_pop_alto >= umbral_pct_pop

    # Prioridad: celeste > azul > verde > naranja > rojo
    es_celeste = tiene_epic & fuerte_pop
    es_azul = tiene_epic & fuerte_comp & ~es_celeste
    es_verde = sin_epic & fuerte_comp
    es_naranja = sin_epic & fuerte_pop & ~es_verde

    color = np.select(
        [es_celeste, es_azul, es_verde, es_naranja],
        [
            COLOR_GRILLA["celeste"],
            COLOR_GRILLA["azul"],
            COLOR_GRILLA["verde"],
            COLOR_GRILLA["naranja"],
        ],
        default=COLOR_GRILLA["rojo"],
    )

    etiqueta = np.select(
        [es_celeste, es_azul, es_verde, es_naranja],
        [
            ETIQUETA_GRILLA["celeste"],
            ETIQUETA_GRILLA["azul"],
            ETIQUETA_GRILLA["verde"],
            ETIQUETA_GRILLA["naranja"],
        ],
        default=ETIQUETA_GRILLA["rojo"],
    )

    intensidad = np.clip(
        np.maximum(pct_compradores.to_numpy(), pct_pop_alto.to_numpy()), 0, 1
    )

    return pd.Series(color), pd.Series(etiqueta), pd.Series(intensidad)


def aggregate_grids(
    df: pd.DataFrame,
    umbral_pct: float,
    umbral_pct_pop: float,
) -> pd.DataFrame:
    grid = df.groupby("grid_id", as_index=False).agg(
        grid_lat=("grid_lat", "first"),
        grid_lon=("grid_lon", "first"),
        total_clientes=("cliente_id", "count"),
        clientes_compradores=("cumple_comprador", "sum"),
        clientes_pop_alto=("cumple_pop_alto", "sum"),
        n_epicentros=("es_epicentro", "sum"),
        pop_promedio_grilla=("pop_promedio", "mean"),
    )

    grid = grid[grid["total_clientes"] >= MIN_CLIENTES_GRILLA].copy()
    grid["pct_compradores"] = grid["clientes_compradores"] / grid["total_clientes"]
    grid["pct_pop_alto"] = grid["clientes_pop_alto"] / grid["total_clientes"]

    color, etiqueta, intensidad = _color_grid(
        grid["pct_compradores"],
        grid["pct_pop_alto"],
        grid["n_epicentros"],
        umbral_pct,
        umbral_pct_pop,
    )
    grid["color_grilla"] = color.to_numpy()
    grid["etiqueta_zona"] = etiqueta.to_numpy()
    grid["intensidad"] = intensidad.to_numpy()

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
        out["intensidad"] * 100
        + out["n_epicentros"] * 10
        + out["total_clientes"]
    )
    return (
        out.sort_values("_prioridad", ascending=False)
        .head(max_grillas)
        .drop(columns="_prioridad")
    )
