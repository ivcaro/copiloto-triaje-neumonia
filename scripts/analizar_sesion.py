# -*- coding: utf-8 -*-
"""Analiza la sesion con el medico: de los CSV del formulario a sesion.json y al acta.

USO
    python scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 lectura1.csv --lectura2 lectura2.csv
    python scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 planb.csv --planb planb.csv
    (ensayo) ... --sesion pruebas/sesion/ensayo --salida pruebas/sesion/ensayo/sesion.json --acta pruebas/sesion/ensayo/acta-h7.md

Escribe docs/validacion-semisintetica/sesion.json y acta-h7.md (rellena la
plantilla). Ninguna cifra del acta se teclea: todas salen de sesion.json, que
lleva tambien los sha256 de <sesion>/corpus/mensajes.json y <sesion>/clave.json
para que el congelado sea verificable. La clave tiene que ser la definitiva
(la de `preparar_sesion.py --fase mensajes`).
"""
import argparse
import json
import math
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.validacion import concordancia as cc  # noqa: E402
from copiloto_triaje.validacion.datos import sha256_de  # noqa: E402

CARPETA = REPO / "docs" / "validacion-semisintetica"


def sin_nan(x):
    """Lo mismo, con `None` donde habia un NaN o un infinito: «NaN» no es
    JSON, y un lector estricto no abriria sesion.json."""
    if isinstance(x, dict):
        return {clave: sin_nan(valor) for clave, valor in x.items()}
    if isinstance(x, (list, tuple)):
        return [sin_nan(valor) for valor in x]
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--sesion", default=str(REPO / "pruebas" / "sesion"))
    p.add_argument("--lectura1", required=True, help="CSV de la lectura sin copiloto (o el del plan B)")
    p.add_argument("--lectura2", help="CSV de la lectura con copiloto")
    p.add_argument("--planb", help="CSV del plan B (lectura secuencial)")
    p.add_argument("--salida", default=str(CARPETA / "sesion.json"))
    p.add_argument("--acta", default=str(CARPETA / "acta-h7.md"))
    args = p.parse_args()
    if args.lectura2 and args.planb:
        raise SystemExit("o lectura 2 o plan B, no los dos")

    sesion_dir = pathlib.Path(args.sesion)
    ruta_clave = sesion_dir / "clave.json"
    ruta_mensajes = sesion_dir / "corpus" / "mensajes.json"
    for ruta in (ruta_clave, ruta_mensajes):
        if not ruta.is_file():
            raise SystemExit(f"no existe {ruta}: el acta cita su sha256")
    clave = json.loads(ruta_clave.read_text(encoding="utf-8"))
    huellas = {"mensajes_json": sha256_de(ruta_mensajes), "clave_json": sha256_de(ruta_clave)}
    l1 = cc.leer_csv(sesion_dir / args.lectura1)
    l2 = cc.leer_csv(sesion_dir / args.lectura2) if args.lectura2 else None
    pb = cc.leer_csv(sesion_dir / args.planb) if args.planb else None
    try:
        resultado = cc.analizar(clave, l1, l2, pb, huellas=huellas)
    except ValueError as exc:
        raise SystemExit(f"no se analiza: {exc}") from None

    # Lo que se escribe y lo que rellena el acta es lo mismo: el resultado sin
    # NaN. Se serializa ANTES de abrir: si falla, el fichero anterior sigue.
    escrito = sin_nan(resultado)
    texto = json.dumps(escrito, ensure_ascii=False, indent=1, allow_nan=False)
    salida = pathlib.Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(texto, encoding="utf-8")
    plantilla = (CARPETA / "acta-h7-plantilla.md").read_text(encoding="utf-8")
    acta = cc.rellenar_acta(plantilla, cc.valores_para_acta(escrito, clave))
    ruta_acta = pathlib.Path(args.acta)
    ruta_acta.parent.mkdir(parents=True, exist_ok=True)
    ruta_acta.write_text(acta, encoding="utf-8")
    k = resultado["kappa"]["ponderado_lineal"]
    print(f"kappa ponderado {k['kappa']:.3f} (BCa {k['ic95_bca'][0]:.2f} a {k['ic95_bca'][1]:.2f}); "
          f"{len(resultado['desacuerdos'])} desacuerdos; sesion.json y acta escritos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
