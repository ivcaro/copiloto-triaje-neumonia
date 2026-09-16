"""La garantia numero uno del proyecto, verificada sobre los ARTEFACTOS.

Hallazgo I6 (Important) de la oleada final: `test_particion.py` prueba la
FUNCION `particionar_por_paciente` y la funcion `verificar_sin_fuga`, pero
nadie relee los tres CSV que el pipeline llega a escribir. Si alguien borrara
la llamada a `verificar_sin_fuga` del script, o cambiara el orden de los
pasos, ninguna prueba se pondria roja y la ausencia de fuga dejaria de estar
garantizada justo donde importa: en los archivos que luego lee el Dataset.

Esta prueba corre el script de preparacion de verdad -de zip a manifiestos- y
comprueba la propiedad sobre los CSV emitidos. Los pacientes sinteticos
tienen VARIAS imagenes cada uno: con una sola imagen por paciente la
disyuncion seria trivial y la prueba no vigilaria nada.
"""
import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "preparar_datos.py"

N_PACIENTES = 40
IMAGENES_POR_PACIENTE = 2
N_SIN_ETIQUETA = 3  # imagenes cuyo patientId no esta en el CSV de etiquetas


def _escribir_dicom(ruta: Path, patient_id: str, lado: int = 32) -> None:
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientAge = "051Y"
    ds.PatientSex = "F"
    ds.ViewPosition = "PA"
    ds.Modality = "CR"
    ds.Rows, ds.Columns = lado, lado
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = (np.arange(lado * lado) % 256).astype(np.uint8).tobytes()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.save_as(str(ruta), enforce_file_format=True)


def _construir_zip_rsna(destino: Path) -> Path:
    """Un zip con la misma estructura interna que el de RSNA, en miniatura."""
    crudo = destino / "contenido"
    imagenes = crudo / "stage_2_train_images"
    imagenes.mkdir(parents=True)

    filas = ["patientId,x,y,width,height,Target"]
    for i in range(N_PACIENTES):
        pid = f"P{i:04d}"
        etiqueta = 1 if i < int(N_PACIENTES * 0.225) else 0
        for j in range(IMAGENES_POR_PACIENTE):
            _escribir_dicom(imagenes / f"{pid}_{j}.dcm", pid)
        if etiqueta:
            # Un positivo tiene varias cajas: varias filas para el mismo
            # paciente, como en el CSV real.
            filas.append(f"{pid},10,10,50,50,1")
            filas.append(f"{pid},80,80,40,40,1")
        else:
            filas.append(f"{pid},,,,,0")

    # Imagenes sin etiqueta: el script debe avisar en voz alta de que se
    # quedan fuera, no descartarlas en silencio.
    for k in range(N_SIN_ETIQUETA):
        _escribir_dicom(imagenes / f"FANTASMA{k}.dcm", f"FANTASMA{k}")

    (crudo / "stage_2_train_labels.csv").write_text("\n".join(filas) + "\n",
                                                    encoding="utf-8")
    ruta_zip = destino / "rsna-miniatura.zip"
    with zipfile.ZipFile(ruta_zip, "w") as z:
        for archivo in sorted(crudo.rglob("*")):
            if archivo.is_file():
                z.write(archivo, archivo.relative_to(crudo).as_posix())
    return ruta_zip


@pytest.fixture(scope="module")
def pipeline_ejecutado(tmp_path_factory):
    """Ejecuta el script de preparacion UNA vez y devuelve (raiz, salida)."""
    base = tmp_path_factory.mktemp("rsna")
    ruta_zip = _construir_zip_rsna(base)
    raiz = base / "trabajo"
    proceso = subprocess.run(
        [sys.executable, str(SCRIPT), "--zip", str(ruta_zip),
         "--raiz", str(raiz), "--semilla", "42"],
        capture_output=True, text=True, timeout=600)
    assert proceso.returncode == 0, (
        f"el script fallo:\n{proceso.stdout}\n{proceso.stderr}")
    return raiz, proceso.stdout


def _manifiestos(raiz: Path) -> dict[str, pd.DataFrame]:
    dir_manifiestos = raiz / "manifiestos"
    return {nombre: pd.read_csv(dir_manifiestos / f"{nombre}.csv")
            for nombre in ("train", "val", "test")}


