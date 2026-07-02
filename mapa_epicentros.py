"""Mapa de epicentros marketplace — punto de entrada Streamlit."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from streamlit_folium import st_folium

from epicentros.config import (
    COLOR_GRILLA,
    COMPRADOR_L3M,
    DEFAULT_MAX_GRILLAS,
    DEFAULT_MIN_PARTNERS_COMPRADORES,
    DEFAULT_UMBRAL_PCT_COMPRADORES,
    DEFAULT_UMBRAL_PCT_POP,
    DEFAULT_UMBRAL_POP,
    ETIQUETA_GRILLA,
    GRID_SIZE_M,
    MIN_CLIENTES_GRILLA,
    NO_COMPRADOR_L3M,
    PARTNERS,
    data_setup_hint,
)
from epicentros.data import load_full_dataset
from epicentros.filters import apply_geo_filters
from epicentros.mapa import build_map
from epicentros.pipeline import clamp_min_partners, run_pipeline

ETIQUETAS_GRILLA = list(ETIQUETA_GRILLA.values())
_COLOR_KEYS = ("verde", "azul", "celeste", "naranja", "rojo")
_DEFAULTS_VERSION = 2


def _init_session_state() -> None:
    defaults = {
        "min_partners_compradores": DEFAULT_MIN_PARTNERS_COMPRADORES,
        "umbral_pct": DEFAULT_UMBRAL_PCT_COMPRADORES,
        "umbral_pop": DEFAULT_UMBRAL_POP,
        "umbral_pct_pop": DEFAULT_UMBRAL_PCT_POP,
        "colores_sel": ETIQUETAS_GRILLA,
        "canal_sel": "Todos",
        "gerencias_sel": [],
        "solo_epicentro": False,
        "segmento_sel": "Todos",
        "max_grillas": DEFAULT_MAX_GRILLAS,
        "show_pocs": True,
    }
    if st.session_state.get("_defaults_version") != _DEFAULTS_VERSION:
        for key, value in defaults.items():
            st.session_state[key] = value
        st.session_state["_defaults_version"] = _DEFAULTS_VERSION
    else:
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value


def _map_render_key(**params) -> str:
    raw = json.dumps(params, sort_keys=True, default=str)
    return "map_" + hashlib.md5(raw.encode()).hexdigest()[:16]


def _color_metric_html(key: str, count: int, pct: float) -> str:
    color = COLOR_GRILLA[key]
    title = ETIQUETA_GRILLA[key].split("—")[0].strip()
    return (
        f'<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;'
        f'padding:10px 12px;border-left:5px solid {color};min-height:88px">'
        f'<div style="font-size:13px;color:#6b7280;font-weight:600">{title}</div>'
        f'<div style="font-size:26px;font-weight:700;color:#111827;line-height:1.2">{count:,}</div>'
        f'<div style="font-size:12px;color:#4b5563">{pct:.1f}% de grillas visibles</div>'
        f"</div>"
    )


def render_kpis(df, grid_stats, grid_full) -> None:
    n_grillas = len(grid_stats)
    n_total = len(grid_full)
    dist = grid_stats.groupby("etiqueta_zona").size().to_dict()

    st.subheader("Indicadores del filtro actual")
    r1 = st.columns(4)
    r1[0].metric("Clientes filtrados", f"{len(df):,}")
    r1[1].metric("Epicentros (POCs)", f"{int(df['es_epicentro'].sum()):,}")
    r1[2].metric(
        "% compradores (clientes)",
        f"{df['cumple_comprador'].mean():.1%}",
        help="Clientes que cumplen el mínimo de partners compradores",
    )
    r1[3].metric(
        "Grillas en mapa",
        f"{n_grillas:,}",
        f"{n_grillas / n_total:.0%} del total" if n_total else None,
    )

    r2 = st.columns(5)
    for col, key in zip(r2, _COLOR_KEYS):
        label = ETIQUETA_GRILLA[key]
        count = int(dist.get(label, 0))
        pct = (count / n_grillas * 100) if n_grillas else 0.0
        col.markdown(_color_metric_html(key, count, pct), unsafe_allow_html=True)


@st.cache_data(show_spinner="Cargando datos…")
def get_data():
    return load_full_dataset()


@st.cache_data(show_spinner="Calculando grillas…")
def cached_pipeline(
    partners_key: tuple[str, ...],
    min_partners_compradores: int,
    umbral_pct: float,
    umbral_pop: float,
    umbral_pct_pop: float,
    canal: str,
    gerencias_key: tuple[str, ...],
    solo_epicentro: bool,
    segmento: str,
    colores_key: tuple[str, ...],
    max_grillas: int,
):
    prefix = PARTNERS[partners_key[0]] if partners_key else None
    df = apply_geo_filters(
        get_data(),
        canal,
        gerencias_key,
        solo_epicentro,
        segmento,
        prefix,
    )
    if df.empty:
        return None
    return run_pipeline(
        df,
        list(partners_key),
        min_partners_compradores,
        umbral_pct,
        umbral_pop,
        umbral_pct_pop,
        max_grillas,
        colores_key,
    )


st.set_page_config(page_title="Mapa Epicentros", layout="wide")
_init_session_state()

st.title("Mapa dinámico de epicentros — compradores y POP")

try:
    df_base = get_data()
except FileNotFoundError:
    st.error("No se encontró el dataset.")
    st.info(data_setup_hint())
    st.stop()

# --- Sidebar: filtros reactivos (sin form; cada cambio recalcula vía caché) ---
st.sidebar.header("Partners")
partners_sel = st.sidebar.multiselect(
    "Partners activos",
    options=list(PARTNERS.keys()),
    default=list(PARTNERS.keys()),
    key="partners_sel",
)

if not partners_sel:
    st.warning("Selecciona al menos un partner.")
    st.stop()

n_partners = len(partners_sel)
partners_key = tuple(partners_sel)

if st.session_state.get("_partners_key") != partners_key:
    st.session_state["_partners_key"] = partners_key
    st.session_state["min_partners_compradores"] = clamp_min_partners(
        n_partners,
        st.session_state.get("min_partners_compradores", DEFAULT_MIN_PARTNERS_COMPRADORES),
    )

st.sidebar.subheader("Umbrales de color")

if n_partners == 1:
    st.session_state["min_partners_compradores"] = 1
    st.sidebar.caption("1 partner → mín. compradores: **1**")
else:
    st.sidebar.slider(
        "Partners compradores mín. por cliente",
        1,
        n_partners,
        key="min_partners_compradores",
    )

st.sidebar.slider(
    "% compradores en grilla (verde/azul)",
    0.0,
    1.0,
    step=0.05,
    key="umbral_pct",
)
st.sidebar.slider(
    "POP mínimo por cliente",
    0.0,
    1.0,
    step=0.01,
    key="umbral_pop",
)
st.sidebar.slider(
    "% clientes POP alto en grilla (celeste/naranja)",
    0.0,
    1.0,
    step=0.05,
    key="umbral_pct_pop",
)

st.sidebar.multiselect(
    "Mostrar grillas",
    ETIQUETAS_GRILLA,
    key="colores_sel",
)

st.sidebar.subheader("Geografía")
st.sidebar.selectbox(
    "Canal",
    ["Todos"] + sorted(df_base["canal"].dropna().unique()),
    key="canal_sel",
)
st.sidebar.multiselect(
    "Gerencias",
    sorted(df_base["gerencia"].dropna().unique()),
    key="gerencias_sel",
    help="Vacío = todas las gerencias",
)
st.sidebar.checkbox("Solo clientes epicentro", key="solo_epicentro")

partner_ref = partners_sel[0]
st.sidebar.selectbox(
    f"Comprador ({partner_ref})",
    ["Todos", COMPRADOR_L3M, NO_COMPRADOR_L3M],
    key="segmento_sel",
)

st.sidebar.slider("Máx. grillas", 500, 12_000, step=500, key="max_grillas")
st.sidebar.checkbox("Mostrar POCs epicentro", key="show_pocs")

# Valores activos desde session_state (siempre los últimos del widget)
min_partners_compradores = int(st.session_state["min_partners_compradores"])
umbral_pct = float(st.session_state["umbral_pct"])
umbral_pop = float(st.session_state["umbral_pop"])
umbral_pct_pop = float(st.session_state["umbral_pct_pop"])
colores_sel = list(st.session_state["colores_sel"])
canal_sel = st.session_state["canal_sel"]
gerencias_key = tuple(st.session_state["gerencias_sel"])
solo_epicentro = bool(st.session_state["solo_epicentro"])
segmento_sel = st.session_state["segmento_sel"]
max_grillas = int(st.session_state["max_grillas"])
show_pocs = bool(st.session_state["show_pocs"])

result = cached_pipeline(
    partners_key,
    min_partners_compradores,
    umbral_pct,
    umbral_pop,
    umbral_pct_pop,
    canal_sel,
    gerencias_key,
    solo_epicentro,
    segmento_sel,
    tuple(colores_sel),
    max_grillas,
)

if result is None:
    st.warning("No hay clientes con los filtros actuales.")
    st.stop()

df, grid_full, grid_stats, paso_lat, paso_lon = result

if grid_stats.empty:
    st.warning(f"No hay grillas con ≥{MIN_CLIENTES_GRILLA} clientes.")
    st.stop()

render_kpis(df, grid_stats, grid_full)

folium_map = build_map(
    df,
    grid_stats,
    paso_lat,
    paso_lon,
    partners_sel,
    min_partners_compradores,
    umbral_pct,
    umbral_pct_pop,
    umbral_pop,
    show_pocs=show_pocs,
)

map_key = _map_render_key(
    partners=partners_key,
    min_partners=min_partners_compradores,
    umbral_pct=umbral_pct,
    umbral_pop=umbral_pop,
    umbral_pct_pop=umbral_pct_pop,
    canal=canal_sel,
    gerencias=gerencias_key,
    solo_epicentro=solo_epicentro,
    segmento=segmento_sel,
    colores=tuple(colores_sel),
    max_grillas=max_grillas,
    show_pocs=show_pocs,
    n_grillas=len(grid_stats),
    color_sig=tuple(grid_stats["color_grilla"].value_counts().items()),
)

st_folium(
    folium_map,
    width=None,
    height=760,
    returned_objects=[],
    key=map_key,
)

st.caption(
    f"Grilla **{GRID_SIZE_M}×{GRID_SIZE_M} m** · Los colores, KPIs y leyenda se actualizan al cambiar cualquier filtro. "
    f"Umbrales: compradores ≥{umbral_pct:.0%}, POP cliente ≥{umbral_pop:.2f}, "
    f"% POP alto en grilla ≥{umbral_pct_pop:.0%}."
)

with st.expander("Distribución detallada"):
    dist = grid_stats.groupby("etiqueta_zona").size()
    st.dataframe(
        dist.reset_index(name="grillas").rename(columns={"etiqueta_zona": "zona"}),
        hide_index=True,
        width="stretch",
    )
