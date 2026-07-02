# Mapa dinámico de Epicentros

Mapa interactivo de Perú en **Streamlit** — grillas 400×400 m, compradores marketplace, POP y epicentros.

## Links

| Entorno | URL |
|---------|-----|
| **Repo** | https://github.com/viziasac/epicentros_mapa |
| **Local** | http://localhost:8501 |
| **Streamlit Cloud** | [share.streamlit.io](https://share.streamlit.io) → `viziasac/epicentros_mapa` → `streamlit_app.py` |

## Compartir desde tu PC (ngrok)

```powershell
# 1. Token gratis: https://dashboard.ngrok.com/get-started/your-authtoken
copy .env.example .env
# Edita .env → NGROK_AUTHTOKEN=tu_token

# 2. Un solo comando (Streamlit + túnel)
.\scripts\run_ngrok.ps1
```

Te mostrará el link `https://xxxx.ngrok-free.app` para compartir.

## Ejecución local

```powershell
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Despliegue Streamlit Cloud (sin configuración extra)

1. Conecta el repo `viziasac/epicentros_mapa`
2. Main file: **`streamlit_app.py`**
3. Python: **3.11**
4. **Deploy** — el dataset ya está en `data/base_epicentros_full_grid400m.parquet` (~14 MB)

No requiere secrets ni túneles (`loca.lt` rompe Streamlit).

## Archivos del proyecto

```
streamlit_app.py              # Entry point Cloud
mapa_epicentros.py            # UI Streamlit
data/
  base_epicentros_full_grid400m.parquet   # Dataset deploy
epicentros/
  config.py data.py filters.py grid.py
  mapa.py pipeline.py scoring.py
scripts/
  verify_app.py               # Auditoría completa
  export_parquet.py           # Regenerar parquet desde CSV
requirements.txt
.streamlit/config.toml
.github/workflows/verify.yml    # CI en cada push
```

**No incluidos (gitignore):** `base_epicentros_full.csv` (~83 MB, solo desarrollo local).

## Auditoría

```powershell
python scripts/verify_app.py
```

Valida: layout, imports, colores, carga de datos, simulación Cloud y render del mapa.

## Colores de grilla

| Color | Condición |
|-------|-----------|
| Verde | Sin epicentro · ≥% compradores |
| Azul | Con epicentro · ≥% compradores |
| Celeste | Con epicentro · ≥% POP alto |
| Naranja | Sin epicentro · ≥% POP alto |
| Rojo | Resto |

**Defaults:** 10% compradores · POP 0.50 · 30% POP alto.

## Regenerar datos

Si actualizas el CSV local:

```powershell
python scripts/export_parquet.py
git add data/base_epicentros_full_grid400m.parquet
git commit -m "Actualizar dataset"
git push
```
