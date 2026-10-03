"""Recuperar la contraseña por correo.

1. La persona escribe su usuario o su correo → si hay una cuenta activa con correo,
   se le envía un enlace. La respuesta es siempre la misma (no revela qué cuentas existen).
2. El enlace trae un código de un solo uso que vence en una hora. En la base de datos
   solo se guarda su huella (SHA-256), nunca el código.
3. Con el código, elige una contraseña nueva. El enlace deja de servir si se usa, si
   vence, o si la contraseña cambia por cualquier otro camino.
"""
from __future__ import annotations

import hashlib
import html
import secrets
import time

from ..domain.entidades import Usuario
from ..domain.errores import EnlaceInvalido, ErrorValidacion, NoAutenticado
from ..domain.puertos import (
    ControlIntentos,
    EmisorTokens,
    EnviadorCorreos,
    HasherContrasenas,
    RepositorioRestablecimientos,
    RepositorioUsuarios,
)
from ..domain.reglas import normalizar_usuario, validar_contrasena

VIGENCIA_SEGUNDOS = 60 * 60
MAX_POR_CUENTA_HORA = 3
MAX_POR_IP_HORA = 20

MENSAJE_GENERICO = (
    "Si los datos corresponden a una cuenta con correo registrado, te enviamos un enlace para "
    "elegir una nueva contraseña. Revisa también la carpeta de spam. El enlace sirve por 1 hora."
)


def _huella(codigo: str) -> str:
    return hashlib.sha256(codigo.encode()).hexdigest()


