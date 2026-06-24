from __future__ import annotations

import pandas as pd

from epicentros.config import CSV_EPICENTROS, CSV_MARKETPLACE, PARTNERS


def _coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def load_marketplace() -> pd.DataFrame:
    if not CSV_MARKETPLACE.is_file():
        raise FileNotFoundError(f"No se encontró: {CSV_MARKETPLACE}")

    df = pd.read_csv(CSV_MARKETPLACE, low_memory=False)
    df["cliente_id"] = df["cliente_id"].astype(str).str.strip()
    df = df.dropna(subset=["latitud", "longitud"])

    numeric_cols = [
        "latitud",
        "longitud",
        "total_soles_backus_l3m",
        "total_soles_marketplace_l3m",
    ]
    for prefix in PARTNERS.values():
        numeric_cols.extend(
            [f"{prefix}_cajas_l3m", f"{prefix}_nr_l3m", f"{prefix}_nr_prom_l3m"]
        )

    for prefix in PARTNERS.values():
        col = f"{prefix}_segmento_resumen"
        if col in df.columns:
            df[col] = df[col].fillna("No Comprador").astype(str).str.strip()

    return _coerce_numeric(df, numeric_cols)


def load_epicentros() -> pd.DataFrame:
    if not CSV_EPICENTROS.is_file():
        raise FileNotFoundError(f"No se encontró: {CSV_EPICENTROS}")

    df = pd.read_csv(CSV_EPICENTROS, low_memory=False)
    df["cliente_id"] = df["cliente_id"].astype(str).str.strip()
    return df.drop_duplicates(subset=["cliente_id"])


def merge_datasets(marketplace: pd.DataFrame, epicentros: pd.DataFrame) -> pd.DataFrame:
    cols_epic = ["cliente_id", "Epicentro", "Tipo", "Zona", "Supervisor"]
    cols_epic = [c for c in cols_epic if c in epicentros.columns]

    df = marketplace.merge(epicentros[cols_epic], on="cliente_id", how="left")
    df["epicentro"] = (
        df["Epicentro"].fillna("Sin Epicentro") if "Epicentro" in df.columns else "Sin Epicentro"
    )

    if "Tipo" in df.columns:
        tipo_norm = df["Tipo"].fillna("").astype(str).str.strip().str.upper()
        df["tipo"] = df["Tipo"].fillna("Sin Tipo").astype(str).str.strip()
        df["en_listado"] = (tipo_norm != "").astype(int)
        df["es_epicentro"] = (tipo_norm == "EPICENTRO").astype(int)
        df["es_gemelo"] = (tipo_norm == "GEMELO").astype(int)
        # Epicentro + Gemelo cuentan como POC del listado para grillas
        df["es_poc"] = ((tipo_norm == "EPICENTRO") | (tipo_norm == "GEMELO")).astype(int)
    else:
        df["tipo"] = "Sin Tipo"
        df["en_listado"] = 0
        df["es_epicentro"] = 0
        df["es_gemelo"] = 0
        df["es_poc"] = 0

    df["en_epicentro"] = df["en_listado"]
    return df


def load_full_dataset() -> pd.DataFrame:
    marketplace = load_marketplace()
    try:
        epicentros = load_epicentros()
        return merge_datasets(marketplace, epicentros)
    except FileNotFoundError:
        marketplace = marketplace.copy()
        marketplace["epicentro"] = "Sin Epicentro"
        marketplace["tipo"] = "Sin Tipo"
        marketplace["en_listado"] = 0
        marketplace["es_epicentro"] = 0
        marketplace["es_gemelo"] = 0
        marketplace["es_poc"] = 0
        marketplace["en_epicentro"] = 0
        return marketplace
