#!/bin/sh
# Arranque del contenedor: prepara la base de datos y enciende Gunicorn.
#
# La carpeta de datos suele montarse desde el servidor (./datos), y Docker la crea
# como root. Por eso arrancamos como root, le damos la carpeta al usuario "portal"
# y Gunicorn atiende las peticiones ya sin privilegios.
set -e
DATA_DIR="${DATA_DIR:-/datos}"
mkdir -p "$DATA_DIR"

flask --app wsgi inicializar

if [ "$(id -u)" = "0" ]; then
    chown -R portal:portal "$DATA_DIR"
    exec gunicorn -c gunicorn.conf.py --user portal --group portal wsgi:app
else
    exec gunicorn -c gunicorn.conf.py wsgi:app
fi
