# -*- coding: utf-8 -*-
"""Prepara la sesion con el medico (spec de SP5 §5.1-§5.8; plan SP5-A, D2-D3).

Dos fases:
  --fase elegir    elige los 24 + 3 casos con semilla, genera las viñetas,
                   copia las placas, y escribe casos.json (para el arnes),
                   clave.json (provisional), formulario/datos_lectura1.js y
                   dosier_lectura1.md. Borra antes lo que dependia de una
                   eleccion anterior (lectura 2, plan B, mensajes.json,
                   placas), y no pisa una clave que ya tiene la fase
                   mensajes salvo con --forzar.
  --fase mensajes  lee corpus/mensajes.json (lo deja `pruebas/reproducir_casos.py
                   --casos`), comprueba que cada mensaje repite la viñeta y que
                   su bloque es el previsto (concordancia, puntuacion, RV de
                   imagen, prevalencia; y, con bots, que el bot y el copiloto
                   coinciden), y escribe datos_lectura2.js, datos_planb.js,
                   dosier_lectura2.md y la clave definitiva: la categoria del
                   sistema sale del bloque DEL MENSAJE, que es lo que el
                   medico ve. Los mensajes salen todos del mismo origen
                   (el acta cita UNO): una mezcla de mensajes con bots y sin
                   bots se rechaza. Si no se generaron con bots, exige
                   --imagen-tag y --imagen-digest, que el acta cita (spec §5.6).

Cada eleccion lleva una marca, `preparacion` (semilla y hora), que viaja a
los datos del formulario: el navegador no retoma un estado guardado de otra
preparacion (el ensayo, una eleccion anterior).

Nada de lo que escribe se versiona (`pruebas/sesion/` esta en .gitignore).

ENTORNO
    RSNA_RAIZ   raiz del dataset preparado, SIN valor por defecto: las placas
                en <RSNA_RAIZ>/crudo/stage_2_train_images/<id>.dcm y los PNG
                en <RSNA_RAIZ>/png/<id>.png

USO
    python scripts/preparar_sesion.py --fase elegir --salida pruebas/sesion --semilla 20261006
    python pruebas/reproducir_casos.py --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus
    python scripts/preparar_sesion.py --fase mensajes --salida pruebas/sesion
      (sin bots: ... --imagen-tag h7-sesion --imagen-digest sha256:...)
"""
import argparse
import datetime
import json
import pathlib
import shutil
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.config import raiz_rsna  # noqa: E402
from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE  # noqa: E402
from copiloto_triaje.validacion import datos, oraculo, sesion  # noqa: E402
from copiloto_triaje.validacion.categoria import categoria_del_sistema  # noqa: E402

FORMULARIO = REPO / "pruebas" / "formulario"
ROTULO = "simulación semisintética — sesión H7"


def entrada_formulario(caso: dict, mensaje, control: bool = False) -> dict:
    return {"id": caso["patientId"], "placa": f"placas/{caso['patientId']}.png",
            "vineta": sesion.vineta(caso), "mensaje": mensaje, "control": bool(control)}


