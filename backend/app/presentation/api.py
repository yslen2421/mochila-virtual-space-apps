"""Controladores REST (capa de presentación). Solo JSON, nunca HTML.

Cada función: lee la petición → valida en el borde (esquemas) → llama un caso de
uso → serializa la respuesta. No hay lógica de negocio aquí.
"""
from __future__ import annotations

import os
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, current_app, g, jsonify, request, send_file

from ..contenedor import Contenedor
from ..domain.entidades import Rol
from ..domain.errores import ErrorValidacion, NoAutenticado
from . import esquemas, serializadores as ser

api = Blueprint("api", __name__, url_prefix="/api/v1")


def svc() -> Contenedor:
    return current_app.extensions["contenedor"]


def _json():
    return request.get_json(silent=True)


def _ip_cliente() -> str:
    return request.remote_addr or "desconocida"


# ---------------------------------------------------------------- decoradores de acceso

def requiere_sesion(funcion):
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        cabecera = request.headers.get("Authorization", "")
        if not cabecera.startswith("Bearer "):
            raise NoAutenticado("Inicia sesión para continuar.")
        g.usuario = svc().auth.usuario_de_token(cabecera[7:].strip())
        return funcion(*args, **kwargs)
    return envoltura


def requiere_superadmin(funcion):
    @requiere_sesion
    @wraps(funcion)
    def envoltura(*args, **kwargs):
        svc().auth.exigir_rol(g.usuario, Rol.SUPERADMIN)
        return funcion(*args, **kwargs)
    return envoltura


# ---------------------------------------------------------------- salud

@api.get("/salud")
def salud():
    svc().db.uno("SELECT 1")
    return jsonify(estado="ok")


# ---------------------------------------------------------------- identidad del evento (pública)

@api.get("/publico/marca")
def publico_marca():
    """Logo del evento y aliados: se muestran incluso antes de iniciar sesión."""
    # Sin caché: si el Superadmin cambia el logo, se ve de inmediato.
    return jsonify(ser.marca(svc().marca.marca(incluir_grupos_vacios=False)))


@api.get("/publico/archivos/<int:archivo_id>")
def publico_archivo(archivo_id: int):
    archivo, ruta, es_miniatura = svc().marca.archivo_publico(archivo_id, request.args.get("miniatura") == "1")
    respuesta = send_file(ruta, mimetype="image/webp" if es_miniatura else archivo.tipo_mime,
                          download_name=archivo.nombre_original, conditional=True, max_age=3600)
    respuesta.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
    respuesta.headers["Cache-Control"] = "public, max-age=3600"
    return respuesta


# ---------------------------------------------------------------- autenticación

@api.post("/auth/login")
def login():
    usuario, contrasena = esquemas.credenciales(_json())
    token, u = svc().auth.iniciar_sesion(usuario, contrasena, _ip_cliente())
    return jsonify(token=token, usuario=ser.usuario(u), expira_en_horas=svc().config.horas_token)


@api.post("/auth/login-panel")
def login_panel():
    """Ingreso del panel de organización: solo cuentas Superadmin obtienen sesión."""
    usuario, contrasena = esquemas.credenciales(_json())
    token, u = svc().auth.iniciar_sesion(usuario, contrasena, _ip_cliente(), rol_requerido=Rol.SUPERADMIN)
    return jsonify(token=token, usuario=ser.usuario(u), expira_en_horas=svc().config.horas_token)


@api.get("/auth/yo")
@requiere_sesion
def yo():
    return jsonify(usuario=ser.usuario(g.usuario))


@api.post("/auth/cambiar-contrasena")
@requiere_sesion
def cambiar_contrasena():
    actual, nueva = esquemas.cambio_contrasena(_json())
    return jsonify(token=svc().auth.cambiar_contrasena(g.usuario, actual, nueva))


# ---------------------------------------------------------------- mochila (participante y admin)

@api.get("/mochila")
@requiere_sesion
def mochila():
    return jsonify(secciones=[ser.seccion(s, n) for s, n in svc().mochila.indice()])


@api.get("/mochila/proximos")
@requiere_sesion
def mochila_proximos():
    ahora = datetime.now(ZoneInfo(svc().config.zona_horaria)).strftime("%Y-%m-%d %H:%M")
    return jsonify(ahora=ahora, eventos=[ser.item(i) for i in svc().mochila.proximos_eventos(ahora)])


@api.get("/mochila/secciones/<int:seccion_id>")
@requiere_sesion
def mochila_seccion(seccion_id: int):
    return jsonify(seccion=ser.seccion(svc().mochila.seccion(g.usuario, seccion_id), con_items=True))


