from __future__ import annotations

import re

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
    """Prefijos en orden canónico de PARTNERS (estable y sin duplicados)."""
    selected = set(selected_partners)
    return [pref for name, pref in PARTNERS.items() if name in selected]


def compute_client_metrics(
    df: pd.DataFrame,
    prefixes: list[str],
    min_partners_compradores: int,
    umbral_pop: float,
) -> pd.DataFrame:
    if not prefixes:
        raise ValueError("Selecciona al menos un partner.")

    n = len(df)
    k = len(prefixes)
    comprador_mat = np.empty((n, k), dtype=np.int8)
    pop_mat = np.empty((n, k), dtype=np.float64)

    for i, p in enumerate(prefixes):
        flag_col = f"{p}_flag_comprador_l3m"
        pop_col = f"{p}_pop"
        if flag_col not in df.columns:
            raise KeyError(f"Columna requerida no encontrada: {flag_col}")
        if pop_col not in df.columns:
            raise KeyError(f"Columna requerida no encontrada: {pop_col}")

        flags = df[flag_col].to_numpy()
        comprador_mat[:, i] = np.asarray(flags == COMPRADOR_L3M, dtype=np.int8)
        pop_mat[:, i] = pd.to_numeric(df[pop_col], errors="coerce").fillna(0).to_numpy(
            dtype=np.float64
        )

    min_req = max(1, min(int(min_partners_compradores), k))
    partners_compradores = comprador_mat.sum(axis=1)
    pop_promedio = pop_mat.mean(axis=1)

    out = df.copy(deep=False)
    out["n_partners_sel"] = k
    out["partners_compradores"] = partners_compradores
    out["pop_promedio"] = pop_promedio
    out["cumple_comprador"] = (partners_compradores >= min_req).astype(np.int8)
    out["cumple_pop_alto"] = (pop_promedio >= float(umbral_pop)).astype(np.int8)
    return out


def _color_grid(
    pct_compradores: pd.Series,
    pct_pop_alto: pd.Series,
    n_epicentros: pd.Series,
    umbral_pct: float,
    umbral_pct_pop: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tiene_epic = n_epicentros.to_numpy() >= 1
    sin_epic = ~tiene_epic
    fuerte_comp = pct_compradores.to_numpy() >= umbral_pct
    fuerte_pop = pct_pop_alto.to_numpy() >= umbral_pct_pop

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
    return color, etiqueta, intensidad


def aggregate_grids(
    df: pd.DataFrame,
    umbral_pct: float,
    umbral_pct_pop: float,
) -> pd.DataFrame:
    grid = df.groupby(["grid_i", "grid_j"], as_index=False, sort=False).agg(
        grid_lat=("grid_lat", "first"),
        grid_lon=("grid_lon", "first"),
        total_clientes=("cliente_id", "count"),
        clientes_compradores=("cumple_comprador", "sum"),
        clientes_pop_alto=("cumple_pop_alto", "sum"),
        n_epicentros=("es_epicentro", "sum"),
        pop_promedio_grilla=("pop_promedio", "mean"),
    )

    grid = grid.loc[grid["total_clientes"] >= MIN_CLIENTES_GRILLA].copy()
    if grid.empty:
        return grid

    grid["grid_id"] = (
        grid["grid_i"].astype(str) + "_" + grid["grid_j"].astype(str)
    )
    total = grid["total_clientes"].to_numpy(dtype=float)
    grid["pct_compradores"] = grid["clientes_compradores"].to_numpy(dtype=float) / total
    grid["pct_pop_alto"] = grid["clientes_pop_alto"].to_numpy(dtype=float) / total

    color, etiqueta, intensidad = _color_grid(
        grid["pct_compradores"],
        grid["pct_pop_alto"],
        grid["n_epicentros"],
        umbral_pct,
        umbral_pct_pop,
    )
    grid["color_grilla"] = color
    grid["etiqueta_zona"] = etiqueta
    grid["intensidad"] = intensidad
    return grid


_DASH_PATTERN = re.compile(r"[\u2010-\u2015\-–—]")


def _normalize_dashes(text: str) -> str:
    return _DASH_PATTERN.sub("—", text.strip())


def canonical_etiqueta(label: str) -> str | None:
    """Mapea variantes de guión / etiquetas viejas a la etiqueta canónica."""
    if not label:
        return None
    raw = label.strip()
    if raw in ETIQUETA_GRILLA.values():
        return raw
    normalized = _normalize_dashes(raw)
    for canon in ETIQUETA_GRILLA.values():
        if _normalize_dashes(canon) == normalized:
            return canon
    return None


def canonical_etiquetas(labels: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for label in labels:
        canon = canonical_etiqueta(label)
        if canon and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def filter_grids_by_color(grid: pd.DataFrame, colores_sel: list[str] | None) -> pd.DataFrame:
    if not colores_sel:
        return grid
    canon = canonical_etiquetas(colores_sel)
    if not canon:
        return grid
    return grid.loc[grid["etiqueta_zona"].isin(canon)].copy()


def limit_grids_for_render(
    grid: pd.DataFrame, max_grillas: int = MAX_GRILLAS_RENDER
) -> pd.DataFrame:
    """max_grillas <= 0 → sin límite (todas las grillas elegibles)."""
    if max_grillas <= 0 or len(grid) <= max_grillas:
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
