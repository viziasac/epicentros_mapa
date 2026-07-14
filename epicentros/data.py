from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from epicentros.config import (
    CACHE_DIR,
    CSV_FOCO_REDBULL,
    CSV_FULL,
    ENV_DATA_URL,
    NO_COMPRADOR_L3M,
    PARQUET_BUNDLED,
    PARQUET_FULL,
    PARQUET_LOCAL,
    PARTNERS,
    data_setup_hint,
)
from epicentros.grid import assign_grid_columns, ensure_grid_indices, set_grid_step_from_dataframe

_PARTNER_PREFIXES = tuple(PARTNERS.values())


def _coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def _required_columns() -> list[str]:
    cols = [
        "cliente_id",
        "latitud",
        "longitud",
        "flag_epicentro",
        "canal",
        "gerencia",
        "total_soles_backus_l3m",
        "total_soles_marketplace_l3m",
    ]
    for prefix in _PARTNER_PREFIXES:
        cols.append(f"{prefix}_flag_comprador_l3m")
        cols.append(f"{prefix}_pop")
    return cols


def _validate_schema(df: pd.DataFrame) -> None:
    missing = [c for c in _required_columns() if c not in df.columns]
    if missing:
        raise KeyError(
            "Dataset incompleto. Faltan columnas: " + ", ".join(missing[:12])
            + ("…" if len(missing) > 12 else "")
        )


def _remote_data_url() -> str | None:
    url = os.environ.get(ENV_DATA_URL, "").strip()
    if url:
        return url
    try:
        import streamlit as st

        data_secrets = st.secrets.get("data", {})
        return (
            data_secrets.get("parquet_url")
            or data_secrets.get("csv_url")
            or data_secrets.get("url")
        )
    except Exception:
        return None


def _download_remote(url: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ext = ".parquet" if ".parquet" in url.lower() else ".csv"
    name = hashlib.md5(url.encode()).hexdigest()[:16]
    dest = CACHE_DIR / f"remote_{name}{ext}"
    if not dest.is_file():
        urllib.request.urlretrieve(url, dest)
    return dest


def _load_foco_redbull_ids() -> set[str]:
    path = CSV_FOCO_REDBULL
    if not path.is_file():
        return set()
    foco = pd.read_csv(path, usecols=["cliente_id"])
    return set(foco["cliente_id"].astype(str).str.strip())


def _attach_foco_redbull(df: pd.DataFrame) -> pd.DataFrame:
    """Left join lógico: marca clientes presentes en clientes_foco_redbull."""
    out = df.copy(deep=False)
    out["cliente_id"] = out["cliente_id"].astype(str).str.strip()
    foco_ids = _load_foco_redbull_ids()
    out["es_foco_redbull"] = out["cliente_id"].isin(foco_ids).astype("int8")
    return out


def _normalize_partner_flags(df: pd.DataFrame) -> pd.DataFrame:
    from epicentros.config import COMPRADOR_L3M

    for prefix in _PARTNER_PREFIXES:
        col = f"{prefix}_flag_comprador_l3m"
        if col not in df.columns:
            continue
        cleaned = df[col].fillna(NO_COMPRADOR_L3M).astype(str).str.strip()
        upper = cleaned.str.casefold()
        is_buyer = upper.isin({"comprador l3m", "comprador"})
        df[col] = np.where(is_buyer, COMPRADOR_L3M, NO_COMPRADOR_L3M)
    return df


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    _validate_schema(df)
    df = df.copy()
    df["cliente_id"] = df["cliente_id"].astype(str).str.strip()
    df = df.dropna(subset=["latitud", "longitud"])

    numeric_cols = [
        "latitud",
        "longitud",
        "total_soles_backus_l3m",
        "total_soles_marketplace_l3m",
        "flag_epicentro",
    ]
    for prefix in _PARTNER_PREFIXES:
        numeric_cols.extend(
            [f"{prefix}_cajas_l3m", f"{prefix}_nr_l3m", f"{prefix}_pop"]
        )

    df = _coerce_numeric(df, numeric_cols)
    df = _normalize_partner_flags(df)
    df["es_epicentro"] = (df["flag_epicentro"].fillna(0).astype(int) > 0).astype("int8")
    df, _, _ = assign_grid_columns(df)
    return _attach_foco_redbull(df)


def _ensure_parquet_runtime(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza columnas críticas si el parquet viene preprocesado."""
    _validate_schema(df)
    out = df
    if "es_epicentro" not in out.columns:
        out = out.copy(deep=False)
        out["es_epicentro"] = (
            out["flag_epicentro"].fillna(0).astype(int) > 0
        ).astype("int8")
    # Flags ya deberían venir limpios del export; re-strip liviano si hace falta
    for prefix in _PARTNER_PREFIXES:
        col = f"{prefix}_flag_comprador_l3m"
        sample = out[col].iloc[0] if len(out) else ""
        if isinstance(sample, str) and sample not in (
            "Comprador L3M",
            "No Comprador L3M",
        ):
            out = _normalize_partner_flags(out.copy(deep=False))
            break
    set_grid_step_from_dataframe(out)
    out = ensure_grid_indices(out)
    return _attach_foco_redbull(out)


def _load_from_csv(path: Path) -> pd.DataFrame:
    return _prepare_dataframe(pd.read_csv(path, low_memory=False))


def _load_from_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "grid_id" not in df.columns:
        return _prepare_dataframe(df)
    return _ensure_parquet_runtime(df)


def _load_from_path(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".parquet":
        return _load_from_parquet(path)
    return _load_from_csv(path)


def _resolve_local_parquet() -> Path | None:
    for path in (PARQUET_BUNDLED, PARQUET_FULL, PARQUET_LOCAL):
        if path.is_file():
            return path
    return None


def load_full_dataset() -> pd.DataFrame:
    remote = _remote_data_url()
    if remote:
        return _load_from_path(_download_remote(remote))

    parquet_path = _resolve_local_parquet()
    if parquet_path is not None:
        if not CSV_FULL.is_file() or parquet_path.stat().st_mtime >= CSV_FULL.stat().st_mtime:
            try:
                return _load_from_parquet(parquet_path)
            except Exception:
                pass

    if CSV_FULL.is_file():
        df = _load_from_csv(CSV_FULL)
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            out = PARQUET_LOCAL
            df.to_parquet(out, index=False)
        except Exception:
            pass
        return df

    raise FileNotFoundError(
        f"No se encontró dataset. {data_setup_hint()}"
    )
