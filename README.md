# Mapa dinámico de Epicentros

Mapa interactivo de Perú en **Streamlit** con grillas 400×400 m coloreadas por compradores, POP y epicentros.

## Ejecución local (recomendado)

```powershell
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Abre **http://localhost:8501** en tu navegador.

> **No uses localtunnel/loca.lt** con Streamlit: rompe la carga de módulos JS. Para compartir con otras personas usa **Streamlit Cloud** (abajo).

## Despliegue en Streamlit Cloud (link público estable)

1. Repo: **https://github.com/viziasac/epicentros_mapa**
2. Ve a [share.streamlit.io](https://share.streamlit.io) → **New app**
3. Configura:
   - Repository: `viziasac/epicentros_mapa`
   - Branch: `main`
   - Main file: `streamlit_app.py`
4. **Deploy** — no requiere secrets (el dataset va en `data/base_epicentros_full_grid400m.parquet`)

El link será algo como: `https://epicentros-mapa.streamlit.app`

## Datos

| Archivo | Uso |
|---------|-----|
| `data/base_epicentros_full_grid400m.parquet` | Dataset incluido en repo (~14 MB, listo para Cloud) |
| `base_epicentros_full.csv` | Solo desarrollo local (no en git) |

Regenerar parquet tras actualizar CSV:

```powershell
python scripts/export_parquet.py
Copy-Item base_epicentros_full_grid400m.parquet data\ -Force
```

## Colores de grilla

| Color | Condición |
|-------|-----------|
| Verde | Sin epicentro · ≥% compradores |
| Azul | Con epicentro · ≥% compradores |
| Celeste | Con epicentro · ≥% POP alto |
| Naranja | Sin epicentro · ≥% POP alto |
| Rojo | Resto |

**Defaults:** 10% compradores · POP 0.50 · 30% POP alto en grilla.

## Estructura

```
streamlit_app.py          # Entry point Streamlit Cloud
mapa_epicentros.py        # UI principal
data/                     # Parquet de deploy
epicentros/               # Pipeline, mapa, scoring
scripts/verify_app.py       # Auditoría local
```

## Auditoría

```powershell
python scripts/verify_app.py
```
