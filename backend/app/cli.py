"""Comandos de consola para operar el portal.

    flask --app wsgi inicializar           # crea el Superadmin (desde .env) y las secciones base
    flask --app wsgi crear-superadmin      # crea otro Superadmin de forma interactiva
    flask --app wsgi cambiar-contrasena    # cambia la contraseña de una cuenta (si se olvidó)
    flask --app wsgi sembrar               # carga las secciones de ejemplo de la mochila
    flask --app wsgi respaldar             # copia de seguridad de la base de datos
    flask --app wsgi limpiar-archivos      # borra archivos que ningún ítem usa
"""
from __future__ import annotations

import os

import click
from flask import Flask, current_app

from .application.comandos import CrearItem, CrearSeccion, CrearUsuario
from .domain.entidades import Modalidad, Rol, TipoItem
from .domain.errores import ErrorDominio


def _c():
    return current_app.extensions["contenedor"]


def _hay_superadmin() -> bool:
    return any(u.rol == Rol.SUPERADMIN for u in _c().usuarios.listar())


def _crear_superadmin(usuario: str, nombre: str, contrasena: str) -> None:
    _c().usuarios.crear(CrearUsuario(usuario=usuario, nombre=nombre, rol=Rol.SUPERADMIN,
                                     modalidad=Modalidad.PRESENCIAL, contrasena=contrasena))


# Contenido inicial: las secciones del documento de requisitos, con ejemplos para editar.
SECCIONES_BASE: list[tuple[str, str, str, list[CrearItem]]] = [
    ("Anuncios", "📣", "Avisos del equipo organizador de Ola Fibonacci.", [
        CrearItem(TipoItem.TEXTO, "¡Bienvenida a la tripulación!",
                  "Esta es tu mochila virtual del NASA Space Apps Challenge San Vicente Ferrer. "
                  "Aquí encontrarás todo lo que necesitas antes, durante y después del hackathon.\n\n"
                  "Revisa esta sección seguido: aquí publicaremos cambios de horario y avisos importantes."),
    ]),
    ("Cronograma", "🗓️", "Agenda del evento, con lugares y enlaces de conexión.", [
        CrearItem(TipoItem.EVENTO, "Registro y bienvenida", fecha="2026-11-14", hora_inicio="08:00",
                  hora_fin="09:00", lugar="Sede principal · San Vicente Ferrer",
                  descripcion="Llegada, entrega de escarapelas y acomodación de equipos."),
        CrearItem(TipoItem.EVENTO, "Inauguración y presentación de retos", fecha="2026-11-14",
                  hora_inicio="09:00", hora_fin="10:00", lugar="Auditorio + transmisión virtual",
                  url="https://meet.google.com/", descripcion="Reemplaza el enlace por el de la transmisión real."),
        CrearItem(TipoItem.EVENTO, "Inicio del hackathon", fecha="2026-11-14", hora_inicio="10:00",
                  lugar="Sede y salas virtuales"),
        CrearItem(TipoItem.EVENTO, "Presentaciones finales", fecha="2026-11-15", hora_inicio="14:00",
                  hora_fin="17:00", lugar="Auditorio + transmisión virtual"),
        CrearItem(TipoItem.EVENTO, "Feria astronómica abierta al municipio", fecha="2026-11-15",
                  hora_inicio="17:00", lugar="Parque principal"),
    ]),
    ("Recursos de los retos", "🛰️", "Datos abiertos de la NASA, retos y guías de inicio.", [
        CrearItem(TipoItem.ENLACE, "Retos oficiales de Space Apps", url="https://www.spaceappschallenge.org/",
                  descripcion="Lee los retos y elige el de tu equipo."),
        CrearItem(TipoItem.ENLACE, "Datos abiertos de la NASA", url="https://data.nasa.gov/",
                  descripcion="Catálogo de conjuntos de datos abiertos."),
        CrearItem(TipoItem.ENLACE, "NASA Earthdata", url="https://www.earthdata.nasa.gov/",
                  descripcion="Datos de observación de la Tierra."),
    ]),
    ("Cómo solicitar tu licencia de AWS", "☁️", "Guía paso a paso para obtener créditos de Amazon Web Services.", [
        CrearItem(TipoItem.TEXTO, "Paso a paso",
                  "1. Crea tu cuenta en la plataforma de Space Apps y únete a un equipo.\n"
                  "2. Sigue las instrucciones del correo oficial de Space Apps sobre los créditos de AWS.\n"
                  "3. Si tienes problemas, búscanos en Mentores y soporte.\n\n"
                  "(Edita este texto con el procedimiento oficial de esta edición.)"),
    ]),
    ("Kit de herramientas", "🧰", "Herramientas recomendadas para tu equipo.", [
        CrearItem(TipoItem.ENLACE, "GitHub", url="https://github.com/", descripcion="Código y control de versiones."),
        CrearItem(TipoItem.ENLACE, "Visual Studio Code", url="https://code.visualstudio.com/", descripcion="Editor de código."),
        CrearItem(TipoItem.ENLACE, "Figma", url="https://www.figma.com/", descripcion="Diseño de interfaces y prototipos."),
    ]),
    ("Wallpapers", "🌌", "Fondos de pantalla oficiales del evento en alta resolución.", []),
    ("Souvenirs virtuales", "🎁", "Stickers, insignias, fondos para Zoom y certificados.", []),
    ("Mentores y soporte", "🧑‍🚀", "A quién acudir y en qué horario.", [
        CrearItem(TipoItem.TEXTO, "Canales de soporte",
                  "Presencial: mesa de ayuda junto al registro.\nVirtual: canal de soporte (agrega aquí el enlace)."),
    ]),
    ("Guía de entrega", "🚀", "Cómo subir tu proyecto a la plataforma oficial de Space Apps.", []),
    ("Preguntas frecuentes", "❓", "Respuestas rápidas a lo que más nos preguntan.", []),
]


