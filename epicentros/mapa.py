from __future__ import annotations

import html
import uuid

import folium
import pandas as pd
from branca.element import MacroElement
from folium.plugins import MarkerCluster
from jinja2 import Template

from epicentros.config import (
    COLOR_GRILLA,
    COLOR_POC,
    COLOR_POC_FOCO,
    ETIQUETA_GRILLA,
    GRID_SIZE_M,
    PARTNERS,
)
from epicentros.geojson import grids_to_geojson

_COLOR_ORDER = ("verde", "azul", "celeste", "naranja", "rojo")


class MapLegend(MacroElement):
    """Leyenda compacta, colapsable y filtrada por lo visible en el mapa."""

    def __init__(
        self,
        items: list[dict],
        *,
        show_pocs: bool = True,
        show_pocs_foco: bool = True,
        n_pocs: int = 0,
        n_foco: int = 0,
        grid_size_m: int = GRID_SIZE_M,
        start_open: bool = False,
    ):
        super().__init__()
        self._name = "MapLegend"
        legend_id = f"epic-legend-{uuid.uuid4().hex[:8]}"

        rows = []
        for item in items:
            title = html.escape(str(item["title"]))
            desc = html.escape(str(item["desc"]))
            color = html.escape(str(item["color"]))
            rows.append(
                f'<div style="display:flex;gap:10px;margin:0 0 10px 0;align-items:flex-start">'
                f'<span style="flex-shrink:0;width:14px;height:14px;margin-top:2px;'
                f'border-radius:3px;background:{color};border:1px solid #111827"></span>'
                f'<div style="flex:1;min-width:0">'
                f'<div style="display:flex;justify-content:space-between;gap:8px;'
                f'align-items:baseline">'
                f'<div style="font-weight:800;font-size:13px;color:#111827">{title}</div>'
                f'<div style="flex-shrink:0;font-size:11px;font-weight:700;color:#374151">'
                f'{item["count"]:,} · {item["pct"]:.0f}%</div>'
                f"</div>"
                f'<div style="font-size:11px;line-height:1.4;color:#4b5563;margin-top:2px;'
                f'white-space:normal">{desc}</div>'
                f"</div></div>"
            )

        extras = []
        if show_pocs and n_pocs > 0:
            extras.append(
                f'<div style="display:flex;gap:10px;margin:0 0 8px 0;align-items:flex-start">'
                f'<span style="flex-shrink:0;width:14px;height:14px;margin-top:2px;'
                f'border-radius:50%;background:{COLOR_POC};border:1px solid #fff;'
                f'box-shadow:0 0 0 1px #333"></span>'
                f'<div style="flex:1">'
                f'<div style="display:flex;justify-content:space-between;gap:8px">'
                f'<div style="font-weight:800;font-size:12px;color:#111827">POC epicentro</div>'
                f'<div style="font-size:11px;font-weight:700;color:#374151">{n_pocs:,}</div>'
                f"</div>"
                f'<div style="font-size:11px;line-height:1.4;color:#4b5563;margin-top:2px">'
                f"Cliente marcado como epicentro. Azul = comprador; celeste = POP alto; "
                f"gris = resto. El tamaño del punto crece con el POP.</div>"
                f"</div></div>"
            )
        if show_pocs_foco and n_foco > 0:
            extras.append(
                f'<div style="display:flex;gap:10px;margin:0 0 8px 0;align-items:flex-start">'
                f'<span style="flex-shrink:0;width:14px;height:14px;margin-top:2px;'
                f'border-radius:50%;background:{COLOR_POC_FOCO};border:1px solid #fff;'
                f'box-shadow:0 0 0 1px #333"></span>'
                f'<div style="flex:1">'
                f'<div style="display:flex;justify-content:space-between;gap:8px">'
                f'<div style="font-weight:800;font-size:12px;color:#111827">POC Foco Red Bull</div>'
                f'<div style="font-size:11px;font-weight:700;color:#374151">{n_foco:,}</div>'
                f"</div>"
                f'<div style="font-size:11px;line-height:1.4;color:#4b5563;margin-top:2px">'
                f"Cliente incluido en el listado de foco Red Bull "
                f"(emparejado por cliente_id).</div>"
                f"</div></div>"
            )

        body_parts = []
        if rows:
            body_parts.append(
                f'<div style="font-size:10px;color:#6b7280;margin-bottom:8px;line-height:1.35">'
                f"Celdas de {grid_size_m}×{grid_size_m} m. Prioridad de color: "
                f"celeste → azul → verde → naranja → rojo. "
                f"Solo se listan colores visibles con el filtro actual.</div>"
            )
            body_parts.append("".join(rows))
        if extras:
            if rows:
                body_parts.append(
                    '<div style="border-top:1px solid #e5e7eb;margin:4px 0 8px"></div>'
                    '<div style="font-size:10px;font-weight:700;color:#6b7280;'
                    'margin-bottom:6px;text-transform:uppercase;letter-spacing:0.03em">'
                    "Puntos en el mapa</div>"
                )
            body_parts.append("".join(extras))

        if not body_parts:
            body_html = (
                '<div style="font-size:12px;color:#6b7280">Sin capas visibles</div>'
            )
        else:
            body_html = "".join(body_parts)

        open_attr = " open" if start_open else ""
        n_colors = len(items)
        summary_hint = f"{n_colors} color{'es' if n_colors != 1 else ''}"
        if n_pocs and show_pocs:
            summary_hint += " · epicentro"
        if n_foco and show_pocs_foco:
            summary_hint += " · foco"

        self._template = Template(
            f"""
            {{% macro html(this, kwargs) %}}
            <details id="{legend_id}"{open_attr} style="
              position:absolute;bottom:12px;left:12px;z-index:9999;
              background:rgba(255,255,255,0.97);padding:10px 12px;
              border-radius:10px;border:1px solid #d1d5db;
              box-shadow:0 2px 12px rgba(0,0,0,0.16);
              font-family:system-ui,-apple-system,Segoe UI,sans-serif;
              width:min(340px, calc(100% - 28px));
              max-height:min(52vh, 420px);
              overflow:hidden;
              pointer-events:auto;">
              <summary style="
                cursor:pointer;list-style:none;display:flex;align-items:center;
                justify-content:space-between;gap:8px;user-select:none;
                font-size:13px;font-weight:800;color:#111827;">
                <span>Leyenda</span>
                <span style="font-size:11px;font-weight:600;color:#6b7280">{summary_hint}</span>
              </summary>
              <div style="margin-top:10px;max-height:min(44vh, 360px);overflow-y:auto;
                padding-right:2px;">
                {body_html}
              </div>
            </details>
            <style>
              #{legend_id} > summary::-webkit-details-marker {{ display:none; }}
              #{legend_id}:not([open]) {{ max-height:none; padding:7px 10px; width:auto; }}
              #{legend_id}:not([open]) > div {{ display:none; }}
            </style>
            {{% endmacro %}}
            """
        )


