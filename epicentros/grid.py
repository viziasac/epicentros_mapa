from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from epicentros import config
from epicentros.config import GRID_SIZE_M

GRID_META_NAME = "grid_meta.json"


def grid_step(lat_mean: float) -> tuple[float, float]:
    paso_lat = GRID_SIZE_M / 111_320
    paso_lon = paso_lat / np.cos(np.radians(lat_mean))
    return paso_lat, paso_lon


def meta_path(data_dir: Path | None = None) -> Path:
    base = data_dir or config.DATA_DIR
    return base / GRID_META_NAME


def save_grid_meta(
    paso_lat: float,
    paso_lon: float,
    ref_lat: float,
    path: Path | None = None,
) -> None:
    target = path or meta_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "grid_size_m": GRID_SIZE_M,
        "paso_lat": paso_lat,
        "paso_lon": paso_lon,
        "ref_lat": ref_lat,
    }
    target.write_text(json.dumps(payload), encoding="utf-8")
    apply_grid_meta(payload)


def load_grid_meta(path: Path | None = None) -> dict | None:
    target = path or meta_path()
    if not target.is_file():
        alt = config.ROOT_DIR / "data" / GRID_META_NAME
        target = alt if alt.is_file() else target
    if not target.is_file():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def apply_grid_meta(meta: dict) -> tuple[float, float]:
    config.GRID_PASO_LAT = float(meta["paso_lat"])
    config.GRID_PASO_LON = float(meta["paso_lon"])
    config.GRID_REF_LAT = float(meta.get("ref_lat", config.GRID_REF_LAT))
    return config.GRID_PASO_LAT, config.GRID_PASO_LON


def set_grid_step_from_dataframe(df: pd.DataFrame) -> tuple[float, float]:
    meta = load_grid_meta()
    if meta and int(meta.get("grid_size_m", 0)) == GRID_SIZE_M:
        return apply_grid_meta(meta)

    lat_mean = float(df["latitud"].mean())
    paso_lat, paso_lon = grid_step(lat_mean)
    config.GRID_PASO_LAT = paso_lat
    config.GRID_PASO_LON = paso_lon
    config.GRID_REF_LAT = lat_mean
    save_grid_meta(paso_lat, paso_lon, lat_mean)
    return paso_lat, paso_lon


def get_grid_step() -> tuple[float, float]:
    if config.GRID_PASO_LAT is not None and config.GRID_PASO_LON is not None:
        return config.GRID_PASO_LAT, config.GRID_PASO_LON
    meta = load_grid_meta()
    if meta:
        return apply_grid_meta(meta)
    return grid_step(config.GRID_REF_LAT)


def ensure_grid_indices(df: pd.DataFrame) -> pd.DataFrame:
    paso_lat, paso_lon = get_grid_step()
    out = df
    if "grid_i" not in out.columns or "grid_j" not in out.columns:
        out = out.copy()
        if "grid_lat" in out.columns and "grid_lon" in out.columns:
            out["grid_i"] = np.rint(out["grid_lat"].to_numpy(float) / paso_lat).astype(np.int64)
            out["grid_j"] = np.rint(out["grid_lon"].to_numpy(float) / paso_lon).astype(np.int64)
        else:
            out["grid_i"] = np.rint(out["latitud"].to_numpy(float) / paso_lat).astype(np.int64)
            out["grid_j"] = np.rint(out["longitud"].to_numpy(float) / paso_lon).astype(np.int64)
            out["grid_lat"] = out["grid_i"] * paso_lat
            out["grid_lon"] = out["grid_j"] * paso_lon
    if "grid_id" not in out.columns:
        out = out.copy()
        out["grid_id"] = out["grid_i"].astype(str) + "_" + out["grid_j"].astype(str)
    return out


def cell_bounds(
    grid_i: int,
    grid_j: int,
    paso_lat: float,
    paso_lon: float,
) -> tuple[float, float, float, float]:
    """Esquina SW y NE de la celda (índices enteros → sin drift float)."""
    half_lat = paso_lat * 0.5
    half_lon = paso_lon * 0.5
    lat_c = grid_i * paso_lat
    lon_c = grid_j * paso_lon
    return (
        lat_c - half_lat,
        lon_c - half_lon,
        lat_c + half_lat,
        lon_c + half_lon,
    )


def cell_ring(
    grid_i: int,
    grid_j: int,
    paso_lat: float,
    paso_lon: float,
) -> list[list[float]]:
    lat_min, lon_min, lat_max, lon_max = cell_bounds(
        grid_i, grid_j, paso_lat, paso_lon
    )
    # Solape mínimo (~0.5 m) para evitar líneas blancas entre polígonos en Leaflet
    eps_lat = paso_lat * 0.00125
    eps_lon = paso_lon * 0.00125
    return [
        [lon_min - eps_lon, lat_min - eps_lat],
        [lon_max + eps_lon, lat_min - eps_lat],
        [lon_max + eps_lon, lat_max + eps_lat],
        [lon_min - eps_lon, lat_max + eps_lat],
        [lon_min - eps_lon, lat_min - eps_lat],
    ]


def assign_grid_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    paso_lat, paso_lon = set_grid_step_from_dataframe(df)
    out = df.copy()
    out["grid_i"] = np.rint(out["latitud"].to_numpy(dtype=float) / paso_lat).astype(np.int64)
    out["grid_j"] = np.rint(out["longitud"].to_numpy(dtype=float) / paso_lon).astype(np.int64)
    out["grid_lat"] = out["grid_i"] * paso_lat
    out["grid_lon"] = out["grid_j"] * paso_lon
    out["grid_id"] = out["grid_i"].astype(str) + "_" + out["grid_j"].astype(str)
    return out, paso_lat, paso_lon
