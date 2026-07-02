from __future__ import annotations

import folium
import pandas as pd
from branca.element import MacroElement
from folium.plugins import MarkerCluster
from jinja2 import Template

from epicentros.config import COLOR_GRILLA, COLOR_POC, ETIQUETA_GRILLA, GRID_SIZE_M, PARTNERS
from epicentros.grid import cell_ring

_COLOR_ORDER = ("verde", "azul", "celeste", "naranja", "rojo")


class MapLegend(MacroElement):
    """Leyenda HTML anclada al mapa (no al viewport del navegador)."""

    def __init__(
        self,
        items: list[dict],
        *,
        show_pocs: bool = True,
        grid_size_m: int = GRID_SIZE_M,
    ):
        super().__init__()
        self._name = "MapLegend"

        rows = []
        for item in items:
            rows.append(
                f'<div style="display:flex;align-items:flex-start;gap:10px;margin:8px 0">'
                f'<span style="flex-shrink:0;width:22px;height:22px;border-radius:4px;'
                f'background:{item["color"]};border:2px solid #1f2937;'
                f'margin-top:1px"></span>'
                f'<div style="line-height:1.35">'
                f'<div style="font-weight:700;font-size:14px;color:#111827">{item["title"]}</div>'
                f'<div style="font-size:12px;color:#4b5563">{item["desc"]}</div>'
                f'<div style="font-size:12px;font-weight:600;color:#374151;margin-top:2px">'
                f'{item["count"]:,} grillas · {item["pct"]:.1f}%</div>'
                f"</div></div>"
            )

        poc_block = ""
        if show_pocs:
            poc_block = (
                '<div style="border-top:1px solid #e5e7eb;margin-top:10px;padding-top:10px">'
                '<div style="font-weight:700;font-size:13px;margin-bottom:6px">POCs epicentro</div>'
                f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px">'
                f'<span style="width:14px;height:14px;border-radius:50%;background:{COLOR_POC};'
                f'border:2px solid #fff;box-shadow:0 0 0 1px #333"></span>Comprador</div>'
                '<div style="display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px">'
                '<span style="width:14px;height:14px;border-radius:50%;background:#06b6d4;'
                'border:2px solid #fff;box-shadow:0 0 0 1px #333"></span>POP alto</div>'
                '<div style="display:flex;align-items:center;gap:8px;margin:4px 0;font-size:12px">'
                '<span style="width:14px;height:14px;border-radius:50%;background:#9ca3af;'
                'border:2px solid #fff;box-shadow:0 0 0 1px #333"></span>Otros</div>'
                '<div style="font-size:11px;color:#6b7280;margin-top:4px">Tamaño ∝ POP</div>'
                "</div>"
            )

        rows_html = "".join(rows)
        self._template = Template(
            f"""
            {{% macro html(this, kwargs) %}}
            <div id="epicentros-legend" style="
              position:absolute;bottom:14px;left:14px;z-index:9999;
              background:rgba(255,255,255,0.97);padding:14px 16px;
              border-radius:10px;border:2px solid #d1d5db;
              box-shadow:0 4px 16px rgba(0,0,0,0.18);
              font-family:system-ui,-apple-system,Segoe UI,sans-serif;
              min-width:300px;max-width:340px;max-height:88%;
              overflow-y:auto;pointer-events:auto;">
              <div style="font-size:16px;font-weight:800;color:#111827;margin-bottom:4px">
                Leyenda de colores
              </div>
              <div style="font-size:11px;color:#6b7280;margin-bottom:6px">
                Grilla {grid_size_m}×{grid_size_m} m · opacidad = intensidad
              </div>
              {rows_html}
              {poc_block}
            </div>
            {{% endmacro %}}
            """
        )


def _legend_items(
    grid_stats: pd.DataFrame,
    umbral_pct: float,
    umbral_pct_pop: float,
    umbral_pop: float,
) -> list[dict]:
    counts = grid_stats.groupby("etiqueta_zona").size().to_dict() if not grid_stats.empty else {}
    total = len(grid_stats) or 1

    descriptions = {
        "verde": f"Sin epicentro · ≥{umbral_pct:.0%} clientes compradores",
        "azul": f"Con epicentro · ≥{umbral_pct:.0%} clientes compradores",
        "celeste": (
            f"Con epicentro · ≥{umbral_pct_pop:.0%} clientes con POP ≥{umbral_pop:.2f}"
        ),
        "naranja": (
            f"Sin epicentro · ≥{umbral_pct_pop:.0%} clientes con POP ≥{umbral_pop:.2f}"
        ),
        "rojo": "No cumple ninguna condición anterior",
    }
    titles = {
        "verde": "Verde",
        "azul": "Azul",
        "celeste": "Celeste",
        "naranja": "Naranja",
        "rojo": "Rojo",
    }

    items = []
    for key in _COLOR_ORDER:
        label = ETIQUETA_GRILLA[key]
        count = int(counts.get(label, 0))
        items.append(
            {
                "color": COLOR_GRILLA[key],
                "title": titles[key],
                "desc": descriptions[key],
                "count": count,
                "pct": count / total * 100,
            }
        )
    return items


