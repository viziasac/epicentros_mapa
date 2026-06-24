Set-Location $PSScriptRoot

Get-ChildItem -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

python scripts/verify_app.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

streamlit run mapa_epicentros.py --server.headless true