def _legend_items(
    grid_stats: pd.DataFrame,
    umbral_pct: float,
    umbral_pct_pop: float,
    umbral_pop: float,
) -> list[dict]:
    """Solo colores con grillas visibles tras los filtros actuales."""
    if grid_stats.empty:
        return []

    counts = grid_stats.groupby("etiqueta_zona").size().to_dict()
    total = len(grid_stats) or 1

    descriptions = {
        "verde": (
            f"Sin epicentro en la celda y al menos {umbral_pct:.0%} de los clientes "
            f"son compradores de los partners activos."
        ),
        "azul": (
            f"Hay al menos un epicentro y al menos {umbral_pct:.0%} de los clientes "
            f"son compradores (no alcanza el umbral de POP alto)."
        ),
        "celeste": (
            f"Hay al menos un epicentro y al menos {umbral_pct_pop:.0%} de los clientes "
            f"tienen POP ≥ {umbral_pop:.2f} (prioridad sobre azul)."
        ),
        "naranja": (
            f"Sin epicentro y al menos {umbral_pct_pop:.0%} de los clientes tienen "
            f"POP ≥ {umbral_pop:.2f}, pero no llegan al umbral de compradores."
        ),
        "rojo": (
            "La celda no cumple los umbrales de compradores ni de POP alto "
            "(ni con epicentro ni sin él)."
        ),
    }
    titles = {
        "verde": "Verde — compradores",
        "azul": "Azul — compradores + epicentro",
        "celeste": "Celeste — epicentro + POP alto",
        "naranja": "Naranja — POP alto sin epicentro",
        "rojo": "Rojo — resto",
    }

    items = []
    for key in _COLOR_ORDER:
        label = ETIQUETA_GRILLA[key]
        count = int(counts.get(label, 0))
        if count <= 0:
            continue
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


def _map_center(df: pd.DataFrame) -> tuple[float, float, int]:
    if df.empty:
        return -12.0, -77.0, 6
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


