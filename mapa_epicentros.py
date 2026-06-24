"""Mapa de epicentros marketplace — punto de entrada Streamlit."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from streamlit_folium import st_folium

from epicentros.config import (
    DEFAULT_MAX_GRILLAS,
    DEFAULT_MIN_PARTNERS_ESTABLES,
    DEFAULT_NR_BACKUS,
    DEFAULT_NR_MARKETPLACE,
    DEFAULT_UMBRAL_PCT,
    GRID_SIZE_M,
    MIN_CLIENTES_GRILLA,
    PARTNERS,
    SEGMENTO_ESTABLE,
    SEGMENTO_INESTABLE,
    SEGMENTO_NO_COMPRADOR,
)
from epicentros.data import load_full_dataset
from epicentros.mapa import build_map
from epicentros.pipeline import apply_geo_filters, clamp_min_partners, run_pipeline

ETIQUETAS_GRILLA = [
    "Fuerte + POC",
    "Fuerte sin POC",
    "Débil + POC",
    "Débil sin POC",
]

st.set_page_config(page_title="Mapa Epicentros Marketplace", layout="wide")
st.title("Mapa dinámico de segmentación por partner y epicentros")


@st.cache_data(show_spinner="Cargando datos…")
def get_data():
    return load_full_dataset()


@st.cache_data(show_spinner="Calculando grillas…")
def cached_pipeline(
    partners_key: tuple[str, ...],
    min_partners_estables: int,
    umbral_pct: float,
    umbral_nr_mp: float,
    umbral_nr_backus: float,
    canal: str,
    gerencia: str,
    solo_listado: bool,
    segmento: str,
    colores_key: tuple[str, ...],
    max_grillas: int,
):
    prefix = PARTNERS[partners_key[0]] if partners_key else None
    df = apply_geo_filters(
        get_data(),
        canal,
        gerencia,
        solo_listado,
        segmento,
        prefix,
    )
    if df.empty:
        return None
    return run_pipeline(
        df,
        list(partners_key),
        min_partners_estables,
        umbral_pct,
        umbral_nr_mp,
        umbral_nr_backus,
        max_grillas,
        colores_key,
    )


try:
    df_base = get_data()
except FileNotFoundError as exc:
    st.error(f"Archivo de datos faltante: {exc}")
    st.stop()

# --- Sidebar ---
st.sidebar.header("Filtros")

partners_sel = st.sidebar.multiselect(
    "Partners activos",
    options=list(PARTNERS.keys()),
    default=list(PARTNERS.keys()),
)

if not partners_sel:
    st.warning("Selecciona al menos un partner.")
    st.stop()

n_partners = len(partners_sel)
partners_key = tuple(partners_sel)

if st.session_state.get("_partners_key") != partners_key:
    st.session_state["_partners_key"] = partners_key
    st.session_state["min_partners_estables"] = clamp_min_partners(
        n_partners,
        st.session_state.get("min_partners_estables", DEFAULT_MIN_PARTNERS_ESTABLES),
    )
else:
    st.session_state["min_partners_estables"] = clamp_min_partners(
        n_partners,
        st.session_state.get("min_partners_estables", DEFAULT_MIN_PARTNERS_ESTABLES),
    )

st.sidebar.subheader("Color de grillas")
if n_partners == 1:
    min_partners_estables = 1
    st.session_state["min_partners_estables"] = 1
    st.sidebar.info(f"1 partner activo → mínimo estables: **1** (`{partners_sel[0]}`)")
else:
    min_partners_estables = st.sidebar.slider(
        "Partners estables mín. por cliente",
        1,
        n_partners,
        key="min_partners_estables",
    )
umbral_pct = st.sidebar.slider("% mín. clientes estables en grilla", 0.0, 1.0, DEFAULT_UMBRAL_PCT, 0.05)

st.sidebar.subheader("NR en grilla (0 = off)")
umbral_nr_mp = st.sidebar.number_input("NR Marketplace L3M", 0.0, value=float(DEFAULT_NR_MARKETPLACE), step=50.0)
umbral_nr_backus = st.sidebar.number_input("NR Backus L3M", 0.0, value=float(DEFAULT_NR_BACKUS), step=100.0)

colores_sel = st.sidebar.multiselect(
    "Mostrar solo grillas",
    ETIQUETAS_GRILLA,
    default=ETIQUETAS_GRILLA,
    help="Filtra por color/tipo de grilla en el mapa.",
)

st.sidebar.subheader("Geografía y segmento")
canal_sel = st.sidebar.selectbox("Canal", ["Todos"] + sorted(df_base["canal"].dropna().unique()))
gerencia_sel = st.sidebar.selectbox("Gerencia", ["Todas"] + sorted(df_base["gerencia"].dropna().unique()))
solo_listado = st.sidebar.checkbox("Solo POCs del listado", value=False)

partner_ref = partners_sel[0]
seg_col = f"{PARTNERS[partner_ref]}_segmento_resumen"
segmento_sel = st.sidebar.selectbox(
    f"Segmento ({partner_ref})",
    ["Todos", SEGMENTO_ESTABLE, SEGMENTO_INESTABLE, SEGMENTO_NO_COMPRADOR],
)

st.sidebar.subheader("Rendimiento")
max_grillas = st.sidebar.slider("Máx. grillas", 500, 12_000, DEFAULT_MAX_GRILLAS, 500)

st.sidebar.subheader("POCs en mapa")
show_pocs = st.sidebar.checkbox("Mostrar puntos POC", value=True)
min_nr_mp_poc = st.sidebar.number_input("NR MP mín. POC", 0.0, value=0.0, step=10.0, disabled=not show_pocs)
min_nr_backus_poc = st.sidebar.number_input("NR Backus mín. POC", 0.0, value=0.0, step=50.0, disabled=not show_pocs)

result = cached_pipeline(
    partners_key,
    min_partners_estables,
    umbral_pct,
    umbral_nr_mp,
    umbral_nr_backus,
    canal_sel,
    gerencia_sel,
    solo_listado,
    segmento_sel,
    tuple(colores_sel),
    max_grillas,
)

if result is None:
    st.warning("No hay clientes con los filtros actuales.")
    st.stop()

df, grid_full, grid_stats, paso_lat, paso_lon = result

if grid_stats.empty:
    st.warning(f"No hay grillas (≥{MIN_CLIENTES_GRILLA} clientes). Ajusta filtros o colores de grilla.")
    st.stop()

folium_map = build_map(
    df,
    grid_stats,
    paso_lat,
    paso_lon,
    partners_sel,
    min_partners_estables,
    show_pocs=show_pocs,
    min_nr_mp_poc=min_nr_mp_poc,
    min_nr_backus_poc=min_nr_backus_poc,
)

st_folium(folium_map, width=None, height=720, returned_objects=[])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Clientes", f"{len(df):,}")
c2.metric("Grillas", f"{len(grid_stats):,}", f"{GRID_SIZE_M}×{GRID_SIZE_M} m")
c3.metric(f"≥{min_partners_estables} est.", f"{int(df['cumple_umbral_estables'].sum()):,}")
c4.metric("POCs listado", f"{int(df['es_poc'].sum()):,}")
c5.metric("NR MP", f"S/ {df['total_soles_marketplace_l3m'].sum():,.0f}")

st.caption(
    f"Grilla **{GRID_SIZE_M}×{GRID_SIZE_M} m** · POC = Tipo Epicentro o Gemelo · "
    "Verde fuerte sin POC · Azul fuerte con POC · Naranja débil con POC · Rojo débil sin POC · "
    "Puntos: azul Epicentro, gris Gemelo."
)

with st.expander("Distribución de grillas"):
    st.dataframe(
        grid_stats.groupby("etiqueta_zona").size().reset_index(name="grillas"),
        hide_index=True,
        width="stretch",
    )
