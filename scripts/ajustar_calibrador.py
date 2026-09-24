# -*- coding: utf-8 -*-
"""Ajusta el calibrador sobre el conjunto de VALIDACION de una corrida.

Se ejecuta UNA vez por corrida, y su salida -calibrador.json- viaja con el
modelo al contenedor. Sin el, el servidor devolveria la salida cruda del
modelo como si fuera una probabilidad.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader

RAIZ_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ_REPO / "src"))

from copiloto_triaje.datos.dataset import DatasetRadiografias  # noqa: E402
from copiloto_triaje.modelo.arquitectura import construir_modelo  # noqa: E402
from copiloto_triaje.servicio.calibracion import ajustar_calibrador  # noqa: E402

PREVALENCIA = 0.2215
NOMBRE_PESOS = "pesos_modelo_cpu.pt"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Ajusta el calibrador sobre validacion")
    parser.add_argument("--corrida", required=True, type=Path,
                        help="carpeta de la corrida, con checkpoints/ dentro")
    parser.add_argument("--raiz", required=True, type=Path,
                        help="raiz de datos, con png/ y manifiestos/")
    parser.add_argument("--arquitectura", default="efficientnet_b0")
    parser.add_argument("--tam-imagen", type=int, default=320)
    args = parser.parse_args(argv)

    pesos = args.corrida / "checkpoints" / NOMBRE_PESOS
    if not pesos.is_file():
        print(f"ERROR: no estan los pesos en {pesos}", file=sys.stderr)
        return 2
    manifiesto = args.raiz / "manifiestos" / "val.csv"
    if not manifiesto.is_file():
        print(f"ERROR: no esta el manifiesto de validacion {manifiesto}",
              file=sys.stderr)
        return 2

    modelo = construir_modelo(args.arquitectura, congelar_backbone=False,
                              preentrenado=False)
    modelo.load_state_dict(torch.load(pesos, map_location="cpu",
                                      weights_only=True))
    modelo.eval()

    df = pd.read_csv(manifiesto)
    conjunto = DatasetRadiografias(df, args.raiz / "png", args.tam_imagen,
                                   entrenamiento=False)
    cargador = DataLoader(conjunto, batch_size=32, num_workers=0)

    print(f"evaluando {len(df)} imagenes de validacion ...", flush=True)
    y, s = [], []
    with torch.no_grad():
        for x, etiquetas in cargador:
            s.extend(torch.sigmoid(modelo(x).view(-1)).tolist())
            y.extend(etiquetas.tolist())

    calibrador = ajustar_calibrador(y, s, PREVALENCIA, args.corrida.name)
    ruta = calibrador.a_json(args.corrida / "calibrador.json")
    print(f"calibrador ajustado sobre {len(y)} imagenes -> {ruta}")
    print(f"  procedencia: {calibrador.procedencia} | "
          f"prevalencia: {calibrador.prevalencia}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
