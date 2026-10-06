"""Lectura de DICOM de RSNA y conversion a PNG.

Verificado el 16-sep-2026: los DICOM de RSNA vienen en uint8 con
PhotometricInterpretation MONOCHROME2, de modo que la conversion es
directa. El reescalado solo actua como red de seguridad si algun archivo
llegara con otra profundidad de bits.

Y la regla de lo que el MOTOR puede evaluar (SP5-B4),
`comprobar_que_se_puede_evaluar`, en UN solo sitio: la aplica
`leer_dicom_desde_bytes`, el lector del servidor y de la app, antes de
descodificar un solo pixel. `leer_dicom`, el del entrenamiento y el EDA sobre
RSNA, no la aplica.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pydicom
import pydicom.errors
import pydicom.filereader
import pydicom.uid
from PIL import Image

CAMPOS = {
    "patientId": "PatientID",
    "edad": "PatientAge",
    "sexo": "PatientSex",
    "vista": "ViewPosition",
}


def _extraer_metadatos(ds) -> dict:
    """Extrae metadatos de un dataset pydicom."""
    meta = {clave: str(getattr(ds, campo, "")) for clave, campo in CAMPOS.items()}
    meta["filas"] = int(getattr(ds, "Rows", 0))
    meta["columnas"] = int(getattr(ds, "Columns", 0))
    return meta


# --------------------------------------------------------------------------
# Lo que el motor puede evaluar (SP5-B4)
# --------------------------------------------------------------------------
# El motor convierte la placa con `Image.fromarray(arreglo).convert("RGB")`, y el
# modelo se entreno con las de RSNA: 8 bits sin signo, MONOCHROME2, una muestra
# por pixel y un cuadro. Lo demas lo veria mal y daria una cifra que no vale: con
# mas de 8 bits, `convert` satura casi a blanco todo lo que pasa de 255 (medido:
# una neumonia en 16 bits baja de 0,91 a 0,48, y el mapa cae fuera del pulmon), y
# el entrenamiento convertia esos casos con min-max, un desajuste entre
# entrenamiento y servicio; una MONOCHROME1 la veria al reves. Y `pixel_array` no
# lleva tope de memoria: reserva lo que declara la cabecera antes de mirar nada.
BITS_DE_LA_PLACA = 8
FOTOMETRIA_DE_LA_PLACA = "MONOCHROME2"
# Un lado de mas de 5000 pixeles no es una placa de torax digital (rondan los
# 4300 x 4300): con 8 bits, una muestra y un cuadro, lo mas que se descodifica son
# 25 MB. Sin tope, unos 600 bytes en RLE que declaran 60 000 x 60 000 hacen
# reservar 3,4 GiB, y el contenedor del bot muere y se reinicia.
LADO_MAXIMO_DE_LA_PLACA = 5000
# Un cuadro, por lo mismo -5000 x 5000 por miles de cuadros tambien se reserva
# entero- y porque el modelo evalua una placa sola.
CUADROS_MAXIMOS = 1
# Lo que pydicom necesita para descodificar la imagen: sin uno de estos campos,
# o con uno vacio, `pixel_array` lanza un AttributeError (medido con pydicom
# 3.0.2), que el motor no traduce a proposito.
CAMPOS_DE_LA_IMAGEN = ("Rows", "Columns", "BitsAllocated", "BitsStored",
                       "SamplesPerPixel", "PhotometricInterpretation",
                       "PixelRepresentation")

# El texto de cada motivo: NUESTRO, de una plantilla con solo enteros dentro. Nunca
# lleva texto de pydicom ni bytes del fichero, porque el servidor lo devuelve (el
# motor le antepone «La placa no se puede evaluar: ») y el bot lo registra. Va en
# castellano con sus tildes: lo lee una persona. La app no lo ensena: traduce el
# motivo a sus propios mensajes.
_TEXTOS = {
    "sin_metainformacion": (
        "el fichero no trae la metainformación de un DICOM (el grupo 0002, con una "
        "sintaxis de transferencia que se conozca), así que no se sabe cómo leerlo."),
    "deflated": (
        "el fichero viene comprimido entero (en DICOM, «Deflated Explicit VR Little "
        "Endian»), y no se descomprime: podría ocupar cientos de veces lo que pesa."),
    "cabecera_incompleta": (
        "a la cabecera le falta alguno de los campos que dicen cómo leer la imagen "
        "(filas, columnas, bits, signo, muestras por píxel o fotometría), o lo trae sin "
        "un valor que se entienda."),
    "tamano": (
        "declara {filas} × {columnas} píxeles, y no se leen placas de más de {lado} de "
        "lado (una placa de tórax digital ronda los 4300 × 4300)."),
    "cuadros": "el fichero trae {cuadros} imágenes, y se evalúa una placa sola.",
    "bits": (
        "es de {bits}, y el modelo solo evalúa placas de 8 bits sin signo, como las de "
        "RSNA con las que se entrenó."),
    "fotometria": (
        "guarda la escala de grises invertida (en DICOM, MONOCHROME1), y el modelo solo "
        "evalúa placas MONOCHROME2, como las de RSNA con las que se entrenó."),
    "color": (
        "no está en escala de grises, y el modelo solo evalúa placas en grises (en "
        "DICOM, MONOCHROME2 con una muestra por píxel), como las de RSNA con las que se "
        "entrenó."),
    "sin_pixeles": ("el fichero trae la cabecera pero no la imagen: puede que esté "
                    "recortado."),
}


class PlacaNoEvaluable(ValueError):
    """Un DICOM que el motor no puede evaluar, decidido sin descodificar un pixel.

    `motivo` es un codigo corto y estable, para que quien llama lo traduzca a sus
    palabras sin interpretar el texto (la app, a los mensajes de su pantalla):

        sin_metainformacion  sin preambulo con «DICM» y grupo 0002 legible, o sin
                             una sintaxis de transferencia que se conozca
        deflated             la sintaxis Deflated: todo el conjunto de datos va
                             comprimido, y leer la cabecera ya lo inflaria entero
        cabecera_incompleta  falta uno de CAMPOS_DE_LA_IMAGEN, esta vacio o no se
                             entiende (o `NumberOfFrames`, si viene, no se entiende)
        tamano               un lado de mas de LADO_MAXIMO_DE_LA_PLACA (`filas`,
                             `columnas`)
        cuadros              mas de CUADROS_MAXIMOS (`cuadros`)
        bits                 no es de 8 bits sin signo (`bits`, `con_signo`)
        fotometria           MONOCHROME1: la escala de grises invertida
        color                no esta en escala de grises: otra fotometria, o mas de
                             una muestra por pixel
        sin_pixeles          la cabecera esta en regla, pero el fichero no trae la
                             imagen (recortado)

    Los datos van como enteros (y `con_signo`, un booleano), y el texto sale de
    `_TEXTOS`: nunca interpola texto de pydicom ni bytes del fichero.
    """

    def __init__(self, motivo: str, *, bits: int | None = None,
                 con_signo: bool = False, filas: int | None = None,
                 columnas: int | None = None, cuadros: int | None = None):
        self.motivo = motivo
        # `int()` y `bool()`: lo que llega de pydicom (un `US`, un `IS`) se queda en
        # un entero y nada mas, que es lo unico que el texto puede llevar.
        self.bits = None if bits is None else int(bits)
        self.con_signo = bool(con_signo)
        self.filas = None if filas is None else int(filas)
        self.columnas = None if columnas is None else int(columnas)
        self.cuadros = None if cuadros is None else int(cuadros)
        bits_en_texto = None if self.bits is None else (
            f"{self.bits} bit{'' if self.bits == 1 else 's'}"
            + (" con signo" if self.con_signo else ""))
        super().__init__(_TEXTOS[motivo].format(
            bits=bits_en_texto, filas=self.filas, columnas=self.columnas,
            cuadros=self.cuadros, lado=LADO_MAXIMO_DE_LA_PLACA))


def _sintaxis_de_transferencia(datos: bytes) -> str | None:
    """La sintaxis de transferencia del fichero, leida SOLO del grupo 0002 -la
    metainformacion, que nunca va comprimida- y sin tocar el conjunto de datos.
    `None` si no la hay: sin el prefijo «DICM», con el grupo cortado o sin ese
    campo.

    Es lo que hace `pydicom.filereader.read_file_meta_info`, que solo acepta una
    ruta: `read_preamble` y `_read_file_meta_info`, que lee elemento a elemento y
    para en el primero que no es del grupo 0002. Es privada, y por eso va con
    `pydicom==3.0.2` fijado; si cambiara, ningun DICOM pasaria de aqui y las
    pruebas lo dirian. (Era `sintaxis_de_transferencia` de la app, SP5-C1.)"""
    try:
        fichero = io.BytesIO(datos)
        pydicom.filereader.read_preamble(fichero, False)
        sintaxis = pydicom.filereader._read_file_meta_info(fichero).get(
            "TransferSyntaxUID")
    except Exception:
        return None
    sintaxis = str(sintaxis or "").strip()
    return sintaxis or None


def comprobar_que_se_puede_evaluar(datos: bytes) -> None:
    """La regla de lo que el motor puede evaluar, decidida SIN descodificar un
    pixel y sin inflar nada: devuelve `None` si la placa se puede leer y el
    modelo la veria como las de RSNA, o lanza `PlacaNoEvaluable` con el motivo.

    Primero la metainformacion (el preambulo y el grupo 0002, que nunca va
    comprimido): sin ella, o si no declara una sintaxis de transferencia que se
    conozca, no se sabe leer el fichero. Con la sintaxis Deflated, TODO el
    conjunto de datos va comprimido con zlib, y pydicom lo infla entero en cuanto
    se le pide la cabecera (un fichero de 214 KiB inflaba cientos de MiB): se
    rechaza sin abrirlo. Despues, la cabecera, leida con `stop_before_pixels`:
    `comprobar_la_cabecera`.

    Si pydicom no sabe leer la cabecera, su excepcion sale tal cual: el motor la
    traduce a `dicom_invalido` con su clausula de siempre, y lo que no es un DICOM
    legible no es asunto de esta regla."""
    sintaxis = _sintaxis_de_transferencia(datos)
    # `is_deflated` lanza ValueError con un UID que no es de transferencia: por eso
    # se mira antes que lo sea.
    if sintaxis is None or not pydicom.uid.UID(sintaxis).is_transfer_syntax:
        raise PlacaNoEvaluable("sin_metainformacion")
    if pydicom.uid.UID(sintaxis).is_deflated:
        raise PlacaNoEvaluable("deflated")
    comprobar_la_cabecera(pydicom.dcmread(io.BytesIO(datos), stop_before_pixels=True))


def _campos_de_la_imagen(cabecera) -> dict | None:
    """Lo que la regla mira de la cabecera, ya como enteros (y la fotometria sin
    espacios y en mayusculas, como la miraba la app), o `None` si falta uno de
    CAMPOS_DE_LA_IMAGEN, esta vacio (pydicom da `None`) o no se entiende. Tambien
    `NumberOfFrames`, que puede faltar: entonces es un cuadro."""
    try:
        valores = {campo: cabecera.get(campo) for campo in CAMPOS_DE_LA_IMAGEN}
        if any(valor is None or valor == "" for valor in valores.values()):
            return None
        cuadros = cabecera.get("NumberOfFrames")
        return {
            "filas": int(valores["Rows"]), "columnas": int(valores["Columns"]),
            "bits": int(valores["BitsAllocated"]),
            "muestras": int(valores["SamplesPerPixel"]),
            "con_signo": int(valores["PixelRepresentation"]) == 1,
            "cuadros": 1 if cuadros in (None, "") else int(cuadros),
            "fotometria": str(valores["PhotometricInterpretation"]).strip().upper(),
        }
    except (TypeError, ValueError):
        return None


def comprobar_la_cabecera(cabecera) -> None:
    """La regla sobre la cabecera ya leida (un `Dataset`, sin los pixeles): los
    campos de CAMPOS_DE_LA_IMAGEN, un lado de LADO_MAXIMO_DE_LA_PLACA como mucho,
    CUADROS_MAXIMOS, 8 bits, MONOCHROME2, una muestra por pixel y sin signo.
    `None`, o `PlacaNoEvaluable`.

    El orden es el de la app (SP5-C1, R27), para que alli cada placa siga
    recibiendo el mensaje de siempre: lo que falta, el tamano y los cuadros (lo
    que reservaria memoria), los bits, la escala invertida y el color. El signo va
    el ultimo -en la app lo paraba la segunda red, con los pixeles ya leidos-, asi
    que una placa con signo Y otra cosa recibe el motivo de esa otra cosa."""
    campos = _campos_de_la_imagen(cabecera)
    if campos is None:
        raise PlacaNoEvaluable("cabecera_incompleta")
    if (campos["filas"] > LADO_MAXIMO_DE_LA_PLACA
            or campos["columnas"] > LADO_MAXIMO_DE_LA_PLACA):
        raise PlacaNoEvaluable("tamano", filas=campos["filas"],
                               columnas=campos["columnas"])
    if campos["cuadros"] > CUADROS_MAXIMOS:
        raise PlacaNoEvaluable("cuadros", cuadros=campos["cuadros"])
    if campos["bits"] != BITS_DE_LA_PLACA:
        raise PlacaNoEvaluable("bits", bits=campos["bits"],
                               con_signo=campos["con_signo"])
    if campos["fotometria"] == "MONOCHROME1":
        raise PlacaNoEvaluable("fotometria")
    if campos["fotometria"] != FOTOMETRIA_DE_LA_PLACA or campos["muestras"] != 1:
        raise PlacaNoEvaluable("color")
    if campos["con_signo"]:
        raise PlacaNoEvaluable("bits", bits=campos["bits"], con_signo=True)


def comprobar_los_pixeles(arreglo: np.ndarray) -> None:
    """La segunda red, ya con los pixeles: lo que no sale `uint8` el modelo no lo
    ve como las placas de RSNA. Con la cabecera en regla no deberia pasar (8 bits
    sin signo dan `uint8`); si pasa, `PlacaNoEvaluable` con los bits del arreglo."""
    if arreglo.dtype != np.uint8:
        raise PlacaNoEvaluable(
            "bits", bits=arreglo.dtype.itemsize * 8,
            con_signo=np.issubdtype(arreglo.dtype, np.signedinteger))


def leer_dicom(ruta: Path) -> tuple[np.ndarray, dict]:
    """Devuelve (pixeles, metadatos) de un DICOM."""
    ds = pydicom.dcmread(str(ruta))
    meta = _extraer_metadatos(ds)
    return ds.pixel_array, meta


def leer_dicom_desde_bytes(datos: bytes) -> tuple[np.ndarray, dict]:
    """Igual que `leer_dicom` pero desde memoria, y solo si el motor puede
    evaluar la placa.

    El servidor de SP2 recibe el DICOM por la red. Escribirlo a un fichero
    temporal solo para volver a leerlo seria un viaje al disco por peticion,
    y dejaria restos que limpiar si el proceso muere a mitad.

    SP5-B4: antes de nada, `comprobar_que_se_puede_evaluar`, sin descodificar un
    pixel. Despues se lee entero, y si no trae la imagen -un fichero recortado:
    pydicom lo lee sin el Pixel Data, y `pixel_array` lanzaria un
    AttributeError- es `sin_pixeles`. Y tras `pixel_array`, la segunda red:
    `comprobar_los_pixeles`. Todo rechazo es `PlacaNoEvaluable`; lo que pydicom no
    sabe leer sale con su excepcion de siempre. Para una placa que pasa, lo que
    devuelve es lo de antes, byte a byte.
    """
    comprobar_que_se_puede_evaluar(datos)
    ds = pydicom.dcmread(io.BytesIO(datos))
    if "PixelData" not in ds:
        raise PlacaNoEvaluable("sin_pixeles")
    arreglo = ds.pixel_array
    comprobar_los_pixeles(arreglo)
    return arreglo, _extraer_metadatos(ds)


def _leer_metadatos_dicom(ruta: Path) -> dict:
    """Lee solo metadatos de un DICOM sin decodificar píxeles."""
    ds = pydicom.dcmread(str(ruta), stop_before_pixels=True)
    return _extraer_metadatos(ds)


def _png_legible(ruta_png: Path) -> bool:
    """Un PNG existe y esta COMPLETO.

    Descodifica de verdad (`load()`) en vez de `verify()`. verify() recorre
    los chunks y detecta la mayoria de los truncados, pero la unica prueba
    que vale es la operacion que hace el entrenamiento al leer la imagen: si
    esta funcion dice que si y el DataLoader revienta con "image file is
    truncated", la comprobacion no sirve de nada. Cuesta mas, y es el precio
    correcto: el fallo alternativo aparece horas despues, a mitad de un
    entrenamiento, y obliga a repetirlo.
    """
    try:
        with Image.open(ruta_png) as imagen:
            imagen.load()
        return True
    except Exception:
        # Cualquier fallo al abrirlo o descodificarlo significa lo mismo para
        # quien llama: hay que reconvertirlo.
        return False


def convertir_a_png(ruta_dcm: Path, ruta_png: Path) -> dict:
    """Convierte un DICOM a PNG de 8 bits y devuelve sus metadatos."""
    arr, meta = leer_dicom(ruta_dcm)
    if arr.dtype != np.uint8:
        minimo, maximo = int(arr.min()), int(arr.max())
        rango = max(maximo - minimo, 1)
        arr = ((arr.astype(np.float32) - minimo) / rango * 255).astype(np.uint8)
    ruta_png.parent.mkdir(parents=True, exist_ok=True)
    # Escritura ATOMICA: al temporal primero y luego os.replace, que en POSIX
    # es atomico. Guardar directo sobre el destino final significa que un
    # corte a mitad -disco lleno, runtime reciclado- deja un PNG truncado CON
    # EL NOMBRE DEFINITIVO, y a partir de ahi nadie lo distingue de uno bueno:
    # el entrenamiento reventaba horas despues con "image file is truncated".
    # Con el temporal, una escritura interrumpida deja un .tmp que no se
    # confunde con nada y el destino final o esta completo o no esta.
    temporal = ruta_png.with_name(ruta_png.name + ".tmp")
    try:
        Image.fromarray(arr).save(temporal, format="PNG")
        os.replace(temporal, ruta_png)
    finally:
        temporal.unlink(missing_ok=True)
    meta["archivo_png"] = ruta_png.name
    return meta


def convertir_lote(rutas_dcm, dir_png: Path) -> tuple[list[dict], list[dict]]:
    """Convierte una lista de DICOM. Un archivo ilegible se omite y se
    registra, pero nunca aborta el proceso: una perdida silenciosa de datos
    seria peor que un fallo ruidoso.

    Es idempotente: si el PNG ya existe Y SE PUEDE LEER, no lo reescribe. La
    comprobacion de lectura no sobra: con `destino.exists()` a secas, un PNG
    truncado por una escritura interrumpida se daba por convertido en cada
    reintento y no habia forma de repararlo salvo borrandolo a mano.
    """
    dir_png = Path(dir_png)
    dir_png.mkdir(parents=True, exist_ok=True)
    convertidos: list[dict] = []
    omitidos: list[dict] = []
    for ruta in rutas_dcm:
        ruta = Path(ruta)
        destino = dir_png / (ruta.stem + ".png")
        try:
            if destino.exists() and _png_legible(destino):
                meta = _leer_metadatos_dicom(ruta)
                meta["archivo_png"] = destino.name
            else:
                meta = convertir_a_png(ruta, destino)
            convertidos.append(meta)
        # TypeError esta en la lista porque un tag PRESENTE pero VACIO existe
        # en DICOM y devuelve None: `int(getattr(ds, "Rows", 0))` con Rows
        # vacio no lanza ValueError sino TypeError. Un solo archivo asi
        # abortaba a mitad una conversion de 21 minutos sobre los 26 684
        # DICOM de RSNA, que es exactamente lo que este try existe para
        # impedir. No se anade el TypeError a costa de la regla de la Tarea 4:
        # los errores de PROGRAMACION (NameError, AttributeError...) siguen
        # propagandose ruidosamente en vez de camuflarse como "omitidos".
        except (pydicom.errors.InvalidDicomError, OSError, ValueError,
                TypeError) as exc:
            omitidos.append({"archivo": ruta.name, "motivo": f"{type(exc).__name__}: {exc}"})
    return convertidos, omitidos