class ServicioRecuperacion:
    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        restablecimientos: RepositorioRestablecimientos,
        hasher: HasherContrasenas,
        tokens: EmisorTokens,
        correos: EnviadorCorreos,
        intentos: ControlIntentos,
    ):
        self._usuarios = usuarios
        self._restablecimientos = restablecimientos
        self._hasher = hasher
        self._tokens = tokens
        self._correos = correos
        self._intentos = intentos

    # ------------------------------------------------------------ 1. pedir el enlace

    def solicitar(self, identificador: str, ip: str, url_portal: str) -> str:
        identificador = (identificador or "").strip()
        if not identificador:
            raise ErrorValidacion("Escribe tu usuario o tu correo.", {"campo": "identificador"})

        clave_ip = f"olvido-ip:{ip}"
        if self._intentos.fallos_recientes(clave_ip, 3600) >= MAX_POR_IP_HORA:
            return MENSAJE_GENERICO  # sin pistas: igual que si no existiera
        self._intentos.registrar_fallo(clave_ip)

        for usuario in self._buscar(identificador):
            clave_cuenta = f"olvido-u:{usuario.id}"
            if self._intentos.fallos_recientes(clave_cuenta, 3600) >= MAX_POR_CUENTA_HORA:
                continue
            self._intentos.registrar_fallo(clave_cuenta)
            codigo = secrets.token_urlsafe(32)
            self._restablecimientos.crear(_huella(codigo), usuario.id, usuario.version_token,
                                          time.time() + VIGENCIA_SEGUNDOS)
            self._enviar_enlace(usuario, f"{url_portal.rstrip('/')}/#/restablecer/{codigo}")
        return MENSAJE_GENERICO

    def _buscar(self, identificador: str) -> list[Usuario]:
        if "@" in identificador:
            candidatos = self._usuarios.por_email(identificador)
        else:
            u = self._usuarios.por_usuario(normalizar_usuario(identificador))
            candidatos = [u] if u else []
        return [u for u in candidatos if u.activo and u.email]

    def _enviar_enlace(self, usuario: Usuario, enlace: str) -> None:
        nombre = usuario.nombre.split(" ")[0]
        asunto = "Restablece tu contraseña de la Mochila virtual"
        texto = (
            f"Hola {nombre}:\n\n"
            f"Pediste restablecer la contraseña de tu cuenta «{usuario.usuario}» en la Mochila virtual "
            "del NASA Space Apps Challenge San Vicente Ferrer.\n\n"
            "Para elegir una nueva, abre este enlace. Sirve una sola vez y durante 1 hora:\n"
            f"{enlace}\n\n"
            "Si no fuiste tú, ignora este correo: tu contraseña sigue igual.\n\n"
            "Equipo de Ola Fibonacci"
        )
        e = html.escape
        cuerpo_html = f"""<!doctype html><html lang="es"><body style="margin:0;padding:24px;background:#f4f2fb;font-family:Arial,sans-serif;color:#1d1640">
<div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:12px;padding:28px">
<p style="margin:0 0 6px;color:#d4302a;font-weight:bold">NASA Space Apps · San Vicente Ferrer</p>
<h1 style="margin:0 0 16px;font-size:22px">Restablece tu contraseña</h1>
<p>Hola {e(nombre)}:</p>
<p>Pediste restablecer la contraseña de tu cuenta <strong>{e(usuario.usuario)}</strong> en la Mochila virtual.</p>
<p style="margin:24px 0"><a href="{e(enlace)}" style="background:#5b34c4;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:999px;font-weight:bold;display:inline-block">Elegir nueva contraseña</a></p>
<p style="font-size:14px;color:#595377">El enlace sirve una sola vez y durante 1 hora. Si el botón no funciona, copia esta dirección en tu navegador:<br><span style="word-break:break-all">{e(enlace)}</span></p>
<p style="font-size:14px;color:#595377">Si no fuiste tú, ignora este correo: tu contraseña sigue igual.</p>
<p>Equipo de Ola Fibonacci</p>
</div></body></html>"""
        self._correos.enviar(usuario.email, asunto, texto, cuerpo_html)

    # ------------------------------------------------------------ 2. usar el enlace

    def _usuario_del_codigo(self, codigo: str) -> tuple[Usuario, str]:
        huella = _huella(codigo or "")
        registro = self._restablecimientos.buscar(huella)
        if not registro:
            raise EnlaceInvalido("Este enlace no es válido. Pide uno nuevo desde «¿Olvidaste tu contraseña?».")
        usuario_id, version, expira, usado = registro
        usuario = self._usuarios.por_id(usuario_id)
        if usado or not usuario or usuario.version_token != version:
            raise EnlaceInvalido("Este enlace ya se usó o la contraseña cambió después. Pide uno nuevo si lo necesitas.")
        if time.time() > expira:
            raise EnlaceInvalido("Este enlace venció (sirve por 1 hora). Pide uno nuevo.")
        if not usuario.activo:
            raise NoAutenticado("Tu cuenta está desactivada. Escríbele al equipo organizador.")
        return usuario, huella

    def verificar(self, codigo: str) -> Usuario:
        return self._usuario_del_codigo(codigo)[0]

    def restablecer(self, codigo: str, nueva: str) -> tuple[str, Usuario]:
        usuario, huella = self._usuario_del_codigo(codigo)
        validar_contrasena(nueva)
        self._restablecimientos.marcar_usado(huella)
        usuario.password_hash = self._hasher.hashear(nueva)
        usuario.invalidar_sesiones()  # cierra sesiones viejas y anula otros enlaces pendientes
        usuario = self._usuarios.guardar(usuario)
        self._intentos.limpiar(f"u:{usuario.usuario}")  # quita el bloqueo por intentos fallidos
        return self._tokens.emitir(usuario), usuario

    # ------------------------------------------------------------ correo de prueba (panel)

    @property
    def correo_configurado(self) -> bool:
        return self._correos.configurado

    @property
    def remitente(self) -> str:
        return self._correos.remitente

    def enviar_prueba(self, destino: str) -> None:
        if "@" not in (destino or ""):
            raise ErrorValidacion("Escribe un correo válido para la prueba.", {"campo": "destino"})
        texto = ("Este es un correo de prueba de la Mochila virtual del NASA Space Apps Challenge San Vicente Ferrer.\n\n"
                 "Si lo recibiste, la recuperación de contraseñas por correo está funcionando.")
        self._correos.enviar_ahora(destino.strip(), "Prueba de correo: Mochila virtual", texto)
