"""Cambiar contraseñas desde el panel y recuperarlas por correo."""
import email
import re
from email import policy


def _correos(app):
    carpeta = app.extensions["contenedor"].config.carpeta_datos / "correos"
    return sorted(carpeta.glob("*.eml")) if carpeta.exists() else []


def _enlace(app):
    msg = email.message_from_bytes(_correos(app)[-1].read_bytes(), policy=policy.default)
    texto = msg.get_body(("plain",)).get_content()
    return msg, re.search(r"https://\S+/#/restablecer/(\S+)", texto)


def _id(cliente, admin, usuario):
    return next(u["id"] for u in cliente.get("/api/v1/admin/usuarios", headers=admin).json["usuarios"] if u["usuario"] == usuario)


# ---------------------------------------------------------------- desde el panel

def test_superadmin_pone_la_contrasena_que_quiera(cliente, admin, ana):
    r = cliente.post(f"/api/v1/admin/usuarios/{_id(cliente, admin, 'ana')}/restablecer-contrasena",
                     headers=admin, json={"contrasena": "nueva-clave-ana"})
    assert r.status_code == 200 and r.json["usuario"]["contrasena_generada"] == "nueva-clave-ana"
    assert cliente.get("/api/v1/mochila", headers=ana).status_code == 401  # la sesión vieja se cierra
    assert cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "nueva-clave-ana"}).status_code == 200


def test_contrasena_corta_rechazada_y_generada_sigue_funcionando(cliente, admin):
    uid = _id(cliente, admin, "ana")
    assert cliente.post(f"/api/v1/admin/usuarios/{uid}/restablecer-contrasena", headers=admin,
                        json={"contrasena": "corta"}).status_code == 400
    r = cliente.post(f"/api/v1/admin/usuarios/{uid}/restablecer-contrasena", headers=admin)
    assert re.match(r"^[a-z]+-[a-z]+-\d{4}$", r.json["usuario"]["contrasena_generada"])


def test_participante_no_puede_cambiar_contrasenas_ajenas(cliente, admin, ana):
    uid = _id(cliente, admin, "admin")
    assert cliente.post(f"/api/v1/admin/usuarios/{uid}/restablecer-contrasena", headers=ana,
                        json={"contrasena": "hackeado123"}).status_code == 403


# ---------------------------------------------------------------- olvidé mi contraseña

def test_flujo_completo_por_correo(app, cliente):
    r = cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ana"})
    assert r.status_code == 200 and "enlace" in r.json["mensaje"]
    msg, hallado = _enlace(app)
    assert msg["To"] == "ana@correo.com"
    assert hallado, "el correo trae el enlace"
    assert hallado.group(0).startswith("https://mochila.ejemplo.org/#/restablecer/")  # dominio configurado, no el Host
    codigo = hallado.group(1)

    v = cliente.post("/api/v1/auth/restablecer/verificar", json={"codigo": codigo})
    assert v.status_code == 200 and v.json["usuario"]["nombre"] == "Ana"

    r = cliente.post("/api/v1/auth/restablecer", json={"codigo": codigo, "nueva": "recuperada-123"})
    assert r.status_code == 200 and r.json["token"]
    assert cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "recuperada-123"}).status_code == 200
    # El enlace sirve una sola vez
    r = cliente.post("/api/v1/auth/restablecer", json={"codigo": codigo, "nueva": "otra-vez-123"})
    assert r.status_code == 400 and r.json["error"]["codigo"] == "ENLACE_INVALIDO"


def test_por_correo_tambien_funciona(app, cliente):
    cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ANA@correo.com"})
    assert len(_correos(app)) == 1


def test_no_revela_si_la_cuenta_existe(app, cliente, admin):
    existe = cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ana"}).json
    no_existe = cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "nadie"}).json
    sin_correo = cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "admin"}).json
    assert existe == no_existe == sin_correo
    assert len(_correos(app)) == 1  # solo a quien tiene cuenta y correo


def test_enlace_vencido(app, cliente):
    cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ana"})
    codigo = _enlace(app)[1].group(1)
    app.extensions["contenedor"].db.conexion().execute("UPDATE restablecimientos SET expira_en = 0")
    r = cliente.post("/api/v1/auth/restablecer", json={"codigo": codigo, "nueva": "recuperada-123"})
    assert r.status_code == 400 and "venció" in r.json["error"]["mensaje"]


def test_enlace_muere_si_el_admin_cambia_la_contrasena(app, cliente, admin):
    cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ana"})
    codigo = _enlace(app)[1].group(1)
    cliente.post(f"/api/v1/admin/usuarios/{_id(cliente, admin, 'ana')}/restablecer-contrasena", headers=admin)
    assert cliente.post("/api/v1/auth/restablecer/verificar", json={"codigo": codigo}).status_code == 400


def test_limite_de_correos_por_cuenta(app, cliente):
    for _ in range(5):
        cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ana"})
    assert len(_correos(app)) == 3  # máximo 3 por hora para la misma cuenta


def test_cuenta_desactivada_no_recibe_correo(app, cliente, admin):
    cliente.put(f"/api/v1/admin/usuarios/{_id(cliente, admin, 'ana')}", headers=admin, json={"activo": False})
    cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ana"})
    assert _correos(app) == []


def test_restablecer_quita_el_bloqueo_por_intentos(app, cliente):
    for _ in range(8):
        cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "mala"})
    assert cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "ana-secreta"}).status_code == 429
    cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ana"})
    cliente.post("/api/v1/auth/restablecer", json={"codigo": _enlace(app)[1].group(1), "nueva": "recuperada-123"})
    assert cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "recuperada-123"}).status_code == 200


def test_correo_invalido_al_crear(cliente, admin):
    r = cliente.post("/api/v1/admin/usuarios", headers=admin, json={
        "nombre": "X", "usuario": "xx.yy", "categoria": "universidad", "email": "no-es-correo"})
    assert r.status_code == 400 and r.json["error"]["detalle"] == {"campo": "email"}


def test_estado_y_prueba_de_correo(app, cliente, admin):
    estado = cliente.get("/api/v1/admin/correo", headers=admin).json
    assert estado["configurado"] is False and estado["url_portal"] == "https://mochila.ejemplo.org/"
    r = cliente.post("/api/v1/admin/correo/prueba", headers=admin, json={"destino": "yo@correo.com"})
    assert r.status_code == 200 and len(_correos(app)) == 1
