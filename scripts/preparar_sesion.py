# -*- coding: utf-8 -*-
"""Prepara la sesion con el medico (spec de SP5 §5.1-§5.8; plan SP5-A, D2-D3).

Dos fases:
  --fase elegir    elige los 24 + 3 casos con semilla, genera las viñetas,
                   copia las placas, y escribe casos.json (para el arnes),
                   clave.json (provisional), formulario/datos_lectura1.js y
                   dosier_lectura1.md.
  --fase mensajes  lee corpus/mensajes.json (lo deja `pruebas/reproducir_casos.py
                   --casos`), comprueba que cada mensaje repite la viñeta y que
                   la concordancia coincide con la prevista, y escribe
                   datos_lectura2.js, datos_planb.js, dosier_lectura2.md y la
                   clave definitiva: la categoria del sistema sale del bloque
                   DEL MENSAJE, que es lo que el medico ve.

Nada de lo que escribe se versiona (`pruebas/sesion/` esta en .gitignore).

ENTORNO
    RSNA_RAIZ   raiz del dataset preparado, SIN valor por defecto: las placas
                en <RSNA_RAIZ>/crudo/stage_2_train_images/<id>.dcm y los PNG
                en <RSNA_RAIZ>/png/<id>.png

USO
    python scripts/preparar_sesion.py --fase elegir --salida pruebas/sesion --semilla 20261006
    python pruebas/reproducir_casos.py --casos pruebas/sesion/casos.json --salida pruebas/sesion/corpus
    python scripts/preparar_sesion.py --fase mensajes --salida pruebas/sesion
"""
import argparse
import json
import os
import pathlib
import shutil
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE  # noqa: E402
from copiloto_triaje.validacion import datos, oraculo, sesion  # noqa: E402
from copiloto_triaje.validacion.categoria import categoria_del_sistema  # noqa: E402

FORMULARIO = REPO / "pruebas" / "formulario"
ROTULO = "simulación semisintética — sesión H7"


def raiz_rsna() -> pathlib.Path:
    raiz = os.environ.get("RSNA_RAIZ")
    if not raiz:
        raise SystemExit("falta RSNA_RAIZ: la raíz del dataset preparado, sin valor "
                         "por defecto (spec de SP5 §6.1)")
    return pathlib.Path(raiz)


def entrada_formulario(caso: dict, mensaje, control: bool = False) -> dict:
    return {"id": caso["patientId"], "placa": f"placas/{caso['patientId']}.png",
            "vineta": sesion.vineta(caso), "mensaje": mensaje, "control": bool(control)}