def sembrar_secciones() -> int:
    c = _c()
    if c.secciones.listar():
        return 0
    for titulo, icono, descripcion, items in SECCIONES_BASE:
        seccion = c.secciones.crear(CrearSeccion(titulo=titulo, descripcion=descripcion, icono=icono))
        for item in items:
            c.items.crear(seccion.id, item)
    return len(SECCIONES_BASE)


def registrar_comandos(app: Flask) -> None:
    @app.cli.command("inicializar")
    def inicializar():
        """Crea el Superadmin desde SUPERADMIN_USUARIO / SUPERADMIN_CONTRASENA y las secciones base."""
        if not _hay_superadmin():
            usuario = os.environ.get("SUPERADMIN_USUARIO")
            contrasena = os.environ.get("SUPERADMIN_CONTRASENA")
            if usuario and contrasena:
                _crear_superadmin(usuario, os.environ.get("SUPERADMIN_NOMBRE", "Superadmin"), contrasena)
                click.echo(f"✔ Superadmin '{usuario}' creado.")
            else:
                click.echo("! No hay Superadmin. Define SUPERADMIN_USUARIO y SUPERADMIN_CONTRASENA "
                           "o ejecuta: flask --app wsgi crear-superadmin")
        n = sembrar_secciones()
        click.echo(f"✔ {n} secciones base creadas." if n else "✔ Las secciones ya existían; no se tocaron.")

    @app.cli.command("crear-superadmin")
    @click.option("--usuario", prompt="Usuario")
    @click.option("--nombre", prompt="Nombre", default="Superadmin")
    @click.option("--contrasena", prompt="Contraseña", hide_input=True, confirmation_prompt=True)
    def crear_superadmin(usuario, nombre, contrasena):
        """Crea un Superadmin."""
        try:
            _crear_superadmin(usuario, nombre, contrasena)
            click.echo(f"✔ Superadmin '{usuario}' creado.")
        except ErrorDominio as e:
            raise click.ClickException(e.mensaje)

    @app.cli.command("cambiar-contrasena")
    @click.option("--usuario", prompt="Usuario", default="admin", show_default=True)
    @click.option("--contrasena", prompt="Nueva contraseña", hide_input=True, confirmation_prompt="Repítela")
    def cambiar_contrasena(usuario, contrasena):
        """Cambia la contraseña de cualquier cuenta (sirve si se olvidó la del admin)."""
        try:
            u = _c().usuarios.fijar_contrasena(usuario, contrasena)
        except ErrorDominio as e:
            raise click.ClickException(e.mensaje)
        _c().auth.desbloquear(u.usuario)
        click.echo(f"✔ Contraseña de '{u.usuario}' cambiada. Ya puedes entrar.")

    @app.cli.command("sembrar")
    def sembrar():
        """Carga las secciones de ejemplo (solo si no hay ninguna)."""
        n = sembrar_secciones()
        click.echo(f"✔ {n} secciones creadas." if n else "Ya hay secciones; no se cargó nada.")

    @app.cli.command("respaldar")
    @click.option("--conservar", default=30, help="Cuántos respaldos guardar (los más viejos se borran).")
    def respaldar(conservar):
        """Copia segura de la base de datos (funciona con el portal encendido)."""
        import sqlite3
        from datetime import datetime
        from pathlib import Path

        config = _c().config
        carpeta = Path(config.carpeta_datos) / "respaldos"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"portal-{datetime.now():%Y%m%d-%H%M%S}.db"
        with sqlite3.connect(config.ruta_bd) as origen, sqlite3.connect(destino) as copia:
            origen.backup(copia)
        for viejo in sorted(carpeta.glob("portal-*.db"))[:-conservar]:
            viejo.unlink()
        click.echo(f"✔ Respaldo guardado en {destino}")

    @app.cli.command("limpiar-archivos")
    def limpiar_archivos():
        """Borra archivos subidos que ya no usa ningún ítem."""
        click.echo(f"✔ {_c().archivos.limpiar_huerfanos()} archivos eliminados.")
