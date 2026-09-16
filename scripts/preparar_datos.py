"""Prepara los datos de RSNA: zip -> PNG -> manifiestos.

Uso:
    C:\\venv-copiloto\\Scripts\\python.exe scripts/preparar_datos.py ^
        --zip "C:\\Users\\[retirado]\\datasets\\rsna-pneumonia\\rsna-pneumonia-detection-challenge.zip" ^
        --raiz "C:\\Users\\[retirado]\\datasets\\rsna-pneumonia\\trabajo" ^
        [--limite 200]

Es idempotente: descomprimir y convertir se saltan si ya estan hechos.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copiloto_triaje.config import Config  # noqa: E402
from copiloto_triaje.datos.dicom import convertir_lote  # noqa: E402
from copiloto_triaje.datos.particion import (  # noqa: E402
    particionar_por_paciente, verificar_sin_fuga,
)
from copiloto_triaje.datos.preparacion import (  # noqa: E402
    cargar_etiquetas, construir_registros, escribir_manifiestos, verificar_zip_existe,
)


def descomprimir(zip_rsna: Path, destino: Path) -> Path:
    """Descomprime el zip si aun no se hizo. Devuelve el directorio."""
    marca = destino / ".descomprimido"
    if marca.exists():
        print(f"[1/4] Ya descomprimido en {destino}")
        return destino
    destino.mkdir(parents=True, exist_ok=True)
    print(f"[1/4] Descomprimiendo {zip_rsna.name} ...")
    with zipfile.ZipFile(zip_rsna) as z:
        z.extractall(destino)
    marca.write_text("ok", encoding="utf-8")
    return destino


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara los datos de RSNA")
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--raiz", required=True, type=Path)
    parser.add_argument("--limite", type=int, default=0,
                        help="procesar solo N imagenes (para pruebas rapidas)")
    parser.add_argument("--semilla", type=int, default=42)
    args = parser.parse_args()

    # Config no puede validar rutas (otras pruebas la construyen a proposito
    # con rutas temporales inexistentes), asi que la configuracion invalida
    # se detecta aqui, antes de tocar nada: fallar al inicio, no a mitad del
    # proceso, con un mensaje que cite la ruta buscada.
    verificar_zip_existe(args.zip)

    cfg = Config(raiz_datos=args.raiz, zip_rsna=args.zip, semilla=args.semilla)
    crudo = descomprimir(args.zip, args.raiz / "crudo")

    dicoms = sorted((crudo / "stage_2_train_images").glob("*.dcm"))
    if args.limite:
        dicoms = dicoms[: args.limite]
    print(f"[2/4] Convirtiendo {len(dicoms)} DICOM a PNG ...")
    convertidos, omitidos = convertir_lote(dicoms, cfg.dir_png)
    print(f"      convertidos: {len(convertidos)} | omitidos: {len(omitidos)}")
    if omitidos:
        (cfg.dir_png.parent / "omitidos.json").write_text(
            json.dumps(omitidos, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[3/4] Cruzando con las etiquetas ...")
    etiquetas = cargar_etiquetas(crudo / "stage_2_train_labels.csv")
    registros = construir_registros(convertidos, etiquetas)
    positivos = sum(r["etiqueta"] for r in registros)
    print(f"      registros: {len(registros)} | positivos: {positivos} "
          f"({positivos / max(len(registros), 1) * 100:.1f}%)")

    print("[4/4] Particionando por paciente y verificando fuga ...")
    particiones = particionar_por_paciente(registros, cfg.proporciones, cfg.semilla)
    verificar_sin_fuga(particiones)
    rutas = escribir_manifiestos(particiones, cfg.dir_manifiestos, cfg.semilla)
    for nombre, ruta in rutas.items():
        print(f"      {nombre}: {len(particiones[nombre])} imagenes -> {ruta}")
    print("LISTO. Sin fuga de datos entre particiones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
