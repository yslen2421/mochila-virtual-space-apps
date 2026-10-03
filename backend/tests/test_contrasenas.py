"""El Superadmin cambia la contraseña de cualquier cuenta."""
import re


def _id(cliente, admin, usuario):
    return next(u["id"] for u in cliente.get("/api/v1/admin/usuarios", headers=admin).json["usuarios"] if u["usuario"] == usuario)


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


def test_correo_invalido_al_crear(cliente, admin):
    r = cliente.post("/api/v1/admin/usuarios", headers=admin, json={
        "nombre": "X", "usuario": "xx.yy", "categoria": "universidad", "email": "no-es-correo"})
    assert r.status_code == 400 and r.json["error"]["detalle"] == {"campo": "email"}


def test_rutas_de_correo_ya_no_existen(cliente):
    assert cliente.post("/api/v1/auth/olvide-contrasena", json={"identificador": "ana"}).status_code == 404
