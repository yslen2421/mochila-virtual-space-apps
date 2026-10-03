"""Configuración leída de variables de entorno (archivo .env opcional)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parent.parent


def _cargar_env(ruta: Path) -> None:
    """Carga un .env sencillo (CLAVE=valor) sin depender de librerías extra."""
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def _bool(nombre: str, defecto: bool) -> bool:
    valor = os.environ.get(nombre)
    return defecto if valor is None else valor.strip().lower() in {"1", "true", "si", "sí", "yes"}


def _secreto(carpeta_datos: Path) -> str:
    """SECRET_KEY del entorno; si no hay, se genera una y se guarda junto a los datos.

    Guardarla en disco hace que todos los procesos de gunicorn usen la misma y que
    las sesiones sobrevivan a un reinicio.
    """
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    archivo = carpeta_datos / ".secret_key"
    carpeta_datos.mkdir(parents=True, exist_ok=True)
    if not archivo.exists():
        try:
            fd = os.open(archivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_urlsafe(48))
        except FileExistsError:
            pass  # otro proceso la creó al mismo tiempo
    return archivo.read_text().strip()


def _url_portal() -> str:
    """Base de los enlaces de los correos.

    PORTAL_URL manda. Si no está, en el servidor (detrás de Caddy, DETRAS_DE_PROXY=1) se usa
    https://DOMINIO/. En el computador queda vacía y se usa la dirección desde la que se abrió
    el portal (por ejemplo http://localhost:5000/), aunque el .env traiga un DOMINIO de ejemplo.
    """
    if os.environ.get("PORTAL_URL", "").strip():
        return os.environ["PORTAL_URL"].strip()
    dominio = os.environ.get("DOMINIO", "").strip()
    if dominio and _bool("DETRAS_DE_PROXY", False):
        return f"https://{dominio}/"
    return ""


@dataclass
class Configuracion:
    carpeta_datos: Path
    ruta_bd: str
    carpeta_archivos: str
    secret_key: str
    horas_token: int = 24
    origenes_cors: list[str] = field(default_factory=list)
    max_subida_mb: int = 100
    servir_frontend: bool = True
    usar_x_accel: bool = False
    detras_de_proxy: bool = False
    metodo_hash: str = "scrypt"
    zona_horaria: str = "America/Bogota"   # el cronograma se escribe en hora de Colombia
    # Dirección pública del portal, para los enlaces de los correos (https://tu-dominio/)
    url_portal: str = ""
    # Correo saliente (recuperación de contraseña). Sin SMTP_HOST, los correos se guardan en datos/correos/
    smtp_host: str = ""
    smtp_puerto: int = 587
    smtp_usuario: str = ""
    smtp_contrasena: str = ""
    smtp_seguridad: str = "starttls"        # starttls (puerto 587), ssl (puerto 465) o ninguna
    correo_remitente: str = ""
    correo_en_segundo_plano: bool = True

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        _cargar_env(RAIZ_BACKEND / ".env")
        datos = Path(os.environ.get("DATA_DIR", RAIZ_BACKEND / "data")).resolve()
        return cls(
            carpeta_datos=datos,
            ruta_bd=os.environ.get("DATABASE_PATH", str(datos / "portal.db")),
            carpeta_archivos=os.environ.get("UPLOAD_DIR", str(datos / "archivos")),
            secret_key=_secreto(datos),
            horas_token=int(os.environ.get("TOKEN_HORAS", "24")),
            origenes_cors=[o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()],
            max_subida_mb=int(os.environ.get("MAX_SUBIDA_MB", "100")),
            servir_frontend=_bool("SERVIR_FRONTEND", True),
            usar_x_accel=_bool("USAR_X_ACCEL", False),
            detras_de_proxy=_bool("DETRAS_DE_PROXY", False),
            zona_horaria=os.environ.get("ZONA_HORARIA", "America/Bogota"),
            url_portal=_url_portal(),
            smtp_host=os.environ.get("SMTP_HOST", "").strip(),
            smtp_puerto=int(os.environ.get("SMTP_PUERTO", "587")),
            smtp_usuario=os.environ.get("SMTP_USUARIO", "").strip(),
            smtp_contrasena=os.environ.get("SMTP_CONTRASENA", "").replace(" ", ""),
            smtp_seguridad=os.environ.get("SMTP_SEGURIDAD", "starttls").strip().lower(),
            correo_remitente=os.environ.get("CORREO_REMITENTE", "").strip(),
        )
