# -*- coding: utf-8 -*-
"""Empaqueta los ejemplos de la app como DICOM (SP5-C1, spec §6).

USO
    python app/empaquetar_ejemplos.py
    python app/empaquetar_ejemplos.py --reducir CARPETA

Sin argumentos lee los PNG de app/assets/originales/ (radiografías reducidas, en
escala de grises de 8 bits) y escribe en app/assets/ejemplos/ los cuatro DICOM de la
app: una radiografía normal en PA, una con opacidad en PA, una en AP y el «rechazado»,
que es la normal con una edad de 15 años para enseñar cómo el motor rechaza lo que
no puede evaluar (`fuera_de_alcance`). Volver a correrlo da los mismos bytes: los UID
salen del nombre de cada ejemplo y no del azar, y la cabecera no lleva fechas ni horas.

Con --reducir rehace antes los PNG desde las descargas de Wikimedia Commons. Espera
en CARPETA los ficheros normal_pa.jpg, neumonia_pa.jpg y neumonia_ap.jpg, comprueba el
SHA-1 de cada uno contra el de su página de origen (app/assets/LICENCIAS.md), baja el
lado mayor a 768 px y los guarda en gris. Reduce los tres en memoria y solo escribe
cuando los tres están bien: uno que no es el de Commons, o que está en color, no deja
nada escrito. Las descargas, de hasta 2765 px, no se versionan: este paso solo hace
falta para rehacer los PNG.

La cabecera de cada DICOM lleva lo que leen el motor y la app (edad, sexo, vista, y
el identificador `EJEMPLO-n`), los UID y lo mínimo de una imagen de 8 bits
MONOCHROME2 sin comprimir. El nombre del paciente va vacío, y no hay ninguna fecha, ni
hora, ni otro dato de paciente o de equipo. La edad y el sexo de las tres imágenes son
los de la persona de cada una según su página de origen; la edad del «rechazado» es
inventada, y LICENCIAS.md lo dice.

Necesita pydicom, Pillow y NumPy; no usa el motor ni el modelo.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import sys
import uuid
from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import UID, ExplicitVRLittleEndian

AQUI = Path(__file__).resolve().parent
CARPETA_ORIGINALES = AQUI / "assets" / "originales"
CARPETA_EJEMPLOS = AQUI / "assets" / "ejemplos"

LADO_MAYOR = 768                      # px: el lado mayor de las imágenes reducidas

# El SHA-1 de cada descarga de Wikimedia Commons, el que da la API de su página de
# origen (las páginas están en LICENCIAS.md). Solo sirve para comprobar que lo que se
# reduce es lo que se dice, no para nada de seguridad.
SHA1_DE_LOS_ORIGINALES = {
    "normal_pa": "3124c4cf4c55eb3d2defa9b909f08f94e941ec43",
    "neumonia_pa": "dcb6d1627f722498e203ba547afcab17d49efa0a",
    "neumonia_ap": "1520e41ffc60375b20d946908cdfc1b1fd8cd61a",
}

SECONDARY_CAPTURE = UID("1.2.840.10008.5.1.4.1.1.7")   # Secondary Capture Image Storage


class Ejemplo(NamedTuple):
    """Un DICOM de la app: de qué PNG sale y qué declara su cabecera."""
    nombre: str          # el del fichero, sin la extensión
    imagen: str          # el PNG de originales/, sin la extensión
    paciente: str        # PatientID
    edad: str            # PatientAge, con el formato de DICOM ("021Y")
    sexo: str            # PatientSex
    vista: str           # ViewPosition


EJEMPLOS = (
    Ejemplo("normal_pa", "normal_pa", "EJEMPLO-1", "021Y", "F", "PA"),
    Ejemplo("neumonia_pa", "neumonia_pa", "EJEMPLO-2", "088Y", "M", "PA"),
    Ejemplo("neumonia_ap", "neumonia_ap", "EJEMPLO-3", "076Y", "F", "AP"),
    # La primera imagen con 15 años: el motor la rechaza (fuera_de_alcance).
    Ejemplo("rechazado_menor", "normal_pa", "EJEMPLO-4", "015Y", "F", "PA"),
)


# --------------------------------------------------------------------------
# Los UID: de un nombre, no del azar
# --------------------------------------------------------------------------
# Un UUID de nombre (versión 5) escrito como UID bajo la raíz 2.25, la que DICOM
# reserva para los UID hechos de un UUID (PS3.5, B.2): no hace falta una raíz propia,
# y el mismo nombre da siempre el mismo UID, así que el guion da siempre los mismos
# bytes.
_ESPACIO_DE_UID = uuid.uuid5(uuid.NAMESPACE_URL, "urn:copiloto-triaje:ejemplos")


def _uid(nombre: str, papel: str) -> UID:
    return UID(f"2.25.{uuid.uuid5(_ESPACIO_DE_UID, f'{nombre}/{papel}').int}")


# --------------------------------------------------------------------------
# De un PNG a un DICOM
# --------------------------------------------------------------------------
def construir_dicom(ejemplo: Ejemplo, pixeles: np.ndarray) -> bytes:
    """Los bytes del DICOM de `ejemplo` con esos píxeles (uint8, 2D).

    Sin compresión, para que el lector del proyecto lo abra sin más. La cabecera es
    la de una captura secundaria de una radiografía de tórax, la misma forma que las
    de RSNA, sin ningún dato que no sea el declarado. Pydicom rellena a un número par
    de bytes la imagen que no lo tenga.
    """
    if pixeles.ndim != 2 or pixeles.dtype != np.uint8:
        raise ValueError(f"{ejemplo.nombre}: los píxeles tienen que ser un arreglo 2D "
                         f"de uint8 y son {pixeles.dtype} de forma {pixeles.shape}")
    ds = Dataset()
    ds.SOPClassUID = SECONDARY_CAPTURE
    ds.SOPInstanceUID = _uid(ejemplo.nombre, "instancia")
    ds.Modality = "CR"
    ds.ConversionType = "WSD"
    ds.PatientName = ""
    ds.PatientID = ejemplo.paciente
    ds.PatientSex = ejemplo.sexo
    ds.PatientAge = ejemplo.edad
    ds.BodyPartExamined = "CHEST"
    ds.ViewPosition = ejemplo.vista
    ds.StudyInstanceUID = _uid(ejemplo.nombre, "estudio")
    ds.SeriesInstanceUID = _uid(ejemplo.nombre, "serie")
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows, ds.Columns = pixeles.shape
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = np.ascontiguousarray(pixeles).tobytes()

    # La implementación, fija: si no, pydicom escribe su versión y los bytes cambian
    # al actualizarlo.
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.ImplementationClassUID = _uid("copiloto-triaje", "implementacion")
    ds.file_meta.ImplementationVersionName = "EJEMPLOS_1"

    salida = io.BytesIO()
    ds.save_as(salida, enforce_file_format=True)
    return salida.getvalue()


def _leer_png(ruta: Path) -> np.ndarray:
    """Los píxeles de un PNG en escala de grises de 8 bits; otra cosa, no."""
    if not ruta.is_file():
        raise FileNotFoundError(f"falta {ruta.name} en {ruta.parent}")
    with Image.open(ruta) as imagen:
        if imagen.mode != "L":
            raise ValueError(f"{ruta.name}: tiene que estar en escala de grises de "
                             f"8 bits (modo L) y está en modo {imagen.mode}")
        imagen.load()
        return np.array(imagen, dtype=np.uint8)


def empaquetar(origen: Path | None = None, destino: Path | None = None) -> list[Path]:
    """Escribe en `destino` el DICOM de cada ejemplo, desde los PNG de `origen`, y
    devuelve sus rutas. Por defecto, las carpetas de la app.

    Los arma todos antes de escribir el primero: un PNG que falta o que no está en
    gris no deja la carpeta a medias.
    """
    origen = CARPETA_ORIGINALES if origen is None else Path(origen)
    destino = CARPETA_EJEMPLOS if destino is None else Path(destino)
    dicoms = {e.nombre: construir_dicom(e, _leer_png(origen / f"{e.imagen}.png"))
              for e in EJEMPLOS}
    destino.mkdir(parents=True, exist_ok=True)
    rutas = []
    for nombre, datos in dicoms.items():
        ruta = destino / f"{nombre}.dcm"
        ruta.write_bytes(datos)
        rutas.append(ruta)
    return rutas


# --------------------------------------------------------------------------
# De una descarga de Commons a un PNG
# --------------------------------------------------------------------------
def _en_gris(imagen: Image.Image, nombre: str) -> Image.Image:
    """La imagen en modo L. Las descargas de Commons son JPEG con los tres canales
    iguales: se toma el canal tal cual, sin reponderar. Una imagen en color no es
    una radiografía de estas, y se rechaza."""
    if imagen.mode == "L":
        return imagen.copy()
    if imagen.mode == "RGB":
        canales = np.asarray(imagen)
        if (np.array_equal(canales[..., 0], canales[..., 1])
                and np.array_equal(canales[..., 1], canales[..., 2])):
            return Image.fromarray(np.ascontiguousarray(canales[..., 0]))
    raise ValueError(f"{nombre}: no es una imagen en escala de grises (es de modo "
                     f"{imagen.mode}, o sus canales no son iguales)")


def _escalado(lado: int, mayor: int) -> int:
    """`lado` reducido en la proporción que lleva `mayor` a LADO_MAYOR, redondeado
    en enteros (sin pasar por coma flotante) y nunca por debajo de 1."""
    return max(1, (lado * LADO_MAYOR + mayor // 2) // mayor)


def _reducida(origen: Path, sha1_esperado: str) -> Image.Image:
    """La descarga de `origen` ya reducida, en memoria: comprueba su SHA-1, la pasa a
    escala de grises de 8 bits y baja el lado mayor a 768 px (LANCZOS). Una imagen
    que ya cabe no se amplía. No escribe nada."""
    datos = origen.read_bytes()
    sha1 = hashlib.sha1(datos, usedforsecurity=False).hexdigest()
    if sha1 != sha1_esperado:
        raise ValueError(f"{origen.name}: su SHA-1 es {sha1} y el de su página de "
                         f"origen es {sha1_esperado}: no es esa descarga")
    with Image.open(io.BytesIO(datos)) as imagen:
        gris = _en_gris(imagen, origen.name)
    ancho, alto = gris.size
    mayor = max(ancho, alto)
    if mayor > LADO_MAYOR:
        gris = gris.resize((_escalado(ancho, mayor), _escalado(alto, mayor)),
                           Image.Resampling.LANCZOS)
    return gris


def _guardar_png(imagen: Image.Image, destino: Path) -> None:
    """Un PNG sin ningún trozo auxiliar (ni dpi, ni texto, ni fecha)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagen.save(destino, format="PNG", optimize=True)


