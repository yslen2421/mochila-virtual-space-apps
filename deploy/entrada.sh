#!/bin/sh
# Arranque del contenedor: prepara la base de datos y enciende Gunicorn.
set -e
flask --app wsgi inicializar
exec gunicorn -c gunicorn.conf.py wsgi:app
