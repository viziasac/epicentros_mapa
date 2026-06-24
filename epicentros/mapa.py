from __future__ import annotations

import folium
import pandas as pd
from folium.plugins import MarkerCluster

from epicentros.config import COLOR_POC, GRID_SIZE_M, PARTNERS


def _grids_geojson(
    grid_stats: pd.DataFrame,
    paso_lat: float,
    paso_lon: float,
    min_partners_estables: int,
) -> dict:
    medio_lat = paso_lat / 2
    medio_lon = paso_lon / 2
    features = []

    for row in grid_stats.itertuples(index=False):
        lat, lon = float(row.grid_lat), float(row.grid_lon)
        ring = [
            [lon - medio_lon, lat - medio_lat],
            [lon + medio_lon, lat - medio_lat],
            [lon + medio_lon, lat + medio_lat],
            [lon - medio_lon, lat + medio_lat],
            [lon - medio_lon, lat - medio_lat],
        ]
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "color": row.color_grilla,
                    "etiqueta": row.etiqueta_zona,
                    "clientes": int(row.total_clientes),
                    "pct": round(float(row.pct_cumplen) * 100, 1),
                    "cumplen": int(row.clientes_cumplen),
                    "nr_mp": int(row.nr_marketplace),
                    "nr_backus": int(row.nr_backus),
                    "pocs": int(row.pocs_listado),
                    "min_est": min_partners_estables,
                },
            }
        )

    return {"type": "FeatureCollection", "features": features}


def _map_center(df: pd.DataFrame) -> tuple[float, float, int]:
    lat = float(df["latitud"].mean())
    lon = float(df["longitud"].mean())
    span = max(
        float(df["latitud"].max() - df["latitud"].min()),
        float(df["longitud"].max() - df["longitud"].min()),
    )
    if span > 8:
        zoom = 6
    elif span > 3:
        zoom = 8
    elif span > 1:
        zoom = 10
    else:
        zoom = 12
    return lat, lon, zoom


def build_map(
    df: pd.DataFrame,
    grid_stats: pd.DataFrame,
    paso_lat: float,
    paso_lon: float,
    selected_partners: list[str],
    min_partners_estables: int,
    show_pocs: bool = True,
    min_nr_mp_poc: float = 0.0,
    min_nr_backus_poc: float = 0.0,
) -> folium.Map:
    centro_lat, centro_lon, zoom = _map_center(df)

    m = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=zoom,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )

    if not grid_stats.empty:
        geojson = _grids_geojson(grid_stats, paso_lat, paso_lon, min_partners_estables)

        def style_fn(feature: dict) -> dict:
            color = feature["properties"]["color"]
            return {
                "fillColor": color,
                "color": "#374151",
                "weight": 1,
                "fillOpacity": 0.42,
            }

        folium.GeoJson(
            geojson,
            name=f"Grillas {GRID_SIZE_M}×{GRID_SIZE_M} m",
            style_function=style_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=["etiqueta", "clientes", "pct", "cumplen", "pocs", "nr_mp"],
                aliases=["Zona", "Clientes", "% estables", "Cumplen", "POCs listado", "NR MP"],
                localize=True,
            ),
        ).add_to(m)

    if show_pocs:
        pocs = df[df["es_poc"] == 1].copy()
        if min_nr_mp_poc > 0:
            pocs = pocs[pocs["total_soles_marketplace_l3m"] >= min_nr_mp_poc]
        if min_nr_backus_poc > 0:
            pocs = pocs[pocs["total_soles_backus_l3m"] >= min_nr_backus_poc]

        if not pocs.empty:
            _add_poc_layer(m, pocs, selected_partners, min_partners_estables)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def _add_poc_layer(
    m: folium.Map,
    pocs: pd.DataFrame,
    selected_partners: list[str],
    min_partners_estables: int,
) -> None:
    fg = folium.FeatureGroup(name="POCs listado", show=True)
    cluster = MarkerCluster(
        disableClusteringAtZoom=14,
        maxClusterRadius=40,
        spiderfyOnMaxZoom=True,
    ).add_to(fg)

    for row in pocs.itertuples(index=False):
        is_epic = bool(row.es_epicentro)
        fill = COLOR_POC["epicentro"] if is_epic else COLOR_POC["gemelo"]
        rol = "Epicentro" if is_epic else "Gemelo"
        html = (
            f"<div style='font-size:13px;min-width:180px'>"
            f"<b>{rol}</b> · {row.cliente_id}<br>"
            f"<b>Zona:</b> {row.epicentro}<br>"
            f"<b>Canal:</b> {row.canal}<br>"
            f"<b>Estables:</b> {int(row.partners_estables)}/"
            f"{int(row.n_partners_sel)} (mín. {min_partners_estables})<br>"
            f"{_partner_lines(row, selected_partners)}"
            f"<b>NR Backus:</b> S/ {row.total_soles_backus_l3m:,.0f}<br>"
            f"<b>NR MP:</b> S/ {row.total_soles_marketplace_l3m:,.0f}"
            f"</div>"
        )
        folium.CircleMarker(
            location=[float(row.latitud), float(row.longitud)],
            radius=9 if is_epic else 7,
            color="#ffffff",
            fill=True,
            fill_color=fill,
            fill_opacity=1.0,
            weight=2.5,
            tooltip=folium.Tooltip(html, sticky=True),
        ).add_to(cluster)

    fg.add_to(m)


def _partner_lines(row, selected_partners: list[str]) -> str:
    lines = []
    for name in selected_partners:
        p = PARTNERS[name]
        seg = getattr(row, f"{p}_segmento_resumen", "No Comprador")
        nr = getattr(row, f"{p}_nr_l3m", 0)
        lines.append(f"<b>{name}:</b> {seg} (S/ {nr:,.0f})<br>")
    return "".join(lines)
