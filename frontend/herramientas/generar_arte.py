"""Genera el arte SVG del portal (cielo, planeta, cordillera y espiral de Fibonacci).

Uso:  python frontend/herramientas/generar_arte.py
Escribe:
  - frontend/assets/img/cielo.svg       (escena completa, referencia)
  - frontend/assets/img/estrellas.svg   (mosaico de estrellas para fondos)
  - frontend/assets/img/cordillera.svg  (silueta de montañas para el borde de bandas)
  - e inserta la escena en <template id="plantilla-cielo"> de index.html y admin/index.html
"""
import math
import random
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
IMG = RAIZ / "assets" / "img"
PHI = (1 + 5 ** 0.5) / 2

# Paleta (igual que en base.css)
COSMOS = "#0e0a24"
NEBULOSA = "#1a1442"
VIOLETA_1 = "#2a1d63"
VIOLETA_2 = "#3d2a8c"
VIOLETA_3 = "#5b34c4"
MARTE = "#d4302a"
POLVO = "#f08a5d"
LAVANDA = "#b9a6ff"


def f(n: float) -> str:
    return f"{n:.0f}"


def estrellas(ancho, alto, cantidad, semilla, alto_max=None):
    rnd = random.Random(semilla)
    alto_max = alto_max or alto
    partes = []
    for _ in range(cantidad):
        x, y = rnd.uniform(0, ancho), rnd.uniform(0, alto_max) ** 1.08 / alto_max ** 0.08
        r = rnd.choice([0.7, 0.7, 0.9, 1.1, 1.4, 1.9])
        op = rnd.uniform(0.35, 1)
        partes.append(f'<circle cx="{f(x)}" cy="{f(y)}" r="{r}" opacity="{op:.2f}"/>')
    # unas pocas estrellas con destello en cruz
    for _ in range(max(2, cantidad // 60)):
        x, y = rnd.uniform(0, ancho), rnd.uniform(0, alto_max * 0.7)
        s = rnd.uniform(5, 9)
        partes.append(
            f'<path d="M{f(x)} {f(y - s)}Q{f(x)} {f(y)} {f(x + s)} {f(y)}Q{f(x)} {f(y)} {f(x)} {f(y + s)}'
            f'Q{f(x)} {f(y)} {f(x - s)} {f(y)}Q{f(x)} {f(y)} {f(x)} {f(y - s)}Z"/>')
    return f'<g fill="#fff">{"".join(partes)}</g>'


def cordillera(ancho, base, amplitud, crestas, semilla, color, desfase=0.0):
    """Montañas onduladas suaves (curvas cúbicas), como las de los pósters."""
    rnd = random.Random(semilla)
    puntos = []
    paso = ancho / crestas
    for i in range(crestas + 2):
        x = i * paso - paso * desfase
        alto = amplitud * (0.55 + 0.45 * rnd.random())
        y = base - alto if i % 2 == 0 else base - alto * rnd.uniform(0.15, 0.45)
        puntos.append((x, y))
    d = f"M{f(puntos[0][0])} {f(puntos[0][1])}"
    for (x0, y0), (x1, y1) in zip(puntos, puntos[1:]):
        cx = (x1 - x0) / 2
        d += f"C{f(x0 + cx)} {f(y0)} {f(x1 - cx)} {f(y1)} {f(x1)} {f(y1)}"
    d += f"L{f(ancho + paso)} 2000L{f(-paso)} 2000Z"
    return f'<path d="{d}" fill="{color}"/>'


def espiral(centro, destino, vueltas):
    """Espiral áurea que nace en `centro` y termina exactamente en `destino`."""
    crudos = []
    n = 500
    for i in range(n + 1):
        t = vueltas * 2 * math.pi * i / n
        r = PHI ** (2 * t / math.pi)
        crudos.append((r * math.cos(t), -r * math.sin(t)))
    ex, ey = crudos[-1]
    dx, dy = destino[0] - centro[0], destino[1] - centro[1]
    escala = math.hypot(dx, dy) / math.hypot(ex, ey)
    giro = math.atan2(dy, dx) - math.atan2(ey, ex)
    c, s_ = math.cos(giro), math.sin(giro)
    puntos = [(centro[0] + escala * (x * c - y * s_), centro[1] + escala * (x * s_ + y * c)) for x, y in crudos]
    return "M" + "L".join(f"{f(x)} {f(y)}" for x, y in puntos), puntos


def escena():
    W, H = 1600, 1000
    planeta = (1000, 290)
    # la espiral termina en el borde del planeta: "donde tus ideas nos llevarán más lejos"
    d_espiral, pts = espiral((860, 540), (planeta[0] - 74, planeta[1] + 54), 2.25)
    p1, p2 = pts[250], pts[390]
    capas = [
        f'<rect width="{W}" height="{H}" fill="url(#cielo-degradado)"/>',
        estrellas(W, H, 260, 7, alto_max=760),
        # planeta rojo con su terminador
        f'<g transform="translate({planeta[0]} {planeta[1]})">'
        f'<circle r="92" fill="url(#planeta-degradado)"/>'
        '<circle cx="-26" cy="-18" r="13" fill="#000" opacity=".12"/>'
        '<circle cx="30" cy="22" r="8" fill="#000" opacity=".1"/>'
        '<circle cx="8" cy="-46" r="6" fill="#000" opacity=".1"/>'
        '<circle r="92" fill="url(#planeta-sombra)"/>'
        '</g>',
        # órbita: espiral de Fibonacci (Ola Fibonacci) que se dibuja al cargar
        f'<g class="orbita" mask="url(#orbita-mascara)"><path class="orbita-trazo" d="{d_espiral}"/></g>',
        f'<circle class="astro" cx="{f(p1[0])}" cy="{f(p1[1])}" r="4"/>',
        f'<circle class="astro frio" cx="{f(p2[0])}" cy="{f(p2[1])}" r="6"/>',
        # cordillera en capas, de la más lejana a la más cercana
        cordillera(W, 840, 190, 7, 3, VIOLETA_1),
        cordillera(W, 900, 150, 9, 11, VIOLETA_2, 0.4),
        cordillera(W, 960, 110, 11, 21, VIOLETA_3, 0.7),
        cordillera(W, 1000, 60, 13, 5, COSMOS, 0.2),
    ]
    defs = (
        "<defs>"
        f'<mask id="orbita-mascara"><path class="orbita-revela" d="{d_espiral}" fill="none" stroke="#fff" stroke-width="12"/></mask>'
        '<linearGradient id="cielo-degradado" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{COSMOS}"/><stop offset=".55" stop-color="{NEBULOSA}"/>'
        '<stop offset="1" stop-color="#3a1f6e"/></linearGradient>'
        '<radialGradient id="planeta-degradado" cx=".35" cy=".35" r=".8">'
        f'<stop offset="0" stop-color="{POLVO}"/><stop offset=".55" stop-color="{MARTE}"/>'
        '<stop offset="1" stop-color="#7a1712"/></radialGradient>'
        '<linearGradient id="planeta-sombra" x1=".2" y1=".15" x2=".95" y2=".9">'
        '<stop offset=".45" stop-color="#0e0a24" stop-opacity="0"/>'
        '<stop offset="1" stop-color="#0e0a24" stop-opacity=".7"/></linearGradient>'
        "</defs>"
    )
    return (f'<svg class="cielo" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" '
            f'aria-hidden="true" focusable="false">{defs}{"".join(capas)}</svg>')


def mosaico_estrellas():
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" width="600" height="600">'
            f'{estrellas(600, 600, 70, 42)}</svg>')


def silueta_cordillera():
    W = 1600
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} 200" preserveAspectRatio="none">'
            f'<g transform="translate(0 -800)">'
            f'{cordillera(W, 880, 70, 9, 3, VIOLETA_1)}'
            f'{cordillera(W, 930, 60, 11, 11, VIOLETA_2, 0.4)}'
            f'{cordillera(W, 975, 45, 13, 21, VIOLETA_3, 0.7)}'
            f'{cordillera(W, 1000, 25, 15, 5, COSMOS, 0.2)}'
            '</g></svg>')


def main():
    svg = escena()
    estilo = ('<style>.orbita-trazo{fill:none;stroke:#b9a6ff;stroke-width:2.4;stroke-dasharray:8 7;'
              'stroke-linecap:round;opacity:.9}.astro{fill:#fff}.astro.frio{fill:#b9a6ff}</style>')
    (IMG / "cielo.svg").write_text(
        svg.replace('<svg class="cielo"', '<svg xmlns="http://www.w3.org/2000/svg"').replace("<defs>", estilo + "<defs>", 1),
        encoding="utf-8")
    (IMG / "estrellas.svg").write_text(mosaico_estrellas(), encoding="utf-8")
    (IMG / "cordillera.svg").write_text(silueta_cordillera(), encoding="utf-8")
    for html in (RAIZ / "index.html", RAIZ / "admin" / "index.html"):
        texto = html.read_text(encoding="utf-8")
        nuevo = re.sub(r'<template id="plantilla-[a-z]+">.*?</template>',
                       f'<template id="plantilla-cielo">\n{svg}\n  </template>', texto, flags=re.S)
        html.write_text(nuevo, encoding="utf-8")
    print("Arte generado:", len(svg), "bytes de escena")


if __name__ == "__main__":
    main()
