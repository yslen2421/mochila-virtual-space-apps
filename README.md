# Mochila virtual — NASA Space Apps Challenge San Vicente Ferrer

Portal privado de participantes de la sede San Vicente Ferrer, organizada por **Ola Fibonacci**.
Cada participante (presencial o virtual) entra con usuario y contraseña y encuentra la misma
mochila: cronograma con enlaces de conexión, recursos de los retos, guía de AWS, wallpapers,
souvenirs y lo que la organización agregue. El equipo organizador lo administra todo desde un
panel, sin tocar código.

- **Portal de participantes:** `https://tu-dominio/`
- **Panel de organización (Superadmin):** `https://tu-dominio/admin/`

---

## 1. Ponerlo a andar

### Opción A — En tu computador (para probar)

Necesitas Python 3.11 o superior.

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env          # edita SUPERADMIN_USUARIO y SUPERADMIN_CONTRASENA
flask --app wsgi inicializar     # crea el Superadmin y las 10 secciones base
python wsgi.py                   # abre http://localhost:5000
```

### Opción B — En un servidor (para el evento)

Lo más sencillo es un servidor pequeño en la nube (DigitalOcean, Hetzner, AWS Lightsail…,
1 CPU y 1 GB de RAM alcanzan; ~US$6–12 al mes) con Docker instalado y un dominio o
subdominio apuntando a su IP (por ejemplo `mochila.olafibonacci.org`).

```bash
git clone <este repositorio> && cd portal-spaceapps
cp .env.example .env             # pon tu DOMINIO, SECRET_KEY y el Superadmin
docker compose up -d --build
```

Listo: Caddy saca el certificado HTTPS solo, y el portal queda en `https://tu-dominio/`.
Todo lo que importa (base de datos, archivos subidos, respaldos) vive en la carpeta `datos/`.

> No uses servicios "serverless" o sin disco persistente (Vercel, Netlify Functions, Render
> gratuito…): la base de datos es un archivo y se perdería en cada reinicio.

---

## 2. Operación del evento

### Antes del evento

1. **Entra al panel** (`/admin/`) con el Superadmin del `.env` y cambia esa contraseña.
2. **Llena la mochila.** Las 10 secciones base ya existen con contenido de ejemplo. Revisa
   y reemplaza: fechas y enlaces del **Cronograma**, el paso a paso de **AWS**, etc. Para
   wallpapers y souvenirs usa **Subir varios archivos**: cada archivo se vuelve un ítem.
   Lo que no esté listo, desmárcalo como visible.
3. **Carga a los participantes.** En *Participantes → Importar lista*, sube el CSV de
   inscritos exportado de Excel o Google Sheets. Columnas: `nombre` (obligatoria),
   `usuario`, `email`, `modalidad` (`presencial` o `virtual`). Si no hay usuario, se arma
   uno con nombre y primer apellido (`juan.zapata`).
4. **Descarga el CSV de credenciales** que aparece al terminar (las contraseñas no se
   vuelven a mostrar) y envíaselas a cada persona. Para una sola persona, el panel arma
   el mensaje de WhatsApp listo para copiar.

### Durante el evento

- **"Lo próximo"** aparece arriba del portal: la actividad en curso o la siguiente, con el
  botón para entrar a la transmisión. Se actualiza solo cada minuto.
- **¿Alguien olvidó la contraseña?** Búscalo en *Participantes → Nueva contraseña*. Su
  sesión anterior se cierra.
- **¿Una cuenta no debería entrar?** *Desactivar* la saca de inmediato.
- **Anuncios:** agrega un ítem de texto en la sección Anuncios; se ve al instante.
- **Estadísticas:** cuántas personas ya entraron, qué secciones visitan y qué descargan.

### Respaldos

```bash
docker compose exec app flask --app wsgi respaldar      # con Docker
flask --app wsgi respaldar                               # sin Docker (desde backend/)
```

Guarda copias en `datos/respaldos/` (conserva las últimas 30). Hazlo antes del evento y
cada noche durante el hackathon. Para programarlo cada hora en el servidor:
`crontab -e` → `0 * * * * cd /ruta/portal-spaceapps && docker compose exec -T app flask --app wsgi respaldar`.

