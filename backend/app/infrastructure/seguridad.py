"""Implementaciones de seguridad: hash de contraseñas, tokens JWT y reloj."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from werkzeug.security import check_password_hash, generate_password_hash

from ..domain.entidades import Usuario
from ..domain.errores import NoAutenticado


class HasherWerkzeug:
    """scrypt por defecto (lento a propósito para frenar ataques de fuerza bruta)."""

    def __init__(self, metodo: str = "scrypt"):
        self._metodo = metodo

    def hashear(self, contrasena: str) -> str:
        return generate_password_hash(contrasena, method=self._metodo)

    def verificar(self, contrasena: str, hash_guardado: str) -> bool:
        try:
            return check_password_hash(hash_guardado, contrasena)
        except ValueError:
            return False


class EmisorJwt:
    ALGORITMO = "HS256"

    def __init__(self, secreto: str, duracion: timedelta):
        if len(secreto) < 32:
            raise ValueError("SECRET_KEY debe tener al menos 32 caracteres.")
        self._secreto = secreto
        self._duracion = duracion

    def emitir(self, usuario: Usuario) -> str:
        ahora = datetime.now(timezone.utc)
        return jwt.encode(
            {"sub": str(usuario.id), "rol": usuario.rol.value, "ver": usuario.version_token,
             "iat": ahora, "exp": ahora + self._duracion},
            self._secreto, algorithm=self.ALGORITMO,
        )

    def leer(self, token: str) -> dict:
        try:
            return jwt.decode(token, self._secreto, algorithms=[self.ALGORITMO],
                              options={"require": ["sub", "exp", "ver"]})
        except jwt.ExpiredSignatureError:
            raise NoAutenticado("Tu sesión expiró. Inicia sesión de nuevo.")
        except jwt.InvalidTokenError:
            raise NoAutenticado("Sesión no válida. Inicia sesión de nuevo.")


class RelojSistema:
    def ahora(self) -> datetime:
        return datetime.now(timezone.utc)
