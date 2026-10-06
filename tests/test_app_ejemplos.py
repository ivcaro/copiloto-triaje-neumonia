# -*- coding: utf-8 -*-
"""Los ejemplos de la app (SP5-C1, spec §6): `app/empaquetar_ejemplos.py`, las
imágenes de `app/assets/originales/`, los DICOM de `app/assets/ejemplos/` y
`app/assets/LICENCIAS.md`.

QUÉ VIGILA
- Cada DICOM se lee con el lector del proyecto, declara la edad, el sexo y la vista
  que dice LICENCIAS.md y no lleva nada más de paciente: ningún nombre, ninguna
  fecha ni hora, ningún otro identificador que el `EJEMPLO-n`. Hay uno por tipo
  (normal en PA, opacidad en PA y una AP) y el «rechazado», con 15 años.
- Cada uno tiene en LICENCIAS.md su fuente, su autor, su licencia y su atribución, y
  el documento avisa de que no son de RSNA ni del NIH y de que el modelo no se ha
  medido con ellos.
- Se pueden rehacer: volver a empaquetar los PNG da los mismos bytes, los píxeles
  del DICOM son los del PNG y el guion sabe reducir las descargas de Commons (con la
  comprobación de su SHA-1).
- El motor acepta a los tres adultos y rechaza al menor con `fuera_de_alcance`.

Los valores esperados están escritos aquí a mano, no sacados de la tabla del guion:
una tabla equivocada no puede dar por buena a la prueba que la comprueba.
"""
import hashlib
import importlib.util
import io
import re
import sys
from pathlib import Path

import numpy as np
import pydicom
import pytest
from PIL import Image
from pydicom.uid import UID

from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes

REPO = Path(__file__).resolve().parents[1]
GUION = REPO / "app" / "empaquetar_ejemplos.py"
CARPETA_EJEMPLOS = REPO / "app" / "assets" / "ejemplos"
CARPETA_ORIGINALES = REPO / "app" / "assets" / "originales"
LICENCIAS = REPO / "app" / "assets" / "LICENCIAS.md"
CALIBRADOR = REPO / "servidor" / "calibrador.json"

LADO_MAYOR = 768
UN_MEGA = 1024 * 1024

# Los cuatro ejemplos, en el orden de la app.
EJEMPLOS = ("normal_pa", "neumonia_pa", "neumonia_ap", "rechazado_menor")
IMAGENES = ("normal_pa", "neumonia_pa", "neumonia_ap")      # las de originales/
# De qué imagen sale cada DICOM: el «rechazado» es la primera con otra edad.
IMAGEN_DE = {"normal_pa": "normal_pa", "neumonia_pa": "neumonia_pa",
             "neumonia_ap": "neumonia_ap", "rechazado_menor": "normal_pa"}
# Lo que la cabecera de cada uno declara: (PatientID, PatientAge, PatientSex,
# ViewPosition). Las edades y los sexos son los de la persona de cada imagen según
# su página de origen; la del «rechazado» es inventada, a propósito.
CABECERA = {
    "normal_pa": ("EJEMPLO-1", "021Y", "F", "PA"),
    "neumonia_pa": ("EJEMPLO-2", "088Y", "M", "PA"),
    "neumonia_ap": ("EJEMPLO-3", "076Y", "F", "AP"),
    "rechazado_menor": ("EJEMPLO-4", "015Y", "F", "PA"),
}
# (ancho, alto) de cada PNG reducido: lo que sale de bajar el lado mayor a 768.
TAMANOS = {"normal_pa": (671, 768), "neumonia_pa": (768, 667),
           "neumonia_ap": (768, 696)}
# Lo que Commons da de cada descarga y se anota en LICENCIAS.md.
SHA1 = {"normal_pa": "3124c4cf4c55eb3d2defa9b909f08f94e941ec43",
        "neumonia_pa": "dcb6d1627f722498e203ba547afcab17d49efa0a",
        "neumonia_ap": "1520e41ffc60375b20d946908cdfc1b1fd8cd61a"}
