# -*- coding: utf-8 -*-
"""Analiza la sesion con el medico: de los CSV del formulario a sesion.json y al acta.

USO
    python scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 lectura1.csv --lectura2 lectura2.csv
    python scripts/analizar_sesion.py --sesion pruebas/sesion --lectura1 planb.csv --planb planb.csv

Escribe docs/validacion-semisintetica/sesion.json y acta-h7.md (rellena la
plantilla). Ninguna cifra del acta se teclea: todas salen de sesion.json.
"""
import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from copiloto_triaje.validacion import concordancia as cc  # noqa: E402

CARPETA = REPO / "docs" / "validacion-semisintetica"


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
    clave = json.loads((sesion_dir / "clave.json").read_text(encoding="utf-8"))
    l1 = cc.leer_csv(sesion_dir / args.lectura1)
    l2 = cc.leer_csv(sesion_dir / args.lectura2) if args.lectura2 else None
    pb = cc.leer_csv(sesion_dir / args.planb) if args.planb else None
    resultado = cc.analizar(clave, l1, l2, pb)

    salida = pathlib.Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")
    plantilla = (CARPETA / "acta-h7-plantilla.md").read_text(encoding="utf-8")
    acta = cc.rellenar_acta(plantilla, cc.valores_para_acta(resultado, clave, l1, l2))
    pathlib.Path(args.acta).write_text(acta, encoding="utf-8")
    k = resultado["kappa"]["ponderado_lineal"]
    print(f"kappa ponderado {k['kappa']:.3f} (BCa {k['ic95_bca'][0]:.2f} a {k['ic95_bca'][1]:.2f}); "
          f"{len(resultado['desacuerdos'])} desacuerdos; sesion.json y acta escritos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
