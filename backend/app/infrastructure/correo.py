"""Envío de correos.

- EnviadorSmtp: el real. Sirve con Gmail, Outlook, Brevo, Mailgun, Amazon SES… cualquier SMTP.
- EnviadorArchivo: si no hay SMTP configurado, guarda cada correo como archivo en
  datos/correos/ (así se puede probar todo en el computador sin enviar nada).
- EnvioEnSegundoPlano: envuelve a cualquiera de los dos para que la respuesta al
  navegador no espere al servidor de correo (y que el tiempo de respuesta no
  revele si una cuenta existe).
"""
from __future__ import annotations

import logging
import re
import smtplib
import ssl
import threading
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr
from pathlib import Path

log = logging.getLogger("portal.correo")


def _mensaje(remitente: str, destino: str, asunto: str, texto: str, html: str | None) -> EmailMessage:
    msg = EmailMessage()
    nombre, direccion = parseaddr(remitente)
    msg["From"] = formataddr((nombre, direccion)) if nombre else direccion
    msg["To"] = destino
    msg["Subject"] = asunto
    msg["Message-ID"] = make_msgid(domain=direccion.split("@")[-1] if "@" in direccion else None)
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


class EnviadorSmtp:
    configurado = True

    def __init__(self, servidor: str, puerto: int, usuario: str, contrasena: str, remitente: str, seguridad: str = "starttls"):
        self._servidor = servidor
        self._puerto = puerto
        self._usuario = usuario
        self._contrasena = contrasena
        self.remitente = remitente
        self._seguridad = seguridad.lower()

    def enviar(self, destino: str, asunto: str, texto: str, html: str | None = None) -> None:
        msg = _mensaje(self.remitente, destino, asunto, texto, html)
        contexto = ssl.create_default_context()
        if self._seguridad == "ssl":
            conexion = smtplib.SMTP_SSL(self._servidor, self._puerto, context=contexto, timeout=20)
        else:
            conexion = smtplib.SMTP(self._servidor, self._puerto, timeout=20)
        with conexion as smtp:
            if self._seguridad == "starttls":
                smtp.starttls(context=contexto)
            if self._usuario:
                smtp.login(self._usuario, self._contrasena)
            smtp.send_message(msg)
        log.info("Correo enviado a %s: %s", destino, asunto)

    enviar_ahora = enviar


class EnviadorArchivo:
    """Modo sin SMTP: deja cada correo en un archivo .eml (se abre con Outlook, Thunderbird o el Bloc de notas)."""
    configurado = False

    def __init__(self, carpeta: str, remitente: str):
        self._carpeta = Path(carpeta)
        self.remitente = remitente

    def enviar(self, destino: str, asunto: str, texto: str, html: str | None = None) -> None:
        self._carpeta.mkdir(parents=True, exist_ok=True)
        seguro = re.sub(r"[^a-zA-Z0-9@._-]", "_", destino)[:60]
        ruta = self._carpeta / f"{datetime.now():%Y%m%d-%H%M%S-%f}-{seguro}.eml"
        ruta.write_bytes(bytes(_mensaje(self.remitente, destino, asunto, texto, html)))
        log.warning("SMTP sin configurar: el correo para %s se guardó en %s", destino, ruta)

    enviar_ahora = enviar


class EnvioEnSegundoPlano:
    def __init__(self, enviador):
        self._enviador = enviador

    @property
    def configurado(self) -> bool:
        return self._enviador.configurado

    @property
    def remitente(self) -> str:
        return self._enviador.remitente

    def enviar(self, destino: str, asunto: str, texto: str, html: str | None = None) -> None:
        def tarea():
            try:
                self._enviador.enviar(destino, asunto, texto, html)
            except Exception:
                log.exception("No se pudo enviar el correo a %s", destino)
        threading.Thread(target=tarea, daemon=True).start()

    def enviar_ahora(self, destino: str, asunto: str, texto: str, html: str | None = None) -> None:
        """Para el correo de prueba del panel: aquí sí queremos ver el error si falla."""
        self._enviador.enviar(destino, asunto, texto, html)