@api.get("/archivos/<int:archivo_id>")
@requiere_sesion
def descargar_archivo(archivo_id: int):
    descargar = request.args.get("descargar") == "1"
    archivo, ruta, es_miniatura = svc().archivos.para_descarga(
        g.usuario, archivo_id, registrar=descargar, miniatura=request.args.get("miniatura") == "1")
    mime = "image/webp" if es_miniatura else archivo.tipo_mime
    nombre = archivo.nombre_original

    if svc().config.usar_x_accel:
        # Nginx entrega el archivo directamente; Flask solo autoriza.
        relativo = os.path.relpath(ruta, svc().config.carpeta_archivos)
        respuesta = Response(status=200, mimetype=mime)
        respuesta.headers["X-Accel-Redirect"] = f"/_archivos_protegidos/{relativo}"
        disposicion = "attachment" if descargar else "inline"
        respuesta.headers["Content-Disposition"] = f"{disposicion}; filename*=UTF-8''{_codificar(nombre)}"
    else:
        respuesta = send_file(ruta, mimetype=mime, as_attachment=descargar, download_name=nombre,
                              conditional=True, max_age=86400)
    # Archivos subidos nunca se ejecutan como página, aunque sean SVG o HTML disfrazado.
    respuesta.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
    respuesta.headers["Cache-Control"] = "private, max-age=86400"
    return respuesta


def _codificar(nombre: str) -> str:
    from urllib.parse import quote
    return quote(nombre)


# ---------------------------------------------------------------- admin: secciones

@api.get("/admin/secciones")
@requiere_superadmin
def admin_listar_secciones():
    return jsonify(secciones=[ser.seccion(s, n) for s, n in svc().secciones.listar()])


@api.post("/admin/secciones")
@requiere_superadmin
def admin_crear_seccion():
    return jsonify(seccion=ser.seccion(svc().secciones.crear(esquemas.crear_seccion(_json())))), 201


@api.put("/admin/secciones/orden")
@requiere_superadmin
def admin_reordenar_secciones():
    svc().secciones.reordenar(esquemas.lista_ids(_json()))
    return jsonify(ok=True)


@api.get("/admin/secciones/<int:seccion_id>")
@requiere_superadmin
def admin_obtener_seccion(seccion_id: int):
    seccion = svc().secciones.obtener(seccion_id)
    seccion.items = svc().items.listar(seccion_id)
    return jsonify(seccion=ser.seccion(seccion, con_items=True))


@api.route("/admin/secciones/<int:seccion_id>", methods=["PUT", "PATCH"])
@requiere_superadmin
def admin_actualizar_seccion(seccion_id: int):
    s = svc().secciones.actualizar(seccion_id, esquemas.actualizar_seccion(_json()))
    return jsonify(seccion=ser.seccion(s))


@api.delete("/admin/secciones/<int:seccion_id>")
@requiere_superadmin
def admin_eliminar_seccion(seccion_id: int):
    svc().secciones.eliminar(seccion_id)
    return "", 204


# ---------------------------------------------------------------- admin: ítems

@api.get("/admin/secciones/<int:seccion_id>/items")
@requiere_superadmin
def admin_listar_items(seccion_id: int):
    return jsonify(items=[ser.item(i) for i in svc().items.listar(seccion_id)])


@api.post("/admin/secciones/<int:seccion_id>/items")
@requiere_superadmin
def admin_crear_item(seccion_id: int):
    return jsonify(item=ser.item(svc().items.crear(seccion_id, esquemas.crear_item(_json())))), 201


@api.put("/admin/secciones/<int:seccion_id>/items/orden")
@requiere_superadmin
def admin_reordenar_items(seccion_id: int):
    svc().items.reordenar(seccion_id, esquemas.lista_ids(_json()))
    return jsonify(ok=True)


@api.route("/admin/items/<int:item_id>", methods=["PUT", "PATCH"])
@requiere_superadmin
def admin_actualizar_item(item_id: int):
    return jsonify(item=ser.item(svc().items.actualizar(item_id, esquemas.actualizar_item(_json()))))


@api.delete("/admin/items/<int:item_id>")
@requiere_superadmin
def admin_eliminar_item(item_id: int):
    svc().items.eliminar(item_id)
    return "", 204


# ---------------------------------------------------------------- admin: archivos

@api.post("/admin/archivos")
@requiere_superadmin
def admin_subir_archivo():
    archivo = request.files.get("archivo")
    if not archivo or not archivo.filename:
        raise ErrorValidacion("Adjunta un archivo en el campo 'archivo'.", {"campo": "archivo"})
    return jsonify(archivo=ser.archivo(svc().archivos.subir(archivo.filename, archivo.stream))), 201