def _add_poc_layer(
    m: folium.Map,
    pocs: pd.DataFrame,
    *,
    name: str,
    selected_partners: list[str],
    fill_color_fn,
    title: str,
) -> None:
    if pocs.empty:
        return

    fg = folium.FeatureGroup(name=name, show=True)
    cluster = MarkerCluster(
        disableClusteringAtZoom=14,
        maxClusterRadius=40,
        spiderfyOnMaxZoom=True,
    ).add_to(fg)

    lat = pocs["latitud"].to_numpy(dtype=float)
    lon = pocs["longitud"].to_numpy(dtype=float)
    pop = pocs["pop_promedio"].to_numpy(dtype=float) if "pop_promedio" in pocs.columns else None
    cliente_id = pocs["cliente_id"].astype(str).to_numpy()
    canal = (
        pocs["canal"].astype(str).to_numpy()
        if "canal" in pocs.columns
        else [""] * len(pocs)
    )
    backus = (
        pocs["total_soles_backus_l3m"].to_numpy(dtype=float)
        if "total_soles_backus_l3m" in pocs.columns
        else [0.0] * len(pocs)
    )
    mp = (
        pocs["total_soles_marketplace_l3m"].to_numpy(dtype=float)
        if "total_soles_marketplace_l3m" in pocs.columns
        else [0.0] * len(pocs)
    )

    partner_cols = []
    for pname in selected_partners:
        prefix = PARTNERS[pname]
        flag_col = f"{prefix}_flag_comprador_l3m"
        pop_col = f"{prefix}_pop"
        partner_cols.append(
            (
                pname,
                pocs[flag_col].astype(str).to_numpy()
                if flag_col in pocs.columns
                else None,
                pocs[pop_col].to_numpy(dtype=float) if pop_col in pocs.columns else None,
            )
        )

    cumple_comprador = (
        pocs["cumple_comprador"].to_numpy()
        if "cumple_comprador" in pocs.columns
        else None
    )
    cumple_pop = (
        pocs["cumple_pop_alto"].to_numpy() if "cumple_pop_alto" in pocs.columns else None
    )
    partners_comp = (
        pocs["partners_compradores"].to_numpy()
        if "partners_compradores" in pocs.columns
        else None
    )
    n_partners = (
        pocs["n_partners_sel"].to_numpy() if "n_partners_sel" in pocs.columns else None
    )

    for i in range(len(pocs)):
        pop_i = float(pop[i]) if pop is not None else 0.0
        radius = 7 + min(pop_i, 1.0) * 5
        fill = fill_color_fn(
            i,
            cumple_comprador,
            cumple_pop,
        )
        partner_html = []
        for pname, flags, pops in partner_cols:
            flag = flags[i] if flags is not None else "No Comprador L3M"
            pp = float(pops[i]) if pops is not None else 0.0
            partner_html.append(f"<b>{html.escape(pname)}:</b> {html.escape(str(flag))} · POP {pp:.3f}<br>")

        extra = ""
        if partners_comp is not None and n_partners is not None and cumple_comprador is not None:
            extra = (
                f"<b>Comprador:</b> {'Sí' if bool(cumple_comprador[i]) else 'No'} "
                f"({int(partners_comp[i])}/{int(n_partners[i])})<br>"
            )

        tip = (
            f"<div style='font-size:12px'>"
            f"<b>{html.escape(title)}</b> · {html.escape(cliente_id[i])}<br>"
            f"<b>Canal:</b> {html.escape(str(canal[i]))}<br>"
            f"{extra}{''.join(partner_html)}"
            f"<b>POP prom.:</b> {pop_i:.3f}<br>"
            f"<b>NR Backus:</b> S/ {float(backus[i]):,.0f}<br>"
            f"<b>NR MP:</b> S/ {float(mp[i]):,.0f}"
            f"</div>"
        )
        folium.CircleMarker(
            location=[float(lat[i]), float(lon[i])],
            radius=radius,
            color="#ffffff",
            fill=True,
            fill_color=fill,
            fill_opacity=1.0,
            weight=2.5,
            tooltip=folium.Tooltip(tip, sticky=True),
        ).add_to(cluster)

    fg.add_to(m)


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
    show_pocs_foco: bool = True,
) -> folium.Map:
    centro_lat, centro_lon, zoom = _map_center(df)

    m = folium.Map(
        location=[centro_lat, centro_lon],
        zoom_start=zoom,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )

    if not grid_stats.empty:
        geojson = grids_to_geojson(grid_stats)

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

    n_pocs = int((df["es_epicentro"] == 1).sum()) if "es_epicentro" in df.columns else 0
    n_foco = (
        int((df["es_foco_redbull"] == 1).sum())
        if "es_foco_redbull" in df.columns
        else 0
    )

    legend_items = _legend_items(grid_stats, umbral_pct, umbral_pct_pop, umbral_pop)
    m.get_root().add_child(
        MapLegend(
            legend_items,
            show_pocs=show_pocs,
            show_pocs_foco=show_pocs_foco,
            n_pocs=n_pocs if show_pocs else 0,
            n_foco=n_foco if show_pocs_foco else 0,
            start_open=False,
        )
    )

    if show_pocs and n_pocs > 0:

        def epic_fill(i, cumple_comprador, cumple_pop):
            if cumple_pop is not None and bool(cumple_pop[i]):
                return "#06b6d4"
            if cumple_comprador is not None and bool(cumple_comprador[i]):
                return COLOR_POC
            return "#9ca3af"

        _add_poc_layer(
            m,
            df[df["es_epicentro"] == 1],
            name="POCs Epicentro",
            selected_partners=selected_partners,
            fill_color_fn=epic_fill,
            title="Epicentro",
        )

    if show_pocs_foco and n_foco > 0 and "es_foco_redbull" in df.columns:

        def foco_fill(i, cumple_comprador, cumple_pop):
            return COLOR_POC_FOCO

        _add_poc_layer(
            m,
            df[df["es_foco_redbull"] == 1],
            name="POCs Foco Red Bull",
            selected_partners=selected_partners,
            fill_color_fn=foco_fill,
            title="Foco Red Bull",
        )

    folium.LayerControl(collapsed=True).add_to(m)
    return m