---

## 3. Capacidad: 150 personas a la vez

Prueba de carga incluida (`backend/pruebas_carga.py`), hecha en una máquina de **2 núcleos**
con Gunicorn (3 procesos × 8 hilos). Cada persona entra, abre la mochila, las 10 secciones
y las miniaturas de los wallpapers, tres veces seguidas.

| Escenario | Peticiones | Errores | Login (mediana / p95) | Resto (mediana / p95) |
|---|---|---|---|---|
| 150 personas entrando en 30 s (realista) | 7 350 | 0 | 124 / 284 ms | 1–2 / 5–7 ms |
| 150 personas entrando en el mismo milisegundo (peor caso) | 4 950 | 0 | 4,7 / 7,9 s | 75–126 ms / hasta 5 s |

El único punto que se resiente es el login simultáneo: la contraseña se verifica con
**scrypt**, que es lento a propósito para que nadie pueda adivinar claves a la fuerza. En la
práctica la gente entra a lo largo de varios minutos y la sesión dura 24 horas, así que cada
persona hace login una vez al día.

Lo que hace que aguante:

- **SQLite en modo WAL**: las lecturas (casi todo el tráfico) no se bloquean entre sí.
- **Miniaturas WebP** generadas solas: un wallpaper 4K de 5 MB se previsualiza con ~60 KB,
  clave para el wifi de la sede. El original solo se baja si la persona lo pide.
- **Archivos estáticos con caché** y compresión (gzip/zstd) en Caddy.
- **Tipografías alojadas en el propio servidor**: el portal no depende de servicios externos.

Para repetir la prueba (usa una base de datos de prueba: crea cuentas `carga1…carga150`):

```bash
python backend/pruebas_carga.py --url http://localhost:5000 --clave CLAVE_ADMIN --usuarios 150 --rampa 30
```

---

## 4. Seguridad

- Contraseñas guardadas con **scrypt** (nunca en texto plano). Mínimo 8 caracteres.
- Sesión con **JWT firmado** (24 h). Cada usuario tiene una versión de sesión: restablecer
  la contraseña, cambiarla o desactivar la cuenta **cierra todas sus sesiones al instante**.
- **Límite de intentos:** 8 fallos por usuario o 60 por IP en 15 minutos (alto por IP porque
  en la sede todos comparten el wifi). El mensaje de error no revela si el usuario existe.
- **Archivos privados:** solo se descargan con sesión, y un participante solo puede bajar
  archivos de ítems y secciones visibles. Se guardan con nombre aleatorio; el tipo se decide
  por la extensión (lista blanca) y se sirven con una política que impide ejecutarlos.
- **Sin inyección de HTML:** el front inserta todo como texto; los enlaces solo aceptan
  `http(s)://`. Política de seguridad de contenido (CSP) estricta: sin scripts externos.
- HTTPS obligatorio en producción (Caddy) con HSTS.

---

## 5. Arquitectura

```
portal-spaceapps/
├── backend/                     Python + Flask, responde solo JSON
│   ├── app/
│   │   ├── domain/              Entidades, reglas de negocio y puertos (interfaces)
│   │   ├── application/         Casos de uso: autenticación, mochila, contenido, usuarios…
│   │   ├── infrastructure/      SQLite, disco local, JWT, scrypt
│   │   ├── presentation/        Controladores REST, validación de entrada, errores JSON
│   │   ├── contenedor.py        Arma todas las piezas (único lugar con clases concretas)
│   │   └── cli.py               inicializar, crear-superadmin, respaldar, limpiar-archivos
│   ├── tests/                   pytest (el dominio se prueba sin servidor ni base de datos)
│   ├── gunicorn.conf.py
│   └── pruebas_carga.py
├── frontend/                    HTML + CSS + JS sin frameworks, consume la API asíncronamente
│   ├── index.html               Portal de participantes
│   ├── admin/index.html         Panel de organización
│   └── assets/                  css/, js/, fonts/ (Bricolage Grotesque y Atkinson Hyperlegible)
├── deploy/                      Caddyfile y script de arranque
├── Dockerfile
└── docker-compose.yml
```