def reducir_original(origen: Path, destino: Path, sha1_esperado: str) -> None:
    """De una descarga de Commons al PNG `destino`: la reduce (ver `_reducida`) y la
    guarda. Si el SHA-1 o los canales no cuadran, no escribe nada."""
    _guardar_png(_reducida(Path(origen), sha1_esperado), Path(destino))


def reducir_originales(descargas: Path, destino: Path | None = None) -> list[Path]:
    """De las tres descargas de Commons que hay en `descargas` (normal_pa.jpg,
    neumonia_pa.jpg y neumonia_ap.jpg) a los tres PNG de `destino` (por defecto,
    originales/), y devuelve sus rutas.

    Las reduce las tres en memoria y solo escribe cuando las tres están bien, como
    `empaquetar` con los DICOM: una descarga que no es la de Commons (otro SHA-1) o que
    está en color no deja en `destino` unos PNG nuevos mezclados con los de antes.
    """
    destino = CARPETA_ORIGINALES if destino is None else Path(destino)
    reducidas = {nombre: _reducida(Path(descargas) / f"{nombre}.jpg", sha1)
                 for nombre, sha1 in SHA1_DE_LOS_ORIGINALES.items()}
    rutas = []
    for nombre, imagen in reducidas.items():
        ruta = destino / f"{nombre}.png"
        _guardar_png(imagen, ruta)
        rutas.append(ruta)
    return rutas


# --------------------------------------------------------------------------
# La línea de órdenes
# --------------------------------------------------------------------------
def principal(argumentos: list[str] | None = None) -> int:
    analizador = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    analizador.add_argument(
        "--reducir", type=Path, metavar="CARPETA",
        help="antes de empaquetar, rehace los PNG de originales/ desde las "
             "descargas de Commons que hay en CARPETA")
    opciones = analizador.parse_args(argumentos)
    try:
        if opciones.reducir is not None:
            for ruta in reducir_originales(opciones.reducir):
                print(f"reducida: {ruta.name}")
        for ruta in empaquetar():
            print(f"empaquetado: {ruta.name} ({ruta.stat().st_size} bytes)")
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(principal())
