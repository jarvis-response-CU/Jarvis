# References:
#   https://fly.io/docs/languages-and-frameworks/dockerfile/
#   https://www.uvicorn.org/deployment/#running-behind-nginx

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src
# Editable, so PROJECT_ROOT (found from the source files' location) is /app.
RUN pip install --no-cache-dir -e .

COPY web ./web
# The server only needs the built structures table and the loss factors, not
# the raw county downloads they're made from.
COPY data/loss_factors.csv ./data/loss_factors.csv
COPY data/processed/structures.csv ./data/processed/structures.csv
# The flood model never downloads elevation; fetch_dem.py makes this file.
COPY data/raw/flood/nyc/dem.tif ./data/raw/flood/nyc/dem.tif

ENV JARVIS_HOST=0.0.0.0 JARVIS_PORT=8080
EXPOSE 8080
CMD ["uvicorn", "jarvis.server:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
