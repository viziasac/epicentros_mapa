# Mapa dinámico de Epicentros

Mapa interactivo de Perú en **Streamlit** con grillas geográficas coloreadas según compradores marketplace, POP y epicentros.

## Requisitos

- Python 3.11+
- Dataset `base_epicentros_full.csv` (generado internamente; **no incluido en el repo**)

## Ejecución local

```powershell
pip install -r requirements.txt
# Coloca base_epicentros_full.csv en la raíz del proyecto
python scripts/verify_app.py
streamlit run streamlit_app.py
```

O en Windows: `.\run.ps1`

## Estructura

```
mapa_epicentros.py      # UI Streamlit
streamlit_app.py        # Entry point para Streamlit Cloud
epicentros/
  config.py             # Constantes y rutas
  data.py               # Carga CSV/parquet/URL remota
  filters.py            # Filtros geográficos
  grid.py               # Grilla 400×400 m
  scoring.py            # Métricas y colores (5 zonas)
  pipeline.py           # Orquestación
  mapa.py               # Mapa Folium + leyenda
scripts/
  verify_app.py         # Auditoría local
  export_parquet.py     # Exportar parquet para deploy
sql/                    # Query de referencia Databricks
```

## Lógica de colores (grilla 400 m)

| Color | Condición |
|-------|-----------|
| Verde | Sin epicentro · ≥% compradores en grilla |
| Azul | Con epicentro · ≥% compradores |
| Celeste | Con epicentro · ≥% clientes con POP alto |
| Naranja | Sin epicentro · ≥% clientes con POP alto |
| Rojo | Resto |

**Defaults:** 10% compradores · POP mín. 0.50 · 30% POP alto en grilla.

## Despliegue en Streamlit Community Cloud

### 1. Subir código a GitHub

```bash
git add .
git commit -m "App epicentros lista para deploy"
git push origin main
```

> **No subas** `base_epicentros_full.csv` (~83 MB) ni archivos `.parquet`. Están en `.gitignore`.

### 2. Preparar datos para la nube

Genera un parquet optimizado (~15 MB):

```powershell
python scripts/export_parquet.py
```

Sube `base_epicentros_full_grid400m.parquet` a un almacenamiento accesible por URL (S3, GCS, Azure Blob, GitHub Release privado, etc.).

### 3. Crear app en [share.streamlit.io](https://share.streamlit.io)

| Campo | Valor |
|-------|-------|
| Repository | `viziasac/mapadinamico_epicentros` |
| Branch | `main` |
| Main file | `streamlit_app.py` |
| Python | 3.11 |

### 4. Configurar Secrets

En **Settings → Secrets**, pega (ajusta la URL):

```toml
[data]
parquet_url = "https://tu-url/base_epicentros_full_grid400m.parquet"
```

Alternativa local: copia `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`.

También puedes usar variable de entorno `EPICENTROS_DATA_URL`.

### 5. Recursos recomendados

- **Memoria:** app con ~220k filas; plan con ≥1 GB RAM recomendado.
- Primera carga puede tardar 30–60 s (descarga + caché en memoria Streamlit).

## Privacidad y datos

- El dataset contiene IDs de cliente, coordenadas y métricas comerciales.
- **No publiques** CSVs de producción en repos públicos.
- Archivos legacy (`base_epicentros_marketplace.csv`, `clientes_gemelos_*`) no son usados por la app actual; conviene retirarlos del historial git si el repo es público.

## CI

GitHub Actions ejecuta `scripts/verify_app.py` en cada push (tests de lógica sin dataset).

## Licencia

Uso interno — definir licencia antes de hacer el repo público.