Las capas dependen solo hacia adentro: `presentation → application → domain ← infrastructure`.
El dominio no importa Flask ni SQLite, así que se puede:

- **Pasar de SQLite a PostgreSQL** escribiendo nuevos repositorios en `infrastructure/` y
  cambiando una línea en `contenedor.py`.
- **Guardar archivos en S3** con otra clase que cumpla el puerto `AlmacenArchivos`.
- **Agregar un tipo de ítem** (por ejemplo "video embebido") sumando una regla en
  `domain/reglas.py` y su presentación en el front.

### Flujo del participante

```
Login ──► Inicio: saludo + "Lo próximo" + faja de insignias (secciones visibles)
             │
             └─► Sección: texto, enlaces, archivos, galería de imágenes o cronograma
                   ├─ Descargar archivo (con barra de progreso)
                   └─ Ver imagen en grande / descargar original
Menú (nombre): cambiar contraseña · cerrar sesión
```

### API (JSON, prefijo `/api/v1`)

Todas las respuestas de error tienen la misma forma:

```json
{ "error": { "codigo": "NO_AUTENTICADO", "mensaje": "Usuario o contraseña incorrectos.", "detalle": null } }
```

| Método | Ruta | Quién | Qué hace |
|---|---|---|---|
| POST | `/auth/login` | todos | `{usuario, contrasena}` → `{token, usuario}` |
| GET | `/auth/yo` | sesión | Datos del usuario actual |
| POST | `/auth/cambiar-contrasena` | sesión | `{actual, nueva}` → token nuevo |
| GET | `/mochila` | sesión | Secciones visibles con cuántos ítems tienen |
| GET | `/mochila/proximos` | sesión | Actividades en curso o siguientes del cronograma |
| GET | `/mochila/secciones/{id}` | sesión | Sección con sus ítems visibles |
| GET | `/archivos/{id}` | sesión | Archivo (`?descargar=1`, `?miniatura=1`) |
| GET, POST | `/admin/secciones` | superadmin | Listar / crear secciones |
| PUT | `/admin/secciones/orden` | superadmin | `{ids: [...]}` nuevo orden |
| GET, PUT, DELETE | `/admin/secciones/{id}` | superadmin | Ver con ítems / editar / borrar |
| GET, POST | `/admin/secciones/{id}/items` | superadmin | Listar / crear ítems |
| PUT | `/admin/secciones/{id}/items/orden` | superadmin | Reordenar ítems |
| PUT, DELETE | `/admin/items/{id}` | superadmin | Editar / borrar ítem |
| POST | `/admin/archivos` | superadmin | Subir archivo (multipart, campo `archivo`) |
| GET, POST | `/admin/usuarios` | superadmin | Listar / crear (devuelve la contraseña generada una vez) |
| POST | `/admin/usuarios/importar` | superadmin | `{usuarios: [...]}`; todo o nada |
| PUT, DELETE | `/admin/usuarios/{id}` | superadmin | Editar, activar/desactivar / borrar |
| POST | `/admin/usuarios/{id}/restablecer-contrasena` | superadmin | Nueva contraseña |
| GET | `/admin/estadisticas` | superadmin | Ingresos, visitas por sección, descargas |
| GET | `/salud` | todos | Para monitoreo |

Tipos de ítem: `texto`, `enlace`, `archivo`, `imagen`, `evento` (fecha, hora de inicio y
fin, lugar y enlace de conexión).

### Frontend y API en dominios distintos

Por defecto Flask sirve también el front (más simple de mantener). Si prefieres alojar
`frontend/` aparte (por ejemplo en GitHub Pages), cambia `apiBase` en
`frontend/assets/js/config.js` y pon el dominio del front en `CORS_ORIGINS`.

---

## 6. Pruebas

```bash
cd backend
python -m pytest            # 15 pruebas: dominio, permisos, flujo completo, sesiones
```

## 7. Ideas para después

Personalizar la mochila por equipo o modalidad, un rol "Editor de contenido", contador de
descargas por persona, insignias por completar secciones. La estructura por capas permite
agregarlas sin tocar lo existente.