def datos_js(nombre, lectura, modo, casos, practica, salida: pathlib.Path, preparacion: str):
    contenido = {"lectura": lectura, "modo": modo, "preparacion": preparacion,
                 "casos": casos, "practica": practica}
    (salida / "formulario").mkdir(parents=True, exist_ok=True)
    (salida / "formulario" / nombre).write_text(
        "window.DATOS = " + json.dumps(contenido, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8")


def dosier(titulo, practica, entradas, salida: pathlib.Path, nombre):
    """El respaldo impreso, con la numeracion del formulario: «Práctica N»
    para los de practica y «Caso N» para los demas, y el patientId."""
    partes = [f"# {titulo}\n\n",
              "Simulación semisintética: la placa es real (RSNA, conjunto de prueba); "
              "la clínica es generada. Respaldo impreso del formulario, no instrumento "
              "de medida (spec de SP5 §5.8).\n"]
    numeradas = ([("Práctica", n, e) for n, e in enumerate(practica, 1)]
                 + [("Caso", n, e) for n, e in enumerate(entradas, 1)])
    for rotulo, n, e in numeradas:
        partes.append(f"\n## {rotulo} {n} — {e['id']}\n\n![placa](formulario/{e['placa']})\n\n"
                      f"```\n{e['vineta']}\n```\n")
        if e["mensaje"]:
            partes.append("\nMensaje del copiloto:\n\n```\n" + e["mensaje"] + "\n```\n")
    (salida / nombre).write_text("".join(partes), encoding="utf-8")


def _escribir_clave(salida, clave):
    (salida / "clave.json").write_text(json.dumps(clave, ensure_ascii=False, indent=1),
                                       encoding="utf-8")


# Lo que sale de una eleccion y deja de valer cuando se elige otra vez.
DE_UNA_ELECCION_ANTERIOR = (pathlib.Path("formulario") / "datos_lectura2.js",
                            pathlib.Path("formulario") / "datos_planb.js",
                            pathlib.Path("dosier_lectura2.md"),
                            pathlib.Path("corpus") / "mensajes.json")


def fase_elegir(salida: pathlib.Path, semilla: int, forzar: bool = False):
    ruta_clave = salida / "clave.json"
    if ruta_clave.is_file() and not forzar:
        previa = json.loads(ruta_clave.read_text(encoding="utf-8"))
        if previa.get("fase") == "mensajes":
            raise SystemExit("clave.json ya tiene la fase mensajes; repetir la elección borra la "
                             "lectura 2 y los bloques del mensaje (usa --forzar)")
    raiz = raiz_rsna()
    df = datos.cargar_crudas()
    cal = datos.calibrador_desplegado()
    _, q, rv = datos.evidencia_imagen(df["cruda"].values, cal)
    modelo = oraculo.ajustar(q, df["etiqueta"].values.astype(int), *sesion.RHO_SESION)
    casos, practica = sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, semilla)
    ordenes = sesion.ordenes(casos, np.random.default_rng(semilla + 1))
    preparacion = f"{semilla}-{datetime.datetime.now().strftime('%Y%m%dT%H%M%S')}"

    for relativa in DE_UNA_ELECCION_ANTERIOR:
        (salida / relativa).unlink(missing_ok=True)
    if (salida / "formulario" / "placas").is_dir():
        shutil.rmtree(salida / "formulario" / "placas")
    (salida / "formulario" / "placas").mkdir(parents=True, exist_ok=True)
    for nombre in ("index.html", "formulario.js"):
        if (FORMULARIO / nombre).is_file():
            shutil.copy(FORMULARIO / nombre, salida / "formulario" / nombre)
        else:
            print(f"AVISO: falta {FORMULARIO / nombre}; el formulario se copia cuando exista")
    for c in casos + practica:
        png = raiz / "png" / f"{c['patientId']}.png"
        if not png.is_file():
            raise SystemExit(f"no existe {png}")
        shutil.copy(png, salida / "formulario" / "placas" / png.name)

    (salida / "casos.json").write_text(json.dumps([
        {"patientId": c["patientId"],
         "ruta_dcm": str(raiz / "crudo" / "stage_2_train_images" / f"{c['patientId']}.dcm"),
         "signos": c["signos"], "sintomas": c["sintomas"], "cruda": c["cruda"]}
        for c in casos + practica], ensure_ascii=False, indent=1), encoding="utf-8")

    por_id = {c["patientId"]: c for c in casos}
    lectura1 = [entrada_formulario(por_id[i], None) for i in ordenes["lectura1"]]
    practica_f = [entrada_formulario(c, None) for c in practica]
    datos_js("datos_lectura1.js", 1, "simple", lectura1, practica_f, salida, preparacion)
    dosier("Dosier de la lectura 1 (sin copiloto) — simulación semisintética",
           practica_f, lectura1, salida, "dosier_lectura1.md")
    _escribir_clave(salida, {
        "rotulo": ROTULO, "semilla": semilla, "preparacion": preparacion,
        "prevalencia_sesion": PREVALENCIA_COHORTE,
        "rho_sesion": list(sesion.RHO_SESION), "ordenes": ordenes,
        "casos": casos, "practica": practica, "fase": "elegir"})
    print(f"{len(casos)} casos y {len(practica)} de práctica en {salida} (preparación {preparacion}).")
    print(f"Ahora: python pruebas/reproducir_casos.py --casos {salida / 'casos.json'} "
          f"--salida {salida / 'corpus'}")


def _problemas_del_bloque(c: dict, bloque: dict, prevalencia_sesion: float) -> list:
    """Lo que distingue el bloque del mensaje del previsto al elegir: la
    concordancia, la puntuacion, la RV de imagen (el estrato) y la prevalencia."""
    pid = c["patientId"]
    previsto = c["bloque_previsto"]
    problemas = []
    if bool(bloque["concordantes"]) != c["concordante"]:
        problemas.append(f"{pid}: concordancia {bloque['concordantes']} ≠ prevista {c['concordante']}")
    if bloque["puntuacion"] != previsto["puntuacion"]:
        problemas.append(f"{pid}: puntuación {bloque['puntuacion']} ≠ prevista {previsto['puntuacion']}")
    if abs(bloque["rv_imagen"] / c["rv_imagen"] - 1.0) > 1e-3:
        problemas.append(f"{pid}: RV de imagen {bloque['rv_imagen']} ≠ la del caso {c['rv_imagen']}")
    if abs(bloque["prevalencia"] - prevalencia_sesion) > 5e-5:
        problemas.append(f"{pid}: prevalencia {bloque['prevalencia']} ≠ la de la sesión "
                         f"{prevalencia_sesion}")
    return problemas


def fase_mensajes(salida: pathlib.Path, imagen_tag: str | None = None,
                  imagen_digest: str | None = None):
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    if "preparacion" not in clave:
        raise SystemExit("clave.json no lleva la marca de preparación: repite --fase elegir")
    mensajes = json.loads((salida / "corpus" / "mensajes.json").read_text(encoding="utf-8"))
    problemas = []
    for c in clave["casos"] + clave["practica"]:
        pid = c["patientId"]
        m = mensajes.get(pid)
        if m is None:
            problemas.append(f"{pid}: sin mensaje")
            continue
        if m.get("error") or m.get("fallo"):
            problemas.append(f"{pid}: {m.get('error') or m.get('fallo')}")
            continue
        if m.get("con_bots") and str(m.get("coincide") or "").startswith("NO"):
            problemas.append(f"{pid}: lo que guardó el bot y esta lectura no coinciden ({m['coincide']})")
            continue
        if sesion.linea_explorado(c["signos"]) not in (m.get("texto") or ""):
            problemas.append(f"{pid}: EXPLORADO no repite la viñeta")
            continue
        bloque = (m.get("resultado") or {}).get("combinacion")
        if not bloque:
            problemas.append(f"{pid}: el mensaje no lleva combinación")
            continue
        del_bloque = _problemas_del_bloque(c, bloque, clave["prevalencia_sesion"])
        if del_bloque:
            problemas += del_bloque
            continue
        c["bloque"] = bloque
        c["categoria"] = categoria_del_sistema(bloque)
        c["mensaje"] = m["texto"]
        c["con_bots"] = m.get("con_bots")
    if problemas:
        raise SystemExit("mensajes que no sirven; no se escribe la lectura 2:\n  "
                         + "\n  ".join(problemas))
    todos = clave["casos"] + clave["practica"]
    sin_bots = [c["patientId"] for c in todos if not c["con_bots"]]
    if sin_bots and len(sin_bots) < len(todos):
        raise SystemExit(f"los mensajes mezclan orígenes: {len(todos) - len(sin_bots)} con bots y "
                         f"{len(sin_bots)} sin bots (sin bots: {', '.join(sin_bots)}). La sesión "
                         f"usa un solo modo para los {len(todos)} casos, porque el acta cita un "
                         f"solo origen: repite pruebas/reproducir_casos.py --casos con todos los "
                         f"casos en el mismo modo; no se escribe la lectura 2")
    con_bots = not sin_bots
    if not con_bots and not (imagen_tag and imagen_digest):
        raise SystemExit("los mensajes no se generaron con bots: el acta cita la imagen "
                         "local de la que salieron (spec §5.6); pasa --imagen-tag y "
                         "--imagen-digest (docker image inspect <imagen> --format \"{{.Id}}\")")
    clave["origen_mensajes"] = {"con_bots": con_bots, "imagen_tag": imagen_tag,
                                "imagen_digest": imagen_digest}
    por_id = {c["patientId"]: c for c in clave["casos"]}
    controles = set(clave["ordenes"]["controles"])
    lectura2 = [entrada_formulario(por_id[i], None if i in controles else por_id[i]["mensaje"],
                                   control=i in controles)
                for i in clave["ordenes"]["lectura2"]]
    planb = [entrada_formulario(por_id[i], por_id[i]["mensaje"])
             for i in clave["ordenes"]["lectura1"]]
    practica_f = [entrada_formulario(c, c["mensaje"]) for c in clave["practica"]]
    datos_js("datos_lectura2.js", 2, "simple", lectura2, practica_f, salida, clave["preparacion"])
    datos_js("datos_planb.js", 1, "secuencial", planb, practica_f, salida, clave["preparacion"])
    dosier("Dosier de la lectura 2 (con copiloto) — simulación semisintética",
           practica_f, lectura2, salida, "dosier_lectura2.md")
    clave["fase"] = "mensajes"
    _escribir_clave(salida, clave)
    print("lectura 2 y plan B listos; la clave lleva el bloque y la categoría "
          "del mensaje de cada caso")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fase", choices=("elegir", "mensajes"), required=True)
    p.add_argument("--salida", default=str(REPO / "pruebas" / "sesion"))
    p.add_argument("--semilla", type=int, default=20261006)
    p.add_argument("--forzar", action="store_true",
                   help="elegir de nuevo aunque clave.json ya tenga la fase mensajes")
    p.add_argument("--imagen-tag", help="sin bots: el tag de la imagen local (h7-sesion)")
    p.add_argument("--imagen-digest", help="sin bots: su digest (docker image inspect --format \"{{.Id}}\")")
    args = p.parse_args()
    salida = pathlib.Path(args.salida)
    if args.fase == "elegir":
        fase_elegir(salida, args.semilla, forzar=args.forzar)
    else:
        fase_mensajes(salida, imagen_tag=args.imagen_tag, imagen_digest=args.imagen_digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
