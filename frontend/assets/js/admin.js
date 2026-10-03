/* ==========================================================================
   Panel de organización (solo Superadmin).
   Pestañas: Contenido, Participantes, Estadísticas.
   ========================================================================== */
"use strict";

(() => {
  const app = document.getElementById("app");
  const sesion = new Sesion(CLAVE_SESION);
  const api = crearClienteApi(sesion, (mensaje) => mostrarIngreso(mensaje));
  const URL_PORTAL = new URL("../", location.href).href;

  const TIPOS = {
    texto: { icono: "📝", nombre: "Texto" },
    enlace: { icono: "🔗", nombre: "Enlace" },
    archivo: { icono: "📄", nombre: "Archivo descargable" },
    imagen: { icono: "🖼️", nombre: "Imagen" },
    evento: { icono: "🗓️", nombre: "Actividad del cronograma" },
  };
  const EXT_IMAGEN = ["png", "jpg", "jpeg", "webp", "gif", "svg"];

  const estado = { usuario: null, pestana: "contenido", secciones: [], seleccion: null, seccion: null, usuarios: [] };

  /* ---------------------------------------------------------------- arranque y sesión */

  async function iniciar() {
    estado.logoUrl = logoDeMarca(await cargarMarca(api));
    if (!sesion.token) return mostrarIngreso();
    try {
      const { usuario } = await api.pedir("/auth/yo");
      // Un participante con sesión abierta no se desconecta: solo se le muestra el camino a su mochila.
      if (usuario.rol !== "superadmin") return mostrarIngreso(avisoNoAdmin(usuario.nombre));
      estado.usuario = usuario;
      montar();
    } catch (error) {
      if (error.estado !== 401) mostrarIngreso(error.message);
    }
  }

  function avisoNoAdmin(nombre) {
    return [
      `${nombre ? `${nombre.split(" ")[0]}, tu` : "Tu"} cuenta es de participante: no tiene acceso al panel de organización. `,
      h("a", { href: URL_PORTAL }, "Ir a mi mochila"),
    ];
  }

  function mostrarIngreso(mensaje) {
    estado.usuario = null;
    vaciar(app, pantallaIngreso({
      titulo: "Panel de organización",
      subtitulo: "Entra como Superadmin",
      nota: "Solo para el equipo organizador.",
      enlace: { texto: "¿Eres participante? Entra a tu mochila", href: URL_PORTAL },
      logo: estado.logoUrl,
      mensajeInicial: mensaje,
      alEntrar: async (usuario, contrasena) => {
        const r = await api.pedir("/auth/login", { metodo: "POST", cuerpo: { usuario, contrasena } });
        sesion.token = r.token;  // la sesión sirve también en el portal
        if (r.usuario.rol !== "superadmin") return mostrarIngreso(avisoNoAdmin(r.usuario.nombre));
        estado.usuario = r.usuario;
        montar();
      },
    }));
  }

  /* ---------------------------------------------------------------- estructura */

  let principal;
  const PESTANAS = [["contenido", "Contenido de la mochila"], ["marca", "Logos y aliados"], ["participantes", "Participantes"], ["estadisticas", "Estadísticas"]];

  function montar() {
    principal = h("main", { class: "contenedor panel", id: "principal" });
    const pestanas = h("nav", { class: "pestanas", role: "tablist", "aria-label": "Secciones del panel" },
      PESTANAS.map(([id, nombre]) => h("button", { type: "button", role: "tab", "aria-selected": String(estado.pestana === id),
        "data-pestana": id, onclick: () => cambiarPestana(id) }, nombre)));
    vaciar(app,
      h("header", { class: "banda-admin" }, h("div", { class: "contenedor" },
        h("span", { class: "marca" }, h("img", { src: "../assets/img/insignia.svg", alt: "" }), "Panel de organización"),
        pestanas,
        h("div", { class: "acciones-banda" },
          h("a", { href: URL_PORTAL }, "Ver portal"),
          h("button", { type: "button", class: "boton discreto pequeno", onclick: salir }, "Salir")))),
      principal);
    cambiarPestana(estado.pestana);
  }

  function salir() {
    sesion.cerrar();
    mostrarIngreso();
  }

  function cambiarPestana(id) {
    estado.pestana = id;
    document.querySelectorAll(".pestanas button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.pestana === id)));
    if (id === "contenido") vistaContenido();
    else if (id === "marca") vistaMarca();
    else if (id === "participantes") vistaParticipantes();
    else vistaEstadisticas();
  }

  function fallo(error) { avisar(error.message, "error"); }

  /* ================================================================ CONTENIDO */

  let columnaLista, columnaDetalle;

  async function vistaContenido() {
    document.title = "Contenido — Panel de organización";
    columnaLista = h("section", { class: "tarjeta lista-secciones", "aria-label": "Secciones" }, h("p", { class: "cargando" }, "Cargando…"));
    columnaDetalle = h("section", { class: "tarjeta detalle-seccion", "aria-live": "polite" });
    vaciar(principal,
      h("h1", {}, "Contenido de la mochila"),
      h("p", { class: "intro" }, "Cada sección aparece como una insignia en el portal. Lo que marques como oculto no lo ven los participantes. Todos reciben la misma mochila, presenciales y virtuales."),
      h("div", { class: "editor" }, columnaLista, columnaDetalle));
    await recargarSecciones();
  }

  async function recargarSecciones() {
    try {
      estado.secciones = (await api.pedir("/admin/secciones")).secciones;
    } catch (error) { return vaciar(columnaLista, bloqueError(error)); }
    if (!estado.secciones.some((s) => s.id === estado.seleccion)) estado.seleccion = estado.secciones[0]?.id ?? null;
    pintarListaSecciones();
    await abrirSeccion(estado.seleccion);
  }

  function pintarListaSecciones() {
    const total = estado.secciones.length;
    vaciar(columnaLista,
      h("div", { class: "cabeza" },
        h("h2", {}, "Secciones"),
        h("button", { type: "button", class: "boton pequeno", onclick: dialogoNuevaSeccion }, "Nueva sección")),
      total === 0
        ? h("p", { class: "vacio" }, "Aún no hay secciones. Crea la primera.")
        : h("ol", {}, estado.secciones.map((s, i) => h("li", { class: `fila-seccion ${s.id === estado.seleccion ? "activa-seleccion" : ""}` },
          h("button", { type: "button", class: "elegir", "aria-current": s.id === estado.seleccion ? "true" : null,
            onclick: () => abrirSeccion(s.id) },
            h("span", { class: "icono", "aria-hidden": "true" }, s.icono),
            h("span", {},
              h("span", { class: "titulo" }, s.titulo), h("br"),
              h("span", { class: "meta" }, `${s.cantidad_items} ${s.cantidad_items === 1 ? "ítem" : "ítems"}`,
                !s.activa && h("span", { class: "oculta" }, ", oculta")))),
          h("span", { class: "mover" },
            h("button", { type: "button", disabled: i === 0, "aria-label": `Subir ${s.titulo}`, onclick: () => moverSeccion(i, -1) }, "▲"),
            h("button", { type: "button", disabled: i === total - 1, "aria-label": `Bajar ${s.titulo}`, onclick: () => moverSeccion(i, 1) }, "▼"))))));
  }

  async function moverSeccion(indice, delta) {
    const lista = [...estado.secciones];
    [lista[indice], lista[indice + delta]] = [lista[indice + delta], lista[indice]];
    estado.secciones = lista;
    pintarListaSecciones();
    try {
      await api.pedir("/admin/secciones/orden", { metodo: "PUT", cuerpo: { ids: lista.map((s) => s.id) } });
    } catch (error) { fallo(error); recargarSecciones(); }
  }

  async function abrirSeccion(id) {
    estado.seleccion = id;
    pintarListaSecciones();
    if (id === null) {
      vaciar(columnaDetalle, h("p", { class: "vacio" }, "Crea una sección para empezar a llenar la mochila."));
      return;
    }
    vaciar(columnaDetalle, h("p", { class: "cargando" }, "Abriendo…"));
    try {
      estado.seccion = (await api.pedir(`/admin/secciones/${id}`)).seccion;
      pintarDetalle();
    } catch (error) { vaciar(columnaDetalle, bloqueError(error)); }
  }

  function pintarDetalle() {
    const s = estado.seccion;
    const zonaError = h("div");
    const icono = h("input", { type: "text", id: "s-icono", class: "icono-input", valor: s.icono, maxlength: "16", "aria-describedby": "s-icono-ayuda" });
    const titulo = h("input", { type: "text", id: "s-titulo", valor: s.titulo, maxlength: "120", required: true });
    const descripcion = h("textarea", { id: "s-desc", rows: "2", maxlength: "2000" });
    descripcion.value = s.descripcion;
    const activa = h("input", { type: "checkbox", id: "s-activa" });
    activa.checked = s.activa;
    const guardar = h("button", { type: "submit", class: "boton" }, "Guardar sección");

    const formulario = h("form", { class: "form-seccion", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        vaciar(zonaError);
        guardar.disabled = true;
        try {
          const r = await api.pedir(`/admin/secciones/${s.id}`, { metodo: "PUT", cuerpo: {
            icono: icono.value.trim() || "📦", titulo: titulo.value, descripcion: descripcion.value, activa: activa.checked } });
          Object.assign(estado.seccion, r.seccion);
          const enLista = estado.secciones.find((x) => x.id === s.id);
          Object.assign(enLista, r.seccion);
          pintarListaSecciones();
          avisar("Sección guardada");
        } catch (error) { zonaError.append(bloqueError(error)); }
        finally { guardar.disabled = false; }
      } },
      zonaError,
      h("div", { class: "fila" },
        h("div", { class: "campo" }, h("label", { for: "s-icono" }, "Icono"), icono),
        h("div", { class: "campo" }, h("label", { for: "s-titulo" }, "Título"), titulo)),
      h("span", { class: "ayuda", id: "s-icono-ayuda" }, "El icono es un emoji: en Windows ábrelos con Windows + punto; en celular, desde el teclado."),
      h("div", { class: "campo" }, h("label", { for: "s-desc" }, "Descripción corta"), descripcion),
      h("label", { class: "casilla" }, activa, "Visible para los participantes"),
      h("div", { class: "barra-acciones" },
        guardar,
        h("button", { type: "button", class: "boton peligro secundario pequeno separar", onclick: eliminarSeccion }, "Eliminar sección")));

    const entradaVarios = h("input", { type: "file", multiple: true, class: "solo-lector", id: "subir-varios",
      onchange: (e) => subirVarios([...e.target.files]) });

    vaciar(columnaDetalle,
      formulario,
      h("div", { class: "items-cabeza" },
        h("h3", {}, "Contenido de la sección"),
        h("div", { class: "barra-acciones" },
          entradaVarios,
          h("label", { for: "subir-varios", class: "boton secundario pequeno", role: "button", tabindex: "0",
            onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); entradaVarios.click(); } } }, "Subir varios archivos"),
          h("button", { type: "button", class: "boton pequeno", onclick: () => dialogoItem() }, "Agregar ítem"))),
      listaItems());
  }

  function describirItem(i) {
    if (i.tipo === "evento") {
      const horas = i.hora_inicio ? `, ${hora12(i.hora_inicio)}${i.hora_fin ? ` a ${hora12(i.hora_fin)}` : ""}` : "";
      return `${nombreDia(i.fecha, true)}${horas}${i.lugar ? `. ${i.lugar}` : ""}`;
    }
    if (i.tipo === "enlace") return i.url;
    if (i.archivo) return `${i.archivo.nombre} (${formatoTamano(i.archivo.tamano_bytes)})`;
    if (i.tipo === "texto") return i.descripcion.length > 110 ? `${i.descripcion.slice(0, 110)}…` : i.descripcion;
    return "Sin archivo";
  }

  function listaItems() {
    const items = estado.seccion.items;
    if (!items.length) {
      return h("p", { class: "vacio" }, "Esta sección está vacía. Agrega textos, enlaces, archivos, imágenes o actividades del cronograma.");
    }
    return h("ol", { class: "lista-items" }, items.map((i, n) => h("li", { class: `fila-item ${i.activo ? "" : "inactivo"}` },
      h("span", { class: "tipo", title: TIPOS[i.tipo].nombre, "aria-hidden": "true" }, TIPOS[i.tipo].icono),
      h("span", { class: "titulo" }, i.titulo, " ", !i.activo && h("span", { class: "marca-estado oculto" }, "Oculto")),
      h("span", { class: "meta" }, `${TIPOS[i.tipo].nombre}: ${describirItem(i)}`),
      h("span", { class: "controles" },
        i.tipo !== "evento" && h("span", { class: "mover" },
          h("button", { type: "button", disabled: n === 0, "aria-label": `Subir ${i.titulo}`, onclick: () => moverItem(n, -1) }, "▲"),
          h("button", { type: "button", disabled: n === items.length - 1, "aria-label": `Bajar ${i.titulo}`, onclick: () => moverItem(n, 1) }, "▼")),
        h("button", { type: "button", class: "boton discreto pequeno", onclick: () => alternarItem(i) }, i.activo ? "Ocultar" : "Mostrar"),
        h("button", { type: "button", class: "boton secundario pequeno", onclick: () => dialogoItem(i) }, "Editar"),
        h("button", { type: "button", class: "boton peligro secundario pequeno", onclick: () => eliminarItem(i) }, "Eliminar")))));
  }

  async function refrescarSeccion() {
    estado.seccion = (await api.pedir(`/admin/secciones/${estado.seccion.id}`)).seccion;
    const enLista = estado.secciones.find((x) => x.id === estado.seccion.id);
    if (enLista) enLista.cantidad_items = estado.seccion.items.length;
    pintarListaSecciones();
    pintarDetalle();
  }

  async function moverItem(indice, delta) {
    const items = [...estado.seccion.items];
    [items[indice], items[indice + delta]] = [items[indice + delta], items[indice]];
    try {
      await api.pedir(`/admin/secciones/${estado.seccion.id}/items/orden`, { metodo: "PUT", cuerpo: { ids: items.map((i) => i.id) } });
      await refrescarSeccion();
    } catch (error) { fallo(error); }
  }

  async function alternarItem(item) {
    try {
      await api.pedir(`/admin/items/${item.id}`, { metodo: "PUT", cuerpo: { activo: !item.activo } });
      await refrescarSeccion();
      avisar(item.activo ? "Ítem oculto" : "Ítem visible");
    } catch (error) { fallo(error); }
  }

  async function eliminarItem(item) {
    if (!await confirmar("Eliminar ítem", `¿Eliminar "${item.titulo}"? Esta acción no se puede deshacer.`)) return;
    try {
      await api.pedir(`/admin/items/${item.id}`, { metodo: "DELETE" });
      await refrescarSeccion();
      avisar("Ítem eliminado");
    } catch (error) { fallo(error); }
  }

  async function eliminarSeccion() {
    const s = estado.seccion;
    const n = s.items.length;
    const aviso = n ? `Se borrarán también sus ${n} ${n === 1 ? "ítem" : "ítems"}.` : "La sección está vacía.";
    if (!await confirmar("Eliminar sección", `¿Eliminar "${s.titulo}"? ${aviso} Si solo quieres esconderla, desmarca "Visible para los participantes".`)) return;
    try {
      await api.pedir(`/admin/secciones/${s.id}`, { metodo: "DELETE" });
      estado.seleccion = null;
      await recargarSecciones();
      avisar("Sección eliminada");
    } catch (error) { fallo(error); }
  }

  function dialogoNuevaSeccion() {
    const zonaError = h("div");
    const icono = h("input", { type: "text", id: "n-icono", class: "icono-input", valor: "📦", maxlength: "16" });
    const titulo = h("input", { type: "text", id: "n-titulo", maxlength: "120", required: true });
    const descripcion = h("input", { type: "text", id: "n-desc", maxlength: "2000" });
    const dialogo = abrirDialogo(h("form", { class: "dialogo-cuerpo", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        vaciar(zonaError);
        try {
          const r = await api.pedir("/admin/secciones", { metodo: "POST", cuerpo: {
            icono: icono.value.trim() || "📦", titulo: titulo.value, descripcion: descripcion.value } });
          dialogo.close();
          estado.seleccion = r.seccion.id;
          await recargarSecciones();
          avisar("Sección creada");
        } catch (error) { zonaError.append(bloqueError(error)); }
      } },
      h("h2", {}, "Nueva sección"),
      zonaError,
      h("div", { class: "rejilla-2" },
        h("div", { class: "campo" }, h("label", { for: "n-icono" }, "Icono (emoji)"), icono),
        h("div", { class: "campo" }, h("label", { for: "n-titulo" }, "Título"), titulo)),
      h("div", { class: "campo" }, h("label", { for: "n-desc" }, "Descripción corta"), descripcion),
      h("div", { class: "dialogo-acciones" },
        h("button", { type: "button", class: "boton discreto", onclick: () => dialogo.close() }, "Cancelar"),
        h("button", { type: "submit", class: "boton" }, "Crear sección"))));
    titulo.focus();
  }

  /* ---------------------------------------------------------------- diálogo de ítem */

  function dialogoItem(item) {
    const editando = Boolean(item);
    const i = item || { tipo: "texto", titulo: "", descripcion: "", url: "", fecha: "2026-11-14", hora_inicio: "", hora_fin: "", lugar: "", activo: true, archivo: null };
    let archivoId = i.archivo_id || null;
    let subiendo = false;

    const zonaError = h("div");
    const tipo = h("select", { id: "i-tipo" }, Object.entries(TIPOS).map(([v, t]) => h("option", { value: v }, t.nombre)));
    tipo.value = i.tipo;
    const titulo = h("input", { type: "text", id: "i-titulo", valor: i.titulo, maxlength: "200" });
    const descripcion = h("textarea", { id: "i-desc", rows: "5" });
    descripcion.value = i.descripcion;
    const etiquetaDesc = h("label", { for: "i-desc" });
    const ayudaDesc = h("span", { class: "ayuda" });
    const url = h("input", { type: "url", id: "i-url", valor: i.url, placeholder: "https://", inputmode: "url" });
    const etiquetaUrl = h("label", { for: "i-url" });
    const fecha = h("input", { type: "date", id: "i-fecha", valor: i.fecha });
    const horaInicio = h("input", { type: "time", id: "i-hi", valor: i.hora_inicio });
    const horaFin = h("input", { type: "time", id: "i-hf", valor: i.hora_fin });
    const lugar = h("input", { type: "text", id: "i-lugar", valor: i.lugar, maxlength: "200", placeholder: "Auditorio, sala virtual…" });
    const activo = h("input", { type: "checkbox", id: "i-activo" });
    activo.checked = i.activo;

    const archivoActual = h("p", { class: "actual" }, i.archivo ? `${i.archivo.nombre} (${formatoTamano(i.archivo.tamano_bytes)})` : "Ningún archivo todavía");
    const progreso = h("div", { class: "barra-progreso", hidden: true }, h("span"));
    const entradaArchivo = h("input", { type: "file", id: "i-archivo", onchange: async (e) => {
      const f = e.target.files[0];
      if (!f) return;
      subiendo = true;
      guardar.disabled = true;
      progreso.hidden = false;
      archivoActual.textContent = `Subiendo ${f.name}…`;
      try {
        const r = await api.subir("/admin/archivos", f, (p) => progreso.firstChild.style.setProperty("width", `${Math.round(p * 100)}%`));
        archivoId = r.archivo.id;
        archivoActual.textContent = `${r.archivo.nombre} (${formatoTamano(r.archivo.tamano_bytes)})`;
        if (!titulo.value.trim()) titulo.value = tituloDesdeArchivo(r.archivo.nombre);
      } catch (error) {
        archivoActual.textContent = "No se pudo subir";
        vaciar(zonaError, bloqueError(error));
      } finally {
        subiendo = false;
        guardar.disabled = false;
        progreso.hidden = true;
        entradaArchivo.value = "";
      }
    } });

    const grupoDesc = h("div", { class: "campo" }, etiquetaDesc, descripcion, ayudaDesc);
    const grupoUrl = h("div", { class: "campo" }, etiquetaUrl, url);
    const grupoArchivo = h("div", { class: "zona-archivo" },
      h("label", { for: "i-archivo", class: "etiqueta" }, "Archivo"), archivoActual, progreso, entradaArchivo,
      h("span", { class: "ayuda" }, "PDF, imágenes, ZIP, documentos de Office, tipografías, audio o video. Máximo 100 MB."));
    const grupoEvento = h("div", { class: "rejilla-2 rejilla-3" },
      h("div", { class: "campo" }, h("label", { for: "i-fecha" }, "Fecha"), fecha),
      h("div", { class: "campo" }, h("label", { for: "i-hi" }, "Hora de inicio"), horaInicio),
      h("div", { class: "campo" }, h("label", { for: "i-hf" }, "Hora de fin (opcional)"), horaFin));
    const grupoLugar = h("div", { class: "campo" }, h("label", { for: "i-lugar" }, "Lugar"), lugar);

    function ajustarCampos() {
      const t = tipo.value;
      grupoUrl.hidden = !(t === "enlace" || t === "evento");
      grupoArchivo.hidden = !(t === "archivo" || t === "imagen");
      grupoEvento.hidden = grupoLugar.hidden = t !== "evento";
      etiquetaUrl.textContent = t === "evento" ? "Enlace de conexión (Zoom, Meet…), opcional" : "Dirección del enlace";
      etiquetaDesc.textContent = t === "texto" ? "Contenido" : "Descripción (opcional)";
      ayudaDesc.textContent = t === "texto" ? "Deja una línea en blanco entre párrafos. Las direcciones https:// se vuelven enlaces." : "";
      descripcion.rows = t === "texto" ? 8 : 3;
      entradaArchivo.accept = t === "imagen" ? "image/*" : "";
    }
    tipo.addEventListener("change", ajustarCampos);
    ajustarCampos();

    const guardar = h("button", { type: "submit", class: "boton" }, editando ? "Guardar cambios" : "Agregar ítem");

    const dialogo = abrirDialogo(h("form", { class: "dialogo-cuerpo", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        if (subiendo) return;
        vaciar(zonaError);
        const cuerpo = { tipo: tipo.value, titulo: titulo.value, descripcion: descripcion.value, url: url.value.trim(),
          fecha: fecha.value, hora_inicio: horaInicio.value, hora_fin: horaFin.value, lugar: lugar.value, activo: activo.checked };
        if (archivoId) cuerpo.archivo_id = archivoId;
        guardar.disabled = true;
        try {
          if (editando) await api.pedir(`/admin/items/${i.id}`, { metodo: "PUT", cuerpo });
          else await api.pedir(`/admin/secciones/${estado.seccion.id}/items`, { metodo: "POST", cuerpo });
          dialogo.close();
          await refrescarSeccion();
          avisar(editando ? "Cambios guardados" : "Ítem agregado");
        } catch (error) {
          zonaError.append(bloqueError(error));
          zonaError.scrollIntoView({ block: "nearest" });
        } finally { guardar.disabled = false; }
      } },
      h("h2", {}, editando ? "Editar ítem" : "Agregar ítem"),
      zonaError,
      h("div", { class: "rejilla-2" },
        h("div", { class: "campo" }, h("label", { for: "i-tipo" }, "Tipo"), tipo),
        h("div", { class: "campo" }, h("label", { for: "i-titulo" }, "Título"), titulo)),
      grupoEvento, grupoLugar, grupoUrl, grupoArchivo, grupoDesc,
      h("label", { class: "casilla" }, activo, "Visible para los participantes"),
      h("div", { class: "dialogo-acciones" },
        h("button", { type: "button", class: "boton discreto", onclick: () => dialogo.close() }, "Cancelar"),
        guardar)), { ancho: true });
    (editando ? titulo : tipo).focus();
  }

  function tituloDesdeArchivo(nombre) {
    const base = nombre.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ").trim();
    return base.charAt(0).toUpperCase() + base.slice(1);
  }

  async function subirVarios(archivos) {
    if (!archivos.length) return;
    const seccionId = estado.seccion.id;
    let hechos = 0;
    const errores = [];
    avisar(`Subiendo ${archivos.length} ${archivos.length === 1 ? "archivo" : "archivos"}…`);
    for (const f of archivos) {
      try {
        const { archivo } = await api.subir("/admin/archivos", f);
        const ext = f.name.split(".").pop().toLowerCase();
        await api.pedir(`/admin/secciones/${seccionId}/items`, { metodo: "POST", cuerpo: {
          tipo: EXT_IMAGEN.includes(ext) ? "imagen" : "archivo", titulo: tituloDesdeArchivo(f.name), archivo_id: archivo.id } });
        hechos++;
      } catch (error) { errores.push(`${f.name}: ${error.message}`); }
    }
    document.getElementById("subir-varios").value = "";
    await refrescarSeccion();
    if (hechos) avisar(`${hechos} ${hechos === 1 ? "archivo agregado" : "archivos agregados"}`);
    if (errores.length) avisar(`No se pudieron subir: ${errores.join("; ")}`, "error");
  }

  /* ================================================================ LOGOS Y ALIADOS */

  let zonaLogo, zonaGrupos;

  /** Un <label> con aspecto de botón que abre el selector de archivos (y responde al teclado). */
  function botonArchivo(idEntrada, texto, clase = "boton secundario pequeno") {
    return h("label", { for: idEntrada, class: clase, role: "button", tabindex: "0",
      onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); document.getElementById(idEntrada).click(); } } },
    texto);
  }

  async function vistaMarca() {
    document.title = "Logos y aliados — Panel de organización";
    zonaLogo = h("section", { class: "tarjeta bloque-marca", "aria-labelledby": "titulo-logo" }, h("p", { class: "cargando" }, "Cargando…"));
    zonaGrupos = h("section", { class: "tarjeta bloque-marca", "aria-labelledby": "titulo-aliados" });
    vaciar(principal,
      h("h1", {}, "Logos y aliados"),
      h("p", { class: "intro" }, "El logo del evento aparece arriba en el portal y en la pantalla de ingreso. Los aliados se muestran al final de la página de inicio de los participantes, por grupos. Un grupo sin aliados no se muestra."),
      h("div", { class: "editor-marca" }, zonaLogo, zonaGrupos));
    await recargarMarca();
  }

  async function recargarMarca() {
    try {
      estado.marca = await api.pedir("/admin/marca");
    } catch (error) { vaciar(zonaLogo, bloqueError(error)); return; }
    estado.logoUrl = logoDeMarca(estado.marca);
    pintarLogo();
    pintarGrupos();
  }

  async function subirImagen(archivo, barra) {
    if (barra) { barra.hidden = false; barra.firstChild.style.setProperty("width", "0%"); }
    try {
      return (await api.subir("/admin/archivos", archivo,
        (p) => barra && barra.firstChild.style.setProperty("width", `${Math.round(p * 100)}%`))).archivo;
    } finally { if (barra) barra.hidden = true; }
  }

  function pintarLogo() {
    const logo = estado.marca.logo;
    const barra = h("div", { class: "barra-progreso", hidden: true }, h("span"));
    const entrada = h("input", { type: "file", id: "subir-logo", class: "solo-lector", accept: "image/png,image/jpeg,image/svg+xml,image/webp",
      onchange: async (e) => {
        const f = e.target.files[0];
        if (!f) return;
        try {
          const archivo = await subirImagen(f, barra);
          await api.pedir("/admin/marca/logo", { metodo: "PUT", cuerpo: { archivo_id: archivo.id } });
          await recargarMarca();
          avisar("Logo guardado. Ya se ve en el portal.");
        } catch (error) { fallo(error); entrada.value = ""; }
      } });
    vaciar(zonaLogo,
      h("h2", { id: "titulo-logo" }, "Logo del evento"),
      h("div", { class: "vista-logo" },
        logo ? h("span", { class: "placa-logo grande" }, h("img", { src: logo.url, alt: "Logo del evento" }))
          : h("span", { class: "sin-logo" }, "Todavía no hay logo. Mientras tanto se muestra la insignia de la mochila.")),
      barra,
      h("p", { class: "ayuda" }, "Mejor en PNG o SVG con fondo transparente. En el portal va sobre un recuadro blanco, así se lee bien sobre la barra oscura."),
      h("div", { class: "barra-acciones" },
        entrada,
        botonArchivo("subir-logo", logo ? "Cambiar logo" : "Subir logo", "boton pequeno"),
        logo && h("button", { type: "button", class: "boton peligro secundario pequeno", onclick: quitarLogo }, "Quitar logo")));
  }

  async function quitarLogo() {
    if (!await confirmar("Quitar logo", "El portal volverá a mostrar la insignia de la mochila en lugar del logo del evento.", { textoAceptar: "Quitar logo" })) return;
    try {
      await api.pedir("/admin/marca/logo", { metodo: "PUT", cuerpo: { archivo_id: null } });
      await recargarMarca();
      avisar("Logo quitado");
    } catch (error) { fallo(error); }
  }

  function pintarGrupos() {
    const grupos = estado.marca.grupos;
    vaciar(zonaGrupos,
      h("div", { class: "cabeza-marca" },
        h("h2", { id: "titulo-aliados" }, "Aliados del evento"),
        h("button", { type: "button", class: "boton pequeno", onclick: () => dialogoGrupo() }, "Nuevo grupo")),
      grupos.length
        ? grupos.map((g, i) => bloqueGrupo(g, i, grupos.length))
        : h("p", { class: "vacio" }, "No hay grupos. Crea uno, por ejemplo Organizadores, Patrocinadores o Divulgadores."));
  }

  function bloqueGrupo(g, i, total) {
    const idEntrada = `logos-grupo-${g.id}`;
    const n = g.aliados.length;
    const entrada = h("input", { type: "file", id: idEntrada, class: "solo-lector", multiple: true, accept: "image/*",
      onchange: (e) => subirLogosAliados(g, [...e.target.files]) });
    return h("div", { class: "grupo-admin" },
      h("div", { class: "grupo-cabeza" },
        h("h3", {}, g.titulo, " ", h("span", { class: "meta" }, n ? `${n} ${n === 1 ? "aliado" : "aliados"}` : "vacío, no se muestra")),
        h("div", { class: "controles" },
          h("span", { class: "mover" },
            h("button", { type: "button", disabled: i === 0, "aria-label": `Subir el grupo ${g.titulo}`, onclick: () => moverGrupo(i, -1) }, "▲"),
            h("button", { type: "button", disabled: i === total - 1, "aria-label": `Bajar el grupo ${g.titulo}`, onclick: () => moverGrupo(i, 1) }, "▼")),
          h("button", { type: "button", class: "boton discreto pequeno", onclick: () => dialogoGrupo(g) }, "Renombrar"),
          h("button", { type: "button", class: "boton peligro secundario pequeno", onclick: () => eliminarGrupo(g) }, "Eliminar grupo"))),
      h("ul", { class: "logos-admin" },
        g.aliados.map((a, k) => h("li", { class: "aliado-admin" },
          h("span", { class: "placa-aliado" },
            a.logo ? h("img", { src: `${a.logo.url}?miniatura=1`, alt: "" }) : h("span", { class: "solo-nombre" }, a.nombre)),
          a.logo && h("span", { class: "nombre-aliado" }, a.nombre),
          h("span", { class: "controles-aliado" },
            h("button", { type: "button", class: "flecha", disabled: k === 0, "aria-label": `Mover ${a.nombre} antes`, onclick: () => moverAliado(g, k, -1) }, "‹"),
            h("button", { type: "button", class: "boton discreto pequeno", onclick: () => dialogoAliado(g, a) }, "Editar"),
            h("button", { type: "button", class: "flecha", disabled: k === n - 1, "aria-label": `Mover ${a.nombre} después`, onclick: () => moverAliado(g, k, 1) }, "›")))),
        h("li", { class: "aliado-admin" },
          h("button", { type: "button", class: "agregar-aliado", onclick: () => dialogoAliado(g) },
            h("span", { class: "mas", "aria-hidden": "true" }, "+"), "Agregar aliado"))),
      h("div", { class: "barra-acciones" },
        entrada,
        botonArchivo(idEntrada, "Subir varios logos"),
        h("span", { class: "ayuda" }, "Cada imagen se vuelve un aliado con el nombre del archivo; después puedes editarlo.")));
  }

  function dialogoGrupo(grupo) {
    const zonaError = h("div");
    const titulo = h("input", { type: "text", id: "g-titulo", maxlength: "80", valor: grupo ? grupo.titulo : "",
      placeholder: "Por ejemplo: Aliados académicos" });
    const dialogo = abrirDialogo(h("form", { class: "dialogo-cuerpo", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        vaciar(zonaError);
        try {
          if (grupo) await api.pedir(`/admin/aliados/grupos/${grupo.id}`, { metodo: "PUT", cuerpo: { titulo: titulo.value } });
          else await api.pedir("/admin/aliados/grupos", { metodo: "POST", cuerpo: { titulo: titulo.value } });
          dialogo.close();
          await recargarMarca();
          avisar(grupo ? "Grupo renombrado" : "Grupo creado");
        } catch (error) { zonaError.append(bloqueError(error)); }
      } },
      h("h2", {}, grupo ? "Renombrar grupo" : "Nuevo grupo"),
      zonaError,
      h("div", { class: "campo" }, h("label", { for: "g-titulo" }, "Nombre del grupo"), titulo),
      h("div", { class: "dialogo-acciones" },
        h("button", { type: "button", class: "boton discreto", onclick: () => dialogo.close() }, "Cancelar"),
        h("button", { type: "submit", class: "boton" }, grupo ? "Guardar nombre" : "Crear grupo"))));
    titulo.focus();
  }

  async function eliminarGrupo(g) {
    const n = g.aliados.length;
    const detalle = n ? `Se borrarán también sus ${n} ${n === 1 ? "aliado" : "aliados"} y sus logos.` : "El grupo está vacío.";
    if (!await confirmar("Eliminar grupo", `¿Eliminar "${g.titulo}"? ${detalle}`)) return;
    try {
      await api.pedir(`/admin/aliados/grupos/${g.id}`, { metodo: "DELETE" });
      await recargarMarca();
      avisar("Grupo eliminado");
    } catch (error) { fallo(error); }
  }

  async function moverGrupo(i, delta) {
    const ids = estado.marca.grupos.map((g) => g.id);
    [ids[i], ids[i + delta]] = [ids[i + delta], ids[i]];
    try {
      await api.pedir("/admin/aliados/grupos/orden", { metodo: "PUT", cuerpo: { ids } });
      await recargarMarca();
    } catch (error) { fallo(error); }
  }

  async function moverAliado(g, k, delta) {
    const ids = g.aliados.map((a) => a.id);
    [ids[k], ids[k + delta]] = [ids[k + delta], ids[k]];
    try {
      await api.pedir(`/admin/aliados/grupos/${g.id}/aliados/orden`, { metodo: "PUT", cuerpo: { ids } });
      await recargarMarca();
    } catch (error) { fallo(error); }
  }

  function dialogoAliado(g, aliado) {
    const editando = Boolean(aliado);
    let archivoId = null;
    let quitarLogo = false;
    let subiendo = false;
    const zonaError = h("div");
    const nombre = h("input", { type: "text", id: "a-nombre", maxlength: "120", valor: aliado ? aliado.nombre : "" });
    const url = h("input", { type: "url", id: "a-url", inputmode: "url", placeholder: "https://", valor: aliado ? aliado.url : "" });
    const vista = h("span", { class: "placa-aliado" });
    const barra = h("div", { class: "barra-progreso", hidden: true }, h("span"));
    const botonQuitar = h("button", { type: "button", class: "boton peligro secundario pequeno",
      onclick: () => { quitarLogo = true; archivoId = null; mostrarVista(null); } }, "Quitar logo");

    function mostrarVista(src) {
      vaciar(vista, src ? h("img", { src, alt: "" }) : h("span", { class: "solo-nombre" }, "Sin logo: se mostrará el nombre"));
      botonQuitar.hidden = !src;
    }
    mostrarVista(aliado && aliado.logo ? `${aliado.logo.url}?miniatura=1` : null);

    const entrada = h("input", { type: "file", id: "a-logo", class: "solo-lector", accept: "image/*",
      onchange: async (e) => {
        const f = e.target.files[0];
        if (!f) return;
        subiendo = true;
        guardar.disabled = true;
        try {
          const archivo = await subirImagen(f, barra);
          archivoId = archivo.id;
          quitarLogo = false;
          mostrarVista(URL.createObjectURL(f));
          if (!nombre.value.trim()) nombre.value = tituloDesdeArchivo(f.name);
        } catch (error) { vaciar(zonaError, bloqueError(error)); }
        finally { subiendo = false; guardar.disabled = false; entrada.value = ""; }
      } });
    const guardar = h("button", { type: "submit", class: "boton" }, editando ? "Guardar cambios" : "Agregar aliado");

    const dialogo = abrirDialogo(h("form", { class: "dialogo-cuerpo", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        if (subiendo) return;
        vaciar(zonaError);
        const cuerpo = { nombre: nombre.value, url: url.value.trim() };
        if (archivoId) cuerpo.archivo_id = archivoId;
        else if (quitarLogo) cuerpo.archivo_id = null;
        try {
          if (editando) await api.pedir(`/admin/aliados/${aliado.id}`, { metodo: "PUT", cuerpo });
          else await api.pedir(`/admin/aliados/grupos/${g.id}/aliados`, { metodo: "POST", cuerpo });
          dialogo.close();
          await recargarMarca();
          avisar(editando ? "Cambios guardados" : "Aliado agregado");
        } catch (error) { zonaError.append(bloqueError(error)); }
      } },
      h("h2", {}, editando ? `Editar aliado` : `Agregar a ${g.titulo}`),
      zonaError,
      h("div", { class: "zona-logo-aliado" },
        vista,
        h("div", { class: "acciones-logo" },
          entrada,
          botonArchivo("a-logo", aliado && aliado.logo ? "Cambiar logo" : "Subir logo"),
          botonQuitar,
          barra)),
      h("div", { class: "campo" }, h("label", { for: "a-nombre" }, "Nombre de la organización"), nombre),
      h("div", { class: "campo" }, h("label", { for: "a-url" }, "Página web o red social (opcional)"), url,
        h("span", { class: "ayuda" }, "Si la pones, el logo será un enlace en el portal.")),
      h("div", { class: "dialogo-acciones" },
        editando && h("button", { type: "button", class: "boton peligro secundario pequeno separar-izq",
          onclick: async () => { dialogo.close(); await eliminarAliado(aliado); } }, "Eliminar aliado"),
        h("button", { type: "button", class: "boton discreto", onclick: () => dialogo.close() }, "Cancelar"),
        guardar)));
    nombre.focus();
  }

  async function eliminarAliado(a) {
    if (!await confirmar("Eliminar aliado", `¿Quitar a "${a.nombre}" de la página? Esta acción no se puede deshacer.`)) return;
    try {
      await api.pedir(`/admin/aliados/${a.id}`, { metodo: "DELETE" });
      await recargarMarca();
      avisar("Aliado eliminado");
    } catch (error) { fallo(error); }
  }

  async function subirLogosAliados(g, archivos) {
    if (!archivos.length) return;
    avisar(`Subiendo ${archivos.length} ${archivos.length === 1 ? "logo" : "logos"}…`);
    let hechos = 0;
    const errores = [];
    for (const f of archivos) {
      try {
        const archivo = await subirImagen(f);
        await api.pedir(`/admin/aliados/grupos/${g.id}/aliados`, { metodo: "POST",
          cuerpo: { nombre: tituloDesdeArchivo(f.name), archivo_id: archivo.id } });
        hechos++;
      } catch (error) { errores.push(`${f.name}: ${error.message}`); }
    }
    await recargarMarca();
    if (hechos) avisar(`${hechos} ${hechos === 1 ? "aliado agregado" : "aliados agregados"} a ${g.titulo}`);
    if (errores.length) avisar(`No se pudieron subir: ${errores.join("; ")}`, "error");
  }

  /* ================================================================ PARTICIPANTES */

  let filtro = { texto: "", tipo: "todos" };
  let zonaTabla, zonaConteo;

  async function vistaParticipantes() {
    document.title = "Participantes — Panel de organización";
    zonaTabla = h("div", { class: "tarjeta tabla-envoltura" }, h("p", { class: "cargando" }, "Cargando…"));
    zonaConteo = h("p", { class: "conteo", "aria-live": "polite" });
    const buscar = h("input", { type: "search", placeholder: "Buscar por nombre, usuario o correo", "aria-label": "Buscar participantes",
      valor: filtro.texto, oninput: (e) => { filtro.texto = e.target.value; pintarTabla(); } });
    const tipo = h("select", { "aria-label": "Filtrar", onchange: (e) => { filtro.tipo = e.target.value; pintarTabla(); } },
      h("option", { value: "todos" }, "Todas las personas"),
      h("option", { value: "presencial" }, "Presenciales"),
      h("option", { value: "virtual" }, "Virtuales"),
      h("option", { value: "sin_ingreso" }, "Aún no han entrado"),
      h("option", { value: "desactivados" }, "Desactivados"),
      h("option", { value: "superadmin" }, "Superadmins"));
    tipo.value = filtro.tipo;
    vaciar(principal,
      h("h1", {}, "Participantes"),
      h("p", { class: "intro" }, "Crea las cuentas una por una o importa la lista completa. Las contraseñas se generan solas y solo se muestran una vez: guárdalas o envíalas en ese momento."),
      h("div", { class: "herramientas" }, buscar, tipo,
        h("div", { class: "separar" },
          h("button", { type: "button", class: "boton secundario", onclick: dialogoImportar }, "Importar lista"),
          h("button", { type: "button", class: "boton", onclick: dialogoNuevoUsuario }, "Agregar persona"))),
      zonaConteo,
      zonaTabla);
    await recargarUsuarios();
  }

  async function recargarUsuarios() {
    try {
      estado.usuarios = (await api.pedir("/admin/usuarios")).usuarios;
      pintarTabla();
    } catch (error) { vaciar(zonaTabla, bloqueError(error)); }
  }

  function sinTildes(texto) {
    return texto.normalize("NFD").replace(/[̀-ͯ]/g, "");
  }

  function pintarTabla() {
    const q = sinTildes(filtro.texto.trim().toLowerCase());
    const lista = estado.usuarios.filter((u) => {
      if (q && !sinTildes(`${u.nombre} ${u.usuario} ${u.email}`.toLowerCase()).includes(q)) return false;
      switch (filtro.tipo) {
        case "presencial": case "virtual": return u.rol === "participante" && u.modalidad === filtro.tipo;
        case "sin_ingreso": return !u.ultimo_login;
        case "desactivados": return !u.activo;
        case "superadmin": return u.rol === "superadmin";
        default: return true;
      }
    });
    const participantes = estado.usuarios.filter((u) => u.rol === "participante");
    zonaConteo.textContent = `${participantes.length} participantes registrados, ${participantes.filter((u) => u.ultimo_login).length} ya entraron al portal. Mostrando ${lista.length}.`;

    if (!lista.length) {
      vaciar(zonaTabla, h("p", { class: "vacio" }, estado.usuarios.length <= 1
        ? "Todavía no hay participantes. Usa Importar lista para cargarlos todos de una vez."
        : "Nadie coincide con la búsqueda."));
      return;
    }
    const formatoIngreso = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
    vaciar(zonaTabla, h("table", { class: "tabla-personas" },
      h("thead", {}, h("tr", {}, ["Persona", "Usuario", "Modalidad", "Último ingreso", ""].map((t) => h("th", { scope: "col" }, t)))),
      h("tbody", {}, lista.map((u) => h("tr", { class: u.activo ? "" : "inactivo" },
        h("td", {}, h("span", { class: "nombre" }, u.nombre), " ",
          u.rol === "superadmin" && h("span", { class: "marca-estado admin" }, "Superadmin"),
          !u.activo && h("span", { class: "marca-estado oculto" }, "Desactivado"),
          u.email && h("div", { class: "correo" }, u.email)),
        h("td", { "data-etiqueta": "Usuario" }, u.usuario),
        h("td", {}, u.rol === "superadmin" ? "" : h("span", { class: `marca-estado ${u.modalidad}` }, u.modalidad === "virtual" ? "Virtual" : "Presencial")),
        h("td", { "data-etiqueta": "Último ingreso" }, u.ultimo_login ? formatoIngreso.format(new Date(u.ultimo_login)) : "Nunca"),
        h("td", { class: "acciones" },
          h("button", { type: "button", class: "boton discreto pequeno", onclick: () => dialogoEditarUsuario(u) }, "Editar"),
          h("button", { type: "button", class: "boton discreto pequeno", onclick: () => restablecer(u) }, "Nueva contraseña"),
          u.id !== estado.usuario.id && h("button", { type: "button", class: "boton discreto pequeno", onclick: () => alternarUsuario(u) },
            u.activo ? "Desactivar" : "Activar")))))));
  }

  function mensajeAcceso(u, contrasena) {
    return `Hola ${u.nombre.split(" ")[0]}, este es tu acceso a la mochila virtual del NASA Space Apps Challenge San Vicente Ferrer:\n\n` +
      `Portal: ${URL_PORTAL}\nUsuario: ${u.usuario}\nContraseña: ${contrasena}\n\n` +
      "Al entrar puedes cambiar tu contraseña desde el menú con tu nombre.";
  }

  function dialogoCredencial(u, titulo) {
    const mensaje = mensajeAcceso(u, u.contrasena_generada);
    const dialogo = abrirDialogo(h("div", { class: "dialogo-cuerpo" },
      h("h2", {}, titulo),
      h("p", { class: "nota-importante" }, "Esta contraseña no se volverá a mostrar. Cópiala o envíala ahora."),
      h("table", { class: "credenciales" }, h("tbody", {},
        h("tr", {}, h("th", { scope: "row" }, "Usuario"), h("td", { class: "clave" }, u.usuario)),
        h("tr", {}, h("th", { scope: "row" }, "Contraseña"), h("td", { class: "clave" }, u.contrasena_generada)))),
      h("p", { class: "etiqueta" }, "Mensaje listo para WhatsApp o correo"),
      h("div", { class: "caja-mensaje" }, mensaje),
      h("div", { class: "dialogo-acciones" },
        h("button", { type: "button", class: "boton secundario", onclick: () => copiarTexto(mensaje) }, "Copiar mensaje"),
        h("button", { type: "button", class: "boton", onclick: () => dialogo.close() }, "Listo"))));
  }

  function sugerirUsuario(nombre, ocupados) {
    const partes = sinTildes(nombre).toLowerCase().replace(/[^a-z\s]/g, " ").split(/\s+/).filter(Boolean);
    let base = partes.length >= 4 ? `${partes[0]}.${partes[partes.length - 2]}`
      : partes.length >= 2 ? `${partes[0]}.${partes[1]}` : (partes[0] || "participante");
    base = base.slice(0, 32);
    if (base.length < 3) base = `${base}.sa`;
    let candidato = base;
    for (let n = 2; ocupados.has(candidato); n++) candidato = `${base}${n}`;
    return candidato;
  }

  function dialogoNuevoUsuario() {
    const ocupados = new Set(estado.usuarios.map((u) => u.usuario));
    const zonaError = h("div");
    const nombre = h("input", { type: "text", id: "u-nombre", maxlength: "120", autocomplete: "off" });
    const usuario = h("input", { type: "text", id: "u-usuario", maxlength: "40", autocapitalize: "none", spellcheck: "false", autocomplete: "off" });
    let usuarioTocado = false;
    nombre.addEventListener("input", () => { if (!usuarioTocado) usuario.value = nombre.value.trim() ? sugerirUsuario(nombre.value, ocupados) : ""; });
    usuario.addEventListener("input", () => { usuarioTocado = true; });
    const email = h("input", { type: "email", id: "u-email", maxlength: "200", autocomplete: "off" });
    const modalidad = h("select", { id: "u-modalidad" }, h("option", { value: "presencial" }, "Presencial"), h("option", { value: "virtual" }, "Virtual"));
    const rol = h("select", { id: "u-rol" }, h("option", { value: "participante" }, "Participante"), h("option", { value: "superadmin" }, "Superadmin (organización)"));
    const contrasena = h("input", { type: "text", id: "u-contrasena", maxlength: "128", autocomplete: "new-password" });
    const dialogo = abrirDialogo(h("form", { class: "dialogo-cuerpo", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        vaciar(zonaError);
        try {
          const r = await api.pedir("/admin/usuarios", { metodo: "POST", cuerpo: {
            nombre: nombre.value, usuario: usuario.value, email: email.value, modalidad: modalidad.value,
            rol: rol.value, contrasena: contrasena.value || undefined } });
          dialogo.close();
          await recargarUsuarios();
          if (r.usuario.contrasena_generada) dialogoCredencial(r.usuario, "Cuenta creada");
          else avisar("Cuenta creada con la contraseña que escribiste");
        } catch (error) { zonaError.append(bloqueError(error)); }
      } },
      h("h2", {}, "Agregar persona"),
      zonaError,
      h("div", { class: "campo" }, h("label", { for: "u-nombre" }, "Nombre completo"), nombre),
      h("div", { class: "rejilla-2" },
        h("div", { class: "campo" }, h("label", { for: "u-usuario" }, "Usuario"), usuario),
        h("div", { class: "campo" }, h("label", { for: "u-email" }, "Correo (opcional)"), email)),
      h("div", { class: "rejilla-2" },
        h("div", { class: "campo" }, h("label", { for: "u-modalidad" }, "Modalidad"), modalidad),
        h("div", { class: "campo" }, h("label", { for: "u-rol" }, "Rol"), rol)),
      h("div", { class: "campo" }, h("label", { for: "u-contrasena" }, "Contraseña (opcional)"), contrasena,
        h("span", { class: "ayuda" }, "Déjala vacía y se genera una fácil de dictar, como cometa-orbita-4821.")),
      h("div", { class: "dialogo-acciones" },
        h("button", { type: "button", class: "boton discreto", onclick: () => dialogo.close() }, "Cancelar"),
        h("button", { type: "submit", class: "boton" }, "Crear cuenta"))));
    nombre.focus();
  }

  function dialogoEditarUsuario(u) {
    const zonaError = h("div");
    const nombre = h("input", { type: "text", id: "e-nombre", valor: u.nombre, maxlength: "120" });
    const email = h("input", { type: "email", id: "e-email", valor: u.email, maxlength: "200" });
    const modalidad = h("select", { id: "e-modalidad" }, h("option", { value: "presencial" }, "Presencial"), h("option", { value: "virtual" }, "Virtual"));
    modalidad.value = u.modalidad;
    const dialogo = abrirDialogo(h("form", { class: "dialogo-cuerpo", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        vaciar(zonaError);
        try {
          await api.pedir(`/admin/usuarios/${u.id}`, { metodo: "PUT", cuerpo: { nombre: nombre.value, email: email.value, modalidad: modalidad.value } });
          dialogo.close();
          await recargarUsuarios();
          avisar("Cambios guardados");
        } catch (error) { zonaError.append(bloqueError(error)); }
      } },
      h("h2", {}, `Editar a ${u.nombre}`),
      zonaError,
      h("p", {}, `Usuario: ${u.usuario}`),
      h("div", { class: "campo" }, h("label", { for: "e-nombre" }, "Nombre completo"), nombre),
      h("div", { class: "rejilla-2" },
        h("div", { class: "campo" }, h("label", { for: "e-email" }, "Correo"), email),
        h("div", { class: "campo" }, h("label", { for: "e-modalidad" }, "Modalidad"), modalidad)),
      h("div", { class: "dialogo-acciones" },
        u.id !== estado.usuario.id && h("button", { type: "button", class: "boton peligro secundario pequeno",
          onclick: async () => { dialogo.close(); await eliminarUsuario(u); } }, "Eliminar cuenta"),
        h("button", { type: "button", class: "boton discreto", onclick: () => dialogo.close() }, "Cancelar"),
        h("button", { type: "submit", class: "boton" }, "Guardar cambios"))));
  }

  async function restablecer(u) {
    if (!await confirmar("Generar nueva contraseña", `${u.nombre} ya no podrá entrar con su contraseña actual y se cerrarán sus sesiones abiertas.`,
      { textoAceptar: "Generar contraseña", peligro: false })) return;
    try {
      const r = await api.pedir(`/admin/usuarios/${u.id}/restablecer-contrasena`, { metodo: "POST" });
      dialogoCredencial(r.usuario, "Nueva contraseña");
    } catch (error) { fallo(error); }
  }

  async function alternarUsuario(u) {
    if (u.activo && !await confirmar("Desactivar cuenta", `${u.nombre} no podrá entrar hasta que la actives de nuevo. Sus sesiones abiertas se cierran ya.`,
      { textoAceptar: "Desactivar" })) return;
    try {
      await api.pedir(`/admin/usuarios/${u.id}`, { metodo: "PUT", cuerpo: { activo: !u.activo } });
      await recargarUsuarios();
      avisar(u.activo ? "Cuenta desactivada" : "Cuenta activada");
    } catch (error) { fallo(error); }
  }

  async function eliminarUsuario(u) {
    if (!await confirmar("Eliminar cuenta", `¿Eliminar la cuenta de ${u.nombre}? Esta acción no se puede deshacer. Si solo quieres impedir el acceso, desactívala.`)) return;
    try {
      await api.pedir(`/admin/usuarios/${u.id}`, { metodo: "DELETE" });
      await recargarUsuarios();
      avisar("Cuenta eliminada");
    } catch (error) { fallo(error); }
  }

  /* ---------------------------------------------------------------- importar lista (CSV) */

  function parsearCSV(texto) {
    texto = texto.replace(/^﻿/, "").trim();
    if (!texto) return [];
    const primera = texto.split(/\r?\n/)[0];
    const contar = (c) => primera.split(c).length - 1;
    const sep = contar("\t") > Math.max(contar(";"), contar(",")) ? "\t" : contar(";") > contar(",") ? ";" : ",";
    const filas = [];
    let fila = [], campo = "", comillas = false;
    for (let i = 0; i < texto.length; i++) {
      const c = texto[i];
      if (comillas) {
        if (c === '"' && texto[i + 1] === '"') { campo += '"'; i++; }
        else if (c === '"') comillas = false;
        else campo += c;
      } else if (c === '"') comillas = true;
      else if (c === sep) { fila.push(campo); campo = ""; }
      else if (c === "\n" || c === "\r") {
        if (c === "\r" && texto[i + 1] === "\n") i++;
        fila.push(campo); filas.push(fila); fila = []; campo = "";
      } else campo += c;
    }
    fila.push(campo);
    filas.push(fila);
    return filas.filter((f) => f.some((v) => v.trim()));
  }

  const COLUMNAS = {
    nombre: ["nombre", "nombre completo", "nombres", "participante"],
    usuario: ["usuario", "user", "username"],
    email: ["email", "correo", "correo electronico", "e-mail", "mail"],
    modalidad: ["modalidad", "tipo", "asistencia"],
  };

  function filasAUsuarios(filas) {
    if (filas.length < 2) throw new Error("La lista necesita una fila de encabezados y al menos una persona.");
    const encabezados = filas[0].map((x) => sinTildes(x.trim().toLowerCase()));
    const indice = {};
    for (const [clave, nombres] of Object.entries(COLUMNAS)) {
      indice[clave] = encabezados.findIndex((e) => nombres.includes(e));
    }
    if (indice.nombre < 0) throw new Error('No encontré la columna "nombre". La primera fila debe tener los encabezados: nombre, usuario, email, modalidad.');
    const ocupados = new Set(estado.usuarios.map((u) => u.usuario));
    return filas.slice(1).map((f) => {
      const valor = (k) => (indice[k] >= 0 ? (f[indice[k]] || "").trim() : "");
      const nombre = valor("nombre");
      let usuario = valor("usuario").toLowerCase();
      if (!usuario) usuario = sugerirUsuario(nombre, ocupados);
      ocupados.add(usuario);
      const modalidad = sinTildes(valor("modalidad").toLowerCase()).startsWith("virt") ? "virtual" : "presencial";
      return { nombre, usuario, email: valor("email"), modalidad };
    });
  }

  function dialogoImportar() {
    let filas = [];
    const zonaError = h("div");
    const vista = h("p", { class: "ayuda" });
    const texto = h("textarea", { id: "imp-texto", rows: "8", placeholder: "nombre;usuario;email;modalidad\nAna María López;;ana@correo.com;presencial\nLuis Pérez;luis.perez;;virtual",
      oninput: () => actualizar(texto.value) });
    const archivo = h("input", { type: "file", id: "imp-archivo", accept: ".csv,.txt,text/csv",
      onchange: async (e) => { const f = e.target.files[0]; if (f) { texto.value = await f.text(); actualizar(texto.value); } } });
    const importar = h("button", { type: "submit", class: "boton", disabled: true }, "Importar");

    function actualizar(valor) {
      vaciar(zonaError);
      try {
        filas = valor.trim() ? filasAUsuarios(parsearCSV(valor)) : [];
        vista.textContent = filas.length ? `Listas para importar: ${filas.length} personas. Ejemplo: ${filas[0].nombre} quedará como ${filas[0].usuario}.` : "";
        importar.disabled = !filas.length;
        importar.textContent = filas.length ? `Importar ${filas.length} ${filas.length === 1 ? "persona" : "personas"}` : "Importar";
      } catch (error) {
        filas = [];
        vista.textContent = "";
        importar.disabled = true;
        zonaError.append(h("div", { class: "aviso-error" }, error.message));
      }
    }

    const dialogo = abrirDialogo(h("form", { class: "dialogo-cuerpo", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        vaciar(zonaError);
        importar.disabled = true;
        importar.textContent = "Creando cuentas…";
        try {
          const r = await api.pedir("/admin/usuarios/importar", { metodo: "POST", cuerpo: { usuarios: filas } });
          dialogo.close();
          await recargarUsuarios();
          resultadoImportacion(r.usuarios);
        } catch (error) {
          zonaError.append(bloqueError(error));
          importar.disabled = false;
          importar.textContent = `Importar ${filas.length} personas`;
        }
      } },
      h("h2", {}, "Importar lista de participantes"),
      h("p", {}, "Exporta tu hoja de inscritos (Excel o Google Sheets) como CSV o copia y pega las columnas aquí. Solo el nombre es obligatorio; si no pones usuario, se crea uno con nombre y apellido."),
      zonaError,
      h("div", { class: "campo" }, h("label", { for: "imp-archivo" }, "Archivo CSV"), archivo),
      h("div", { class: "campo" }, h("label", { for: "imp-texto" }, "O pega la lista"), texto, vista),
      h("div", { class: "dialogo-acciones" },
        h("button", { type: "button", class: "boton discreto", onclick: () => dialogo.close() }, "Cancelar"),
        importar)), { ancho: true });
  }

  function csvCredenciales(usuarios) {
    const celda = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const lineas = [["nombre", "usuario", "contrasena", "modalidad", "email", "portal"].join(";")];
    for (const u of usuarios) lineas.push([u.nombre, u.usuario, u.contrasena_generada, u.modalidad, u.email, URL_PORTAL].map(celda).join(";"));
    return new Blob(["﻿" + lineas.join("\r\n")], { type: "text/csv;charset=utf-8" });
  }

  function resultadoImportacion(usuarios) {
    const descargar = () => guardarBlob(csvCredenciales(usuarios), `credenciales-space-apps-${new Date().toISOString().slice(0, 10)}.csv`);
    const dialogo = abrirDialogo(h("div", { class: "dialogo-cuerpo" },
      h("h2", {}, `${usuarios.length} cuentas creadas`),
      h("p", { class: "nota-importante" }, "Descarga las credenciales ahora: las contraseñas no se vuelven a mostrar. Guarda el archivo en un lugar privado."),
      h("div", { class: "tabla-envoltura" }, h("table", { class: "credenciales" },
        h("thead", {}, h("tr", {}, h("th", {}, "Nombre"), h("th", {}, "Usuario"), h("th", {}, "Contraseña"))),
        h("tbody", {}, usuarios.map((u) => h("tr", {}, h("td", {}, u.nombre), h("td", {}, u.usuario), h("td", { class: "clave" }, u.contrasena_generada)))))),
      h("div", { class: "dialogo-acciones" },
        h("button", { type: "button", class: "boton secundario", onclick: descargar }, "Descargar credenciales (CSV)"),
        h("button", { type: "button", class: "boton", onclick: () => dialogo.close() }, "Listo"))), { ancho: true });
  }

  /* ================================================================ ESTADÍSTICAS */

  async function vistaEstadisticas() {
    document.title = "Estadísticas — Panel de organización";
    const zona = h("div", {}, h("p", { class: "cargando" }, "Calculando…"));
    vaciar(principal,
      h("h1", {}, "Estadísticas"),
      h("p", { class: "intro" }, "Cómo se está usando la mochila. Las visitas y descargas del equipo organizador no se cuentan."),
      zona);
    let d;
    try { d = await api.pedir("/admin/estadisticas"); } catch (error) { return vaciar(zona, bloqueError(error)); }

    const p = d.participantes;
    const porcentaje = p.total ? Math.round((p.han_ingresado / p.total) * 100) : 0;
    const cifra = (valor, rotulo) => h("div", { class: "tarjeta cifra" }, h("div", { class: "valor" }, valor), h("div", { class: "rotulo" }, rotulo));

    const barras = (lista, valor, etiqueta, detalle, clase = "") => {
      const max = Math.max(1, ...lista.map(valor));
      if (!lista.length || max === 0 && !lista.some(valor)) return h("p", { class: "vacio" }, "Todavía no hay datos.");
      return h("ul", { class: "barras" }, lista.map((x) => h("li", { class: "barra" },
        h("div", { class: "encabezado" }, h("strong", {}, etiqueta(x)), h("span", {}, detalle(x))),
        h("div", { class: "pista", role: "presentation" },
          h("span", { class: `relleno ${clase}`, estilo: { width: `${Math.round((valor(x) / max) * 100)}%` } })))));
    };

    vaciar(zona,
      h("div", { class: "cifras" },
        cifra(p.total, `participantes (${p.por_modalidad.presencial || 0} presenciales, ${p.por_modalidad.virtual || 0} virtuales)`),
        cifra(`${porcentaje} %`, `ya entraron al portal (${p.han_ingresado} de ${p.total})`),
        cifra(d.logins.total, "inicios de sesión en total"),
        cifra(d.descargas.reduce((a, x) => a + x.descargas, 0), "descargas de archivos")),
      h("div", { class: "graficas" },
        h("section", { class: "tarjeta grafica" }, h("h2", {}, "Secciones más visitadas"),
          barras(d.secciones, (x) => x.vistas, (x) => `${x.icono} ${x.titulo}`,
            (x) => `${x.vistas} visitas, ${x.personas} ${x.personas === 1 ? "persona" : "personas"}`)),
        h("section", { class: "tarjeta grafica" }, h("h2", {}, "Archivos más descargados"),
          barras(d.descargas, (x) => x.descargas, (x) => x.nombre,
            (x) => `${x.descargas} (${x.personas} ${x.personas === 1 ? "persona" : "personas"})`, "hilo")),
        h("section", { class: "tarjeta grafica" }, h("h2", {}, "Inicios de sesión por día"),
          barras(d.logins.por_dia, (x) => x.n, (x) => nombreDia(x.dia, true), (x) => String(x.n)))));
  }

  iniciar();
})();
