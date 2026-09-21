"""Reporte de metricas en Markdown y curva ROC como imagen.

El spec pide los dos como entregables (§7 "exportadas a un reporte en JSON y
Markdown" y §12 "Reporte de metricas en JSON y Markdown, con matriz de
confusion, curva ROC y umbral elegido"). Hasta ahora solo se escribia el JSON.

Vive en el paquete y no en el notebook a proposito: lo que se verifica con
pruebas en local tiene que ser exactamente lo que se ejecuta en Colab (spec
§5: "el notebook no contiene logica").

La curva ROC se dibuja como SVG escrito a mano, sin matplotlib. Es una
decision deliberada: matplotlib es una dependencia pesada y este paquete lo
tiene que instalar tambien SP2 para servir inferencia en la CPU de un VPS,
donde una figura no pinta nada. El SVG es texto plano, se ve en cualquier
navegador, se incrusta en el Markdown y no anade ni un byte de dependencias.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve

# Criterios de aceptacion del spec §2. Se listan aqui, y no en `Config`,
# porque `Config` parametriza el pipeline y estos son el baremo con el que se
# juzga su resultado. El AUC estaba entre ellos desde el primer dia y hasta
# ahora no se reportaba sobre el conjunto de prueba, que es donde el spec lo
# exige.
CRITERIOS_ACEPTACION = (
    ("Recall (sensibilidad)", "recall", 0.80, 0.85),
    ("Especificidad", "especificidad", 0.70, 0.75),
    ("AUC-ROC", "auc", 0.85, 0.88),
)

EXPLICACION_PASO = {
    "paso_1_especificidad_objetivo":
        "Paso 1: habia umbrales con especificidad >= objetivo (0,75) y el de "
        "mayor recall alcanzo el recall objetivo (0,85).",
    "paso_2_especificidad_minima":
        "Paso 2: con la especificidad objetivo no se alcanzaba el recall "
        "objetivo, asi que la busqueda se relajo hasta la especificidad "
        "minima aceptable (0,70).",
    "paso_3_recall_minimo_con_especificidad_objetivo":
        "Paso 3: no se alcanza el recall objetivo (0,85) por ningun camino, "
        "pero con especificidad >= objetivo (0,75) si se cumple el recall "
        "minimo (0,80). Se toma ese punto, que es el que mas exige a la "
        "especificidad entre los que cumplen ambos minimos.",
    "paso_4_recall_minimo_con_especificidad_minima":
        "Paso 4: con la especificidad objetivo no se llegaba ni al recall "
        "minimo, asi que se relajo hasta la especificidad minima (0,70), "
        "donde si se cumple. En triaje el falso negativo es el error caro: "
        "cumplir el recall minimo pesa mas que conservar especificidad.",
    "paso_5_no_se_alcanza_el_recall_minimo":
        "Paso 5: ningun umbral dentro del piso de especificidad alcanza el "
        "recall minimo (0,80). Se reporta el de mayor recall disponible tal "
        "cual, sin forzar nada: un numero honesto antes que un umbral "
        "maquillado. El modelo necesita mejorar, no otro umbral.",
    "sin_umbral_con_especificidad_minima":
        "Ningun umbral de la curva alcanzaba la especificidad objetivo; se "
        "tomo el de mayor indice de Youden (tpr - fpr).",
}

_ANCHO, _ALTO = 480, 440
_IZQ, _DER, _ARR, _ABA = 72, 28, 44, 64
_MARCAS = (0.0, 0.25, 0.5, 0.75, 1.0)


def _x(fpr: float) -> float:
    return _IZQ + fpr * (_ANCHO - _IZQ - _DER)


def _y(tpr: float) -> float:
    return (_ALTO - _ABA) - tpr * (_ALTO - _ABA - _ARR)


def guardar_curva_roc(y_true, y_score, ruta, umbral: float | None = None,
                      titulo: str = "Curva ROC - conjunto de prueba") -> Path:
    """Guarda la curva ROC como SVG y devuelve la ruta.

    Si se pasa `umbral`, marca ademas el punto de operacion elegido: sin el,
    la figura ensena el potencial del modelo pero no el punto en el que de
    verdad se le va a usar, que es lo que el informe tiene que defender.
    """
    y_true = np.asarray(y_true)
    y_score = np.asarray(y_score)
    fpr, tpr, _ = roc_curve(y_true, y_score)
    auc = float(roc_auc_score(y_true, y_score))

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_ANCHO}" '
        f'height="{_ALTO}" viewBox="0 0 {_ANCHO} {_ALTO}" '
        f'font-family="Segoe UI, Arial, sans-serif">',
        f'<rect width="{_ANCHO}" height="{_ALTO}" fill="#ffffff"/>',
        f'<text x="{_ANCHO / 2:.0f}" y="26" text-anchor="middle" '
        f'font-size="15" fill="#1a1a1a">{escape(titulo)}</text>',
    ]

    for marca in _MARCAS:  # rejilla y marcas de los dos ejes
        px, py = _x(marca), _y(marca)
        partes.append(
            f'<line x1="{px:.1f}" y1="{_ARR}" x2="{px:.1f}" y2="{_y(0):.1f}" '
            f'stroke="#e6e6e6" stroke-width="1"/>')
        partes.append(
            f'<line x1="{_x(0):.1f}" y1="{py:.1f}" x2="{_x(1):.1f}" '
            f'y2="{py:.1f}" stroke="#e6e6e6" stroke-width="1"/>')
        partes.append(
            f'<text x="{px:.1f}" y="{_y(0) + 18:.1f}" text-anchor="middle" '
            f'font-size="11" fill="#555">{marca:.2f}</text>')
        partes.append(
            f'<text x="{_x(0) - 10:.1f}" y="{py + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="#555">{marca:.2f}</text>')

    partes.append(
        f'<line x1="{_x(0):.1f}" y1="{_y(0):.1f}" x2="{_x(1):.1f}" '
        f'y2="{_y(1):.1f}" stroke="#bbbbbb" stroke-width="1" '
        f'stroke-dasharray="5 4"/>')  # azar: la linea que hay que superar

    puntos = " ".join(f"{_x(a):.1f},{_y(b):.1f}" for a, b in zip(fpr, tpr))
    partes.append(
        f'<polyline points="{puntos}" fill="none" stroke="#1f5fa8" '
        f'stroke-width="2.2" stroke-linejoin="round"/>')

    partes.append(
        f'<rect x="{_x(1) - 132:.1f}" y="{_y(0) - 34:.1f}" width="124" '
        f'height="24" fill="#ffffff" stroke="#d0d0d0"/>')
    partes.append(
        f'<text x="{_x(1) - 70:.1f}" y="{_y(0) - 17:.1f}" '
        f'text-anchor="middle" font-size="12" fill="#1f5fa8">'
        f'AUC = {auc:.3f}</text>')

    if umbral is not None:
        predicho = (y_score >= umbral).astype(int)
        positivos = int((y_true == 1).sum())
        negativos = int((y_true == 0).sum())
        punto_tpr = float(((predicho == 1) & (y_true == 1)).sum()) / max(positivos, 1)
        punto_fpr = float(((predicho == 1) & (y_true == 0)).sum()) / max(negativos, 1)
        partes.append(
            f'<circle cx="{_x(punto_fpr):.1f}" cy="{_y(punto_tpr):.1f}" r="5" '
            f'fill="#c0392b" stroke="#ffffff" stroke-width="1.5"/>')
        # La etiqueta se voltea al otro lado del punto cuando este cae en la
        # mitad derecha, para que no se salga del lienzo.
        a_la_derecha = punto_fpr < 0.5
        partes.append(
            f'<text x="{_x(punto_fpr) + (10 if a_la_derecha else -10):.1f}" '
            f'y="{_y(punto_tpr) + 4:.1f}" font-size="11" fill="#c0392b" '
            f'text-anchor="{"start" if a_la_derecha else "end"}">'
            f'umbral {umbral:.3f} '
            f'(recall {punto_tpr:.3f}, espec. {1 - punto_fpr:.3f})</text>')

    partes.append(
        f'<text x="{_ANCHO / 2:.0f}" y="{_ALTO - 12}" text-anchor="middle" '
        f'font-size="12" fill="#333">Tasa de falsos positivos '
        f'(1 - especificidad)</text>')
    partes.append(
        f'<text x="16" y="{_ALTO / 2:.0f}" font-size="12" fill="#333" '
        f'transform="rotate(-90 16 {_ALTO / 2:.0f})" text-anchor="middle">'
        f'Recall (sensibilidad)</text>')
    partes.append("</svg>")

    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(partes), encoding="utf-8")
    return ruta


def _numero(valor, decimales: int = 3) -> str:
    return "n/d" if valor is None else f"{valor:.{decimales}f}"


def _fila_criterio(nombre: str, valor, minimo: float, objetivo: float) -> str:
    if valor is None:
        veredicto = "NO REPORTADO"
    elif valor >= objetivo:
        veredicto = "cumple el objetivo"
    elif valor >= minimo:
        veredicto = "cumple el minimo"
    else:
        veredicto = "**NO CUMPLE**"
    return (f"| {nombre} | {minimo:.2f} | {objetivo:.2f} | "
            f"{_numero(valor)} | {veredicto} |")


def escribir_reporte_markdown(
    ruta,
    *,
    umbral: float,
    paso: str,
    metricas_validacion: dict,
    metricas_prueba: dict,
    historial=(),
    mejor_epoca: int | None = None,
    ruta_roc=None,
    omitidos=None,
) -> Path:
    """Escribe el reporte legible y devuelve la ruta.

    Contiene lo que pide el spec §12: metricas, matriz de confusion, umbral
    elegido y la regla con la que se eligio, mas la curva ROC enlazada, el
    veredicto frente a los cuatro criterios de aceptacion de §2 y el recuento
    de archivos omitidos que exige §8.

    `ruta_roc` se enlaza de forma relativa al propio reporte, para que los dos
    archivos se puedan mover juntos.
    """
    ruta = Path(ruta)
    prueba = dict(metricas_prueba)
    validacion = dict(metricas_validacion)

    lineas = [
        "# Reporte de metricas - SP1 nucleo de imagen",
        "",
        f"Generado el {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC.",
        "",
        "## Umbral de decision",
        "",
        f"- Umbral elegido sobre la curva ROC de **validacion**: `{umbral:.4f}`",
        f"- Regla aplicada: `{paso}`",
        f"- {EXPLICACION_PASO.get(paso, 'Regla no reconocida.')}",
        "- El umbral se congelo ANTES de tocar el conjunto de prueba, que se "
        "evaluo una sola vez. Cualquier reevaluacion posterior sobre ese mismo "
        "conjunto invalidaria estas metricas y tendria que declararse aqui.",
        "",
        "## Criterios de aceptacion (spec §2), sobre el conjunto de PRUEBA",
        "",
        "| Criterio | Minimo | Objetivo | Obtenido | Veredicto |",
        "| :--- | ---: | ---: | ---: | :--- |",
    ]
    for nombre, clave, minimo, objetivo in CRITERIOS_ACEPTACION:
        lineas.append(_fila_criterio(nombre, prueba.get(clave), minimo, objetivo))

    lineas += [
        "",
        "## Metricas",
        "",
        "| Metrica | Validacion | Prueba |",
        "| :--- | ---: | ---: |",
    ]
    for etiqueta, clave in (("Recall", "recall"), ("Especificidad", "especificidad"),
                            ("Precision", "precision"), ("F1", "f1"),
                            ("AUC-ROC", "auc")):
        lineas.append(f"| {etiqueta} | {_numero(validacion.get(clave))} | "
                      f"{_numero(prueba.get(clave))} |")

    lineas += [
        "",
        "## Matriz de confusion (conjunto de prueba)",
        "",
        "| | Predicho negativo | Predicho positivo |",
        "| :--- | ---: | ---: |",
        f"| **Real negativo** | {prueba.get('tn', 'n/d')} | {prueba.get('fp', 'n/d')} |",
        f"| **Real positivo** | {prueba.get('fn', 'n/d')} | {prueba.get('tp', 'n/d')} |",
        "",
        f"Falsos negativos: **{prueba.get('fn', 'n/d')}**. Es el error que mas "
        "cuesta en triaje (un paciente enfermo despriorizado) y por eso la "
        "metrica primaria del proyecto es el Recall.",
    ]

    if ruta_roc is not None:
        ruta_roc = Path(ruta_roc)
        try:
            enlace = ruta_roc.relative_to(ruta.parent).as_posix()
        except ValueError:
            enlace = ruta_roc.as_posix()
        lineas += ["", "## Curva ROC", "", f"![Curva ROC]({enlace})"]

    if omitidos is not None:
        cantidad = len(omitidos) if hasattr(omitidos, "__len__") else int(omitidos)
        lineas += ["", "## Archivos omitidos en la conversion (spec §8)", "",
                   f"Se omitieron **{cantidad}** archivo(s) por ser ilegibles."]
        motivos = {}
        if hasattr(omitidos, "__iter__") and not isinstance(omitidos, (str, bytes)):
            for registro in omitidos:
                if isinstance(registro, dict):
                    clave = str(registro.get("motivo", "")).split(":")[0]
                    motivos[clave] = motivos.get(clave, 0) + 1
        for motivo, cuenta in sorted(motivos.items()):
            lineas.append(f"- `{motivo}`: {cuenta}")

    if historial:
        lineas += [
            "",
            "## Historial de entrenamiento",
            "",
            "`Recall` y `Especificidad` son los del umbral elegido en esa "
            "epoca, que es el criterio con el que se selecciono la mejor. Las "
            "dos ultimas columnas son el mismo par medido en un 0,5 fijo, solo "
            "como diagnostico: con `pos_weight` compensando el desbalance, el "
            "modelo se sienta encima de ese 0,5 y ahi la metrica satura sin "
            "decir nada del modelo.",
            "",
            "| Epoca | Fase | Perdida | Recall | Especificidad | AUC | Umbral | "
            "Recall@0,5 | Espec.@0,5 |",
            "| ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for registro in historial:
            marca = " **<- mejor**" if registro.get("epoca") == mejor_epoca else ""
            lineas.append(
                f"| {registro.get('epoca')}{marca} | {registro.get('fase')} | "
                f"{_numero(registro.get('perdida'), 4)} | "
                f"{_numero(registro.get('recall'))} | "
                f"{_numero(registro.get('especificidad'))} | "
                f"{_numero(registro.get('auc'))} | "
                f"{_numero(registro.get('umbral'), 4)} | "
                f"{_numero(registro.get('recall_umbral_fijo'))} | "
                f"{_numero(registro.get('especificidad_umbral_fijo'))} |")

    lineas.append("")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(lineas), encoding="utf-8")
    return ruta
