import os
from unittest.mock import patch

import numpy as np
import pydicom
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from copiloto_triaje.datos.dicom import convertir_a_png, convertir_lote, leer_dicom


def crear_dicom(ruta, patient_id="P0001", edad="51", sexo="F", vista="PA", lado=64):
    """Crea un DICOM minimo equivalente a los de RSNA: uint8 MONOCHROME2."""
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientAge = edad
    ds.PatientSex = sexo
    ds.ViewPosition = vista
    ds.Modality = "CR"
    ds.Rows, ds.Columns = lado, lado
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    arr = (np.arange(lado * lado) % 256).astype(np.uint8).reshape(lado, lado)
    ds.PixelData = arr.tobytes()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.save_as(str(ruta), enforce_file_format=True)
    return arr


def test_leer_dicom_devuelve_pixeles_y_metadatos(tmp_path):
    ruta = tmp_path / "a.dcm"
    esperado = crear_dicom(ruta)
    arr, meta = leer_dicom(ruta)
    assert arr.shape == esperado.shape
    assert meta["patientId"] == "P0001"
    assert meta["edad"] == "51"
    assert meta["sexo"] == "F"
    assert meta["vista"] == "PA"


def test_convertir_a_png_escribe_el_archivo_y_conserva_tamano(tmp_path):
    from PIL import Image
    dcm = tmp_path / "a.dcm"
    crear_dicom(dcm, lado=128)
    png = tmp_path / "salida" / "a.png"
    meta = convertir_a_png(dcm, png)
    assert png.exists()
    assert Image.open(png).size == (128, 128)
    assert meta["archivo_png"] == "a.png"


def test_convertir_lote_omite_los_corruptos_sin_abortar(tmp_path):
    buenos = []
    for i in range(3):
        r = tmp_path / f"b{i}.dcm"
        crear_dicom(r, patient_id=f"P{i:04d}")
        buenos.append(r)
    corrupto = tmp_path / "malo.dcm"
    corrupto.write_bytes(b"esto no es un DICOM")
    convertidos, omitidos = convertir_lote(buenos + [corrupto], tmp_path / "png")
    assert len(convertidos) == 3
    assert len(omitidos) == 1
    assert omitidos[0]["archivo"] == "malo.dcm"
    assert omitidos[0]["motivo"]


def crear_dicom_con_tag_vacio(ruta, patient_id="P9999", lado=64):
    """DICOM valido salvo que el tag Rows esta PRESENTE pero VACIO.

    No es un caso inventado: en DICOM un elemento puede existir con longitud
    cero, y pydicom lo devuelve entonces como `None`. `int(None)` lanza
    TypeError, no ValueError."""
    ds = Dataset()
    ds.PatientID = patient_id
    ds.PatientAge = "51"
    ds.PatientSex = "F"
    ds.ViewPosition = "PA"
    ds.Modality = "CR"
    ds.Rows = None                      # tag presente, sin valor
    ds.Columns = lado
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


def test_convertir_lote_omite_un_dicom_con_un_tag_presente_pero_vacio(tmp_path):
    """Diferido de la revision, mandado arreglar en la oleada final:
    `int(getattr(ds, "Rows", 0))` lanza TypeError cuando el tag existe con
    valor None, y TypeError no estaba en la tupla del except. Un solo archivo
    asi entre los 26 684 DICOM de RSNA abortaba a mitad una conversion de 21
    minutos, que es justo lo que ese try existe para impedir."""
    buenos = []
    for i in range(2):
        r = tmp_path / f"b{i}.dcm"
        crear_dicom(r, patient_id=f"P{i:04d}")
        buenos.append(r)
    vacio = tmp_path / "rows_vacio.dcm"
    crear_dicom_con_tag_vacio(vacio)

    convertidos, omitidos = convertir_lote(buenos + [vacio], tmp_path / "png")

    assert len(convertidos) == 2, "los archivos sanos deben convertirse igual"
    assert [o["archivo"] for o in omitidos] == ["rows_vacio.dcm"]
    assert "TypeError" in omitidos[0]["motivo"]


def test_convertir_lote_es_idempotente(tmp_path):
    """Prueba que convertir_lote no reescribe PNG existentes.

    Usa os.utime para retroceder el mtime a una hora conocida antes de la
    segunda ejecucion. Si el archivo fuera reescrito, su mtime cambiaría.
    """
    r = tmp_path / "a.dcm"
    crear_dicom(r)
    dir_png = tmp_path / "png"
    convertir_lote([r], dir_png)
    png_file = dir_png / "a.png"

    # Retroceder el mtime a hace 10 segundos
    tiempo_anterior = os.stat(png_file).st_mtime_ns - (10 * 1_000_000_000)
    os.utime(png_file, ns=(tiempo_anterior, tiempo_anterior))

    mtime_antes = os.stat(png_file).st_mtime_ns
    convertidos, _ = convertir_lote([r], dir_png)
    mtime_despues = os.stat(png_file).st_mtime_ns

    assert len(convertidos) == 1
    assert mtime_antes == mtime_despues  # No fue reescrito


def test_convertir_lote_propaga_errores_de_programacion(tmp_path):
    """Errores de programacion (no de lectura DICOM) se propagan, no se omiten.

    Esto asegura que bugs en el codigo de conversion no queden camuflados
    como "archivos omitidos" esperados. Un NameError real debe fallar ruidoso.
    """
    r = tmp_path / "a.dcm"
    crear_dicom(r)

    # Inyectar un NameError en convertir_a_png
    with patch("copiloto_triaje.datos.dicom.convertir_a_png") as mock_convert:
        mock_convert.side_effect = NameError("variable no definida")
        with pytest.raises(NameError):
            convertir_lote([r], tmp_path / "png")
