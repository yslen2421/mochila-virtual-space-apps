"""Logo del evento y aliados (organizadores, patrocinadores, divulgadores)."""
import io

from PIL import Image


def _png():
    buf = io.BytesIO()
    Image.new("RGBA", (400, 200), (107, 63, 160, 255)).save(buf, "PNG")
    return buf.getvalue()


def _subir(cliente, admin, nombre="logo.png", contenido=None):
    r = cliente.post("/api/v1/admin/archivos", headers=admin, content_type="multipart/form-data",
                     data={"archivo": (io.BytesIO(contenido or _png()), nombre)})
    assert r.status_code == 201, r.json
    return r.json["archivo"]["id"]


def test_grupos_base_y_publico_sin_sesion(cliente, admin):
    grupos = cliente.get("/api/v1/admin/marca", headers=admin).json["grupos"]
    assert [g["titulo"] for g in grupos] == ["Organizadores", "Patrocinadores", "Divulgadores"]
    # Sin sesión se puede leer; los grupos vacíos no se muestran al público
    r = cliente.get("/api/v1/publico/marca")
    assert r.status_code == 200 and r.json == {"logo": None, "grupos": []}


def test_solo_superadmin_cambia_la_marca(cliente, ana):
    assert cliente.get("/api/v1/admin/marca", headers=ana).status_code == 403
    assert cliente.put("/api/v1/admin/marca/logo", json={"archivo_id": None}, headers=ana).status_code == 403
    assert cliente.post("/api/v1/admin/aliados/grupos", json={"titulo": "X"}).status_code == 401


def test_logo_del_evento(cliente, admin):
    archivo_id = _subir(cliente, admin)
    r = cliente.put("/api/v1/admin/marca/logo", json={"archivo_id": archivo_id}, headers=admin)
    assert r.status_code == 200
    logo = cliente.get("/api/v1/publico/marca").json["logo"]
    assert logo["url"] == f"/api/v1/publico/archivos/{archivo_id}"
    # El archivo se ve sin sesión (pantalla de ingreso), y su miniatura también
    assert cliente.get(logo["url"]).status_code == 200
    assert cliente.get(logo["url"] + "?miniatura=1").mimetype == "image/webp"
    # Un PDF no sirve como logo
    pdf = _subir(cliente, admin, "doc.pdf", b"%PDF-1.4")
    assert cliente.put("/api/v1/admin/marca/logo", json={"archivo_id": pdf}, headers=admin).status_code == 400
    # Quitar el logo
    cliente.put("/api/v1/admin/marca/logo", json={"archivo_id": None}, headers=admin)
    assert cliente.get("/api/v1/publico/marca").json["logo"] is None


def test_archivos_privados_no_son_publicos(cliente, admin):
    privado = _subir(cliente, admin, "guia.pdf", b"%PDF-1.4")
    assert cliente.get(f"/api/v1/publico/archivos/{privado}").status_code == 404


def test_aliados_y_grupos_nuevos(cliente, admin):
    grupo = cliente.post("/api/v1/admin/aliados/grupos", json={"titulo": "Aliados académicos"}, headers=admin).json["grupo"]
    logo = _subir(cliente, admin)
    r = cliente.post(f"/api/v1/admin/aliados/grupos/{grupo['id']}/aliados", headers=admin,
                     json={"nombre": "Universidad X", "url": "https://ejemplo.edu.co", "archivo_id": logo})
    assert r.status_code == 201, r.json
    sin_logo = cliente.post(f"/api/v1/admin/aliados/grupos/{grupo['id']}/aliados", headers=admin,
                            json={"nombre": "Colegio Y"}).json["aliado"]
    publico = cliente.get("/api/v1/publico/marca").json["grupos"]
    assert [g["titulo"] for g in publico] == ["Aliados académicos"]
    assert [a["nombre"] for a in publico[0]["aliados"]] == ["Universidad X", "Colegio Y"]
    assert cliente.get(publico[0]["aliados"][0]["logo"]["url"]).status_code == 200

    # Reordenar aliados y grupos
    ids = [a["id"] for a in publico[0]["aliados"]][::-1]
    assert cliente.put(f"/api/v1/admin/aliados/grupos/{grupo['id']}/aliados/orden", json={"ids": ids}, headers=admin).status_code == 200
    assert cliente.get("/api/v1/publico/marca").json["grupos"][0]["aliados"][0]["nombre"] == "Colegio Y"
    todos = [g["id"] for g in cliente.get("/api/v1/admin/marca", headers=admin).json["grupos"]]
    cliente.put("/api/v1/admin/aliados/grupos/orden", json={"ids": [todos[-1], *todos[:-1]]}, headers=admin)
    assert cliente.get("/api/v1/admin/marca", headers=admin).json["grupos"][0]["titulo"] == "Aliados académicos"

    # Editar, validar enlace y borrar
    assert cliente.put(f"/api/v1/admin/aliados/{sin_logo['id']}", json={"url": "ftp://x"}, headers=admin).status_code == 400
    assert cliente.put(f"/api/v1/admin/aliados/{sin_logo['id']}", json={"nombre": "Colegio Z"}, headers=admin).json["aliado"]["nombre"] == "Colegio Z"
    cliente.put("/api/v1/admin/aliados/grupos/%d" % grupo["id"], json={"titulo": "Academia"}, headers=admin)
    assert cliente.delete(f"/api/v1/admin/aliados/grupos/{grupo['id']}", headers=admin).status_code == 204
    assert cliente.get("/api/v1/publico/marca").json["grupos"] == []


def test_grupos_base_no_reaparecen(app, cliente, admin):
    for g in cliente.get("/api/v1/admin/marca", headers=admin).json["grupos"]:
        cliente.delete(f"/api/v1/admin/aliados/grupos/{g['id']}", headers=admin)
    app.extensions["contenedor"].marca.asegurar_grupos_base()  # como al reiniciar el servidor
    assert cliente.get("/api/v1/admin/marca", headers=admin).json["grupos"] == []


def test_limpieza_no_borra_logos(app, cliente, admin):
    c = app.extensions["contenedor"]
    logo = _subir(cliente, admin)
    cliente.put("/api/v1/admin/marca/logo", json={"archivo_id": logo}, headers=admin)
    grupo = cliente.get("/api/v1/admin/marca", headers=admin).json["grupos"][0]
    del_aliado = _subir(cliente, admin)
    cliente.post(f"/api/v1/admin/aliados/grupos/{grupo['id']}/aliados", headers=admin,
                 json={"nombre": "Patrocinador", "archivo_id": del_aliado})
    huerfano = _subir(cliente, admin)
    # Simula que pasó más de un día desde la subida
    c.db.conexion().execute("UPDATE archivos SET creado_en = '2000-01-01T00:00:00+00:00'")
    assert c.archivos.limpiar_huerfanos() == 1
    assert c.marca.marca(True).logo.id == logo
    assert cliente.get(f"/api/v1/publico/archivos/{del_aliado}").status_code == 200
    assert not c.archivos._repo.por_id(huerfano)
