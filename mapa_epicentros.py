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
from epicentros.scoring import canonical_etiqueta

ETIQUETAS_GRILLA = list(ETIQUETA_GRILLA.values())
_ETIQUETAS_SET = set(ETIQUETAS_GRILLA)
_COLOR_KEYS = ("verde", "azul", "celeste", "naranja", "rojo")
_DEFAULTS_VERSION = 6


def _sanitize_colores_sel(raw: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for label in raw:
        canon = canonical_etiqueta(label) if label not in _ETIQUETAS_SET else label
        if canon and canon in _ETIQUETAS_SET and canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out if out else list(ETIQUETAS_GRILLA)


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
        "segmento_partner_sel": "Red Bull",
        "show_pocs": True,
        "show_pocs_foco": True,
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
    dist = grid_stats.groupby("etiqueta_zona").size().to_dict() if not grid_stats.empty else {}

    st.subheader("Indicadores del filtro actual")
    r1 = st.columns(5)
    r1[0].metric("Clientes filtrados", f"{len(df):,}")
    r1[1].metric("Epicentros (POCs)", f"{int(df['es_epicentro'].sum()):,}")
    n_foco = int(df["es_foco_redbull"].sum()) if "es_foco_redbull" in df.columns else 0
    r1[2].metric("Foco Red Bull", f"{n_foco:,}")
    r1[3].metric(
        "% compradores (clientes)",
        f"{df['cumple_comprador'].mean():.1%}",
        help="Clientes que cumplen el mínimo de partners compradores",
    )
    r1[4].metric(
        "Grillas (≥2 clientes)",
        f"{n_grillas:,}",
        "todas visibles" if n_grillas == n_total else f"{n_grillas}/{n_total}",
    )

    active_colors = [
        key for key in _COLOR_KEYS if int(dist.get(ETIQUETA_GRILLA[key], 0)) > 0
    ]
    if active_colors:
        r2 = st.columns(len(active_colors))
        for col, key in zip(r2, active_colors):
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
    segmento_partner: str,
    colores_key: tuple[str, ...],
):
    prefix = PARTNERS.get(segmento_partner) or (
        PARTNERS[partners_key[0]] if partners_key else None
    )
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
        0,
        colores_key,
    )


st.set_page_config(page_title="Mapa Epicentros", layout="wide")
_init_session_state()

st.title("Mapa dinámico de epicentros — compradores y POP")
st.caption(
    "Cada celda del mapa resume la densidad de clientes filtrados. "
    "Los colores dependen de umbrales de compradores, POP y presencia de epicentros."
)

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
    help=(
        "Define qué marcas entran en el cálculo de compradores y POP. "
        "Solo se usan las columnas de los partners seleccionados."
    ),
)

if not partners_sel:
    st.warning("Selecciona al menos un partner.")
    st.stop()

n_partners = len(partners_sel)
# Orden canónico (PARTNERS) → caché estable e independiente del orden del multiselect
partners_key = tuple(name for name in PARTNERS if name in set(partners_sel))

if st.session_state.get("_partners_key") != partners_key:
    st.session_state["_partners_key"] = partners_key
    st.session_state["min_partners_compradores"] = clamp_min_partners(
        n_partners,
        st.session_state.get("min_partners_compradores", DEFAULT_MIN_PARTNERS_COMPRADORES),
    )
    if st.session_state.get("segmento_partner_sel") not in partners_key:
        st.session_state["segmento_partner_sel"] = partners_key[0]

st.sidebar.subheader("Reglas de color de grilla")
st.sidebar.caption(
    "Un cliente cuenta como comprador si cumple el mínimo de partners compradores L3M. "
    "POP alto: el promedio de POP de los partners activos alcanza el umbral."
)

if n_partners == 1:
    st.session_state["min_partners_compradores"] = 1
    st.sidebar.caption("Con un solo partner, el mínimo de compradores queda en **1**.")
else:
    st.sidebar.slider(
        "Mín. partners compradores por cliente",
        1,
        n_partners,
        key="min_partners_compradores",
        help=(
            "Cantidad mínima de partners (entre los activos) en los que el cliente "
            "debe ser Comprador L3M para contarlo como comprador."
        ),
    )

st.sidebar.slider(
    "Umbral % compradores en la grilla",
    0.0,
    1.0,
    step=0.05,
    key="umbral_pct",
    help=(
        "Porcentaje mínimo de clientes compradores dentro de la celda para pintar "
        "verde (sin epicentro) o azul (con epicentro)."
    ),
)
st.sidebar.slider(
    "Umbral POP por cliente",
    0.0,
    1.0,
    step=0.01,
    key="umbral_pop",
    help=(
        "POP promedio mínimo del cliente (sobre partners activos) para considerarlo "
        "de POP alto."
    ),
)
st.sidebar.slider(
    "Umbral % POP alto en la grilla",
    0.0,
    1.0,
    step=0.05,
    key="umbral_pct_pop",
    help=(
        "Porcentaje mínimo de clientes con POP alto en la celda para pintar "
        "celeste (con epicentro, prioridad máxima) o naranja (sin epicentro)."
    ),
)

