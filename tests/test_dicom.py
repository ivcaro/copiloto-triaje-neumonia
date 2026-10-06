import csv
import io
import os
import struct
import tracemalloc
import warnings
import zlib
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pydicom
import pydicom.pixels
import pytest
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.encaps import encapsulate
from pydicom.uid import (
    JPEG2000, DeflatedExplicitVRLittleEndian, ExplicitVRBigEndian, ExplicitVRLittleEndian,
    HTJ2KLossless, ImplicitVRLittleEndian, JPEG2000Lossless, JPEG2000MCLossless,
    JPEGBaseline8Bit, JPEGExtended12Bit, JPEGLosslessSV1, JPEGLSLossless, RLELossless,
    generate_uid,
)

from copiloto_triaje.datos.dicom import (
    PlacaNoEvaluable, comprobar_los_pixeles, comprobar_que_se_puede_evaluar,
    convertir_a_png, convertir_lote, leer_dicom, leer_dicom_desde_bytes,
)

REPO = Path(__file__).resolve().parents[1]


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


def test_convertir_lote_repara_un_png_truncado_en_vez_de_darlo_por_bueno(tmp_path):
    """Corrida 2 en Colab: el entrenamiento reventó con "image file is
    truncated" DESPUES de que la preparacion informara "convertidos: 26684 |
    omitidos: 0". Las dos cosas eran ciertas a la vez porque la idempotencia
    era `if destino.exists()`: un PNG que quedo a medias en un intento
    anterior tenia el nombre definitivo, asi que cada reintento lo daba por
    convertido sin abrirlo nunca. El dato roto no se podia reparar salvo
    borrandolo a mano, y el fallo aparecia horas despues.

    Existir no es estar completo: la idempotencia tiene que mirar la validez.
    """
    origen = tmp_path / "a.dcm"
    crear_dicom(origen)
    dir_png = tmp_path / "png"
    convertir_lote([origen], dir_png)
    png = dir_png / "a.png"
    intacto = png.read_bytes()

    # Truncar a la mitad simula exactamente la escritura interrumpida.
    png.write_bytes(intacto[: len(intacto) // 2])
    assert png.exists() and png.stat().st_size > 0

    convertidos, omitidos = convertir_lote([origen], dir_png)

    assert len(convertidos) == 1 and not omitidos
    assert png.read_bytes() == intacto, "el PNG truncado no se reconvirtio"
    with Image.open(png) as imagen:
        imagen.verify()


def test_convertir_lote_repara_un_png_vacio(tmp_path):
    """El caso limite del anterior: 0 bytes. `exists()` tambien decia que si."""
    origen = tmp_path / "a.dcm"
    crear_dicom(origen)
    dir_png = tmp_path / "png"
    convertir_lote([origen], dir_png)
    png = dir_png / "a.png"
    intacto = png.read_bytes()

    png.write_bytes(b"")
    convertir_lote([origen], dir_png)

    assert png.read_bytes() == intacto


def test_convertir_a_png_no_deja_archivo_final_si_la_escritura_falla(tmp_path):
    """La otra mitad del fallo: `Image.save()` escribia DIRECTO sobre el
    destino final, asi que un corte a mitad -disco lleno, runtime reciclado-
    dejaba un PNG parcial con el nombre bueno. Escribiendo a un temporal y
    renombrando con os.replace, el destino final o esta completo o no esta.
    """
    origen = tmp_path / "a.dcm"
    crear_dicom(origen)
    destino = tmp_path / "png" / "a.png"

    with patch("copiloto_triaje.datos.dicom.os.replace",
               side_effect=OSError("No space left on device")):
        with pytest.raises(OSError):
            convertir_a_png(origen, destino)

    assert not destino.exists(), "quedo un PNG a medias con el nombre definitivo"
    assert not list(destino.parent.glob("*.tmp")), "quedo el temporal sin limpiar"


def test_convertir_lote_repara_un_png_cortado_dentro_del_idat(tmp_path):
    """Truncado con la firma y la cabecera IHDR intactas, cortado dentro del
    bloque de datos. Es la forma de corrupcion mas dificil de distinguir de
    un archivo sano mirando solo el principio.

    Nota honesta: `verify()` tambien detecta este caso -se comprobo-, asi que
    esta prueba NO justifica por si sola el cambio a `load()`. Ese cambio se
    sostiene en otra cosa: `load()` es, por construccion, la misma operacion
    que hace el DataLoader al leer la imagen, de modo que no puede decir que
    un archivo esta bien y que el entrenamiento reviente con el. verify() es
    mas barata y acerto en todos los casos que se pudieron construir, pero es
    una comprobacion distinta de la que importa.
    """
    origen = tmp_path / "a.dcm"
    crear_dicom(origen)
    dir_png = tmp_path / "png"
    convertir_lote([origen], dir_png)
    png = dir_png / "a.png"
    intacto = png.read_bytes()

    # Cortar dentro del IDAT: el PNG conserva firma y cabecera IHDR.
    idat = intacto.index(b"IDAT")
    png.write_bytes(intacto[: idat + 12])
    assert png.stat().st_size > 0

    convertir_lote([origen], dir_png)

    assert png.read_bytes() == intacto, "no se reconvirtio el PNG sin datos"
    with Image.open(png) as imagen:
        imagen.load()


def test_leer_dicom_desde_bytes_da_lo_mismo_que_desde_ruta(tmp_path):
    """El servidor recibe el DICOM por la red, no como fichero. Leer desde
    bytes tiene que dar exactamente lo mismo que leer desde disco: si
    divergieran, el modelo veria en produccion algo distinto de lo que se
    probo, y ninguna prueba de las existentes lo notaria."""
    ruta = tmp_path / "a.dcm"
    esperado = crear_dicom(ruta, edad="051Y", sexo="M", vista="AP")

    desde_ruta, meta_ruta = leer_dicom(ruta)
    desde_bytes, meta_bytes = leer_dicom_desde_bytes(ruta.read_bytes())

    assert np.array_equal(desde_ruta, desde_bytes)
    assert meta_ruta == meta_bytes
    assert meta_bytes["edad"] == "051Y"
    assert desde_bytes.shape == esperado.shape


def test_leer_dicom_desde_bytes_rechaza_lo_que_no_es_dicom():
    """Un PNG, un JSON o basura tienen que fallar con un motivo, no con un
    AttributeError tres capas mas arriba. Desde SP5-B4 el motivo es NUESTRO
    -`sin_metainformacion`, con nuestro texto- y no el error de pydicom, cuyo
    texto el servidor devolveria y el bot registraria."""
    with pytest.raises(PlacaNoEvaluable) as fallo:
        leer_dicom_desde_bytes(b"esto no es un DICOM")
    assert fallo.value.motivo == "sin_metainformacion"


# ==========================================================================
# SP5-B4: la regla de lo que el motor puede evaluar, decidida por la cabecera
# ==========================================================================
#
# El motor convierte la placa con `Image.fromarray(arreglo).convert("RGB")`, que
# con mas de 8 bits satura casi a blanco (una neumonia en 16 bits baja de 0,91 a
# 0,48) y a una MONOCHROME1 la ve al reves; y `pixel_array` no lleva tope de
# memoria. La regla de `datos/dicom.py` decide con la metainformacion y la
# cabecera, ANTES de descodificar un pixel. Aqui, cada motivo con un DICOM
# fabricado en la prueba, y su texto escrito a mano: es NUESTRO -el servidor lo
# devuelve y el bot lo registra-, nunca de pydicom ni con bytes del fichero.

# Los siete campos sin los que pydicom no sabe descodificar la imagen: sin uno,
# `pixel_array` lanza un AttributeError (medido con pydicom 3.0.2).
CAMPOS_DE_LA_IMAGEN = ("Rows", "Columns", "BitsAllocated", "BitsStored",
                       "SamplesPerPixel", "PhotometricInterpretation",
                       "PixelRepresentation")

# Los textos de cada motivo, a mano. El motor les antepone «La placa no se puede
# evaluar: ».
SIN_METAINFORMACION = (
    "el fichero no trae la metainformación de un DICOM (el grupo 0002, con una "
    "sintaxis de transferencia que se conozca), así que no se sabe cómo leerlo.")
DEFLATED = (
    "el fichero viene comprimido entero (en DICOM, «Deflated Explicit VR Little "
    "Endian»), y no se descomprime: podría ocupar cientos de veces lo que pesa.")
CABECERA_INCOMPLETA = (
    "a la cabecera le falta alguno de los campos que dicen cómo leer la imagen "
    "(filas, columnas, bits, signo, muestras por píxel o fotometría), o lo trae sin "
    "un valor que se entienda.")
INVERTIDA = (
    "guarda la escala de grises invertida (en DICOM, MONOCHROME1), y el modelo solo "
    "evalúa placas MONOCHROME2, como las de RSNA con las que se entrenó.")
EN_COLOR = (
    "no está en escala de grises, y el modelo solo evalúa placas en grises (en DICOM, "
    "MONOCHROME2 con una muestra por píxel), como las de RSNA con las que se entrenó.")
SIN_PIXELES = ("el fichero trae la cabecera pero no la imagen: puede que esté "
               "recortado.")
COMPRESION = (
    "el fichero viene comprimido con una sintaxis de transferencia que aquí no se sabe "
    "descomprimir (falta su descodificador), así que no se puede leer la imagen.")


def _bits(texto):
    return (f"es de {texto}, y el modelo solo evalúa placas de 8 bits sin signo, como "
            "las de RSNA con las que se entrenó.")


def _tamano(filas, columnas):
    return (f"declara {filas} × {columnas} píxeles, y no se leen placas de más de "
            "5000 de lado (una placa de tórax digital ronda los 4300 × 4300).")


def _cuadros(cuadros):
    return f"el fichero trae {cuadros} imágenes, y se evalúa una placa sola."


# Fragmentos de los mensajes de pydicom que se han visto en estos casos: ninguno
# puede llegar al texto de un rechazo.
DE_PYDICOM = ("DICM", "Pixel Data", "Missing required", "Unable to", "(0028",
              "(0002", "Transfer Syntax UID", "pydicom", "dataset", "element")


def _placa(tmp_path, cambiar=None, nombre="placa.dcm"):
    """Los bytes de una placa sana de 54 anios (`crear_dicom`: 64 x 64, 8 bits,
    MONOCHROME2, Explicit VR Little Endian), despues de `cambiar(ds)`."""
    ruta = tmp_path / nombre
    crear_dicom(ruta, edad="054Y")
    if cambiar is not None:
        ds = pydicom.dcmread(str(ruta))
        cambiar(ds)
        ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


def _con(**campos):
    """Un `cambiar` que pone esos campos (con `None`, presente y vacio)."""
    def cambiar(ds):
        for campo, valor in campos.items():
            setattr(ds, campo, valor)
    return cambiar


def _sin(campo):
    def cambiar(ds):
        delattr(ds, campo)
    return cambiar


def _de_16_bits(con_signo=False):
    def cambiar(ds):
        ds.BitsAllocated, ds.BitsStored, ds.HighBit = 16, 16, 15
        ds.PixelRepresentation = 1 if con_signo else 0
        ds.PixelData = (np.arange(64 * 64).reshape(64, 64) * 16).astype(
            np.int16 if con_signo else np.uint16).tobytes()
    return cambiar


def _de_1_bit(ds):
    ds.BitsAllocated, ds.BitsStored, ds.HighBit = 1, 1, 0
    ds.PixelData = bytes(64 * 64 // 8)


def _en_color(ds):
    ds.PhotometricInterpretation, ds.SamplesPerPixel, ds.PlanarConfiguration = (
        "RGB", 3, 0)
    ds.PixelData = bytes(64 * 64 * 3)


def _dos_cuadros(ds):
    ds.NumberOfFrames = 2
    ds.PixelData = bytes(2 * 64 * 64)


def _cuadros_ilegibles(tmp_path):
    """`NumberOfFrames` con un valor que no es un numero ("ab"): se escribe "12" y
    se cambia en los bytes, porque pydicom no deja escribir un IS invalido."""
    datos = _placa(tmp_path, _con(NumberOfFrames=12))
    elemento = b"\x28\x00\x08\x00IS\x02\x0012"
    assert datos.count(elemento) == 1
    return datos.replace(elemento, b"\x28\x00\x08\x00IS\x02\x00ab")


def _la_bomba(tmp_path):
    """Unos 600 bytes que declaran 60 000 x 60 000, en RLE: un solo fragmento con
    su cabecera de 64 bytes (un segmento) y un segmento de dos bytes. `pixel_array`
    intentaria reservar 3,35 GiB."""
    def cambiar(ds):
        ds.Rows = ds.Columns = 60000
        ds.file_meta.TransferSyntaxUID = RLELossless
        ds.PixelData = encapsulate(
            [struct.pack("<16L", 1, 64, *([0] * 14)) + b"\x81\x00"])
        ds["PixelData"].VR = "OB"
        ds["PixelData"].is_undefined_length = True
    return _placa(tmp_path, cambiar, "bomba.dcm")


def _deflated(tmp_path):
    """La placa sana con la sintaxis Deflated Explicit VR Little Endian, escrita
    por pydicom: TODO el conjunto de datos tras el grupo 0002, comprimido."""
    def cambiar(ds):
        ds.file_meta.TransferSyntaxUID = DeflatedExplicitVRLittleEndian
    return _placa(tmp_path, cambiar, "deflated.dcm")


def _sin_sintaxis(tmp_path):
    """Un grupo 0002 que se lee, pero sin `TransferSyntaxUID`, y un conjunto de
    datos sano detras."""
    ruta = tmp_path / "sin_sintaxis.dcm"
    crear_dicom(ruta, edad="054Y")
    ds = pydicom.dcmread(str(ruta))
    del ds.file_meta.TransferSyntaxUID
    ds.preamble = bytes(128)
    salida = io.BytesIO()
    pydicom.dcmwrite(salida, ds, enforce_file_format=False, implicit_vr=False,
                     little_endian=True)
    return salida.getvalue()


def _sintaxis_desconocida(tmp_path):
    """La placa sana con una sintaxis de transferencia que no es ninguna: el UID
    de 19 caracteres de Explicit VR Little Endian se cambia en los bytes por otro
    de la misma longitud (pydicom no deja escribir con una sintaxis que no
    conoce). pydicom lee su cabecera, y al descodificar lanza NotImplementedError,
    que el motor no traduce."""
    datos = _placa(tmp_path)
    viejo, nuevo = b"1.2.840.10008.1.2.1\x00", b"1.2.3.4.5.6.7.8.9.1\x00"
    assert datos.count(viejo) == 1
    return datos.replace(viejo, nuevo)


def _sin_pixel_data(tmp_path):
    return _placa(tmp_path, _sin("PixelData"), "sin_pixeles.dcm")


def _recortada(tmp_path):
    """Una placa en RLE de verdad, cortada antes del final de su Pixel Data (como
    la del perfil «fichero corrupto» del corpus, que es JPEG): pydicom la lee sin
    el elemento -avisa de que el fichero se acaba antes del delimitador- y
    `pixel_array` lanzaria un AttributeError."""
    def cambiar(ds):
        ds.compress(RLELossless, PIXELES_DE_LA_PLACA)
    datos = _placa(tmp_path, cambiar, "rle.dcm")
    return datos[: len(datos) - 200]


# Los pixeles que escribe `crear_dicom` con lado 64.
PIXELES_DE_LA_PLACA = (np.arange(64 * 64) % 256).astype(np.uint8).reshape(64, 64)


def _con_pillow(formato, **opciones):
    """Los pixeles de la placa comprimidos por Pillow (JPEG o el codestream de JPEG
    2000), para encapsularlos con la sintaxis que toque."""
    salida = io.BytesIO()
    Image.fromarray(PIXELES_DE_LA_PLACA).save(salida, format=formato, **opciones)
    return salida.getvalue()


def _comprimida(sintaxis, fragmento):
    """Un `cambiar` que encapsula `fragmento` como el Pixel Data con esa sintaxis."""
    def cambiar(ds):
        ds.file_meta.TransferSyntaxUID = sintaxis
        ds.PixelData = encapsulate([fragmento])
        ds["PixelData"].VR = "OB"
        ds["PixelData"].is_undefined_length = True
    return cambiar


def _jpeg():
    return _con_pillow("JPEG", quality=95)


def _j2k(sin_perdida=True):
    if sin_perdida:
        return _con_pillow("JPEG2000", no_jp2=True, irreversible=False)
    return _con_pillow("JPEG2000", no_jp2=True, irreversible=True,
                       quality_mode="rates", quality_layers=[10])


# (identificador, como se fabrica, motivo, los datos del motivo, su texto)
NO_EVALUABLES = [
    ("texto", lambda t: b"esto no es un DICOM", "sin_metainformacion", {},
     SIN_METAINFORMACION),
    ("solo_el_preambulo", lambda t: _placa(t)[:132], "sin_metainformacion", {},
     SIN_METAINFORMACION),
    ("0002_cortado", lambda t: _placa(t)[:150], "sin_metainformacion", {},
     SIN_METAINFORMACION),
    ("0002_sin_sintaxis", _sin_sintaxis, "sin_metainformacion", {},
     SIN_METAINFORMACION),
    ("sintaxis_desconocida", _sintaxis_desconocida, "sin_metainformacion", {},
     SIN_METAINFORMACION),
    ("deflated", _deflated, "deflated", {}, DEFLATED),
    ("16_bits", lambda t: _placa(t, _de_16_bits()), "bits",
     {"bits": 16, "con_signo": False}, _bits("16 bits")),
    ("16_bits_con_signo", lambda t: _placa(t, _de_16_bits(con_signo=True)), "bits",
     {"bits": 16, "con_signo": True}, _bits("16 bits con signo")),
    ("8_bits_con_signo", lambda t: _placa(t, _con(PixelRepresentation=1)), "bits",
     {"bits": 8, "con_signo": True}, _bits("8 bits con signo")),
    ("1_bit", lambda t: _placa(t, _de_1_bit), "bits",
     {"bits": 1, "con_signo": False}, _bits("1 bit")),
    ("monochrome1", lambda t: _placa(t, _con(PhotometricInterpretation="MONOCHROME1")),
     "fotometria", {}, INVERTIDA),
    ("rgb", lambda t: _placa(t, _en_color), "color", {}, EN_COLOR),
    ("paleta", lambda t: _placa(t, _con(PhotometricInterpretation="PALETTE COLOR")),
     "color", {}, EN_COLOR),
    ("tres_muestras_en_grises", lambda t: _placa(t, _con(SamplesPerPixel=3)), "color",
     {}, EN_COLOR),
    ("dos_cuadros", lambda t: _placa(t, _dos_cuadros), "cuadros", {"cuadros": 2},
     _cuadros(2)),
    ("rows_5001", lambda t: _placa(t, _con(Rows=5001)), "tamano",
     {"filas": 5001, "columnas": 64}, _tamano(5001, 64)),
    ("columns_5001", lambda t: _placa(t, _con(Columns=5001)), "tamano",
     {"filas": 64, "columnas": 5001}, _tamano(64, 5001)),
    ("bomba_60000x60000", _la_bomba, "tamano", {"filas": 60000, "columnas": 60000},
     _tamano(60000, 60000)),
    ("rows_vacio", lambda t: _placa(t, _con(Rows=None)), "cabecera_incompleta", {},
     CABECERA_INCOMPLETA),
    *[(f"sin_{campo}", (lambda c: lambda t: _placa(t, _sin(c)))(campo),
       "cabecera_incompleta", {}, CABECERA_INCOMPLETA)
      for campo in CAMPOS_DE_LA_IMAGEN],
    ("cuadros_ilegibles", _cuadros_ilegibles, "cabecera_incompleta", {},
     CABECERA_INCOMPLETA),
    ("sin_pixel_data", _sin_pixel_data, "sin_pixeles", {}, SIN_PIXELES),
    ("recortada", _recortada, "sin_pixeles", {}, SIN_PIXELES),
    # JPEG 2000 Parte 2 (multicomponente): pydicom 3.0.2 no tiene descodificador para
    # ella con ningun plugin, asi que el caso no depende de lo que haya instalado.
    ("jpeg2000_parte_2", lambda t: _placa(t, _comprimida(JPEG2000MCLossless, _j2k())),
     "compresion", {}, COMPRESION),
]


@pytest.mark.parametrize("hacer, motivo, datos, texto", [n[1:] for n in NO_EVALUABLES],
                         ids=[n[0] for n in NO_EVALUABLES])
def test_cada_motivo_se_rechaza_con_su_codigo_sus_datos_y_un_texto_nuestro(
        tmp_path, nadie_descodifica, nadie_infla, hacer, motivo, datos, texto):
    """Cada DICOM que el motor no puede evaluar se rechaza con `PlacaNoEvaluable`,
    su motivo, los enteros que lo explican y NUESTRO texto, sin descodificar un
    pixel y sin inflar nada. La cabecera decide sola, salvo `sin_pixeles`: ahi la
    cabecera esta en regla, y lo que falta lo dice la lectura entera, antes de
    `pixel_array`."""
    with warnings.catch_warnings():
        # pydicom avisa al leer la recortada (el fichero se acaba antes del
        # delimitador) y de los valores que se escriben mal a proposito.
        warnings.simplefilter("ignore", UserWarning)
        placa = hacer(tmp_path)
        with pytest.raises(PlacaNoEvaluable) as fallo:
            leer_dicom_desde_bytes(placa)
        exc = fallo.value
        assert exc.motivo == motivo
        assert {clave: getattr(exc, clave) for clave in datos} == datos
        assert str(exc) == texto
        assert not [f for f in DE_PYDICOM if f in str(exc)]
        if motivo == "sin_pixeles":
            assert comprobar_que_se_puede_evaluar(placa) is None
        else:
            with pytest.raises(PlacaNoEvaluable) as otra:
                comprobar_que_se_puede_evaluar(placa)
            assert (otra.value.motivo, str(otra.value)) == (motivo, texto)
    assert nadie_descodifica == [] and nadie_infla == []


@pytest.mark.parametrize("cambiar, motivo", [
    (lambda ds: (_de_16_bits()(ds), setattr(ds, "Rows", 6000)), "tamano"),
    (lambda ds: (_de_16_bits()(ds), setattr(ds, "NumberOfFrames", 2)), "cuadros"),
    (lambda ds: (_de_16_bits()(ds), setattr(ds, "PhotometricInterpretation", "RGB")),
     "bits"),
    (_con(PixelRepresentation=1, PhotometricInterpretation="MONOCHROME1"), "fotometria"),
    (lambda ds: (_en_color(ds), setattr(ds, "PixelRepresentation", 1)), "color"),
    (lambda ds: (_de_16_bits()(ds), _comprimida(JPEG2000MCLossless, _j2k())(ds)), "bits"),
], ids=["16_bits_y_6000_filas", "16_bits_y_dos_cuadros", "16_bits_en_color",
        "signo_e_invertida", "signo_y_color", "16_bits_y_sin_descodificador"])
def test_con_varias_cosas_mal_manda_la_primera_en_el_orden_de_la_app(
        tmp_path, nadie_descodifica, cambiar, motivo):
    """El orden es el de la app (R27), para que alli cada placa siga recibiendo el
    mensaje de siempre: el tamano y los cuadros, los bits, la escala invertida y el
    color; y el signo, el ULTIMO (en la app lo paraba la segunda red, ya con los
    pixeles). La sintaxis sin descodificador va detras de la cabecera: con 16 bits,
    la app sigue diciendo lo de los 16 bits, como cuando esa placa le llegaba al
    motor y reventaba con un RuntimeError."""
    with pytest.raises(PlacaNoEvaluable) as fallo:
        comprobar_que_se_puede_evaluar(_placa(tmp_path, cambiar))
    assert fallo.value.motivo == motivo
    assert nadie_descodifica == []


def test_una_placa_sana_de_8_bits_pasa_la_regla_y_se_lee_como_siempre(tmp_path):
    ruta = tmp_path / "a.dcm"
    esperado = crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()
    assert comprobar_que_se_puede_evaluar(datos) is None
    arreglo, meta = leer_dicom_desde_bytes(datos)
    assert arreglo.dtype == np.uint8 and np.array_equal(arreglo, esperado)
    assert meta["edad"] == "054Y" and (meta["filas"], meta["columnas"]) == (64, 64)


@pytest.mark.parametrize("cambiar",
                         [_con(NumberOfFrames=1), _con(Rows=5000, Columns=5000)],
                         ids=["un_cuadro", "5000x5000"])
def test_los_bordes_pasan_la_regla(tmp_path, nadie_descodifica, cambiar):
    """Un cuadro declarado y 5 000 x 5 000 justos (la cabecera; los pixeles no se
    miran) pasan, como pasaban en la app."""
    assert comprobar_que_se_puede_evaluar(_placa(tmp_path, cambiar)) is None
    assert nadie_descodifica == []


def test_una_placa_sana_en_rle_pasa_y_se_lee(tmp_path):
    """Una sintaxis comprimida que no es Deflated no se rechaza por serlo: RSNA
    llega en JPEG Baseline. Aqui, RLE, que pydicom descodifica sin plugins."""
    pixeles = (np.arange(64 * 64) % 256).astype(np.uint8).reshape(64, 64)
    datos = _placa(tmp_path, lambda ds: ds.compress(RLELossless, pixeles), "rle.dcm")
    assert comprobar_que_se_puede_evaluar(datos) is None
    assert np.array_equal(leer_dicom_desde_bytes(datos)[0], pixeles)


def test_la_bomba_de_60000_x_60000_se_rechaza_sin_reservar_la_memoria(
        tmp_path, nadie_descodifica):
    """Unos cientos de bytes que declaran 60 000 x 60 000 en RLE: `pixel_array`
    reservaria 3,35 GiB (el contenedor del bot muere y se reinicia). Se rechaza
    por la cabecera: el espia no salta, y el pico de memoria que mide tracemalloc
    -que ve las reservas de numpy- se queda en nada."""
    datos = _la_bomba(tmp_path)
    assert len(datos) < 1000
    tracemalloc.start()
    try:
        with pytest.raises(PlacaNoEvaluable) as fallo:
            leer_dicom_desde_bytes(datos)
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert (fallo.value.motivo, fallo.value.filas, fallo.value.columnas) == (
        "tamano", 60000, 60000)
    assert nadie_descodifica == []
    assert pico < 4 * 2**20, f"pico de {pico / 2**20:.1f} MiB"


MIB_DENTRO_DEL_DEFLATED = 200


@pytest.fixture(scope="session")
def deflated_con_cientos_de_mib(tmp_path_factory):
    """Unos 200 KiB que, inflados, son mas de 200 MiB: la metainformacion de un
    DICOM Deflated escrito por pydicom y, detras, la cabecera de la placa sana con
    un Pixel Data de ceros, comprimido a trozos (sin tener nunca los 200 MiB en
    memoria). Leer su cabecera con `stop_before_pixels` lo infla entero (medido:
    pico de 437 MiB). Se comprueba lo que lleva dentro inflando a trozos de 1 MiB,
    antes de que ningun espia este puesto."""
    pequeno = _deflated(tmp_path_factory.mktemp("deflated"))
    assert pequeno[132:136] == b"\x02\x00\x00\x00"                  # (0002,0000)
    fin_0002 = 144 + struct.unpack("<I", pequeno[140:144])[0]
    dentro = zlib.decompress(pequeno[fin_0002:], -zlib.MAX_WBITS)
    pixel_data = dentro.index(b"\xe0\x7f\x10\x00")
    compresor = zlib.compressobj(9, zlib.DEFLATED, -zlib.MAX_WBITS)
    trozos = [compresor.compress(
        dentro[:pixel_data] + b"\xe0\x7f\x10\x00OB\x00\x00"
        + struct.pack("<I", MIB_DENTRO_DEL_DEFLATED * 2**20))]
    un_mib = bytes(2**20)
    trozos += [compresor.compress(un_mib) for _ in range(MIB_DENTRO_DEL_DEFLATED)]
    trozos.append(compresor.flush())
    datos = pequeno[:fin_0002] + b"".join(trozos)
    inflador, resto, inflado = zlib.decompressobj(-zlib.MAX_WBITS), datos[fin_0002:], 0
    while resto:
        inflado += len(inflador.decompress(resto, 2**20))
        resto = inflador.unconsumed_tail
    assert inflado > MIB_DENTRO_DEL_DEFLATED * 2**20
    assert len(datos) < 300 * 1024
    return datos


def test_un_deflated_con_cientos_de_mib_dentro_se_rechaza_sin_inflarlo(
        deflated_con_cientos_de_mib, monkeypatch, nadie_infla, nadie_descodifica):
    """La sintaxis se mira en el grupo 0002, que nunca va comprimido, ANTES de
    cualquier `dcmread` del conjunto de datos: ni se lee (los espias de
    `dcmread` y de `read_partial`, que es donde pydicom infla), ni se infla (el
    de zlib), y el pico de memoria se queda en nada."""
    lecturas = []

    def espia(nombre):
        def no_leas(*args, **kwargs):
            lecturas.append(nombre)
            raise AssertionError(f"no se tenia que llamar a {nombre}")
        return no_leas

    monkeypatch.setattr(pydicom, "dcmread", espia("pydicom.dcmread"))
    monkeypatch.setattr(pydicom.filereader, "dcmread", espia("filereader.dcmread"))
    monkeypatch.setattr(pydicom.filereader, "read_partial", espia("read_partial"))
    tracemalloc.start()
    try:
        with pytest.raises(PlacaNoEvaluable) as fallo:
            leer_dicom_desde_bytes(deflated_con_cientos_de_mib)
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert fallo.value.motivo == "deflated"
    assert lecturas == [] and nadie_infla == [] and nadie_descodifica == []
    assert pico < 4 * 2**20, f"pico de {pico / 2**20:.1f} MiB"


# --------------------------------------------------------------------------
# Los campos de la imagen repetidos DETRAS del Pixel Data (ronda 1, I1)
# --------------------------------------------------------------------------
def _us(grupo, elemento, valor):
    """Un elemento US de Explicit VR Little Endian, ya codificado."""
    return struct.pack("<HH", grupo, elemento) + b"US" + struct.pack("<HH", 2, valor)


def _cs(grupo, elemento, texto):
    """Un elemento CS de Explicit VR Little Endian, ya codificado (longitud par)."""
    valor = texto.encode("ascii")
    valor += b" " * (len(valor) % 2)
    return struct.pack("<HH", grupo, elemento) + b"CS" + struct.pack("<H", len(valor)) + valor


def _bomba_detras_de_una_rle(tmp_path):
    """Una placa sana en RLE con `Rows` y `Columns` de 60 000 escritos OTRA VEZ detras
    del Pixel Data, que es el ultimo elemento: un DICOM no conforme. La cabecera leida
    hasta el Pixel Data dice 64 x 64; la lectura entera, 60 000 x 60 000, y con ella el
    descodificador de RLE reservaria 3,35 GiB (el revisor lo vio tumbar el contenedor
    del servidor con su limite de 2 GiB)."""
    sana = _placa(tmp_path, lambda ds: ds.compress(RLELossless, PIXELES_DE_LA_PLACA),
                  "rle.dcm")
    return sana + _us(0x0028, 0x0010, 60000) + _us(0x0028, 0x0011, 60000)


def _invertida_detras(tmp_path):
    """Una placa sana con `PhotometricInterpretation` MONOCHROME1 escrito otra vez
    detras del Pixel Data: sin mirar el conjunto entero, recibia una cifra."""
    return _placa(tmp_path) + _cs(0x0028, 0x0004, "MONOCHROME1")


# (identificador, como se fabrica, lo que dice la lectura entera, motivo, datos, texto)
REPETIDOS_DETRAS = [
    ("60000x60000_detras_de_una_rle", _bomba_detras_de_una_rle, ("Rows", 60000),
     "tamano", {"filas": 60000, "columnas": 60000}, _tamano(60000, 60000)),
    ("monochrome1_detras", _invertida_detras, ("PhotometricInterpretation", "MONOCHROME1"),
     "fotometria", {}, INVERTIDA),
]


@pytest.mark.parametrize("hacer, campo_y_valor, motivo, datos, texto",
                         [r[1:] for r in REPETIDOS_DETRAS],
                         ids=[r[0] for r in REPETIDOS_DETRAS])
def test_un_campo_repetido_detras_del_pixel_data_no_se_salta_la_regla(
        tmp_path, nadie_descodifica, nadie_infla, hacer, campo_y_valor, motivo, datos,
        texto):
    """Lo que se descodifica sale de la lectura ENTERA, donde la ultima aparicion de un
    campo pisa a la primera: la regla se mira tambien ahi, despues de `sin_pixeles` y
    antes de `pixel_array`. Sin descodificar un pixel y sin subir la memoria."""
    placa = hacer(tmp_path)
    # Lo que hace la trampa: la cabecera hasta el Pixel Data esta en regla (la primera
    # mirada la deja pasar) y la lectura entera ve otra cosa.
    assert comprobar_que_se_puede_evaluar(placa) is None
    campo, valor = campo_y_valor
    assert pydicom.dcmread(io.BytesIO(placa)).get(campo) == valor
    tracemalloc.start()
    try:
        with pytest.raises(PlacaNoEvaluable) as fallo:
            leer_dicom_desde_bytes(placa)
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert fallo.value.motivo == motivo
    assert {clave: getattr(fallo.value, clave) for clave in datos} == datos
    assert str(fallo.value) == texto
    assert nadie_descodifica == [] and nadie_infla == []
    assert pico < 4 * 2**20, f"pico de {pico / 2**20:.1f} MiB"


# --------------------------------------------------------------------------
# Las sintaxis comprimidas: las de siempre se leen, y sin descodificador, rechazo
# (ronda 1, M2)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("cambiar, sin_perdida", [
    (lambda ds: setattr(ds.file_meta, "TransferSyntaxUID", ImplicitVRLittleEndian), True),
    (lambda ds: ds.compress(RLELossless, PIXELES_DE_LA_PLACA), True),
    (lambda ds: _comprimida(JPEGBaseline8Bit, _jpeg())(ds), False),
    (lambda ds: _comprimida(JPEGExtended12Bit, _jpeg())(ds), False),
    (lambda ds: _comprimida(JPEG2000Lossless, _j2k())(ds), True),
    (lambda ds: _comprimida(JPEG2000, _j2k(sin_perdida=False))(ds), False),
], ids=["implicit_vr_little_endian", "rle", "jpeg_baseline", "jpeg_extended",
        "jpeg2000_sin_perdida", "jpeg2000"])
def test_las_sintaxis_de_siempre_pasan_la_regla_y_se_leen(tmp_path, cambiar,
                                                          sin_perdida):
    """Que el rechazo por falta de descodificador no se lleve ninguna placa valida: las
    sin comprimir, RLE, JPEG Baseline y Extended y JPEG 2000 tienen con que leerse (RSNA
    es JPEG Baseline; los ejemplos de la app, Explicit VR Little Endian), y la placa que
    sale es la de siempre: igual pixel a pixel si la sintaxis no pierde nada."""
    datos = _placa(tmp_path, cambiar)
    assert comprobar_que_se_puede_evaluar(datos) is None
    arreglo, _ = leer_dicom_desde_bytes(datos)
    assert arreglo.dtype == np.uint8 and arreglo.shape == (64, 64)
    if sin_perdida:
        assert np.array_equal(arreglo, PIXELES_DE_LA_PLACA)


@pytest.mark.parametrize("sintaxis", [ExplicitVRLittleEndian, ImplicitVRLittleEndian,
                                      ExplicitVRBigEndian, RLELossless, JPEGBaseline8Bit,
                                      JPEGExtended12Bit, JPEG2000Lossless, JPEG2000])
def test_las_sintaxis_de_siempre_tienen_descodificador_aqui(sintaxis):
    """Lo que la regla le pregunta a pydicom, para cada sintaxis que tiene que seguir
    leyendose. (Explicit VR Big Endian no se puede fabricar con pydicom 3, que no
    convierte de una a otra; se mira solo su descodificador.)"""
    assert pydicom.pixels.get_decoder(sintaxis).is_available


@pytest.mark.parametrize("sintaxis, fragmento", [
    (JPEGLSLossless, _jpeg), (JPEGLosslessSV1, _jpeg), (HTJ2KLossless, _j2k)],
    ids=["jpeg_ls", "jpeg_lossless", "htj2k"])
def test_una_sintaxis_sin_su_plugin_se_rechaza_por_la_cabecera(
        tmp_path, nadie_descodifica, sintaxis, fragmento):
    """JPEG-LS, JPEG Lossless y HTJ2K necesitan un plugin que ni la imagen de pruebas
    ni la del servidor llevan: llegaban hasta `pixel_array` y salian con un
    RuntimeError, un 500. Ahora, `compresion`, sin descodificar nada. Donde si hay
    plugin, no hay nada que comprobar."""
    if pydicom.pixels.get_decoder(sintaxis).is_available:
        pytest.skip(f"aquí hay con qué descodificar {sintaxis.name}: no se rechaza")
    datos = _placa(tmp_path, _comprimida(sintaxis, fragmento()))
    for leer in (comprobar_que_se_puede_evaluar, leer_dicom_desde_bytes):
        with pytest.raises(PlacaNoEvaluable) as fallo:
            leer(datos)
        assert (fallo.value.motivo, str(fallo.value)) == ("compresion", COMPRESION)
    assert nadie_descodifica == []


class _SinPlugin:
    is_available = False


def _sin_descodificador(sintaxis):
    raise NotImplementedError(f"ningún descodificador para {sintaxis}")


@pytest.mark.parametrize("get_decoder", [lambda sintaxis: _SinPlugin(),
                                         _sin_descodificador],
                         ids=["sin_plugin", "sin_descodificador"])
def test_sin_con_que_descomprimir_se_rechaza(tmp_path, monkeypatch, get_decoder):
    """La regla, sin depender de lo instalado: si pydicom dice que no hay descodificador
    (`NotImplementedError`) o que no tiene plugin (`is_available`), `compresion`."""
    datos = _placa(tmp_path)
    monkeypatch.setattr(pydicom.pixels, "get_decoder", get_decoder)
    with pytest.raises(PlacaNoEvaluable) as fallo:
        comprobar_que_se_puede_evaluar(datos)
    assert fallo.value.motivo == "compresion"


@pytest.mark.parametrize("tipo, bits, con_signo", [
    (np.int8, 8, True), (np.uint16, 16, False), (np.int16, 16, True),
    (np.float32, 32, False)], ids=["int8", "uint16", "int16", "float32"])
def test_la_segunda_red_para_lo_que_no_sale_uint8(tmp_path, monkeypatch, tipo, bits,
                                                   con_signo):
    """Si con la cabecera en regla pydicom diera otra cosa que `uint8`, la
    segunda red lo para despues de `pixel_array`: lo que no es uint8 el modelo no
    lo ve como las placas de RSNA."""
    datos = _placa(tmp_path)
    monkeypatch.setattr(pydicom.dataset.Dataset, "pixel_array",
                        property(lambda self: np.zeros((64, 64), tipo)))
    with pytest.raises(PlacaNoEvaluable) as fallo:
        leer_dicom_desde_bytes(datos)
    assert (fallo.value.motivo, fallo.value.bits, fallo.value.con_signo) == (
        "bits", bits, con_signo)
    with pytest.raises(PlacaNoEvaluable):
        comprobar_los_pixeles(np.zeros((4, 4), tipo))
    assert comprobar_los_pixeles(np.zeros((4, 4), np.uint8)) is None


def test_leer_dicom_por_ruta_no_aplica_la_regla(tmp_path):
    """`leer_dicom` es la lectura del entrenamiento y del EDA, sobre RSNA, y
    `convertir_a_png` reescala lo que no es uint8: la regla es del servicio, y
    por ruta un DICOM de 16 bits se sigue leyendo tal cual."""
    ruta = tmp_path / "16.dcm"
    ruta.write_bytes(_placa(tmp_path, _de_16_bits()))
    arreglo, _ = leer_dicom(ruta)
    assert arreglo.dtype == np.uint16


# --------------------------------------------------------------------------
# Ningun falso rechazo en RSNA (se salta sin el corpus o sin el dataset)
# --------------------------------------------------------------------------
CORPUS = REPO / "pruebas" / "corpus"


def _lo_que_rechaza(rutas) -> dict:
    """{nombre: motivo} de lo que la regla rechaza entre esas rutas."""
    rechazados = {}
    for ruta in rutas:
        try:
            comprobar_que_se_puede_evaluar(ruta.read_bytes())
        except PlacaNoEvaluable as exc:
            rechazados[ruta.name] = exc.motivo
    return rechazados


def test_la_regla_no_rechaza_ninguna_placa_del_corpus_de_la_sesion(
        rsna_raiz, nadie_descodifica):
    """Las placas de RSNA de los casos del corpus (`pruebas/corpus/`, que no se
    versiona), por su patientId, y las dos fabricadas que siguen siendo placas
    sanas -sin la edad, y con relleno detras-, pasan la regla sin descodificar un
    pixel. La recortada del perfil «fichero corrupto» se rechaza por lo que es:
    trae la cabecera y no la imagen."""
    if not CORPUS.is_dir():
        pytest.skip("CORPUS DE LA SESIÓN SIN COMPROBAR: no está pruebas/corpus/, que "
                    "no se versiona. Se genera con `python "
                    "pruebas/reproducir_casos.py --sin-bots` (con RSNA_RAIZ y el "
                    "copiloto), y se repite.")
    casos = sorted({p.stem for p in CORPUS.glob("*/*.txt")
                    if not p.stem.endswith("-FABRICADO")})
    assert len(casos) >= 40, casos
    crudo = rsna_raiz / "crudo" / "stage_2_train_images"
    fabricados = CORPUS / "_fabricados"
    assert _lo_que_rechaza([crudo / f"{caso}.dcm" for caso in casos]) == {}
    assert _lo_que_rechaza([fabricados / "sin-edad-FABRICADO.dcm",
                            fabricados / "relleno-FABRICADO.dcm"]) == {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with pytest.raises(PlacaNoEvaluable) as fallo:
            leer_dicom_desde_bytes((fabricados / "truncado-FABRICADO.dcm").read_bytes())
    assert fallo.value.motivo == "sin_pixeles"
    assert nadie_descodifica == []


def test_la_regla_no_rechaza_ninguna_placa_del_conjunto_de_prueba_de_rsna(
        rsna_raiz, nadie_descodifica):
    """Las 3 811 placas de prueba de RSNA (`manifiestos/test.csv`) pasan la regla,
    sin descodificar un pixel. La pasada por las 26 684, una vez y fuera de la
    suite, esta en el informe de SP5-B4."""
    with open(rsna_raiz / "manifiestos" / "test.csv", encoding="utf-8") as f:
        casos = [fila["patientId"] for fila in csv.DictReader(f)]
    assert len(casos) > 3000
    crudo = rsna_raiz / "crudo" / "stage_2_train_images"
    assert _lo_que_rechaza([crudo / f"{caso}.dcm" for caso in casos]) == {}
    assert nadie_descodifica == []
