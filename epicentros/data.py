from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path

import pandas as pd

from epicentros.config import (
    CACHE_DIR,
    COMPRADOR_L3M,
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


def _coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


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


def _prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
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
    for prefix in PARTNERS.values():
        numeric_cols.extend(
            [f"{prefix}_cajas_l3m", f"{prefix}_nr_l3m", f"{prefix}_pop"]
        )

    df = _coerce_numeric(df, numeric_cols)

    for prefix in PARTNERS.values():
        col = f"{prefix}_flag_comprador_l3m"
        if col in df.columns:
            df[col] = df[col].fillna(NO_COMPRADOR_L3M).astype(str).str.strip()

    df["es_epicentro"] = df["flag_epicentro"].astype(int)
    df, _, _ = assign_grid_columns(df)
    return df


def _load_from_csv(path: Path) -> pd.DataFrame:
    return _prepare_dataframe(pd.read_csv(path, low_memory=False))


def _load_from_parquet(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    if "grid_id" not in df.columns:
        df = _prepare_dataframe(df)
    else:
        set_grid_step_from_dataframe(df)
        df = ensure_grid_indices(df)
    return df


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
