/* ==========================================================================
   Portal de participantes (mochila virtual).
   Rutas: #/ (inicio) y #/seccion/:id
   ========================================================================== */
"use strict";

(() => {
  const app = document.getElementById("app");
  const sesion = new Sesion(CLAVE_SESION);
  const api = crearClienteApi(sesion, (mensaje) => mostrarIngreso(mensaje));

  const estado = { usuario: null, indice: null, temporizador: null };
  const TONOS = ["var(--tono-1)", "var(--tono-2)", "var(--tono-3)", "var(--tono-4)", "var(--tono-5)", "var(--tono-6)"];
  const ICONOS_ARCHIVO = { pdf: "📄", zip: "🗜️", png: "🖼️", jpg: "🖼️", jpeg: "🖼️", webp: "🖼️", svg: "🖼️", mp4: "🎬",
    mp3: "🎧", docx: "📝", pptx: "📊", xlsx: "📈", csv: "📈", ics: "🗓️", ttf: "🔤", otf: "🔤", woff: "🔤", woff2: "🔤" };

  /* ---------------------------------------------------------------- arranque */

  async function iniciar() {
    if (!sesion.token) return mostrarIngreso();
    try {
      estado.usuario = (await api.pedir("/auth/yo")).usuario;
      montarPortal();
    } catch (error) {
      if (error.estado !== 401) mostrarIngreso(error.message);
    }
  }

  function mostrarIngreso(mensaje) {
    clearInterval(estado.temporizador);
    estado.usuario = null;
    estado.indice = null;
    document.title = "Mochila virtual — NASA Space Apps San Vicente Ferrer";
    vaciar(app, pantallaIngreso({
      titulo: "Tu mochila para el NASA Space Apps Challenge",
      subtitulo: "Entra a tu mochila",
      nota: "Recibiste tu usuario y contraseña de la organización. Si no los tienes o los olvidaste, escríbele al equipo de Ola Fibonacci.",
      enlace: { texto: "¿Eres del equipo organizador? Entra al panel de organización", href: "admin/" },
      mensajeInicial: mensaje,
      alEntrar: async (usuario, contrasena) => {
        const r = await api.pedir("/auth/login", { metodo: "POST", cuerpo: { usuario, contrasena } });
        sesion.token = r.token;
        estado.usuario = r.usuario;
        if (location.hash.startsWith("#/seccion/")) montarPortal();
        else { history.replaceState(null, "", "#/"); montarPortal(); }
      },
    }));
  }

  /* ---------------------------------------------------------------- estructura */

  let principal;
  let menuAbierto = null;
  document.addEventListener("click", (e) => { if (menuAbierto && !menuAbierto.contains(e.target)) menuAbierto.open = false; });

  function montarPortal() {
    principal = h("main", { id: "principal", tabindex: "-1" });
    vaciar(app,
      h("a", { class: "solo-lector", href: "#principal" }, "Saltar al contenido"),
      banda(),
      principal,
      h("footer", { class: "pie" }, h("div", { class: "contenedor" },
        "NASA Space Apps Challenge, sede San Vicente Ferrer. Organiza Ola Fibonacci, mujeres en ciencia.")));
    enrutar();
  }

  function banda() {
    const u = estado.usuario;
    const menu = h("details", { class: "menu-usuario" },
      h("summary", { "aria-label": `Menú de ${u.nombre}` },
        h("span", { class: "nombre-corto" }, u.nombre.split(" ")[0]),
        h("span", { class: "inicial", "aria-hidden": "true" }, u.nombre.trim().charAt(0).toUpperCase())),
      h("div", { class: "opciones" },
        h("div", { class: "quien" }, u.nombre, h("br"), `Usuario: ${u.usuario}`),
        h("button", { type: "button", onclick: () => { menu.open = false; dialogoContrasena(); } }, "Cambiar contraseña"),
        u.rol === "superadmin" && h("button", { type: "button", onclick: () => { location.href = "admin/"; } }, "Ir al panel de organización"),
        h("button", { type: "button", onclick: salir }, "Cerrar sesión")));
    menuAbierto = menu;
    return h("header", { class: "banda" }, h("div", { class: "contenedor" },
      h("a", { class: "marca", href: "#/" },
        h("img", { src: "assets/img/insignia.svg", alt: "" }),
        h("span", {}, "Mochila virtual", h("small", {}, "Space Apps San Vicente Ferrer"))),
      menu));
  }

  function salir() {
    sesion.cerrar();
    history.replaceState(null, "", "#/");
    mostrarIngreso();
  }

  function enrutar() {
    if (!estado.usuario) return;
    clearInterval(estado.temporizador);
    const coincidencia = location.hash.match(/^#\/seccion\/(\d+)/);
    if (coincidencia) vistaSeccion(Number(coincidencia[1]));
    else vistaInicio();
    window.scrollTo(0, 0);
  }

  window.addEventListener("hashchange", enrutar);

  /* ---------------------------------------------------------------- inicio */

  async function vistaInicio() {
    document.title = "Mochila virtual — NASA Space Apps San Vicente Ferrer";
    const zonaProximo = h("div");
    const zonaFaja = h("div", { class: "cargando" }, "Cargando secciones…");
    vaciar(principal, h("div", { class: "contenedor inicio" },
      h("section", { class: "saludo" },
        h("h1", {}, `Hola, ${estado.usuario.nombre.split(" ")[0]}.`),
        h("p", {}, "Aquí está todo lo del hackathon: horarios, enlaces, guías y descargas. Es lo mismo si vienes a la sede o te conectas desde casa.")),
      zonaProximo,
      h("section", { class: "faja", "aria-labelledby": "titulo-faja" },
        h("h2", { id: "titulo-faja" }, "Tu mochila"),
        zonaFaja)));

    cargarProximos(zonaProximo);
    estado.temporizador = setInterval(() => cargarProximos(zonaProximo), 60000);

    try {
      estado.indice = (await api.pedir("/mochila")).secciones;
      vaciar(zonaFaja);
      zonaFaja.className = "";
      if (!estado.indice.length) {
        zonaFaja.append(h("p", { class: "vacio" }, "La organización todavía está preparando la mochila. Vuelve pronto."));
        return;
      }
      zonaFaja.append(h("ul", { class: "insignias" }, estado.indice.map((s, i) => h("li", {},
        h("a", { class: `insignia ${s.cantidad_items ? "" : "vacia"}`, href: `#/seccion/${s.id}` },
          parche(s, i),
          h("span", { class: "insignia-titulo" }, s.titulo),
          h("span", { class: "insignia-conteo" },
            s.cantidad_items ? `${s.cantidad_items} ${s.cantidad_items === 1 ? "recurso" : "recursos"}` : "Pronto"))))));
    } catch (error) {
      vaciar(zonaFaja, bloqueError(error));
    }
  }

  function parche(seccion, posicion) {
    const i = posicion ?? Math.max(0, (estado.indice || []).findIndex((s) => s.id === seccion.id));
    return h("span", { class: "parche", "aria-hidden": "true", estilo: { "--tono": TONOS[i % TONOS.length] } },
      h("span", { class: "parche-icono" }, seccion.icono || "📦"));
  }

  async function cargarProximos(zona) {
    let datos;
    try { datos = await api.pedir("/mochila/proximos"); } catch { return; }
    const [primero, ...resto] = datos.eventos;
    if (!primero) { vaciar(zona); return; }
    const enCurso = estadoEvento(primero) === "en_curso";
    const url = urlSegura(primero.url);
    vaciar(zona, h("section", { class: `proximo ${enCurso ? "en-curso" : ""}`, "aria-labelledby": "titulo-proximo" },
      h("h2", { id: "titulo-proximo" }, enCurso ? "Ahora mismo" : "Lo próximo"),
      h("div", { class: "proximo-principal" },
        h("p", { class: "cuando" }, cuandoEvento(primero)),
        h("h3", {}, primero.titulo),
        primero.lugar && h("p", { class: "lugar" }, primero.lugar),
        url && h("a", { class: `boton ${enCurso ? "en-vivo" : ""}`, href: url, target: "_blank", rel: "noopener noreferrer" },
          enCurso ? "Entrar a la transmisión" : "Abrir enlace de conexión")),
      resto.length > 0 && h("ul", { class: "proximo-siguientes", "aria-label": "Después" }, resto.map((e) =>
        h("li", {}, h("span", { class: "cuando" }, cuandoEvento(e, true)), h("span", {}, e.titulo))))));
  }

  function cuandoEvento(e, corto = false) {
    const hoy = ahoraLocal().slice(0, 10);
    const dia = e.fecha === hoy ? "Hoy" : nombreDia(e.fecha, corto);
    const horas = e.hora_inicio ? `${hora12(e.hora_inicio)}${e.hora_fin && !corto ? ` a ${hora12(e.hora_fin)}` : ""}` : "";
    return horas ? `${dia}, ${horas}` : dia;
  }

  /* ---------------------------------------------------------------- sección */

  async function vistaSeccion(id) {
    const contenido = h("div", { class: "cargando" }, "Abriendo la sección…");
    vaciar(principal, h("div", { class: "contenedor vista-seccion" },
      h("a", { class: "volver", href: "#/" }, "‹ Volver a la mochila"),
      contenido));
    try {
      const { seccion } = await api.pedir(`/mochila/secciones/${id}`);
      document.title = `${seccion.titulo} — Mochila virtual`;
      const cabecera = h("header", { class: "cabecera-seccion" },
        parche(seccion),
        h("div", {}, h("h1", {}, seccion.titulo), seccion.descripcion && h("p", {}, seccion.descripcion)));
      const bloques = h("div", { class: "bloques" }, construirBloques(seccion.items));
      contenido.replaceWith(cabecera, bloques);
      principal.focus({ preventScroll: true });
    } catch (error) {
      vaciar(contenido, bloqueError(error));
      contenido.className = "";
    }
  }

  /** Agrupa ítems consecutivos del mismo tipo en bloques: galería, cronograma, lista de recursos. */
  function construirBloques(items) {
    if (!items.length) {
      return h("p", { class: "vacio" }, "Esta sección todavía está vacía. La organización la llenará antes del evento.");
    }
    const grupos = [];
    for (const item of items) {
      const familia = item.tipo === "enlace" || item.tipo === "archivo" ? "recurso" : item.tipo;
      const ultimo = grupos[grupos.length - 1];
      if (ultimo && ultimo.familia === familia && familia !== "texto") ultimo.items.push(item);
      else grupos.push({ familia, items: [item] });
    }
    return grupos.map(({ familia, items: lista }) => {
      if (familia === "texto") return bloqueTexto(lista[0]);
      if (familia === "imagen") return h("ul", { class: "galeria" }, lista.map((i) => h("li", {}, figuraImagen(i))));
      if (familia === "evento") return bloqueCronograma(lista);
      return h("ul", { class: "recursos" }, lista.map((i) => h("li", {}, i.tipo === "enlace" ? filaEnlace(i) : filaArchivo(i))));
    });
  }

  function bloqueTexto(item) {
    return h("article", { class: "bloque-texto" }, h("h2", {}, item.titulo), textoEnriquecido(item.descripcion));
  }

  function filaEnlace(item) {
    const url = urlSegura(item.url);
    let dominio = "";
    try { dominio = new URL(url).hostname.replace(/^www\./, ""); } catch { /* sin url */ }
    return h("a", { class: "recurso", href: url || "#", target: "_blank", rel: "noopener noreferrer" },
      h("span", { class: "recurso-icono", "aria-hidden": "true" }, "🔗"),
      h("span", {}, h("span", { class: "recurso-titulo" }, item.titulo), h("br"), h("span", { class: "recurso-meta" }, dominio)),
      item.descripcion && h("span", { class: "recurso-desc" }, item.descripcion),
      h("span", { class: "boton secundario pequeno recurso-accion", "aria-hidden": "true" }, "Abrir"));
  }

  function filaArchivo(item) {
    const a = item.archivo;
    const extension = a ? a.nombre.split(".").pop().toLowerCase() : "";
    return h("div", { class: "recurso" },
      h("span", { class: "recurso-icono", "aria-hidden": "true" }, ICONOS_ARCHIVO[extension] || "📦"),
      h("span", {}, h("span", { class: "recurso-titulo" }, item.titulo), h("br"),
        h("span", { class: "recurso-meta" }, a ? `${extension.toUpperCase()}, ${formatoTamano(a.tamano_bytes)}` : "Archivo no disponible")),
      item.descripcion && h("span", { class: "recurso-desc" }, item.descripcion),
      a && botonDescarga(a, "Descargar", "boton pequeno recurso-accion"));
  }

  function botonDescarga(archivo, texto, clase = "boton pequeno") {
    const boton = h("button", { type: "button", class: clase, "aria-label": `${texto} ${archivo.nombre}` }, texto);
    boton.addEventListener("click", async () => {
      if (boton.disabled) return;
      boton.disabled = true;
      boton.classList.add("descargando");
      const barra = h("span", { class: "progreso", estilo: { width: "0%" } });
      boton.append(barra);
      boton.firstChild.textContent = "Descargando…";
      try {
        const blob = await api.blob(`/archivos/${archivo.id}?descargar=1`,
          (p) => barra.style.setProperty("width", `${Math.round(p * 100)}%`));
        guardarBlob(blob, archivo.nombre);
      } catch (error) {
        avisar(error.message, "error");
      } finally {
        boton.disabled = false;
        boton.classList.remove("descargando");
        barra.remove();
        boton.firstChild.textContent = texto;
      }
    });
    return boton;
  }

  /* Las miniaturas se piden con el token y se cargan solo cuando aparecen en pantalla. */
  const observador = "IntersectionObserver" in window
    ? new IntersectionObserver((entradas) => entradas.forEach((e) => {
        if (e.isIntersecting) { observador.unobserve(e.target); cargarMiniatura(e.target); }
      }), { rootMargin: "200px" })
    : null;

  async function cargarMiniatura(img) {
    try {
      const blob = await api.blob(`/archivos/${img.dataset.archivo}?miniatura=1`);
      img.src = URL.createObjectURL(blob);
    } catch { img.alt = "No se pudo cargar la vista previa"; }
  }

  function figuraImagen(item) {
    const a = item.archivo;
    const img = h("img", { alt: item.descripcion || item.titulo, "data-archivo": a ? a.id : "", decoding: "async" });
    if (a) { if (observador) observador.observe(img); else cargarMiniatura(img); }
    return h("figure", {},
      h("button", { type: "button", class: "miniatura", "aria-label": `Ver ${item.titulo} en grande`,
        onclick: () => a && abrirVisor(item, img.src) }, img),
      h("figcaption", {}, h("span", {}, item.titulo), a && botonDescarga(a, "Descargar", "boton secundario pequeno")));
  }

  function abrirVisor(item, src) {
    const dialogo = abrirDialogo(h("div", { class: "dialogo-cuerpo visor" },
      h("h2", {}, item.titulo),
      src ? h("img", { src, alt: item.descripcion || item.titulo }) : null,
      item.descripcion && h("p", {}, item.descripcion),
      h("div", { class: "dialogo-acciones" },
        h("button", { type: "button", class: "boton discreto", onclick: () => dialogo.close() }, "Cerrar"),
        botonDescarga(item.archivo, `Descargar original (${formatoTamano(item.archivo.tamano_bytes)})`, "boton"))),
    { ancho: true });
  }

  function bloqueCronograma(eventos) {
    const ahora = ahoraLocal();
    const porDia = new Map();
    for (const e of eventos) {
      if (!porDia.has(e.fecha)) porDia.set(e.fecha, []);
      porDia.get(e.fecha).push(e);
    }
    return h("div", { class: "bloque-cronograma" }, [...porDia].map(([fecha, lista]) =>
      h("section", { class: "dia" },
        h("h2", {}, ahora.slice(0, 10) === fecha ? `Hoy, ${nombreDia(fecha).toLowerCase()}` : nombreDia(fecha)),
        h("ol", { class: "cronograma" }, lista.map((e) => {
          const est = estadoEvento(e, ahora);
          const url = urlSegura(e.url);
          return h("li", { class: `evento ${est}` },
            h("div", { class: "evento-hora" },
              e.hora_inicio ? hora12(e.hora_inicio) : "Todo el día",
              e.hora_fin && h("span", {}, `a ${hora12(e.hora_fin)}`)),
            h("div", { class: "evento-cuerpo" },
              est === "en_curso" && h("span", { class: "etiqueta-ahora" }, "Ahora"),
              h("h3", {}, e.titulo),
              e.lugar && h("p", { class: "evento-lugar" }, e.lugar),
              e.descripcion && textoEnriquecido(e.descripcion),
              url && est !== "pasado" && h("a", { class: "boton secundario pequeno", href: url, target: "_blank",
                rel: "noopener noreferrer" }, "Abrir enlace de conexión")));
        })))));
  }

  /* ---------------------------------------------------------------- cambiar contraseña */

  function dialogoContrasena() {
    const zonaError = h("div");
    const actual = h("input", { type: "password", id: "c-actual", autocomplete: "current-password", required: true });
    const nueva = h("input", { type: "password", id: "c-nueva", autocomplete: "new-password", minlength: "8", required: true });
    const repetir = h("input", { type: "password", id: "c-repetir", autocomplete: "new-password", required: true });
    const guardar = h("button", { class: "boton", type: "submit" }, "Guardar contraseña");
    const dialogo = abrirDialogo(h("form", { class: "dialogo-cuerpo", novalidate: true,
      onsubmit: async (e) => {
        e.preventDefault();
        vaciar(zonaError);
        if (nueva.value.length < 8) return zonaError.append(h("div", { class: "aviso-error" }, "La nueva contraseña debe tener al menos 8 caracteres."));
        if (nueva.value !== repetir.value) return zonaError.append(h("div", { class: "aviso-error" }, "Las dos contraseñas nuevas no coinciden."));
        guardar.disabled = true;
        try {
          const r = await api.pedir("/auth/cambiar-contrasena", { metodo: "POST", cuerpo: { actual: actual.value, nueva: nueva.value } });
          sesion.token = r.token;
          dialogo.close();
          avisar("Contraseña guardada");
        } catch (error) {
          zonaError.append(bloqueError(error));
        } finally { guardar.disabled = false; }
      } },
      h("h2", {}, "Cambiar contraseña"),
      zonaError,
      h("div", { class: "campo" }, h("label", { for: "c-actual" }, "Contraseña actual"), actual),
      h("div", { class: "campo" }, h("label", { for: "c-nueva" }, "Nueva contraseña"), nueva,
        h("span", { class: "ayuda" }, "Mínimo 8 caracteres.")),
      h("div", { class: "campo" }, h("label", { for: "c-repetir" }, "Repite la nueva contraseña"), repetir),
      h("div", { class: "dialogo-acciones" },
        h("button", { class: "boton discreto", type: "button", onclick: () => dialogo.close() }, "Cancelar"),
        guardar)));
    actual.focus();
  }

  iniciar();
})();