# ---------------------------------------------------------------- admin: usuarios

def _con_contrasena(r) -> dict:
    return {**ser.usuario(r.usuario), "contrasena_generada": r.contrasena}


@api.get("/admin/usuarios")
@requiere_superadmin
def admin_listar_usuarios():
    return jsonify(usuarios=[ser.usuario(u) for u in svc().usuarios.listar()])


@api.post("/admin/usuarios")
@requiere_superadmin
def admin_crear_usuario():
    return jsonify(usuario=_con_contrasena(svc().usuarios.crear(esquemas.crear_usuario(_json())))), 201


@api.post("/admin/usuarios/importar")
@requiere_superadmin
def admin_importar_usuarios():
    creados = svc().usuarios.importar(esquemas.importar_usuarios(_json()))
    return jsonify(usuarios=[_con_contrasena(r) for r in creados]), 201


@api.route("/admin/usuarios/<int:usuario_id>", methods=["PUT", "PATCH"])
@requiere_superadmin
def admin_actualizar_usuario(usuario_id: int):
    u = svc().usuarios.actualizar(g.usuario, usuario_id, esquemas.actualizar_usuario(_json()))
    return jsonify(usuario=ser.usuario(u))


@api.post("/admin/usuarios/<int:usuario_id>/restablecer-contrasena")
@requiere_superadmin
def admin_restablecer_contrasena(usuario_id: int):
    return jsonify(usuario=_con_contrasena(svc().usuarios.restablecer_contrasena(usuario_id)))


@api.delete("/admin/usuarios/<int:usuario_id>")
@requiere_superadmin
def admin_eliminar_usuario(usuario_id: int):
    svc().usuarios.eliminar(g.usuario, usuario_id)
    return "", 204


# ---------------------------------------------------------------- admin: logos y aliados

@api.get("/admin/marca")
@requiere_superadmin
def admin_marca():
    return jsonify(ser.marca(svc().marca.marca(incluir_grupos_vacios=True)))


@api.put("/admin/marca/logo")
@requiere_superadmin
def admin_fijar_logo():
    return jsonify(logo=ser.archivo_publico(svc().marca.fijar_logo(esquemas.logo_evento(_json()))))


@api.post("/admin/aliados/grupos")
@requiere_superadmin
def admin_crear_grupo():
    return jsonify(grupo=ser.grupo_aliados(svc().marca.crear_grupo(esquemas.titulo_grupo(_json())))), 201


@api.put("/admin/aliados/grupos/orden")
@requiere_superadmin
def admin_reordenar_grupos():
    svc().marca.reordenar_grupos(esquemas.lista_ids(_json()))
    return jsonify(ok=True)


@api.route("/admin/aliados/grupos/<int:grupo_id>", methods=["PUT", "PATCH"])
@requiere_superadmin
def admin_renombrar_grupo(grupo_id: int):
    return jsonify(grupo=ser.grupo_aliados(svc().marca.renombrar_grupo(grupo_id, esquemas.titulo_grupo(_json()))))


@api.delete("/admin/aliados/grupos/<int:grupo_id>")
@requiere_superadmin
def admin_eliminar_grupo(grupo_id: int):
    svc().marca.eliminar_grupo(grupo_id)
    return "", 204


@api.post("/admin/aliados/grupos/<int:grupo_id>/aliados")
@requiere_superadmin
def admin_crear_aliado(grupo_id: int):
    a = svc().marca.crear_aliado(grupo_id, esquemas.datos_aliado(_json(), requerido=True))
    return jsonify(aliado=ser.aliado(a)), 201


@api.put("/admin/aliados/grupos/<int:grupo_id>/aliados/orden")
@requiere_superadmin
def admin_reordenar_aliados(grupo_id: int):
    svc().marca.reordenar_aliados(grupo_id, esquemas.lista_ids(_json()))
    return jsonify(ok=True)


@api.route("/admin/aliados/<int:aliado_id>", methods=["PUT", "PATCH"])
@requiere_superadmin
def admin_actualizar_aliado(aliado_id: int):
    a = svc().marca.actualizar_aliado(aliado_id, esquemas.datos_aliado(_json(), requerido=False))
    return jsonify(aliado=ser.aliado(a))


@api.delete("/admin/aliados/<int:aliado_id>")
@requiere_superadmin
def admin_eliminar_aliado(aliado_id: int):
    svc().marca.eliminar_aliado(aliado_id)
    return "", 204


# ---------------------------------------------------------------- admin: estadísticas

@api.get("/admin/estadisticas")
@requiere_superadmin
def admin_estadisticas():
    return jsonify(svc().estadisticas.resumen())
