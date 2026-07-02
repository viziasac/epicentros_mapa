from __future__ import annotations

import numpy as np
import pandas as pd

from epicentros.config import GRID_SIZE_M


def grid_step(lat_mean: float) -> tuple[float, float]:
    paso_lat = GRID_SIZE_M / 111_320
    paso_lon = paso_lat / np.cos(np.radians(lat_mean))
    return paso_lat, paso_lon


def assign_grid_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, float, float]:
    """Asigna grid_lat, grid_lon y grid_id una sola vez al cargar datos."""
    paso_lat, paso_lon = grid_step(float(df["latitud"].mean()))
    out = df.copy()
    out["grid_lat"] = (out["latitud"] / paso_lat).round() * paso_lat
    out["grid_lon"] = (out["longitud"] / paso_lon).round() * paso_lon
    out["grid_id"] = (
        out["grid_lat"].map(lambda x: f"{x:.6f}")
        + "_"
        + out["grid_lon"].map(lambda x: f"{x:.6f}")
    )
    return out, paso_lat, paso_lon
