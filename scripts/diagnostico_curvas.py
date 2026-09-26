# -*- coding: utf-8 -*-
"""Diagnostico de sobreajuste a partir del historial que deja cada corrida.

QUE HACE, Y POR QUE ESTA AQUI Y NO EN `src/`
--------------------------------------------
`entrenar()` escribe un registro por epoca en `reporte_metricas.json`. Este
modulo lo lee, lo diagnostica y lo dibuja. Vive en `scripts/` y no en `src/`
porque necesita matplotlib, y `src/` es lo unico que el Dockerfile copia a la
imagen que se sirve: meter una libreria de graficos en el contenedor de
inferencia seria pagar 40 MB en cada despliegue por algo que solo se usa fuera.

LAS TRES PERDIDAS, Y CUAL SE COMPARA CON CUAL
---------------------------------------------
Cada epoca trae tres numeros de perdida, y confundirlos es el error que este
modulo existe para no cometer:

  `perdida`        la de la pasada de entrenamiento: promedio MIENTRAS los
                   pesos cambiaban, y sobre imagenes AUMENTADAS (RandomAffine
                   y ColorJitter). Es mas alta de lo que el modelo "sabe".
  `perdida_train`  el MISMO conjunto de entrenamiento medido limpio y con el
                   modelo ya quieto al cerrar la epoca.
  `perdida_val`    validacion, limpia y con el modelo quieto.

**La brecha se mide con `perdida_train` contra `perdida_val`.** Usar `perdida`
en su lugar la subestima -medido aqui: entre 0,10 y 0,15 en la ultima epoca- y
en las primeras epocas puede hasta invertirla, dejando la curva de
entrenamiento POR ENCIMA de la de validacion. Leido de un vistazo eso parece
underfitting, y es la aumentacion.

Las tres salen del mismo criterio, `BCEWithLogitsLoss(pos_weight)`, y eso es lo
que las hace comparables: con un criterio sin peso, la de validacion sale en
otra escala y la distancia entre curvas no mide nada.

USO
---
    python scripts/diagnostico_curvas.py <dir-de-corridas> --figuras <dir>

`<dir-de-corridas>` es una carpeta con una subcarpeta por corrida, cada una con
su `reporte_metricas.json`. Sin `--figuras` solo imprime el diagnostico.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

# Los umbrales del diagnostico. Se declaran aqui, con su razon, y no se
# esconden dentro de un `if`: el veredicto es una afirmacion sobre el modelo y
# quien lo lea tiene que poder discutir el criterio.
#
# SUBIDA_SOBREAJUSTE: cuanto tiene que subir la perdida de validacion desde su
#   minimo para llamarlo sobreajuste y no ruido. El 5 % deja fuera el temblor
#   normal entre epocas y entra en cuanto la tendencia se invierte de verdad.
# BRECHA_ALTA: brecha de AUC entre entrenamiento y validacion que ya no se
#   explica por la dificultad del conjunto.
# PERDIDA_ALTA_AMBAS: por encima de esto las dos curvas juntas es underfitting;
#   es el orden de magnitud de la perdida de una salida constante con el
#   `pos_weight` del desbalance. No se cita aqui un valor concreto a proposito:
#   cada corrida lo calcula sobre SU particion de entrenamiento, y el 3,44 que
#   decia antes esta linea sale del 22,5 % de positivos de RSNA ENTERO, que ya
#   no es el conjunto con el que se entrena -tras descartar los 1 276 menores y
#   los 5 de edad imposible, los positivos son el 22,15 % y el peso ronda 3,5-.
SUBIDA_SOBREAJUSTE = 0.05
BRECHA_ALTA = 0.08
PERDIDA_ALTA_AMBAS = 0.80


def cargar(ruta: Path) -> dict:
    """Un `reporte_metricas.json`, con su nombre de corrida."""
    d = json.loads(Path(ruta).read_text(encoding="utf-8"))
    d["nombre"] = Path(ruta).parent.name
    return d


def cargar_directorio(raiz: Path) -> list[dict]:
    """Todas las corridas de una carpeta, ordenadas por nombre.

    Se salta las que no traen `perdida_val`: son de antes de que el bucle la
    midiera, y mezclarlas daria una comparativa con la mitad de las curvas
    vacias sin decir por que.
    """
    corridas, sin_val = [], []
    for ruta in sorted(Path(raiz).glob("*/reporte_metricas.json")):
        d = cargar(ruta)
        if d.get("historial") and "perdida_val" in d["historial"][0]:
            corridas.append(d)
        else:
            sin_val.append(d["nombre"])
    if sin_val:
        print(f"  (se saltan {len(sin_val)} corrida(s) sin perdida de "
              f"validacion: {', '.join(sin_val)})")
    return corridas


def _brecha(r: dict) -> float | None:
    """Perdida de validacion menos la de entrenamiento LIMPIA."""
    if r.get("perdida_train") is None:
        return None
    return r["perdida_val"] - r["perdida_train"]


def diagnosticar(historial: list[dict]) -> dict:
    """Overfitting, underfitting o comportamiento optimo, con sus cifras.

    El criterio no es una impresion de la grafica: es la epoca del minimo de la
    perdida de validacion. Antes de esa epoca el modelo aprende; despues,
    memoriza. Todo lo demas -la brecha de AUC, la subida de la perdida- son
    consecuencias que se miden para poder discutir el veredicto.
    """
    minimo = min(historial, key=lambda r: r["perdida_val"])
    ultimo = historial[-1]
    subida = ultimo["perdida_val"] / minimo["perdida_val"] - 1

    brecha_auc = None
    if ultimo.get("auc_train") is not None:
        brecha_auc = ultimo["auc_train"] - ultimo["auc"]

    # La primera epoca en la que la perdida de validacion ya no vuelve a bajar
    # del minimo: es donde empieza a memorizar, no donde se nota.
    desde = None
    for r in historial:
        if r["epoca"] > minimo["epoca"] and \
                r["perdida_val"] > minimo["perdida_val"] * (1 + SUBIDA_SOBREAJUSTE):
            desde = r["epoca"]
            break

    if subida > SUBIDA_SOBREAJUSTE or (brecha_auc or 0) > BRECHA_ALTA:
        veredicto = "sobreajuste"
    elif minimo["perdida_val"] > PERDIDA_ALTA_AMBAS and \
            (minimo.get("perdida_train") or 0) > PERDIDA_ALTA_AMBAS:
        veredicto = "subajuste"
    else:
        veredicto = "optimo"

    mejor_auc = max(historial, key=lambda r: r["auc"])
    return {
        "veredicto": veredicto,
        "epoca_minimo_val": minimo["epoca"],
        "perdida_val_minima": minimo["perdida_val"],
        "perdida_val_final": ultimo["perdida_val"],
        "subida_desde_el_minimo": subida,
        "sobreajuste_desde_la_epoca": desde,
        "epoca_mejor_auc": mejor_auc["epoca"],
        "auc_val_maximo": mejor_auc["auc"],
        "auc_val_final": ultimo["auc"],
        "auc_train_final": ultimo.get("auc_train"),
        "brecha_auc_final": brecha_auc,
        "brecha_perdida_minima": _brecha(minimo),
        "brecha_perdida_final": _brecha(ultimo),
        "epocas": len(historial),
        # Cuanto mide la aumentacion: la pasada aumentada contra la limpia, en
        # la ultima epoca. Es la presion regularizadora que ya se esta
        # aplicando, y sin este numero "usar data augmentation" seria una
        # recomendacion a ciegas sobre algo que ya esta puesto.
        "efecto_aumentacion": (
            ultimo["perdida"] - ultimo["perdida_train"]
            if ultimo.get("perdida_train") is not None else None),
    }


def imprimir(corrida: dict) -> dict:
    d = diagnosticar(corrida["historial"])
    print(f"\n{corrida['nombre']}")
    print(f"  veredicto .................. {d['veredicto'].upper()}")
    print(f"  epocas ..................... {d['epocas']}")
    print(f"  minimo de perdida_val ...... {d['perdida_val_minima']:.4f}"
          f" en la epoca {d['epoca_minimo_val']}")
    print(f"  perdida_val final .......... {d['perdida_val_final']:.4f}"
          f"  ({d['subida_desde_el_minimo']:+.1%})")
    if d["sobreajuste_desde_la_epoca"] is not None:
        print(f"  memoriza desde la epoca .... {d['sobreajuste_desde_la_epoca']}")
    if d["brecha_auc_final"] is not None:
        print(f"  AUC train / val finales .... {d['auc_train_final']:.4f}"
              f" / {d['auc_val_final']:.4f}"
              f"  (brecha {d['brecha_auc_final']:.4f})")
    if d["brecha_perdida_final"] is not None:
        print(f"  brecha de perdida .......... {d['brecha_perdida_minima']:.4f}"
              f" en el minimo -> {d['brecha_perdida_final']:.4f} al final")
    if d["efecto_aumentacion"] is not None:
        print(f"  efecto de la aumentacion ... {d['efecto_aumentacion']:.4f}"
              f" de perdida")
    return d


# ---------------------------------------------------------------------------
# ESTRATEGIAS DE MEJORA, EVALUADAS SOBRE EL HISTORIAL GRABADO
#
# No se puede reentrenar para probar cada idea: cada corrida son horas de GPU.
# Pero las politicas de PARADA no hacen falta reentrenarlas, porque no cambian
# el entrenamiento: solo eligen en que epoca cortar y con que pesos quedarse. Y
# eso se reproduce EXACTAMENTE sobre el historial que ya esta grabado.
#
# Lo que esto NO puede evaluar, y hay que decirlo: cualquier cosa que cambie los
# gradientes -mas dropout, mas weight decay, otra aumentacion- produce OTRO
# historial, y simularla sobre este seria inventarselo. Para esas, el modulo
# calcula lo que se espera y lo etiqueta como prediccion, no como medida.
# ---------------------------------------------------------------------------
CRITERIOS = {
    "recall+auc": (
        "el del proyecto: mejor recall en validacion, con el AUC de desempate",
        lambda r: (r["recall"], r["auc"])),
    "auc": (
        "solo AUC en validacion",
        lambda r: (r["auc"],)),
    "perdida_val": (
        "menor perdida de validacion, que es la senal del sobreajuste",
        lambda r: (-r["perdida_val"],)),
}


def simular_parada(historial, criterio="recall+auc", paciencia=5):
    """Que epoca habria elegido esta politica, y donde habria cortado.

    REPRODUCE EL BUCLE REAL, INCLUIDAS SUS FASES, y eso no es un detalle: la
    primera version de esta funcion trataba el historial como una sola fase y
    produjo un hallazgo FALSO -«con paciencia 2 el criterio del proyecto elige
    la epoca 1 y se queda con un AUC de 0,8359»-. No pasa: en `entrenar()` la
    paciencia es POR FASE, y agotarla en la cabeza no abandona el
    entrenamiento, significa que la cabeza convergio y toca pasar al ajuste
    fino.

    Las tres reglas que se copian de `entrenar()` (ver su comentario, que las
    declara):

      - `mejor_*` es GLOBAL entre fases: la mejor epoca puede ser de la cabeza.
      - `sin_mejora` se REINICIA al empezar cada fase.
      - agotar la paciencia corta esa fase y se pasa a la siguiente; solo
        agotarla en la ULTIMA termina la corrida.

    Y el criterio se compara sin redondear, como `_es_mejor`: redondear cambia
    los empates, y el desempate por AUC es lo que decide varias epocas.

    Se puede simular sin reentrenar porque una politica de parada NO cambia el
    entrenamiento: solo elige donde cortar y con que pesos quedarse. Cualquier
    cosa que toque los gradientes -mas dropout, otro weight decay- produciria
    OTRO historial, y simularla sobre este seria inventarsela.
    """
    if criterio not in CRITERIOS:
        raise ValueError(f"criterio desconocido: {criterio}")
    _, clave = CRITERIOS[criterio]

    # El historial agrupado por fases, en orden, que es como corre `entrenar()`.
    fases: list[tuple[str, list[dict]]] = []
    for reg in historial:
        if not fases or fases[-1][0] != reg["fase"]:
            fases.append((reg["fase"], []))
        fases[-1][1].append(reg)

    mejor, mejor_epoca = None, None       # GLOBAL, como en `entrenar()`
    corridas, cortes = 0, []
    for nombre_fase, epocas in fases:
        sin_mejora = 0                    # se reinicia en cada fase
        for reg in epocas:
            corridas += 1
            v = clave(reg)
            if mejor is None or v > mejor:
                mejor, mejor_epoca, sin_mejora = v, reg["epoca"], 0
            else:
                sin_mejora += 1
                if sin_mejora >= paciencia:
                    cortes.append((nombre_fase, reg["epoca"]))
                    break                 # corta ESTA fase, no la corrida

    elegida = next(x for x in historial if x["epoca"] == mejor_epoca)
    return {
        "criterio": criterio,
        "paciencia": paciencia,
        "epoca_elegida": mejor_epoca,
        "cortes": cortes,
        "epocas_corridas": corridas,
        "epocas_ahorradas": len(historial) - corridas,
        "auc_val": elegida["auc"],
        "recall_val": elegida["recall"],
        "especificidad_val": elegida["especificidad"],
        "perdida_val": elegida["perdida_val"],
    }


def comparar_politicas(corrida, paciencias=(5, 3, 2)):
    """Todas las combinaciones de criterio y paciencia, sobre una corrida."""
    h = corrida["historial"]
    filas = []
    for criterio in CRITERIOS:
        for p in paciencias:
            filas.append(simular_parada(h, criterio, p))
    return filas


def imprimir_politicas(corrida):
    print(f"\n  estrategias de parada sobre {corrida['nombre']}:")
    print("    %-13s %-4s %-9s %-26s %-8s %s" % (
        "criterio", "pac", "elige", "agota la paciencia en", "AUC val",
        "ahorra"))
    for f in comparar_politicas(corrida):
        cortes = ", ".join(f"{fa} ep.{e}" for fa, e in f["cortes"]) or "-"
        print("    %-13s %-4d ep. %-5d %-26s %-8.4f %d epocas" % (
            f["criterio"], f["paciencia"], f["epoca_elegida"], cortes,
            f["auc_val"], f["epocas_ahorradas"]))


# ---------------------------------------------------------------------------
# LAS FIGURAS
#
# Requisitos del enunciado: 300 DPI, titulos informativos, ejes rotulados,
# leyenda, colores contrastantes entre entrenamiento y validacion, rejilla y
# anotaciones en los puntos criticos.
#
# Se importa matplotlib DENTRO de las funciones para que `diagnosticar` se
# pueda usar -y probar- sin tenerlo instalado.
# ---------------------------------------------------------------------------
DPI = 300
COLOR_TRAIN = "#1f77b4"      # azul
COLOR_VAL = "#d62728"        # rojo
COLOR_AUMENTADA = "#9ecae1"  # azul claro: es la misma familia que train
COLOR_AVISO = "#ff7f0e"


def _ejes(ax, titulo, x, y):
    ax.set_title(titulo, fontsize=12, fontweight="bold")
    ax.set_xlabel(x, fontsize=10)
    ax.set_ylabel(y, fontsize=10)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(fontsize=9)


def _marcar_fases(ax, historial):
    """La linea vertical donde acaba la cabeza y empieza el ajuste fino.

    Sin ella, la grafica tiene un codo inexplicable: no es que el modelo cambie
    de idea, es que se descongela el backbone y la tasa de aprendizaje baja.
    """
    cabeza = [r["epoca"] for r in historial if r["fase"] == "cabeza"]
    if not cabeza or len(cabeza) == len(historial):
        return
    corte = max(cabeza) + 0.5
    ax.axvline(corte, color="gray", linestyle=":", linewidth=1.2)
    ax.text(corte + 0.1, ax.get_ylim()[1] * 0.97, "ajuste fino",
            fontsize=8, color="gray", va="top")


def figura_perdidas(corrida, destino):
    """A. Entrenamiento contra validacion, que es la curva del diagnostico."""
    import matplotlib.pyplot as plt

    h = corrida["historial"]
    d = diagnosticar(h)
    ep = [r["epoca"] for r in h]
    fig, ax = plt.subplots(figsize=(9, 5.5))

    ax.plot(ep, [r["perdida_train"] for r in h], "-o", color=COLOR_TRAIN,
            markersize=4, label="entrenamiento (limpio, fin de época)")
    ax.plot(ep, [r["perdida_val"] for r in h], "-s", color=COLOR_VAL,
            markersize=4, label="validación")
    ax.plot(ep, [r["perdida"] for r in h], "--", color=COLOR_AUMENTADA,
            linewidth=1.4, label="entrenamiento (aumentado, durante la pasada)")

    e = d["epoca_minimo_val"]
    ax.axvline(e, color=COLOR_AVISO, linestyle="-.", linewidth=1.4)
    ax.annotate(
        f"mínimo de validación\népoca {e} — {d['perdida_val_minima']:.4f}",
        xy=(e, d["perdida_val_minima"]), xycoords="data",
        xytext=(0.32, 0.26), textcoords="axes fraction",
        fontsize=9, color=COLOR_AVISO, ha="left",
        arrowprops=dict(arrowstyle="->", color=COLOR_AVISO, lw=1.2))
    # El texto va anclado a FRACCION DE EJES y no a coordenadas de datos: la
    # perdida final cambia mucho de una corrida a otra -de 0,82 a 1,37 entre
    # las tres arquitecturas- y con una posicion en datos el rotulo se salia
    # del area y la flecha cruzaba el titulo.
    ax.annotate(
        f"a partir de aquí memoriza:\nla validación sube {d['subida_desde_el_minimo']:+.0%}",
        xy=(ep[-1], d["perdida_val_final"]), xycoords="data",
        xytext=(0.62, 0.90), textcoords="axes fraction",
        fontsize=9, color=COLOR_VAL, ha="left",
        arrowprops=dict(arrowstyle="->", color=COLOR_VAL, lw=1.2,
                        connectionstyle="arc3,rad=-0.15"))

    _ejes(ax, f"Pérdida por época — {corrida['nombre']}",
          "época", "pérdida (BCE ponderada por el desbalance)")
    _marcar_fases(ax, h)
    fig.tight_layout()
    fig.savefig(destino, dpi=DPI)
    plt.close(fig)
    return destino


def figura_auc(corrida, destino):
    """B. La misma historia en la metrica que el proyecto usa para decidir."""
    import matplotlib.pyplot as plt

    h = corrida["historial"]
    d = diagnosticar(h)
    ep = [r["epoca"] for r in h]
    fig, ax = plt.subplots(figsize=(9, 5.5))

    ax.plot(ep, [r["auc_train"] for r in h], "-o", color=COLOR_TRAIN,
            markersize=4, label="AUC entrenamiento")
    ax.plot(ep, [r["auc"] for r in h], "-s", color=COLOR_VAL,
            markersize=4, label="AUC validación")
    ax.fill_between(ep, [r["auc"] for r in h], [r["auc_train"] for r in h],
                    color=COLOR_VAL, alpha=0.08)

    ax.annotate(
        f"brecha final {d['brecha_auc_final']:.3f}\n"
        f"({d['auc_train_final']:.4f} vs {d['auc_val_final']:.4f})",
        xy=(ep[-1], (d["auc_train_final"] + d["auc_val_final"]) / 2),
        xytext=(ep[-1] - 5.0, 0.90), fontsize=9,
        arrowprops=dict(arrowstyle="->", color="gray", lw=1.1))
    ax.axvline(d["epoca_minimo_val"], color=COLOR_AVISO, linestyle="-.",
               linewidth=1.2)

    _ejes(ax, f"AUC por época — {corrida['nombre']}", "época", "AUC-ROC")
    _marcar_fases(ax, h)
    fig.tight_layout()
    fig.savefig(destino, dpi=DPI)
    plt.close(fig)
    return destino


def figura_brecha(corridas, destino):
    """La brecha de las tres juntas: el diagnostico en un solo numero."""
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5.5))
    for c in corridas:
        h = c["historial"]
        pares = [(r["epoca"], _brecha(r)) for r in h if _brecha(r) is not None]
        ax.plot([p[0] for p in pares], [p[1] for p in pares], "-o",
                markersize=4, label=c["nombre"].replace("kaggle_", ""))
    ax.axhline(0, color="gray", linewidth=0.8)
    _ejes(ax, "Brecha entre validación y entrenamiento, por arquitectura",
          "época", "pérdida_val − pérdida_train")
    fig.tight_layout()
    fig.savefig(destino, dpi=DPI)
    plt.close(fig)
    return destino


def figura_comparativa(corridas, destino):
    """D. Curvas de validacion por hiperparametro: la arquitectura."""
    import matplotlib.pyplot as plt

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.2))
    for c in corridas:
        h = c["historial"]
        ep = [r["epoca"] for r in h]
        etiqueta = c["nombre"].replace("kaggle_", "")
        a1.plot(ep, [r["perdida_val"] for r in h], "-o", markersize=3.5,
                label=etiqueta)
        a2.plot(ep, [r["auc"] for r in h], "-o", markersize=3.5, label=etiqueta)
        d = diagnosticar(h)
        a1.plot([d["epoca_minimo_val"]], [d["perdida_val_minima"]], "v",
                color="black", markersize=7)

    _ejes(a1, "Pérdida de validación", "época", "pérdida")
    _ejes(a2, "AUC de validación", "época", "AUC-ROC")
    a1.text(0.02, 0.02, "▼ mínimo de cada curva", transform=a1.transAxes,
            fontsize=8, color="black")
    fig.suptitle("Las tres arquitecturas, mismo conjunto y misma partición",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(destino, dpi=DPI)
    plt.close(fig)
    return destino


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("corridas", type=Path,
                   help="carpeta con una subcarpeta por corrida")
    p.add_argument("--figuras", type=Path, default=None,
                   help="carpeta donde escribir los PNG a 300 DPI")
    args = p.parse_args()

    corridas = cargar_directorio(args.corridas)
    if not corridas:
        print("no hay ninguna corrida con perdida de validacion en "
              f"{args.corridas}")
        return 1
    print(f"{len(corridas)} corrida(s) con historial completo")
    for c in corridas:
        imprimir(c)
        imprimir_politicas(c)

    if args.figuras:
        args.figuras.mkdir(parents=True, exist_ok=True)
        escritas = []
        for c in corridas:
            corto = c["nombre"].replace("kaggle_", "")
            escritas.append(figura_perdidas(
                c, args.figuras / f"perdidas_{corto}.png"))
            escritas.append(figura_auc(c, args.figuras / f"auc_{corto}.png"))
        escritas.append(figura_brecha(corridas, args.figuras / "brecha.png"))
        escritas.append(figura_comparativa(
            corridas, args.figuras / "comparativa.png"))
        print(f"\n{len(escritas)} figuras a {DPI} DPI en {args.figuras}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