PAGINAS = {
    "normal_pa": "https://commons.wikimedia.org/wiki/File:"
                 "Normal_posteroanterior_(PA)_chest_radiograph_(X-ray).jpg",
    "neumonia_pa": "https://commons.wikimedia.org/wiki/File:"
                   "Chest_radiograph_in_influensa_and_H_influenzae,_posteroanterior.jpg",
    "neumonia_ap": "https://commons.wikimedia.org/wiki/File:"
                   "Chest_X-ray_in_influenza_and_Haemophilus_influenzae.jpg",
}
FICHEROS_ORIGINALES = {
    "normal_pa": "Normal posteroanterior (PA) chest radiograph (X-ray).jpg",
    "neumonia_pa": "Chest radiograph in influensa and H influenzae, posteroanterior.jpg",
    "neumonia_ap": "Chest X-ray in influenza and Haemophilus influenzae.jpg",
}
LITERAL_DE_LA_LICENCIA = ("This file is made available under the Creative Commons "
                          "CC0 1.0 Universal Public Domain Dedication.")
CREDITO = "Mikael Häggström, vía Wikimedia Commons, CC0 1.0"

# Las etiquetas de LICENCIAS.md: `- **Etiqueta:** valor`, en la sección de cada DICOM.
ETIQUETAS = ("Qué muestra", "Imagen original", "Página de origen", "Autor", "Licencia",
             "Atribución", "SHA-1 del original", "Qué se cambió", "Edad en el DICOM",
             "Sexo en el DICOM", "Vista en el DICOM")

SECONDARY_CAPTURE = "1.2.840.10008.5.1.4.1.1.7"
# Los UID que cambian de un ejemplo a otro: se miran aparte.
UID_DE_LA_CABECERA = ("SOPInstanceUID", "StudyInstanceUID", "SeriesInstanceUID")
# Lo demás de la cabecera, entero y sin más. `Rows` y `Columns` los pone la imagen.
CABECERA_COMUN = {
    "SOPClassUID": SECONDARY_CAPTURE, "Modality": "CR", "ConversionType": "WSD",
    "PatientName": "", "BodyPartExamined": "CHEST", "SamplesPerPixel": 1,
    "PhotometricInterpretation": "MONOCHROME2", "BitsAllocated": 8,
    "BitsStored": 8, "HighBit": 7, "PixelRepresentation": 0,
}
ETIQUETAS_DE_FILE_META = {
    "FileMetaInformationGroupLength", "FileMetaInformationVersion",
    "MediaStorageSOPClassUID", "MediaStorageSOPInstanceUID", "TransferSyntaxUID",
    "ImplementationClassUID", "ImplementationVersionName",
}
# Lo que no puede aparecer ni en el guion ni en LICENCIAS.md ni en un DICOM: la
# ruta de una máquina (unidad de Windows, carpetas de usuario, OneDrive).
RUTA_DE_UNA_MAQUINA = r"(?i)[a-z]:\\|/users/|/home/|appdata|onedrive"