st.sidebar.multiselect(
    "Colores de grilla a mostrar",
    ETIQUETAS_GRILLA,
    key="colores_sel",
    help="Limita qué categorías de color se dibujan en el mapa. Vacío se restablece a todos.",
)

st.sidebar.subheader("Alcance geográfico y de cliente")
st.sidebar.selectbox(
    "Canal",
    ["Todos"] + sorted(df_base["canal"].dropna().unique()),
    key="canal_sel",
    help="Filtra el universo de clientes por canal comercial. 'Todos' deja el total.",
)
st.sidebar.multiselect(
    "Gerencias",
    sorted(df_base["gerencia"].dropna().unique()),
    key="gerencias_sel",
    help="Filtra por una o más gerencias. Sin selección = todas las gerencias.",
)
st.sidebar.checkbox(
    "Solo clientes epicentro",
    key="solo_epicentro",
    help="Restringe el análisis a clientes con flag de epicentro = 1.",
)

if st.session_state.get("segmento_partner_sel") not in partners_key:
    st.session_state["segmento_partner_sel"] = partners_key[0]

st.sidebar.selectbox(
    "Partner del filtro de segmento",
    options=list(partners_key),
    key="segmento_partner_sel",
    help=(
        "Elige qué partner usa el filtro de Comprador L3M / No Comprador L3M. "
        "No cambia el cálculo multi-partner de colores; solo el universo de clientes."
    ),
)
st.sidebar.selectbox(
    "Segmento comprador L3M",
    ["Todos", COMPRADOR_L3M, NO_COMPRADOR_L3M],
    key="segmento_sel",
    help=(
        "Filtra clientes por el flag L3M del partner elegido arriba. "
        "Independiente del mínimo de partners compradores usado en el coloreo."
    ),
)

st.sidebar.subheader("Capas de puntos")
st.sidebar.checkbox(
    "Mostrar POCs epicentro",
    key="show_pocs",
    help="Dibuja puntos de clientes epicentro sobre el mapa (clusterizados).",
)
st.sidebar.checkbox(
    "Mostrar POCs Foco Red Bull",
    key="show_pocs_foco",
    help=(
        "Dibuja en amarillo los clientes del listado de foco Red Bull "
        "que coinciden por cliente_id."
    ),
)

st.sidebar.caption(
    f"Cada grilla requiere al menos **{MIN_CLIENTES_GRILLA} clientes** filtrados. "
    "Se renderizan todas las celdas elegibles."
)

# Valores activos desde session_state
min_partners_compradores = int(st.session_state["min_partners_compradores"])
umbral_pct = float(st.session_state["umbral_pct"])
umbral_pop = float(st.session_state["umbral_pop"])
umbral_pct_pop = float(st.session_state["umbral_pct_pop"])
colores_sel = _sanitize_colores_sel(list(st.session_state["colores_sel"]))
if colores_sel != list(st.session_state["colores_sel"]):
    st.session_state["colores_sel"] = colores_sel
canal_sel = st.session_state["canal_sel"]
gerencias_key = tuple(st.session_state["gerencias_sel"])
solo_epicentro = bool(st.session_state["solo_epicentro"])
segmento_sel = st.session_state["segmento_sel"]
segmento_partner = st.session_state["segmento_partner_sel"]
show_pocs = bool(st.session_state["show_pocs"])
show_pocs_foco = bool(st.session_state["show_pocs_foco"])

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
    segmento_partner,
    tuple(colores_sel),
)

if result is None:
    st.warning("No hay clientes con los filtros actuales.")
    st.stop()

df, grid_full, grid_stats, paso_lat, paso_lon = result

if grid_full.empty:
    st.warning(
        f"No hay grillas con ≥{MIN_CLIENTES_GRILLA} clientes con los filtros actuales."
    )
    st.stop()
if grid_stats.empty:
    st.warning(
        "Ninguna grilla coincide con los colores seleccionados. "
        "Se restablecieron todos los colores."
    )
    st.session_state["colores_sel"] = list(ETIQUETAS_GRILLA)
    st.rerun()

render_kpis(df, grid_stats, grid_full)

folium_map = build_map(
    df,
    grid_stats,
    paso_lat,
    paso_lon,
    list(partners_key),
    min_partners_compradores,
    umbral_pct,
    umbral_pct_pop,
    umbral_pop,
    show_pocs=show_pocs,
    show_pocs_foco=show_pocs_foco,
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
    segmento_partner=segmento_partner,
    colores=tuple(colores_sel),
    show_pocs=show_pocs,
    show_pocs_foco=show_pocs_foco,
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
    f"Grilla **{GRID_SIZE_M}×{GRID_SIZE_M} m** · Haz clic en **Leyenda** (esquina inferior izquierda) "
    f"para mostrar/ocultar · se actualiza con los filtros. "
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
