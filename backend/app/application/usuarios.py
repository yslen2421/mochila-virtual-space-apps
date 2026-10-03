"""Casos de uso del Superadmin sobre usuarios."""
from __future__ import annotations

import secrets
from dataclasses import dataclass

from ..domain.entidades import Rol, Usuario
from ..domain.errores import Conflicto, ErrorValidacion, NoEncontrado
from ..domain.puertos import HasherContrasenas, RepositorioUsuarios
from ..domain.reglas import validar_contrasena, validar_usuario
from .comandos import ActualizarUsuario, CrearUsuario

# Palabras para contraseñas fáciles de dictar en la sede (ej. "cometa-orbita-4821").
_PALABRAS = (
    "astro cometa orbita nebula luna sol marte venus saturno jupiter galaxia estrella "
    "cohete satelite eclipse aurora quasar pulsar meteoro planeta polaris andromeda "
    "orion lyra vega sirius titan europa io ceres"
).split()


def generar_contrasena() -> str:
    return f"{secrets.choice(_PALABRAS)}-{secrets.choice(_PALABRAS)}-{secrets.randbelow(9000) + 1000}"


@dataclass
class UsuarioConContrasena:
    usuario: Usuario
    contrasena: str | None   # solo se devuelve una vez, al crear o restablecer


class ServicioUsuarios:
    def __init__(self, usuarios: RepositorioUsuarios, hasher: HasherContrasenas):
        self._usuarios = usuarios
        self._hasher = hasher

    def listar(self) -> list[Usuario]:
        return self._usuarios.listar()

    def _obtener(self, usuario_id: int) -> Usuario:
        usuario = self._usuarios.por_id(usuario_id)
        if not usuario:
            raise NoEncontrado("El usuario no existe.")
        return usuario

    def _construir(self, cmd: CrearUsuario) -> tuple[Usuario, str | None]:
        nombre = cmd.nombre.strip()
        if not nombre:
            raise ErrorValidacion("El nombre es obligatorio.", {"campo": "nombre"})
        generada = None
        contrasena = cmd.contrasena
        if contrasena:
            validar_contrasena(contrasena)
        else:
            contrasena = generada = generar_contrasena()
        usuario = Usuario(
            id=None, usuario=validar_usuario(cmd.usuario), nombre=nombre[:120], rol=cmd.rol,
            email=cmd.email.strip()[:200], modalidad=cmd.modalidad,
            password_hash=self._hasher.hashear(contrasena),
        )
        return usuario, generada

    def crear(self, cmd: CrearUsuario) -> UsuarioConContrasena:
        if self._usuarios.por_usuario(validar_usuario(cmd.usuario)):
            raise Conflicto("Ese nombre de usuario ya existe.", {"campo": "usuario"})
        usuario, generada = self._construir(cmd)
        return UsuarioConContrasena(self._usuarios.guardar(usuario), generada)

    def importar(self, comandos: list[CrearUsuario]) -> list[UsuarioConContrasena]:
        """Crea muchos usuarios de una vez. Si alguna fila falla, no se crea ninguno."""
        if not comandos:
            raise ErrorValidacion("La lista está vacía.")
        if len(comandos) > 500:
            raise ErrorValidacion("Importa como máximo 500 usuarios por vez.")
        errores, vistos = [], set()
        for n, cmd in enumerate(comandos, start=1):
            try:
                nombre_usuario = validar_usuario(cmd.usuario)
                if not cmd.nombre.strip():
                    raise ErrorValidacion("El nombre es obligatorio.")
                if nombre_usuario in vistos:
                    raise Conflicto("Usuario repetido en la lista.")
                if self._usuarios.por_usuario(nombre_usuario):
                    raise Conflicto("Ese usuario ya existe.")
                vistos.add(nombre_usuario)
            except (ErrorValidacion, Conflicto) as e:
                errores.append({"fila": n, "usuario": cmd.usuario, "error": e.mensaje})
        if errores:
            raise ErrorValidacion("Hay filas con errores; no se importó nada.", errores)
        construidos = [self._construir(cmd) for cmd in comandos]
        guardados = self._usuarios.guardar_varios([u for u, _ in construidos])
        return [UsuarioConContrasena(u, c) for u, (_, c) in zip(guardados, construidos)]

    def actualizar(self, actor: Usuario, usuario_id: int, cmd: ActualizarUsuario) -> Usuario:
        usuario = self._obtener(usuario_id)
        if cmd.activo is False and usuario.id == actor.id:
            raise ErrorValidacion("No puedes desactivar tu propia cuenta.")
        if cmd.nombre is not None:
            if not cmd.nombre.strip():
                raise ErrorValidacion("El nombre es obligatorio.", {"campo": "nombre"})
            usuario.nombre = cmd.nombre.strip()[:120]
        if cmd.email is not None:
            usuario.email = cmd.email.strip()[:200]
        if cmd.modalidad is not None:
            usuario.modalidad = cmd.modalidad
        if cmd.activo is not None and cmd.activo != usuario.activo:
            usuario.activo = cmd.activo
            if not cmd.activo:
                usuario.invalidar_sesiones()
        return self._usuarios.guardar(usuario)

    def restablecer_contrasena(self, usuario_id: int) -> UsuarioConContrasena:
        usuario = self._obtener(usuario_id)
        nueva = generar_contrasena()
        usuario.password_hash = self._hasher.hashear(nueva)
        usuario.invalidar_sesiones()
        return UsuarioConContrasena(self._usuarios.guardar(usuario), nueva)

    def fijar_contrasena(self, nombre_usuario: str, contrasena: str) -> Usuario:
        """Pone una contraseña elegida (uso desde la consola del servidor) y cierra sus sesiones."""
        usuario = self._usuarios.por_usuario(validar_usuario(nombre_usuario))
        if not usuario:
            raise NoEncontrado(f"No existe el usuario '{nombre_usuario}'.")
        validar_contrasena(contrasena)
        usuario.password_hash = self._hasher.hashear(contrasena)
        usuario.activo = True
        usuario.invalidar_sesiones()
        return self._usuarios.guardar(usuario)

    def eliminar(self, actor: Usuario, usuario_id: int) -> None:
        usuario = self._obtener(usuario_id)
        if usuario.id == actor.id:
            raise ErrorValidacion("No puedes eliminar tu propia cuenta.")
        if usuario.rol == Rol.SUPERADMIN and sum(u.rol == Rol.SUPERADMIN for u in self.listar()) <= 1:
            raise ErrorValidacion("Debe quedar al menos un Superadmin.")
        self._usuarios.eliminar(usuario_id)
