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


def test_convertir_lote_es_idempotente(tmp_path):
    r = tmp_path / "a.dcm"
    crear_dicom(r)
    dir_png = tmp_path / "png"
    convertir_lote([r], dir_png)
    mtime = (dir_png / "a.png").stat().st_mtime_ns
    convertidos, _ = convertir_lote([r], dir_png)
    assert len(convertidos) == 1
    assert (dir_png / "a.png").stat().st_mtime_ns == mtime