def _grid_polygons_geojson(
    grid_stats: pd.DataFrame,
    paso_lat: float,
    paso_lon: float,
) -> dict:
    features = []
    has_idx = "grid_i" in grid_stats.columns and "grid_j" in grid_stats.columns

    for row in grid_stats.itertuples(index=False):
        if has_idx:
            ring = cell_ring(int(row.grid_i), int(row.grid_j), paso_lat, paso_lon)
        else:
            gi = int(round(float(row.grid_lat) / paso_lat))
            gj = int(round(float(row.grid_lon) / paso_lon))
            ring = cell_ring(gi, gj, paso_lat, paso_lon)

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "color": row.color_grilla,
                    "etiqueta": row.etiqueta_zona,
                    "clientes": int(row.total_clientes),
                    "pct_comp": round(float(row.pct_compradores) * 100, 1),
                    "pct_pop": round(float(row.pct_pop_alto) * 100, 1),
                    "n_epic": int(row.n_epicentros),
                    "pop_prom": round(float(row.pop_promedio_grilla), 3),
                    "intensidad": float(row.intensidad),
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
        0.01,
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
    min_partners_compradores: int,
    umbral_pct: float,
    umbral_pct_pop: float,
    umbral_pop: float,
    show_pocs: bool = True,
) -> folium.Map:
    centro_lat, centro_lon, zoom = _map_center(df)

    m = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=zoom,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )

    if not grid_stats.empty:
        geojson = _grid_polygons_geojson(grid_stats, paso_lat, paso_lon)

        def style_fn(feature: dict) -> dict:
            props = feature["properties"]
            color = props["color"]
            intensity = float(props.get("intensidad", 0.5))
            opacity = 0.28 + 0.52 * intensity
            return {
                "fillColor": color,
                "color": color,
                "weight": 0,
                "stroke": False,
                "fillOpacity": opacity,
            }

        folium.GeoJson(
            geojson,
            name=f"Grillas {GRID_SIZE_M}m",
            style_function=style_fn,
            tooltip=folium.GeoJsonTooltip(
                fields=["etiqueta", "clientes", "pct_comp", "pct_pop", "n_epic", "pop_prom"],
                aliases=["Zona", "Clientes", "% compradores", "% POP alto", "Epicentros", "POP prom."],
                localize=True,
            ),
        ).add_to(m)

    legend_items = _legend_items(grid_stats, umbral_pct, umbral_pct_pop, umbral_pop)
    m.get_root().add_child(MapLegend(legend_items, show_pocs=show_pocs))

    if show_pocs:
        pocs = df[df["es_epicentro"] == 1]
        if not pocs.empty:
            fg = folium.FeatureGroup(name="POCs Epicentro", show=True)
            cluster = MarkerCluster(
                disableClusteringAtZoom=14,
                maxClusterRadius=40,
                spiderfyOnMaxZoom=True,
            ).add_to(fg)

            for row in pocs.itertuples(index=False):
                pop = float(row.pop_promedio)
                radius = 7 + min(pop, 1.0) * 5
                comprador = bool(row.cumple_comprador)
                fill = "#06b6d4" if row.cumple_pop_alto else (
                    COLOR_POC if comprador else "#9ca3af"
                )
                html = (
                    f"<div style='font-size:13px'>"
                    f"<b>Epicentro</b> · {row.cliente_id}<br>"
                    f"<b>Canal:</b> {row.canal}<br>"
                    f"<b>Comprador:</b> {'Sí' if comprador else 'No'} "
                    f"({int(row.partners_compradores)}/{int(row.n_partners_sel)})<br>"
                    f"{_partner_lines(row, selected_partners)}"
                    f"<b>POP prom.:</b> {pop:.3f}<br>"
                    f"<b>NR Backus:</b> S/ {row.total_soles_backus_l3m:,.0f}<br>"
                    f"<b>NR MP:</b> S/ {row.total_soles_marketplace_l3m:,.0f}"
                    f"</div>"
                )
                folium.CircleMarker(
                    location=[float(row.latitud), float(row.longitud)],
                    radius=radius,
                    color="#ffffff",
                    fill=True,
                    fill_color=fill,
                    fill_opacity=1.0,
                    weight=2.5,
                    tooltip=folium.Tooltip(html, sticky=True),
                ).add_to(cluster)
            fg.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def _partner_lines(row, selected_partners: list[str]) -> str:
    lines = []
    for name in selected_partners:
        p = PARTNERS[name]
        flag = getattr(row, f"{p}_flag_comprador_l3m", "No Comprador L3M")
        pop = getattr(row, f"{p}_pop", 0)
        lines.append(f"<b>{name}:</b> {flag} · POP {pop:.3f}<br>")
    return "".join(lines)
