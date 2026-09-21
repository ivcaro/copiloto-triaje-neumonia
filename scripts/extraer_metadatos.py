"""Extrae los metadatos de todos los DICOM de RSNA sin decodificar pixeles.

Produce la tabla sobre la que se hace el analisis exploratorio de datos:
una fila por paciente con edad, sexo, posicion de la placa, dimensiones y
etiqueta. Leer solo las cabeceras (stop_before_pixels) hace que recorrer
los 26 684 archivos tarde minutos en vez de la media hora que costaria
decodificar cada imagen.

Uso:
    python scripts/extraer_metadatos.py --crudo <dir> --salida <csv>
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import pydicom

CAMPOS = {
    "patientId": "PatientID",
    "edad": "PatientAge",
    "sexo": "PatientSex",
    "vista": "ViewPosition",
    "modalidad": "Modality",
    "parte": "BodyPartExamined",
    "interpretacion": "PhotometricInterpretation",
}


def metadatos_de(ruta: Path) -> dict:
    """Cabecera de un DICOM, sin tocar los pixeles."""
    ds = pydicom.dcmread(str(ruta), stop_before_pixels=True)
    fila = {clave: str(getattr(ds, campo, "")) for clave, campo in CAMPOS.items()}
    fila["filas"] = int(getattr(ds, "Rows", 0) or 0)
    fila["columnas"] = int(getattr(ds, "Columns", 0) or 0)
    fila["bits"] = int(getattr(ds, "BitsAllocated", 0) or 0)
    fila["archivo"] = ruta.name
    fila["bytes"] = ruta.stat().st_size
    return fila


def main() -> int:
    parser = argparse.ArgumentParser(description="Metadatos de los DICOM de RSNA")
    parser.add_argument("--crudo", required=True, type=Path,
                        help="directorio con stage_2_train_images y los CSV")
    parser.add_argument("--salida", required=True, type=Path)
    args = parser.parse_args()

    dicoms = sorted((args.crudo / "stage_2_train_images").glob("*.dcm"))
    print(f"Leyendo cabeceras de {len(dicoms)} DICOM ...", flush=True)

    filas, omitidos, t0 = [], [], time.time()
    for i, ruta in enumerate(dicoms, 1):
        try:
            filas.append(metadatos_de(ruta))
        except Exception as exc:  # noqa: BLE001 - se registra y se continua
            omitidos.append({"archivo": ruta.name, "motivo": f"{type(exc).__name__}: {exc}"})
        if i % 2500 == 0:
            print(f"  {i}/{len(dicoms)}  ({time.time()-t0:.0f}s)", flush=True)

    meta = pd.DataFrame(filas)
    print(f"leidos {len(meta)} | omitidos {len(omitidos)} | {time.time()-t0:.0f}s", flush=True)

    # etiqueta binaria por paciente: positivo si tiene alguna caja de opacidad
    etiquetas = pd.read_csv(args.crudo / "stage_2_train_labels.csv")
    por_paciente = etiquetas.groupby("patientId")["Target"].max().rename("etiqueta")
    cajas = etiquetas.dropna(subset=["x"]).groupby("patientId").size().rename("n_cajas")

    # clase detallada de tres niveles
    clases = (pd.read_csv(args.crudo / "stage_2_detailed_class_info.csv")
              .drop_duplicates("patientId").set_index("patientId")["class"].rename("clase"))

    meta = (meta.merge(por_paciente, left_on="patientId", right_index=True, how="left")
                .merge(clases, left_on="patientId", right_index=True, how="left")
                .merge(cajas, left_on="patientId", right_index=True, how="left"))
    meta["n_cajas"] = meta["n_cajas"].fillna(0).astype(int)

    # la edad viene como texto en el DICOM; a numero para poder analizarla
    meta["edad_num"] = pd.to_numeric(meta["edad"], errors="coerce")

    args.salida.parent.mkdir(parents=True, exist_ok=True)
    meta.to_csv(args.salida, index=False)
    print(f"escrito {args.salida} con {len(meta)} filas y {len(meta.columns)} columnas", flush=True)
    print(f"positivos: {int(meta['etiqueta'].sum())} ({meta['etiqueta'].mean():.1%})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