def datos_js(nombre, lectura, modo, casos, practica, salida: pathlib.Path):
    contenido = {"lectura": lectura, "modo": modo, "casos": casos, "practica": practica}
    (salida / "formulario").mkdir(parents=True, exist_ok=True)
    (salida / "formulario" / nombre).write_text(
        "window.DATOS = " + json.dumps(contenido, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8")


def dosier(titulo, entradas, salida: pathlib.Path, nombre):
    partes = [f"# {titulo}\n\n",
              "Simulación semisintética: la placa es real (RSNA, conjunto de prueba); "
              "la clínica es generada. Respaldo impreso del formulario, no instrumento "
              "de medida (spec de SP5 §5.8).\n"]
    for n, e in enumerate(entradas, 1):
        partes.append(f"\n## Caso {n}\n\n![placa](formulario/{e['placa']})\n\n```\n{e['vineta']}\n```\n")
        if e["mensaje"]:
            partes.append("\nMensaje del copiloto:\n\n```\n" + e["mensaje"] + "\n```\n")
    (salida / nombre).write_text("".join(partes), encoding="utf-8")


def _escribir_clave(salida, clave):
    (salida / "clave.json").write_text(json.dumps(clave, ensure_ascii=False, indent=1),
                                       encoding="utf-8")


def fase_elegir(salida: pathlib.Path, semilla: int):
    raiz = raiz_rsna()
    df = datos.cargar_crudas()
    cal = datos.calibrador_desplegado()
    _, q, rv = datos.evidencia_imagen(df["cruda"].values, cal)
    modelo = oraculo.ajustar(q, df["etiqueta"].values.astype(int), *sesion.RHO_SESION)
    casos, practica = sesion.elegir(df, rv, modelo, PREVALENCIA_COHORTE, semilla)
    ordenes = sesion.ordenes(casos, np.random.default_rng(semilla + 1))

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
    datos_js("datos_lectura1.js", 1, "simple", lectura1, practica_f, salida)
    dosier("Dosier de la lectura 1 (sin copiloto) — simulación semisintética",
           practica_f + lectura1, salida, "dosier_lectura1.md")
    _escribir_clave(salida, {
        "rotulo": ROTULO, "semilla": semilla, "prevalencia_sesion": PREVALENCIA_COHORTE,
        "rho_sesion": list(sesion.RHO_SESION), "ordenes": ordenes,
        "casos": casos, "practica": practica, "fase": "elegir"})
    print(f"{len(casos)} casos y {len(practica)} de práctica en {salida}.")
    print(f"Ahora: python pruebas/reproducir_casos.py --casos {salida / 'casos.json'} "
          f"--salida {salida / 'corpus'}")


def fase_mensajes(salida: pathlib.Path):
    clave = json.loads((salida / "clave.json").read_text(encoding="utf-8"))
    mensajes = json.loads((salida / "corpus" / "mensajes.json").read_text(encoding="utf-8"))
    problemas = []
    for c in clave["casos"] + clave["practica"]:
        m = mensajes.get(c["patientId"])
        if m is None:
            problemas.append(f"{c['patientId']}: sin mensaje")
            continue
        if m.get("error") or m.get("fallo"):
            problemas.append(f"{c['patientId']}: {m.get('error') or m.get('fallo')}")
            continue
        if sesion.linea_explorado(c["signos"]) not in m["texto"]:
            problemas.append(f"{c['patientId']}: EXPLORADO no repite la viñeta")
            continue
        bloque = (m.get("resultado") or {}).get("combinacion")
        if not bloque:
            problemas.append(f"{c['patientId']}: el mensaje no lleva combinación")
            continue
        if bool(bloque["concordantes"]) != c["concordante"]:
            problemas.append(f"{c['patientId']}: concordancia {bloque['concordantes']} "
                             f"≠ prevista {c['concordante']}")
            continue
        c["bloque"] = bloque
        c["categoria"] = categoria_del_sistema(bloque)
        c["mensaje"] = m["texto"]
        c["con_bots"] = m.get("con_bots")
    if problemas:
        raise SystemExit("mensajes que no sirven; no se escribe la lectura 2:\n  "
                         + "\n  ".join(problemas))
    por_id = {c["patientId"]: c for c in clave["casos"]}
    controles = set(clave["ordenes"]["controles"])
    lectura2 = [entrada_formulario(por_id[i], None if i in controles else por_id[i]["mensaje"],
                                   control=i in controles)
                for i in clave["ordenes"]["lectura2"]]
    planb = [entrada_formulario(por_id[i], por_id[i]["mensaje"])
             for i in clave["ordenes"]["lectura1"]]
    practica_f = [entrada_formulario(c, c["mensaje"]) for c in clave["practica"]]
    datos_js("datos_lectura2.js", 2, "simple", lectura2, practica_f, salida)
    datos_js("datos_planb.js", 1, "secuencial", planb, practica_f, salida)
    dosier("Dosier de la lectura 2 (con copiloto) — simulación semisintética",
           practica_f + lectura2, salida, "dosier_lectura2.md")
    clave["fase"] = "mensajes"
    _escribir_clave(salida, clave)
    print("lectura 2 y plan B listos; la clave lleva el bloque y la categoría "
          "del mensaje de cada caso")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--fase", choices=("elegir", "mensajes"), required=True)
    p.add_argument("--salida", default=str(REPO / "pruebas" / "sesion"))
    p.add_argument("--semilla", type=int, default=20261006)
    args = p.parse_args()
    salida = pathlib.Path(args.salida)
    if args.fase == "elegir":
        fase_elegir(salida, args.semilla)
    else:
        fase_mensajes(salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
