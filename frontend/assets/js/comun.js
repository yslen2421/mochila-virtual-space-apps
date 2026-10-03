/* ==========================================================================
   Utilidades compartidas: cliente de la API, construcción segura del DOM,
   avisos y descargas. Sin dependencias externas.
   ========================================================================== */
"use strict";

const API_BASE = (window.PORTAL_CONFIG && window.PORTAL_CONFIG.apiBase) || "/api/v1";

/* ---------------------------------------------------------------- sesión */

/* Portal y panel comparten la misma sesión: quien entra con la cuenta de
   Superadmin en uno puede pasar al otro sin volver a escribir la contraseña. */
const CLAVE_SESION = "mochila.token";

class Sesion {
  constructor(clave) { this.clave = clave; }
  get token() { try { return localStorage.getItem(this.clave); } catch { return null; } }
  set token(valor) {
    try { valor ? localStorage.setItem(this.clave, valor) : localStorage.removeItem(this.clave); } catch { /* modo privado */ }
  }
  cerrar() { this.token = null; }
}

/* ---------------------------------------------------------------- API */

class ErrorApi extends Error {
  constructor(codigo, mensaje, detalle, estado) {
    super(mensaje);
    this.codigo = codigo;
    this.detalle = detalle;
    this.estado = estado;
  }
}

function crearClienteApi(sesion, alExpirar) {
  async function pedir(ruta, { metodo = "GET", cuerpo, formulario } = {}) {
    const cabeceras = {};
    if (sesion.token) cabeceras.Authorization = `Bearer ${sesion.token}`;
    let body;
    if (formulario) body = formulario;
    else if (cuerpo !== undefined) { body = JSON.stringify(cuerpo); cabeceras["Content-Type"] = "application/json"; }

    let respuesta;
    try {
      respuesta = await fetch(API_BASE + ruta, { method: metodo, headers: cabeceras, body });
    } catch {
      throw new ErrorApi("SIN_CONEXION", "No hay conexión con el servidor. Revisa tu internet e intenta de nuevo.", null, 0);
    }
    if (respuesta.status === 204) return null;
    let datos = null;
    try { datos = await respuesta.json(); } catch { /* respuesta vacía */ }
    if (!respuesta.ok) {
      const e = (datos && datos.error) || {};
      const error = new ErrorApi(e.codigo || "ERROR", e.mensaje || "Ocurrió un error inesperado.", e.detalle, respuesta.status);
      if (respuesta.status === 401 && sesion.token && !ruta.startsWith("/auth/login")) {
        sesion.cerrar();
        if (alExpirar) alExpirar(error.message);
      }
      throw error;
    }
    return datos;
  }

  /** Descarga un archivo protegido como blob (el token va en la cabecera, no en la URL). */
  async function blob(ruta, alProgreso) {
    const respuesta = await fetch(API_BASE + ruta, { headers: { Authorization: `Bearer ${sesion.token}` } });
    if (!respuesta.ok) {
      let mensaje = "No se pudo descargar el archivo.";
      try { mensaje = (await respuesta.json()).error.mensaje; } catch { /* sin cuerpo */ }
      if (respuesta.status === 401) { sesion.cerrar(); if (alExpirar) alExpirar(mensaje); }
      throw new ErrorApi("DESCARGA", mensaje, null, respuesta.status);
    }
    const total = Number(respuesta.headers.get("Content-Length")) || 0;
    if (!alProgreso || !total || !respuesta.body) return respuesta.blob();
    const lector = respuesta.body.getReader();
    const partes = [];
    let recibido = 0;
    for (;;) {
      const { done, value } = await lector.read();
      if (done) break;
      partes.push(value);
      recibido += value.length;
      alProgreso(recibido / total);
    }
    return new Blob(partes, { type: respuesta.headers.get("Content-Type") || "" });
  }

  /** Sube un archivo mostrando el progreso (fetch no informa progreso de subida). */
  function subir(ruta, archivo, alProgreso) {
    return new Promise((resolver, rechazar) => {
      const xhr = new XMLHttpRequest();
      const datos = new FormData();
      datos.append("archivo", archivo);
      xhr.open("POST", API_BASE + ruta);
      xhr.setRequestHeader("Authorization", `Bearer ${sesion.token}`);
      xhr.upload.onprogress = (e) => { if (e.lengthComputable && alProgreso) alProgreso(e.loaded / e.total); };
      xhr.onerror = () => rechazar(new ErrorApi("SIN_CONEXION", "Se cortó la conexión durante la subida.", null, 0));
      xhr.onload = () => {
        let cuerpo = null;
        try { cuerpo = JSON.parse(xhr.responseText); } catch { /* vacío */ }
        if (xhr.status >= 200 && xhr.status < 300) return resolver(cuerpo);
        const e = (cuerpo && cuerpo.error) || {};
        rechazar(new ErrorApi(e.codigo || "ERROR", e.mensaje || "No se pudo subir el archivo.", e.detalle, xhr.status));
      };
      xhr.send(datos);
    });
  }

  return { pedir, blob, subir };
}