def test_los_tres_manifiestos_emitidos_existen_y_no_estan_vacios(pipeline_ejecutado):
    raiz, _ = pipeline_ejecutado
    for nombre, df in _manifiestos(raiz).items():
        assert len(df) > 0, f"{nombre}.csv salio vacio"
        assert {"patientId", "archivo_png", "etiqueta", "semilla"} <= set(df.columns)


def test_ningun_patient_id_aparece_en_dos_de_los_csv_emitidos(pipeline_ejecutado):
    """LA prueba del proyecto. No mira la funcion de particion: relee los tres
    archivos que el pipeline dejo en disco, que son los que alimentan al
    Dataset, y exige que sus conjuntos de pacientes sean disjuntos."""
    raiz, _ = pipeline_ejecutado
    ids = {nombre: set(df["patientId"].astype(str))
           for nombre, df in _manifiestos(raiz).items()}

    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        comun = ids[a] & ids[b]
        assert not comun, (
            f"fuga de datos entre '{a}' y '{b}' en los manifiestos emitidos: "
            f"{sorted(comun)[:5]}")


def test_todas_las_imagenes_de_un_paciente_caen_en_el_mismo_csv(pipeline_ejecutado):
    """Con dos imagenes por paciente, la disyuncion de arriba solo significa
    algo si ademas ninguna imagen se separo de sus hermanas."""
    raiz, _ = pipeline_ejecutado
    ubicacion: dict[str, set[str]] = {}
    for nombre, df in _manifiestos(raiz).items():
        for pid in df["patientId"].astype(str):
            ubicacion.setdefault(pid, set()).add(nombre)
    repartidos = {pid: v for pid, v in ubicacion.items() if len(v) > 1}
    assert not repartidos, f"pacientes repartidos entre particiones: {repartidos}"


def test_los_manifiestos_no_pierden_ni_duplican_ninguna_imagen(pipeline_ejecutado):
    """El reparto tiene que ser una particion: ni una imagen de mas ni de
    menos respecto de las que si tenian etiqueta."""
    raiz, _ = pipeline_ejecutado
    manifiestos = _manifiestos(raiz)
    archivos = [a for df in manifiestos.values() for a in df["archivo_png"]]
    esperadas = N_PACIENTES * IMAGENES_POR_PACIENTE
    assert len(archivos) == esperadas
    assert len(set(archivos)) == esperadas, "hay imagenes duplicadas"

    # Y todas apuntan a un PNG que existe de verdad.
    dir_png = raiz / "png"
    faltantes = [a for a in archivos if not (dir_png / a).exists()]
    assert not faltantes, f"manifiestos que apuntan a PNG inexistentes: {faltantes[:5]}"


def test_el_script_avisa_en_voz_alta_de_las_imagenes_sin_etiqueta(pipeline_ejecutado):
    """Diferido de la revision, mandado arreglar en la oleada final: el spec §8
    exige que una perdida silenciosa de datos sea imposible, y hasta ahora la
    unica forma de detectarla era comparar dos lineas de stdout a ojo."""
    raiz, salida = pipeline_ejecutado
    assert "AVISO" in salida, f"el script no aviso de la perdida:\n{salida}"
    assert str(N_SIN_ETIQUETA) in salida

    ruta_aviso = raiz / "sin_etiqueta.json"
    assert ruta_aviso.exists(), "no se dejo por escrito que imagenes se perdieron"
    import json
    detalle = json.loads(ruta_aviso.read_text(encoding="utf-8"))
    assert detalle["imagenes_descartadas"] == N_SIN_ETIQUETA
    assert sorted(detalle["patient_id_sin_etiqueta"]) == \
        sorted(f"FANTASMA{k}" for k in range(N_SIN_ETIQUETA))


def test_la_semilla_queda_registrada_en_los_manifiestos_emitidos(pipeline_ejecutado):
    """Spec §7: la semilla se registra en cada manifiesto para que la particion
    sea un artefacto auditable y reproducible."""
    raiz, _ = pipeline_ejecutado
    for nombre, df in _manifiestos(raiz).items():
        assert (df["semilla"] == 42).all(), f"{nombre}.csv sin la semilla correcta"
