"""Casos de uso de autenticación: iniciar sesión, validar sesión, cambiar contraseña."""
from __future__ import annotations

from ..domain.entidades import Rol, Usuario
from ..domain.errores import DemasiadosIntentos, NoAutenticado, SinPermiso
from ..domain.puertos import (
    ControlIntentos,
    EmisorTokens,
    HasherContrasenas,
    RegistroActividad,
    Reloj,
    RepositorioUsuarios,
)
from ..domain.reglas import normalizar_usuario, validar_contrasena

MENSAJE_CREDENCIALES = "Usuario o contraseña incorrectos."


class ServicioAutenticacion:
    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        hasher: HasherContrasenas,
        tokens: EmisorTokens,
        intentos: ControlIntentos,
        actividad: RegistroActividad,
        reloj: Reloj,
        max_intentos_usuario: int = 8,
        max_intentos_ip: int = 60,
        ventana_segundos: int = 15 * 60,
    ):
        self._usuarios = usuarios
        self._hasher = hasher
        self._tokens = tokens
        self._intentos = intentos
        self._actividad = actividad
        self._reloj = reloj
        self._max_usuario = max_intentos_usuario
        # En la sede presencial muchos comparten la misma IP pública (wifi del evento),
        # por eso el límite por IP es mucho más alto que el límite por usuario.
        self._max_ip = max_intentos_ip
        self._ventana = ventana_segundos
        # Hash señuelo: verificar contra él cuando el usuario no existe evita que
        # el tiempo de respuesta revele qué usuarios existen.
        self._hash_senuelo = hasher.hashear("contrasena-senuelo-no-usar")

    def iniciar_sesion(self, usuario: str, contrasena: str, ip: str) -> tuple[str, Usuario]:
        usuario = normalizar_usuario(usuario)
        clave_usuario, clave_ip = f"u:{usuario}", f"ip:{ip}"

        if (
            self._intentos.fallos_recientes(clave_usuario, self._ventana) >= self._max_usuario
            or self._intentos.fallos_recientes(clave_ip, self._ventana) >= self._max_ip
        ):
            raise DemasiadosIntentos(
                "Demasiados intentos fallidos. Espera 15 minutos o pide a la organización que restablezca tu contraseña."
            )

        encontrado = self._usuarios.por_usuario(usuario)
        hash_a_verificar = encontrado.password_hash if encontrado else self._hash_senuelo
        contrasena_ok = self._hasher.verificar(contrasena or "", hash_a_verificar)

        if not encontrado or not contrasena_ok:
            self._intentos.registrar_fallo(clave_usuario)
            self._intentos.registrar_fallo(clave_ip)
            raise NoAutenticado(MENSAJE_CREDENCIALES)

        if not encontrado.activo:
            raise NoAutenticado("Tu cuenta está desactivada. Escríbele al equipo organizador.")

        self._intentos.limpiar(clave_usuario)
        self._usuarios.registrar_login(encontrado.id, self._reloj.ahora())
        self._actividad.registrar("login", encontrado.id)
        return self._tokens.emitir(encontrado), encontrado

    def desbloquear(self, usuario: str) -> None:
        """Borra los intentos fallidos de un usuario (tras cambiarle la contraseña)."""
        self._intentos.limpiar(f"u:{normalizar_usuario(usuario)}")

    def usuario_de_token(self, token: str) -> Usuario:
        datos = self._tokens.leer(token)  # lanza NoAutenticado si es inválido o venció
        usuario = self._usuarios.por_id(int(datos["sub"]))
        if not usuario or not usuario.activo or usuario.version_token != datos.get("ver"):
            raise NoAutenticado("Tu sesión ya no es válida. Inicia sesión de nuevo.")
        return usuario

    def exigir_rol(self, usuario: Usuario, rol: Rol) -> None:
        if usuario.rol != rol:
            raise SinPermiso("No tienes permiso para esta acción.")

    def cambiar_contrasena(self, usuario: Usuario, actual: str, nueva: str) -> str:
        if not self._hasher.verificar(actual or "", usuario.password_hash):
            raise NoAutenticado("La contraseña actual no es correcta.")
        validar_contrasena(nueva)
        usuario.password_hash = self._hasher.hashear(nueva)
        usuario.invalidar_sesiones()
        self._usuarios.guardar(usuario)
        return self._tokens.emitir(usuario)
