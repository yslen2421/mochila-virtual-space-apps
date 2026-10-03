# Configuración de Gunicorn para producción.
#
# Capacidad: 3 procesos x 8 hilos = 24 peticiones atendidas en paralelo.
# Una petición de la mochila tarda unos milisegundos, así que esto cubre de sobra
# 150 personas usando el portal al mismo tiempo (ver README, prueba de carga).
import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:5000")
workers = int(os.environ.get("GUNICORN_WORKERS", min(3, multiprocessing.cpu_count() * 2 + 1)))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", 8))
timeout = 120            # importar 150 cuentas de una vez toma ~20 s (hash seguro de contraseñas)
graceful_timeout = 30
keepalive = 5
max_requests = 2000      # recicla procesos de vez en cuando (evita fugas de memoria)
max_requests_jitter = 200
accesslog = "-"
errorlog = "-"
loglevel = "info"
forwarded_allow_ips = "*"