/* ---------------------------------------------------------------- DOM seguro
   Todo el contenido se inserta como texto (nunca innerHTML con datos), así lo
   que escriba el Superadmin o un participante no puede inyectar código. */

function h(etiqueta, props, ...hijos) {
  const el = document.createElement(etiqueta);
  for (const [clave, valor] of Object.entries(props || {})) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (clave === "class") el.className = valor;
    else if (clave === "estilo") for (const [p, v] of Object.entries(valor)) el.style.setProperty(p, v);
    else if (clave.startsWith("on") && typeof valor === "function") el.addEventListener(clave.slice(2).toLowerCase(), valor);
    else if (clave === "valor") el.value = valor;
    else if (valor === true) el.setAttribute(clave, "");
    else el.setAttribute(clave, valor);
  }
  agregar(el, hijos);
  return el;
}

function agregar(el, hijos) {
  for (const hijo of hijos.flat(Infinity)) {
    if (hijo === null || hijo === undefined || hijo === false) continue;
    el.append(hijo instanceof Node ? hijo : document.createTextNode(String(hijo)));
  }
  return el;
}

function vaciar(el, ...hijos) {
  el.replaceChildren();
  return agregar(el, hijos);
}

function urlSegura(url) {
  if (!url || !/^https?:\/\//i.test(String(url).trim())) return null;
  try {
    const u = new URL(url, location.href);
    return u.protocol === "https:" || u.protocol === "http:" ? u.href : null;
  } catch { return null; }
}

/** Texto con párrafos y enlaces automáticos (https://...), sin HTML. */
function textoEnriquecido(texto, clase = "texto-rico") {
  const contenedor = h("div", { class: clase });
  const parrafos = String(texto || "").split(/\n{2,}/);
  for (const parrafo of parrafos) {
    const p = h("p");
    const partes = parrafo.split(/(https?:\/\/[^\s<>"')\]]+)/g);
    partes.forEach((parte, i) => {
      if (i % 2 === 1 && urlSegura(parte)) {
        p.append(h("a", { href: urlSegura(parte), target: "_blank", rel: "noopener noreferrer" }, parte));
      } else {
        p.append(document.createTextNode(parte));
      }
    });
    contenedor.append(p);
  }
  return contenedor;
}

/* ---------------------------------------------------------------- avisos */

function avisar(mensaje, tipo = "info") {
  let zona = document.querySelector(".tostadas");
  if (!zona) {
    zona = h("div", { class: "tostadas", role: "status", "aria-live": "polite" });
    document.body.append(zona);
  }
  const t = h("div", { class: `tostada ${tipo === "error" ? "error" : ""}` }, mensaje);
  zona.append(t);
  setTimeout(() => t.remove(), tipo === "error" ? 6000 : 3200);
}

function bloqueError(error) {
  const detalle = Array.isArray(error.detalle) ? error.detalle : null;
  return h("div", { class: "aviso-error", role: "alert" },
    error.message,
    detalle && h("ul", {}, detalle.slice(0, 20).map((d) =>
      h("li", {}, d.fila ? `Fila ${d.fila}${d.usuario ? ` (${d.usuario})` : ""}: ${d.error}` : JSON.stringify(d)))));
}

/* ---------------------------------------------------------------- diálogos */

function abrirDialogo(contenido, { ancho = false, alCerrar } = {}) {
  const dialogo = h("dialog", { class: ancho ? "ancho" : "" }, contenido);
  dialogo.addEventListener("close", () => { dialogo.remove(); if (alCerrar) alCerrar(); });
  document.body.append(dialogo);
  dialogo.showModal();
  return dialogo;
}

function confirmar(titulo, mensaje, { textoAceptar = "Eliminar", peligro = true } = {}) {
  return new Promise((resolver) => {
    let respuesta = false;
    const dialogo = abrirDialogo(h("div", { class: "dialogo-cuerpo" },
      h("h2", {}, titulo),
      h("p", {}, mensaje),
      h("div", { class: "dialogo-acciones" },
        h("button", { class: "boton discreto", type: "button", onclick: () => dialogo.close() }, "Cancelar"),
        h("button", { class: `boton ${peligro ? "peligro" : ""}`, type: "button",
          onclick: () => { respuesta = true; dialogo.close(); } }, textoAceptar))),
    { alCerrar: () => resolver(respuesta) });
  });
}

/* ---------------------------------------------------------------- formato */

function formatoTamano(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

function fechaLocal(iso) {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

const formatoDia = new Intl.DateTimeFormat("es-CO", { weekday: "long", day: "numeric", month: "long" });
const formatoDiaCorto = new Intl.DateTimeFormat("es-CO", { weekday: "short", day: "numeric", month: "short" });

function nombreDia(iso, corto = false) {
  const texto = (corto ? formatoDiaCorto : formatoDia).format(fechaLocal(iso));
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

function hora12(hhmm) {
  if (!hhmm) return "";
  const [h24, min] = hhmm.split(":").map(Number);
  const sufijo = h24 < 12 ? "a. m." : "p. m.";
  return `${((h24 + 11) % 12) + 1}:${String(min).padStart(2, "0")} ${sufijo}`;
}

function ahoraLocal() {
  const d = new Date();
  const dos = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
}

/** "en_curso" | "pasado" | "futuro" para un ítem de cronograma. */
function estadoEvento(evento, ahora = ahoraLocal()) {
  // Sin hora de fin se asume una hora de duración; sin horas, todo el día.
  const inicio = `${evento.fecha} ${evento.hora_inicio || "00:00"}`;
  const horaFin = evento.hora_fin || (evento.hora_inicio ? sumarHoras(evento.hora_inicio, 1) : "23:59");
  const fin = `${evento.fecha} ${horaFin}`;
  if (ahora < inicio) return "futuro";
  if (ahora <= fin) return "en_curso";
  return "pasado";
}

function sumarHoras(hhmm, horas) {
  const [hh, mm] = hhmm.split(":").map(Number);
  const total = Math.min(23 * 60 + 59, hh * 60 + mm + horas * 60);
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/* ---------------------------------------------------------------- descargas */

function guardarBlob(blob, nombre) {
  const url = URL.createObjectURL(blob);
  const a = h("a", { href: url, download: nombre });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 30000);
}

async function copiarTexto(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    avisar("Copiado al portapapeles");
  } catch {
    avisar("No se pudo copiar. Selecciona el texto y cópialo a mano.", "error");
  }
}

/* ---------------------------------------------------------------- marca del evento */

const SVG_NS = "http://www.w3.org/2000/svg";

function iconoPin() {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 32");
  svg.setAttribute("aria-hidden", "true");
  const ruta = document.createElementNS(SVG_NS, "path");
  ruta.setAttribute("d", "M12 0C5.4 0 0 5.3 0 11.9 0 20.8 12 32 12 32s12-11.2 12-20.1C24 5.3 18.6 0 12 0Zm0 16.6a4.7 4.7 0 1 1 0-9.4 4.7 4.7 0 0 1 0 9.4Z");
  svg.append(ruta);
  return svg;
}

/** "NASA / SPACE APPS / • San Vicente Ferrer", como en los pósters del evento. */
function marcaEvento({ compacta = false } = {}) {
  return h("div", { class: `marca-evento ${compacta ? "compacta" : ""}` },
    h("p", { class: "lockup" },
      h("span", { class: "lockup-nasa" }, "NASA"),
      h("span", { class: "lockup-space" }, "Space Apps")),
    h("p", { class: "pin" }, iconoPin(), "San Vicente Ferrer"));
}

/* ---------------------------------------------------------------- identidad del evento */

/** Logo y aliados (público). Si tarda o falla, la página sigue sin ellos. */
async function cargarMarca(api) {
  const espera = new Promise((resolver) => setTimeout(() => resolver(null), 2500));
  try {
    return await Promise.race([api.pedir("/publico/marca"), espera]);
  } catch {
    return null;
  }
}

function logoDeMarca(marca) {
  return marca && marca.logo ? marca.logo.url : null;
}

/* ---------------------------------------------------------------- pantalla de ingreso */

function pantallaIngreso({ titulo, subtitulo, nota, enlace, logo, mensajeInicial, alEntrar }) {
  const errorZona = h("div", { "aria-live": "assertive" });
  const usuario = h("input", { type: "text", id: "usuario", name: "usuario", autocomplete: "username",
    autocapitalize: "none", spellcheck: "false", required: true });
  const contrasena = h("input", { type: "password", id: "contrasena", name: "contrasena",
    autocomplete: "current-password", required: true });
  const verContrasena = h("button", { type: "button", class: "boton discreto pequeno", "aria-pressed": "false",
    onclick: () => {
      const visible = contrasena.type === "password";
      contrasena.type = visible ? "text" : "password";
      verContrasena.textContent = visible ? "Ocultar" : "Mostrar";
      verContrasena.setAttribute("aria-pressed", String(visible));
    } }, "Mostrar");
  const boton = h("button", { class: "boton", type: "submit" }, "Entrar");

  if (mensajeInicial) errorZona.append(h("div", { class: "aviso-error" }, mensajeInicial));

  const formulario = h("form", { novalidate: true,
    onsubmit: async (e) => {
      e.preventDefault();
      vaciar(errorZona);
      if (!usuario.value.trim() || !contrasena.value) {
        errorZona.append(h("div", { class: "aviso-error" }, "Escribe tu usuario y tu contraseña."));
        return;
      }
      boton.disabled = true;
      boton.textContent = "Entrando…";
      try {
        await alEntrar(usuario.value.trim(), contrasena.value);
      } catch (error) {
        errorZona.append(bloqueError(error));
        contrasena.value = "";
        contrasena.focus();
      } finally {
        boton.disabled = false;
        boton.textContent = "Entrar";
      }
    } },
    h("h2", {}, subtitulo),
    errorZona,
    h("div", { class: "campo" }, h("label", { for: "usuario" }, "Usuario"), usuario),
    h("div", { class: "campo" },
      h("div", { class: "fila-etiqueta" }, h("label", { for: "contrasena" }, "Contraseña"), verContrasena),
      contrasena),
    boton,
    nota && h("p", { class: "nota" }, nota),
    enlace && h("p", { class: "nota" }, h("a", { href: enlace.href }, enlace.texto)));

  const arte = h("div", { class: "ingreso-arte" });
  const plantilla = document.getElementById("plantilla-cielo");
  if (plantilla) arte.append(plantilla.content.cloneNode(true));
  arte.append(h("div", { class: "ingreso-marca" },
    logo && h("span", { class: "placa-logo ingreso-logo" }, h("img", { src: logo, alt: "Logo del evento" })),
    marcaEvento(),
    h("h1", {}, titulo),
    h("p", { class: "eslogan" }, "La próxima frontera, donde tus ideas nos llevarán más lejos."),
    h("p", { class: "fechas" }, "14 y 15 de noviembre de 2026. Organiza Ola Fibonacci.")));

  const pantalla = h("main", { class: "ingreso tema-espacio" }, arte, h("section", { class: "ingreso-formulario" }, formulario));
  setTimeout(() => usuario.focus(), 50);
  return pantalla;
}