# --------------------------------------------------------------------------
# Lo que se carga
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def guion():
    """`app/empaquetar_ejemplos.py` cargado por ruta: `app/` no es un paquete."""
    spec = importlib.util.spec_from_file_location("empaquetar_ejemplos", GUION)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["empaquetar_ejemplos"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _datos(nombre):
    return (CARPETA_EJEMPLOS / f"{nombre}.dcm").read_bytes()


def _leer(nombre):
    return pydicom.dcmread(io.BytesIO(_datos(nombre)))


def _licencias():
    """{`fichero.dcm`: {etiqueta: valor}} de LICENCIAS.md: cada sección de nivel 2
    cuyo título es un fichero entre acentos graves lleva viñetas `- **Etiqueta:**
    valor`."""
    secciones, actual = {}, None
    for linea in LICENCIAS.read_text(encoding="utf-8").splitlines():
        if linea.startswith("## "):
            titulo = re.fullmatch(r"## `([\w.-]+\.dcm)`", linea)
            actual = secciones.setdefault(titulo.group(1), {}) if titulo else None
            continue
        campo = re.fullmatch(r"- \*\*([^*]+?):\*\* (.+)", linea)
        if campo and actual is not None:
            actual[campo.group(1)] = campo.group(2).strip()
    return secciones


def _texto_plano(valor):
    """El valor de una viñeta sin el formato de código: `021Y` -> 021Y."""
    return valor.strip().strip("`")


def _sha1(ruta):
    return hashlib.sha1(Path(ruta).read_bytes()).hexdigest()


def _jpeg(carpeta, nombre, ancho, alto, color=None):
    """Una imagen de juguete guardada como JPEG: un degradado en gris, con los
    tres canales iguales como las descargas de Commons, o de un color."""
    if color is None:
        gris = np.tile(np.linspace(0, 255, ancho).astype(np.uint8), (alto, 1))
        imagen = Image.fromarray(gris).convert("RGB")
    else:
        imagen = Image.new("RGB", (ancho, alto), color)
    ruta = Path(carpeta) / nombre
    imagen.save(ruta, format="JPEG", quality=95)
    return ruta


# --------------------------------------------------------------------------
# Lo que hay en las carpetas
# --------------------------------------------------------------------------
def test_las_carpetas_llevan_justo_los_ejemplos():
    assert sorted(p.name for p in CARPETA_EJEMPLOS.iterdir()) == sorted(
        f"{n}.dcm" for n in EJEMPLOS)
    assert sorted(p.name for p in CARPETA_ORIGINALES.iterdir()) == sorted(
        f"{n}.png" for n in IMAGENES)


def test_las_descargas_grandes_no_se_versionan():
    """Las originales de Commons (hasta 2765 px) no viajan: solo las reducidas."""
    grandes = [p.relative_to(REPO).as_posix()
               for p in (REPO / "app").rglob("*")
               if p.suffix.lower() in {".jpg", ".jpeg", ".tif", ".tiff"}]
    assert grandes == []


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_cada_ejemplo_pesa_poco(nombre):
    """El repositorio los versiona, y la app los sube al motor como un DICOM más
    (el servidor admite hasta 5 MB; aquí el tope es de 1 MiB, para que ninguno se
    sustituya sin darse cuenta por una placa a su resolución original)."""
    assert 0 < len(_datos(nombre)) <= UN_MEGA


@pytest.mark.parametrize("nombre", IMAGENES)
def test_cada_imagen_es_un_png_en_gris_de_768_px_y_sin_metadatos(nombre):
    ruta = CARPETA_ORIGINALES / f"{nombre}.png"
    assert 0 < ruta.stat().st_size <= UN_MEGA
    with Image.open(ruta) as imagen:
        imagen.load()
        assert imagen.format == "PNG" and imagen.mode == "L"
        assert imagen.size == TAMANOS[nombre]
        assert max(imagen.size) == LADO_MAYOR
        assert imagen.info == {}                 # ni dpi, ni texto, ni perfil


# --------------------------------------------------------------------------
# El DICOM, con el lector del proyecto
# --------------------------------------------------------------------------
@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_cada_dicom_se_lee_con_el_lector_del_proyecto(nombre):
    arreglo, meta = leer_dicom_desde_bytes(_datos(nombre))
    assert arreglo.dtype == np.uint8 and arreglo.ndim == 2
    assert max(arreglo.shape) == LADO_MAYOR
    assert (meta["filas"], meta["columnas"]) == arreglo.shape
    # una radiografía, no una imagen plana ni a medio tono
    assert len(np.unique(arreglo)) > 200
    assert arreglo.min() < 20 and arreglo.max() > 235
    assert 40 < arreglo.mean() < 215


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_cada_dicom_declara_la_edad_el_sexo_y_la_vista_de_licencias(nombre):
    _, meta = leer_dicom_desde_bytes(_datos(nombre))
    paciente, edad, sexo, vista = CABECERA[nombre]
    assert (meta["patientId"], meta["edad"], meta["sexo"], meta["vista"]) == (
        paciente, edad, sexo, vista)
    seccion = _licencias()[f"{nombre}.dcm"]
    assert _texto_plano(seccion["Edad en el DICOM"]) == meta["edad"]
    assert _texto_plano(seccion["Sexo en el DICOM"]) == meta["sexo"]
    assert _texto_plano(seccion["Vista en el DICOM"]) == meta["vista"]


def test_hay_uno_por_tipo_y_el_rechazado_con_15_anios():
    """Una normal en PA, una con opacidad en PA y una en AP; y la primera con 15
    años, para enseñar el rechazo."""
    metas = {n: leer_dicom_desde_bytes(_datos(n))[1] for n in EJEMPLOS}
    assert [metas[n]["vista"] for n in ("normal_pa", "neumonia_pa", "neumonia_ap")] == [
        "PA", "PA", "AP"]
    assert metas["rechazado_menor"]["edad"] == "015Y"
    assert (metas["rechazado_menor"]["vista"], metas["rechazado_menor"]["sexo"]) == (
        metas["normal_pa"]["vista"], metas["normal_pa"]["sexo"])
    # el «rechazado» es la primera imagen, píxel a píxel, con otra edad
    assert np.array_equal(leer_dicom_desde_bytes(_datos("rechazado_menor"))[0],
                          leer_dicom_desde_bytes(_datos("normal_pa"))[0])
    # y las tres de adultos no se parecen entre sí
    pixeles = [leer_dicom_desde_bytes(_datos(n))[0]
               for n in ("normal_pa", "neumonia_pa", "neumonia_ap")]
    assert not any(a.shape == b.shape and np.array_equal(a, b)
                   for i, a in enumerate(pixeles) for b in pixeles[i + 1:])


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_los_pixeles_del_dicom_son_los_del_png(nombre):
    with Image.open(CARPETA_ORIGINALES / f"{IMAGEN_DE[nombre]}.png") as imagen:
        esperado = np.array(imagen)
    assert np.array_equal(leer_dicom_desde_bytes(_datos(nombre))[0], esperado)


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_la_cabecera_no_lleva_nada_mas_de_paciente(nombre):
    """La cabecera, entera: nada de nombre, de fechas ni de otro identificador.
    Una etiqueta de más, o un valor distinto, hace fallar esta prueba."""
    ds = _leer(nombre)
    paciente, edad, sexo, vista = CABECERA[nombre]
    actual = {e.keyword: (str(e.value) if e.VR in ("PN", "UI") else e.value)
              for e in ds if e.keyword != "PixelData"}
    for uid in UID_DE_LA_CABECERA:
        actual.pop(uid)
    assert actual == {**CABECERA_COMUN, "PatientID": paciente, "PatientSex": sexo,
                      "PatientAge": edad, "ViewPosition": vista,
                      "Rows": ds.Rows, "Columns": ds.Columns}
    # lo que dice la intención, aparte de la letra: ni una fecha, ni una hora, ni un
    # nombre con contenido
    con_contenido = [e.keyword for e in ds
                     if e.VR in ("DA", "DT", "TM", "PN") and str(e.value)]
    assert con_contenido == []
    assert "PixelData" in ds and len(ds.PixelData) >= ds.Rows * ds.Columns


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_el_file_meta_y_el_preambulo_tampoco_llevan_nada(nombre):
    datos = _datos(nombre)
    assert datos[:128] == bytes(128) and datos[128:132] == b"DICM"
    meta = _leer(nombre).file_meta
    assert {e.keyword for e in meta} == ETIQUETAS_DE_FILE_META
    assert meta.TransferSyntaxUID == pydicom.uid.ExplicitVRLittleEndian   # sin comprimir
    assert meta.MediaStorageSOPClassUID == SECONDARY_CAPTURE
    # no dependen de la versión de pydicom con la que se escribieron
    assert not meta.ImplementationVersionName.upper().startswith("PYDICOM")
    assert meta.ImplementationClassUID.startswith("2.25.")


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_el_dicom_no_lleva_la_ruta_de_ninguna_maquina(nombre):
    datos = _datos(nombre)
    cabecera = datos[:datos.index(b"\xe0\x7f\x10\x00")]       # hasta PixelData
    assert re.search(RUTA_DE_UNA_MAQUINA.encode("ascii"), cabecera) is None


def test_los_uid_son_validos_y_distintos_en_cada_dicom():
    por_uid = {}
    for nombre in EJEMPLOS:
        ds = _leer(nombre)
        uids = [str(ds[campo].value) for campo in UID_DE_LA_CABECERA]
        assert str(ds.file_meta.MediaStorageSOPInstanceUID) == str(ds.SOPInstanceUID)
        for uid in uids + [str(ds.file_meta.ImplementationClassUID)]:
            assert UID(uid).is_valid and uid.startswith("2.25."), (nombre, uid)
            assert len(uid) <= 64
        assert len(set(uids)) == 3                  # estudio, serie e instancia
        for uid in uids:
            por_uid.setdefault(uid, []).append(nombre)
    assert all(len(nombres) == 1 for nombres in por_uid.values()), por_uid


# --------------------------------------------------------------------------
# El guion: rehacer los DICOM
# --------------------------------------------------------------------------
def test_volver_a_empaquetar_da_los_mismos_bytes(guion, tmp_path):
    escritos = guion.empaquetar(CARPETA_ORIGINALES, tmp_path)
    assert sorted(p.name for p in escritos) == sorted(f"{n}.dcm" for n in EJEMPLOS)
    for nombre in EJEMPLOS:
        assert (tmp_path / f"{nombre}.dcm").read_bytes() == _datos(nombre), nombre
    # y una segunda vuelta, igual que la primera
    otra = tmp_path / "otra"
    guion.empaquetar(CARPETA_ORIGINALES, otra)
    for nombre in EJEMPLOS:
        assert (otra / f"{nombre}.dcm").read_bytes() == _datos(nombre), nombre


def test_un_png_con_un_numero_impar_de_pixeles_se_empaqueta_y_se_lee(guion, tmp_path):
    """DICOM exige un número par de bytes de píxeles: se rellena con un cero."""
    origen = tmp_path / "originales"
    origen.mkdir()
    for nombre in IMAGENES:
        Image.fromarray(np.arange(15, dtype=np.uint8).reshape(5, 3) * 16).save(
            origen / f"{nombre}.png")
    guion.empaquetar(origen, tmp_path / "ejemplos")
    arreglo, meta = leer_dicom_desde_bytes((tmp_path / "ejemplos" / "normal_pa.dcm").read_bytes())
    assert arreglo.shape == (5, 3) and (meta["filas"], meta["columnas"]) == (5, 3)
    assert np.array_equal(arreglo, np.arange(15, dtype=np.uint8).reshape(5, 3) * 16)


@pytest.mark.parametrize("modo", ["RGB", "RGBA", "LA", "P", "1", "I;16"])
def test_una_imagen_que_no_es_gris_de_8_bits_no_se_empaqueta(guion, tmp_path, modo):
    origen = tmp_path / "originales"
    origen.mkdir()
    for nombre in IMAGENES:
        Image.new("L", (4, 4)).save(origen / f"{nombre}.png")
    Image.new(modo, (4, 4)).save(origen / "neumonia_ap.png")
    with pytest.raises(ValueError, match="neumonia_ap.png"):
        guion.empaquetar(origen, tmp_path / "ejemplos")


def test_un_png_que_falta_se_dice_por_su_nombre(guion, tmp_path):
    with pytest.raises(FileNotFoundError, match="normal_pa.png"):
        guion.empaquetar(tmp_path, tmp_path / "ejemplos")


# --------------------------------------------------------------------------
# El guion: reducir las descargas de Commons
# --------------------------------------------------------------------------
@pytest.mark.parametrize("ancho,alto,esperado", [
    (1929, 2207, (671, 768)),       # las tres de verdad
    (1163, 1010, (768, 667)),
    (2765, 2505, (768, 696)),
    (2000, 1000, (768, 384)),
    (1000, 2000, (384, 768)),
    (769, 769, (768, 768)),
])
def test_reducir_deja_el_lado_mayor_en_768_y_en_gris(guion, tmp_path, ancho, alto,
                                                     esperado):
    origen = _jpeg(tmp_path, "original.jpg", ancho, alto)
    destino = tmp_path / "salida" / "reducida.png"            # la carpeta no existe
    guion.reducir_original(origen, destino, _sha1(origen))
    with Image.open(destino) as imagen:
        imagen.load()
        assert (imagen.format, imagen.mode, imagen.size) == ("PNG", "L", esperado)
        assert imagen.info == {}


def test_reducir_no_amplia_lo_que_ya_es_pequeno(guion, tmp_path):
    origen = _jpeg(tmp_path, "pequena.jpg", 600, 400)
    guion.reducir_original(origen, tmp_path / "pequena.png", _sha1(origen))
    with Image.open(tmp_path / "pequena.png") as imagen:
        assert imagen.size == (600, 400)


def test_reducir_conserva_el_brillo_y_siempre_da_los_mismos_bytes(guion, tmp_path):
    """El gris es el del canal, sin reponderar, y volver a reducir da los mismos
    bytes."""
    origen = _jpeg(tmp_path, "original.jpg", 1024, 1024)
    guion.reducir_original(origen, tmp_path / "a.png", _sha1(origen))
    guion.reducir_original(origen, tmp_path / "b.png", _sha1(origen))
    assert (tmp_path / "a.png").read_bytes() == (tmp_path / "b.png").read_bytes()
    with Image.open(origen) as jpeg, Image.open(tmp_path / "a.png") as png:
        brillo_del_original = float(np.array(jpeg)[..., 0].mean())
        brillo_reducido = float(np.array(png).mean())
    assert abs(brillo_reducido - brillo_del_original) < 1.0


def test_reducir_con_otro_sha1_no_escribe_nada(guion, tmp_path):
    origen = _jpeg(tmp_path, "original.jpg", 900, 800)
    destino = tmp_path / "reducida.png"
    with pytest.raises(ValueError, match="SHA-1"):
        guion.reducir_original(origen, destino, "0" * 40)
    assert not destino.exists()


def test_reducir_no_acepta_una_imagen_en_color(guion, tmp_path):
    origen = _jpeg(tmp_path, "color.jpg", 900, 800, color=(200, 30, 30))
    destino = tmp_path / "reducida.png"
    with pytest.raises(ValueError, match="gris"):
        guion.reducir_original(origen, destino, _sha1(origen))
    assert not destino.exists()


def test_el_guion_va_de_las_descargas_a_los_dicom(guion, tmp_path, monkeypatch, capsys):
    """De punta a punta, con tres descargas de juguete: `--reducir`, y luego los
    cuatro DICOM, que el lector del proyecto lee."""
    descargas = tmp_path / "descargas"
    descargas.mkdir()
    tamanos = {"normal_pa": (900, 1100), "neumonia_pa": (1000, 850),
               "neumonia_ap": (950, 950)}
    sha1 = {n: _sha1(_jpeg(descargas, f"{n}.jpg", *tamano))
            for n, tamano in tamanos.items()}
    monkeypatch.setattr(guion, "SHA1_DE_LOS_ORIGINALES", sha1)
    monkeypatch.setattr(guion, "CARPETA_ORIGINALES", tmp_path / "originales")
    monkeypatch.setattr(guion, "CARPETA_EJEMPLOS", tmp_path / "ejemplos")

    assert guion.principal(["--reducir", str(descargas)]) == 0
    assert sorted(p.name for p in (tmp_path / "originales").iterdir()) == sorted(
        f"{n}.png" for n in IMAGENES)
    assert sorted(p.name for p in (tmp_path / "ejemplos").iterdir()) == sorted(
        f"{n}.dcm" for n in EJEMPLOS)
    salida = capsys.readouterr().out
    assert all(f"{n}.dcm" in salida for n in EJEMPLOS)
    for nombre in EJEMPLOS:
        arreglo, meta = leer_dicom_desde_bytes(
            (tmp_path / "ejemplos" / f"{nombre}.dcm").read_bytes())
        assert max(arreglo.shape) == LADO_MAYOR
        assert meta["edad"] == CABECERA[nombre][1]


def test_el_guion_sin_argumentos_empaqueta_lo_que_hay(guion, tmp_path, monkeypatch):
    monkeypatch.setattr(guion, "CARPETA_EJEMPLOS", tmp_path)
    assert guion.principal([]) == 0
    for nombre in EJEMPLOS:
        assert (tmp_path / f"{nombre}.dcm").read_bytes() == _datos(nombre)


def test_el_guion_con_una_descarga_equivocada_sale_con_1(guion, tmp_path, monkeypatch,
                                                         capsys):
    descargas = tmp_path / "descargas"
    descargas.mkdir()
    for nombre in IMAGENES:
        _jpeg(descargas, f"{nombre}.jpg", 900, 800)           # no son las de Commons
    monkeypatch.setattr(guion, "CARPETA_ORIGINALES", tmp_path / "originales")
    monkeypatch.setattr(guion, "CARPETA_EJEMPLOS", tmp_path / "ejemplos")
    assert guion.principal(["--reducir", str(descargas)]) == 1
    assert "SHA-1" in capsys.readouterr().err
    assert not (tmp_path / "ejemplos").exists()


def test_el_guion_no_lleva_la_ruta_de_ninguna_maquina():
    texto = GUION.read_text(encoding="utf-8")
    assert re.search(RUTA_DE_UNA_MAQUINA, texto) is None


def test_la_tabla_de_sha1_del_guion_es_la_de_commons(guion):
    assert guion.SHA1_DE_LOS_ORIGINALES == SHA1
    assert guion.LADO_MAYOR == LADO_MAYOR


# --------------------------------------------------------------------------
# LICENCIAS.md
# --------------------------------------------------------------------------
def test_licencias_tiene_una_seccion_por_dicom_y_ninguna_de_mas():
    assert sorted(_licencias()) == sorted(f"{n}.dcm" for n in EJEMPLOS)


@pytest.mark.parametrize("nombre", EJEMPLOS)
def test_cada_ejemplo_tiene_fuente_autor_licencia_y_atribucion(nombre):
    seccion = _licencias()[f"{nombre}.dcm"]
    assert set(seccion) == set(ETIQUETAS), (set(ETIQUETAS) ^ set(seccion))
    assert all(valor for valor in seccion.values())
    imagen = IMAGEN_DE[nombre]
    assert FICHEROS_ORIGINALES[imagen] in seccion["Imagen original"]
    assert seccion["Página de origen"] == PAGINAS[imagen]
    assert "Mikael Häggström" in seccion["Autor"]
    assert "CC0 1.0" in seccion["Licencia"]
    assert LITERAL_DE_LA_LICENCIA in seccion["Licencia"]
    assert CREDITO in seccion["Atribución"]
    assert _texto_plano(seccion["SHA-1 del original"]) == SHA1[imagen]
    cambio = seccion["Qué se cambió"]
    assert "768" in cambio and "escala de grises" in cambio and "DICOM" in cambio


def test_el_rechazado_dice_que_su_edad_es_inventada():
    cambio = _licencias()["rechazado_menor.dcm"]["Qué se cambió"]
    assert "15" in cambio and "inventada" in cambio and "fuera_de_alcance" in cambio
    assert "normal_pa" in cambio                    # de dónde salen sus píxeles


def test_licencias_avisa_de_que_no_son_de_rsna_ni_del_nih_ni_medidos():
    texto = LICENCIAS.read_text(encoding="utf-8")
    assert "RSNA" in texto and "NIH" in texto
    assert re.search(r"(?i)no son de RSNA ni del NIH", texto)
    assert re.search(r"(?i)no se ha medido", texto)


def test_licencias_no_lleva_la_ruta_de_ninguna_maquina():
    texto = LICENCIAS.read_text(encoding="utf-8")
    assert re.search(RUTA_DE_UNA_MAQUINA, texto) is None


# --------------------------------------------------------------------------
# El motor, con los ejemplos
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def motor():
    """Un motor con un modelo diminuto y el calibrador del servidor: aquí se prueba
    qué hace el motor con la cabecera de cada ejemplo, no la calidad de la red."""
    import torch
    from copiloto_triaje.servicio.calibracion import Calibrador
    from copiloto_triaje.servicio.inferencia import Motor

    class Trivial(torch.nn.Module):
        def forward(self, x):
            return x.mean(dim=(1, 2, 3)).view(-1, 1)

    return Motor(modelo=Trivial(), calibrador=Calibrador.desde_json(CALIBRADOR),
                 umbral=0.5, tam_imagen=32, nombre_modelo="prueba",
                 auc_validacion=0.88, prevalencia_local=0.1466)


@pytest.mark.parametrize("nombre,edad", [("normal_pa", 21), ("neumonia_pa", 88),
                                         ("neumonia_ap", 76)])
def test_el_motor_acepta_cada_ejemplo_de_adulto(motor, nombre, edad):
    salida = motor.clasificar(_datos(nombre))
    assert salida["edad_paciente"] == edad
    assert salida["clasificacion"] in ("opacidad_probable", "sin_opacidad_probable")


def test_el_motor_rechaza_al_menor_con_fuera_de_alcance(motor):
    from copiloto_triaje.servicio.inferencia import ErrorDeInferencia
    with pytest.raises(ErrorDeInferencia) as fallo:
        motor.clasificar(_datos("rechazado_menor"))
    assert fallo.value.codigo == "fuera_de_alcance"
    assert "15" in str(fallo.value)
