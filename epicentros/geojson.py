from __future__ import annotations

import json

import numpy as np
import pandas as pd

from epicentros.grid import get_grid_step


def grids_to_geojson(grid_stats: pd.DataFrame) -> dict:
    """GeoJSON vectorizado — todas las grillas con grid_i/grid_j."""
    if grid_stats.empty:
        return {"type": "FeatureCollection", "features": []}

    paso_lat, paso_lon = get_grid_step()
    gi = grid_stats["grid_i"].to_numpy(dtype=np.int64)
    gj = grid_stats["grid_j"].to_numpy(dtype=np.int64)

    half_lat = paso_lat * 0.5
    half_lon = paso_lon * 0.5
    eps_lat = paso_lat * 0.00125
    eps_lon = paso_lon * 0.00125

    lat_c = gi * paso_lat
    lon_c = gj * paso_lon
    lat_min = lat_c - half_lat - eps_lat
    lat_max = lat_c + half_lat + eps_lat
    lon_min = lon_c - half_lon - eps_lon
    lon_max = lon_c + half_lon + eps_lon

    colors = grid_stats["color_grilla"].to_numpy()
    etiquetas = grid_stats["etiqueta_zona"].to_numpy()
    clientes = grid_stats["total_clientes"].to_numpy(dtype=np.int64)
    pct_comp = np.round(grid_stats["pct_compradores"].to_numpy() * 100, 1)
    pct_pop = np.round(grid_stats["pct_pop_alto"].to_numpy() * 100, 1)
    n_epic = grid_stats["n_epicentros"].to_numpy(dtype=np.int64)
    pop_prom = np.round(grid_stats["pop_promedio_grilla"].to_numpy(), 3)
    intensidad = grid_stats["intensidad"].to_numpy(dtype=float)

    features = []
    append = features.append
    for idx in range(len(grid_stats)):
        lm, lM, ln, lN = lat_min[idx], lat_max[idx], lon_min[idx], lon_max[idx]
        ring = [
            [ln, lm],
            [lN, lm],
            [lN, lM],
            [ln, lM],
            [ln, lm],
        ]
        append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "color": colors[idx],
                    "etiqueta": etiquetas[idx],
                    "clientes": int(clientes[idx]),
                    "pct_comp": float(pct_comp[idx]),
                    "pct_pop": float(pct_pop[idx]),
                    "n_epic": int(n_epic[idx]),
                    "pop_prom": float(pop_prom[idx]),
                    "intensidad": float(intensidad[idx]),
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def grids_to_geojson_bytes(grid_stats: pd.DataFrame) -> bytes:
    return json.dumps(grids_to_geojson(grid_stats), separators=(",", ":")).encode()
