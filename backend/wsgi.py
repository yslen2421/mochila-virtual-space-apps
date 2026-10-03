"""Punto de entrada.

Desarrollo:   python wsgi.py                      → http://localhost:5000
Producción:   gunicorn -c gunicorn.conf.py wsgi:app
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
