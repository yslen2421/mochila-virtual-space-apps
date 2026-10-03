FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/datos \
    DETRAS_DE_PROXY=1

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY frontend frontend
COPY deploy/entrada.sh /entrada.sh
RUN chmod +x /entrada.sh && useradd --create-home portal && mkdir -p /datos && chown portal /datos

USER portal
WORKDIR /app/backend
EXPOSE 5000
VOLUME ["/datos"]
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/v1/salud')"
ENTRYPOINT ["/entrada.sh"]
