import io


def test_login_incorrecto_da_error_uniforme(cliente):
    r = cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "mala"})
    assert r.status_code == 401
    assert r.json["error"]["codigo"] == "NO_AUTENTICADO"
    assert set(r.json["error"]) == {"codigo", "mensaje", "detalle"}


def test_bloqueo_por_intentos(cliente):
    for _ in range(8):
        cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "mala"})
    r = cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "ana-secreta"})
    assert r.status_code == 429


def test_sin_token_no_hay_mochila(cliente):
    r = cliente.get("/api/v1/mochila")
    assert r.status_code == 401


def test_participante_no_entra_al_admin(cliente, ana):
    assert cliente.get("/api/v1/admin/secciones", headers=ana).status_code == 403


def test_flujo_completo_mochila(cliente, admin, ana):
    # El admin crea una sección visible y una oculta
    s = cliente.post("/api/v1/admin/secciones", json={"titulo": "Wallpapers", "icono": "🌌"}, headers=admin).json["seccion"]
    oculta = cliente.post("/api/v1/admin/secciones", json={"titulo": "Borrador", "activa": False}, headers=admin).json["seccion"]

    # Sube un archivo y crea un ítem que lo usa
    arch = cliente.post("/api/v1/admin/archivos", headers=admin, content_type="multipart/form-data",
                        data={"archivo": (io.BytesIO(b"%PDF-1.4 hola"), "guia.pdf")}).json["archivo"]
    assert arch["tipo_mime"] == "application/pdf"
    item = cliente.post(f"/api/v1/admin/secciones/{s['id']}/items", headers=admin,
                        json={"tipo": "archivo", "titulo": "Guía", "archivo_id": arch["id"]})
    assert item.status_code == 201, item.json

    # La participante solo ve la sección activa
    indice = cliente.get("/api/v1/mochila", headers=ana).json["secciones"]
    assert [x["titulo"] for x in indice] == ["Wallpapers"]
    assert indice[0]["cantidad_items"] == 1
    assert cliente.get(f"/api/v1/mochila/secciones/{oculta['id']}", headers=ana).status_code == 404

    seccion = cliente.get(f"/api/v1/mochila/secciones/{s['id']}", headers=ana).json["seccion"]
    assert seccion["items"][0]["archivo"]["nombre"] == "guia.pdf"

    # Puede descargar el archivo
    r = cliente.get(f"/api/v1/archivos/{arch['id']}?descargar=1", headers=ana)
    assert r.status_code == 200 and r.data.startswith(b"%PDF")
    assert "sandbox" in r.headers["Content-Security-Policy"]

    # Si el admin oculta la sección, el archivo deja de estar disponible
    cliente.put(f"/api/v1/admin/secciones/{s['id']}", json={"activa": False}, headers=admin)
    assert cliente.get(f"/api/v1/archivos/{arch['id']}", headers=ana).status_code == 404

    # Estadísticas registran vistas y descargas
    stats = cliente.get("/api/v1/admin/estadisticas", headers=admin).json
    assert stats["descargas"][0]["descargas"] == 1
    assert stats["logins"]["total"] >= 2


def test_reordenar_secciones(cliente, admin):
    ids = [cliente.post("/api/v1/admin/secciones", json={"titulo": t}, headers=admin).json["seccion"]["id"]
           for t in ("A", "B", "C")]
    assert cliente.put("/api/v1/admin/secciones/orden", json={"ids": ids[::-1]}, headers=admin).status_code == 200
    titulos = [s["titulo"] for s in cliente.get("/api/v1/admin/secciones", headers=admin).json["secciones"]]
    assert titulos == ["C", "B", "A"]
    assert cliente.put("/api/v1/admin/secciones/orden", json={"ids": ids[:2]}, headers=admin).status_code == 400


def test_archivo_no_permitido(cliente, admin):
    r = cliente.post("/api/v1/admin/archivos", headers=admin, content_type="multipart/form-data",
                     data={"archivo": (io.BytesIO(b"MZ"), "virus.exe")})
    assert r.status_code == 400 and r.json["error"]["codigo"] == "VALIDACION"


def test_importar_y_restablecer(cliente, admin):
    r = cliente.post("/api/v1/admin/usuarios/importar", headers=admin, json={"usuarios": [
        {"usuario": "luis", "nombre": "Luis", "modalidad": "virtual"},
        {"usuario": "sofi", "nombre": "Sofía"},
    ]})
    assert r.status_code == 201, r.json
    luis = r.json["usuarios"][0]
    assert luis["modalidad"] == "virtual" and luis["contrasena_generada"]
    token = cliente.post("/api/v1/auth/login", json={"usuario": "luis", "contrasena": luis["contrasena_generada"]}).json["token"]
    h = {"Authorization": f"Bearer {token}"}
    assert cliente.get("/api/v1/mochila", headers=h).status_code == 200

    # Restablecer contraseña invalida la sesión abierta
    cliente.post(f"/api/v1/admin/usuarios/{luis['id']}/restablecer-contrasena", headers=admin)
    assert cliente.get("/api/v1/mochila", headers=h).status_code == 401

    # Un lote con errores no crea nada
    r = cliente.post("/api/v1/admin/usuarios/importar", headers=admin, json={"usuarios": [
        {"usuario": "nuevo", "nombre": "Nuevo"}, {"usuario": "luis", "nombre": "Repetido"}]})
    assert r.status_code == 409 or r.status_code == 400
    assert not any(u["usuario"] == "nuevo" for u in cliente.get("/api/v1/admin/usuarios", headers=admin).json["usuarios"])


def test_desactivar_cierra_sesion(cliente, admin, ana):
    ana_id = next(u["id"] for u in cliente.get("/api/v1/admin/usuarios", headers=admin).json["usuarios"] if u["usuario"] == "ana")
    cliente.put(f"/api/v1/admin/usuarios/{ana_id}", json={"activo": False}, headers=admin)
    assert cliente.get("/api/v1/mochila", headers=ana).status_code == 401


def test_cambiar_contrasena(cliente, ana):
    r = cliente.post("/api/v1/auth/cambiar-contrasena", json={"actual": "ana-secreta", "nueva": "otra-clave-1"}, headers=ana)
    assert r.status_code == 200
    assert cliente.get("/api/v1/mochila", headers=ana).status_code == 401  # el token viejo ya no sirve
    assert cliente.post("/api/v1/auth/login", json={"usuario": "ana", "contrasena": "otra-clave-1"}).status_code == 200
