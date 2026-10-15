"""Pruebas del anonimato del repositorio (spec de SP5 §6.1).

El repositorio se publica, y lo que se publica no puede llevar ninguna cadena
que identifique al cliente, a la empresa, a la maquina ni a los integrantes.
La lista de esas cadenas NO vive aqui: el repositorio lleva solo
`tests/anonimato/huellas.txt`, con el sha256 de cada token (el de desarrollo;
el que se publica lleva solo la del centinela, D9). Por eso estas pruebas
corren siempre, sin la lista: se prueban a si mismas con un token publico, el
centinela, cuya huella va siempre en el fichero.

Los secretos de ejemplo se COMPONEN al correr (`"sk" + "-" + ...`): este
fichero tambien se recorre, y un secreto de ejemplo escrito entero haria
saltar la misma prueba que lo usa.
"""
import base64
import binascii
import codecs
import hashlib
import importlib.util
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zlib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "verificar_anonimato.py"
HUELLAS = RAIZ / "tests" / "anonimato" / "huellas.txt"


def _cargar_script():
    """Importa el script por ruta: no es un modulo del paquete."""
    especificacion = importlib.util.spec_from_file_location(
        "verificar_anonimato", SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


va = _cargar_script()

CENTINELA = "centinelaanonimato7f3a"
OTRO = "tokendeprueba9z"          # un segundo token inventado, para la CLI
OTRO_MAS = "segundotoken5q"       # y un tercero

# De donde sale lo que se recorre (clave `origen` de cada hallazgo).
COPIA, INDICE, COMMIT = "copia de trabajo", "indice", "commit"

# Los binarios versionados, revisados A MANO uno a uno (tests/anonimato/README.md).
# Un binario nuevo hace fallar la prueba hasta que alguien lo abre, lo mira y
# lo añade aquí y a la declaración.
BINARIOS_REVISADOS = (
    "app/assets/ejemplos/neumonia_ap.dcm",
    "app/assets/ejemplos/neumonia_pa.dcm",
    "app/assets/ejemplos/normal_pa.dcm",
    "app/assets/ejemplos/rechazado_menor.dcm",
    "app/assets/originales/neumonia_ap.png",
    "app/assets/originales/neumonia_pa.png",
    "app/assets/originales/normal_pa.png",
    "docs/eda/01_distribucion_clases.png",
    "docs/eda/02_edad_y_atipicos.png",
    "docs/eda/03_vista_confusor.png",
    "docs/eda/04_sexo.png",
    "docs/eda/05_correlaciones.png",
    "docs/eda/06_cajas.png",
    "docs/interfaz/acerca-de-metricas.png",
    "docs/interfaz/acerca-de-modelo.png",
    "docs/interfaz/probar-con-ejemplo-anotada.png",
    "docs/interfaz/probar-con-ejemplo.png",
    "docs/interfaz/rechazado.png",
    "docs/validacion-semisintetica/contencion_rejilla.png",
    "docs/validacion-semisintetica/fiabilidad_0a.png",
    "docs/validacion-semisintetica/fiabilidad_r1-000_r0-030.png",
    "docs/validacion-semisintetica/fiabilidad_r1-000_r0-060.png",
    "docs/validacion-semisintetica/fiabilidad_r1-030_r0-000.png",
    "docs/validacion-semisintetica/fiabilidad_r1-030_r0-030.png",
    "docs/validacion-semisintetica/fiabilidad_r1-060_r0-000.png",
    "docs/validacion-semisintetica/fiabilidad_r1-060_r0-060.png",
    "docs/validacion-semisintetica/horquilla_por_celda.png",
    "docs/validacion-semisintetica/pendiente_rejilla.png",
    "results/figures/calibracion.png",
    "results/figures/roc_prueba.png",
    "results/figures/subgrupos.png",
)
METADATOS_PERMITIDOS = {"Software", "dpi", "Title", "Description"}

# Los binarios de `app/assets/` (los tres PNG y los cuatro DICOM de los ejemplos), las
# capturas de la interfaz de `docs/interfaz/` (las del README y la anotada del manual) y
# las figuras de `results/figures/` (las que dibuja `src/evaluate.py`), fijados además por el
# SHA-256 de sus bytes, como están fijadas las imágenes de los notebooks: declararlos
# solo por su nombre no ve que otra imagen ocupe su sitio, que un PNG gane un trozo
# auxiliar (una fecha, un texto) ni que un DICOM se regenere con otra cabecera. Un
# binario que cambia hace fallar la suite, que dice el fichero y no vuelca sus bytes,
# hasta que alguien lo vuelve a mirar. Las huellas se rehacen a la vez que los binarios
# (otra imagen, otro guion, otra versión de pydicom, otra captura de una pantalla que
# cambió) y solo después de volver a mirarlos: tests/anonimato/README.md.
HUELLAS_DE_LOS_BINARIOS = {
    "app/assets/ejemplos/neumonia_ap.dcm":
        "f881d545a7e0bbefe7840cfc0ebb871476eb549e83904d7416ea67a98c46bc8e",
    "app/assets/ejemplos/neumonia_pa.dcm":
        "df6c6ea765928ea83209b29f38a09b667be4ff5dd1c1eca147fde3f81651df61",
    "app/assets/ejemplos/normal_pa.dcm":
        "77e88f7c5e3c9915ddd54ae372cfc345a5efb1ba8c56747b68cda2903ee509b4",
    "app/assets/ejemplos/rechazado_menor.dcm":
        "186694a0b962ad3af1a2ccc620c99d3ba42af4ac217452e0fda812bdcc5c849f",
    "app/assets/originales/neumonia_ap.png":
        "2d6bc6b1d1989c81c87e492b1f9ec4aa4e3692435b855d541e19da1641378f73",
    "app/assets/originales/neumonia_pa.png":
        "b77ea8c678dd487e8cd25da5302fe8623ca7ad2cc513e41cecc1ce0fe2e29e8b",
    "app/assets/originales/normal_pa.png":
        "211bffe38225a88d56d8fc7b790d6568f1990fda19146bd01bec0c742c787820",
    "docs/interfaz/acerca-de-metricas.png":
        "95f85e8d2b51a4e2c4b89366639adc0e214d12a2a7cae12f5b01bcef3d7dbf22",
    "docs/interfaz/acerca-de-modelo.png":
        "fd4f73b50d6eca3750e22ab5b4cec2d626547694ee53e4182cc66374636c1911",
    "docs/interfaz/probar-con-ejemplo-anotada.png":
        "c98d1cc24e7ad0f7225dc2720287641e5676a6e864628f84500b6eec3e744642",
    "docs/interfaz/probar-con-ejemplo.png":
        "b530dd3b4d293499c62dd6902a85e816ab9ef387997f97dc4ff67002a6ac6b44",
    "docs/interfaz/rechazado.png":
        "9f4dc3096edf2798de4be148d0808f8b9c7e256f6712a924db0286ee95adce1b",
    "results/figures/calibracion.png":
        "e99a11a358763a01d4fb91ef8e5aa7b4f592aa1fd53e665bd044446882beb3e7",
    "results/figures/roc_prueba.png":
        "b88d67f2fd0159b1ef2d81e2120de82ba009325e93b39d870c6be8a757028989",
    "results/figures/subgrupos.png":
        "f8609089c32cfc596fa11528ceb8be5e42451a49ee4c35c69ca72f3b8c702383",
}
# Las carpetas cuyos binarios se declaran SIEMPRE con su SHA-256 en HUELLAS_DE_LOS_BINARIOS.
CARPETAS_CON_HUELLA = ("app/assets/", "docs/interfaz/", "results/figures/")

# Las etiquetas que puede llevar la cabecera de un DICOM versionado (los ejemplos
# de la app), la del `file_meta` y la del conjunto de datos, revisadas a mano. Una
# etiqueta nueva -un nombre, una fecha, un equipo, un comentario- hace fallar la
# prueba hasta que alguien la mira y la añade aquí y a la declaración. Los píxeles
# no son una etiqueta: solo los ve la revisión a mano.
ETIQUETAS_DICOM_PERMITIDAS = {
    "FileMetaInformationGroupLength", "FileMetaInformationVersion",
    "MediaStorageSOPClassUID", "MediaStorageSOPInstanceUID", "TransferSyntaxUID",
    "ImplementationClassUID", "ImplementationVersionName",
    "SOPClassUID", "SOPInstanceUID", "Modality", "ConversionType", "PatientName",
    "PatientID", "PatientSex", "PatientAge", "BodyPartExamined", "ViewPosition",
    "StudyInstanceUID", "SeriesInstanceUID", "SamplesPerPixel",
    "PhotometricInterpretation", "Rows", "Columns", "BitsAllocated", "BitsStored",
    "HighBit", "PixelRepresentation", "PixelData",
}
# Los valores de estos tipos (nombre de persona, fecha, fecha y hora, hora) van
# vacíos: un nombre o una fecha de verdad no se puede comparar con la lista.
TIPOS_DICOM_SIEMPRE_VACIOS = ("PN", "DA", "DT", "TM")

# Las imagenes incrustadas en cada notebook que se publica, por el SHA-256 de
# sus bytes (ya decodificados de base64), ordenadas. Son huellas de IMAGENES,
# no de tokens: se pueden publicar. Una imagen nueva, o una que cambie al
# volver a ejecutar el notebook, hace fallar la prueba hasta que alguien la
# mira y la declara aqui y en tests/anonimato/README.md.
IMAGENES_DE_LOS_NOTEBOOKS = {
    "notebooks/01_exploracion.ipynb": (
        "0bdabb57e4fffdfba64143c5d73626e246a18ba76cd246b84a3dde65adc64207",
        "0db7916271002c6fcdc19ca61bdea62e30f8c438a4d907318abdc290eee91e7f",
        "2cd353815a6b1463c846d336ed478db1d99b98838059458a961a4951c089fefa",
        "52f958410542951c5a0558b5aee4904dd1ab4757751d1ff8e0e7a6bef090b86d",
        "7d4ab28d7b54c08132afb462516338434e924bf81ceaa115d693f554ea295bab",
        "f1c10db558e768c38e7b4cab01ecc04b9d5a49ef6b125dbc8437ee8d727cd69e",
    ),
    "notebooks/02_preprocesamiento.ipynb": (
        "364f62dbfb10a2b07a1752957571570c4ea6f9fdd05b9ab732929802b6a2d517",
        "58a42b7e2d58e8eb21bdb5431620a727e73f932527ec43de437597eb4e409dff",
    ),
    "notebooks/03_modelado.ipynb": (),
    "notebooks/04_optimizacion.ipynb": (
        "63e1597857909841a7970753a27b09350e424c4c8caab0b231f126fe6c461159",
        "64ae39c1c5db36bf0fe55c2be15cb6c2b752581e6d320c5d7f54c28de84a6465",
        "6f10f2cb6ff0c60b12449443454cbb204cd195e9f6e73a8de4ff14e283dc6dbb",
        "72d2665369ba2feeca1357ffcec8dff7851c03c13fd8628755014a262ea97b87",
        "83fa914a3ef359cc46aebe7a48173d11fb9145461b258631819d2e9a855591ea",
        "9a5679fead261be6b575eab26d0d5f78b7c533da8e73311a49ee9b45e4a2e7bf",
        "dbdab841509915ff8c8571eb9713f30e95dde4b2cbb5a58c579e38c8bc4adb1f",
        "f7784b8067bb008ae0b85706f55b93f2b84b76f81666d4cd76b698c41d903964",
    ),
    "notebooks/05_evaluacion.ipynb": (
        "15481a870a5c6a74cf5aa959136055387a1e81e5d37b0389b25e9822175240fd",
        "75262e13b11dd3cb5026f47580f3313961934c27597a92a34c973d01bbc257e2",
        "e61d13081b1a84094ff7f660281d33d34ac8fe5591cab98ea1384daf89be5abb",
        "eb065a5ab6ee98fa2f679861ae0efae42b3b74ac608ff09d63ef514d3ee266c5",
    ),
    "notebooks/entrenar_gpu.ipynb": (),
}
# Las claves de `metadata` que puede llevar un notebook que se publica, las de
# su `colab` y las de cada celda. Un notebook guardado de nuevo desde Colab o
# Kaggle trae campos que las huellas no pueden conocer (un identificador de
# documento, una cuenta): la prueba falla hasta que alguien los mira.
METADATOS_DEL_NOTEBOOK = {"kernelspec", "language_info", "accelerator", "colab"}
METADATOS_DE_COLAB = {"name", "provenance"}
METADATOS_DE_LA_CELDA = {"execution"}


# --------------------------------------------------------------------------
# Tokenizacion y huellas
# --------------------------------------------------------------------------
def test_tokens_pasa_a_minusculas_y_quita_las_tildes():
    assert va.tokens("Canción ÑANDÚ, Pingüino") == {
        "cancion", "nandu", "pinguino"}


def test_tokens_trocea_una_url():
    assert va.tokens("https://n8n.ejemplo.test/webhook/copiloto-paciente") == {
        "https", "n8n", "ejemplo", "test", "webhook", "copiloto", "paciente"}


def test_tokens_trocea_la_variable_de_la_red():
    assert va.tokens("name: ${RED_N8N:-uno_dos}") == {
        "name", "red", "n8n", "uno", "dos"}


def test_tokens_trocea_una_ruta_de_windows():
    assert va.tokens("C:\\Users\\u") == {"c", "users", "u"}


def test_tokens_quita_el_base64_largo_y_conserva_el_corto():
    largo = "iVBORw0KGgo" + "A" * 109            # 120 caracteres
    assert len(largo) == 120
    assert va.tokens(f'"image/png": "{largo}"') == {"image", "png"}
    corto = largo[:119]
    assert corto.lower() in va.tokens(f'"image/png": "{corto}"')


@pytest.mark.parametrize("texto", [
    pytest.param('{"notas": "linea uno\\n' + CENTINELA + '"}',
                 id="barra_n_en_json"),
    pytest.param('"columna\\t' + CENTINELA + '"', id="barra_t"),
    pytest.param("https://ejemplo.test/?q=%20" + CENTINELA,
                 id="por_ciento_20"),
    pytest.param("https:%2F%2F" + CENTINELA + ".test", id="por_ciento_2f"),
    pytest.param("&#99;" + CENTINELA[1:], id="entidad_decimal"),
    pytest.param("&#x63;" + CENTINELA[1:], id="entidad_hexadecimal"),
    pytest.param("\\u0063" + CENTINELA[1:], id="barra_u"),
])
def test_los_escapes_no_pegan_letras_al_token(tmp_path, texto):
    assert CENTINELA in va.tokens(texto)
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "a.json").write_text(texto + "\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"]) for h in hallazgos] == [("a.json", 1)]


@pytest.mark.parametrize("texto", [
    pytest.param("".join(chr(ord(c) + 0xFEE0) for c in CENTINELA),
                 id="ancho_completo"),
    pytest.param(CENTINELA[:9] + "​" + CENTINELA[9:],
                 id="espacio_de_ancho_cero"),
    pytest.param(CENTINELA[:9] + "­" + CENTINELA[9:],
                 id="guion_blando"),
    pytest.param("﻿" + CENTINELA, id="marca_de_orden_pegada"),
    # R7: el caracter de formato tambien hace de separador (union).
    pytest.param("alfa​" + CENTINELA, id="formato_como_separador"),
    pytest.param(CENTINELA[:5] + "​" + CENTINELA[5:],
                 id="formato_dentro_del_token"),
])
def test_compatibilidad_y_caracteres_de_formato(texto):
    # NFKD descompone tambien el ancho completo; los caracteres de formato
    # (categoria Cf) se borran en vez de partir el token.
    assert CENTINELA in va.tokens(texto)


def test_tokens_une_el_texto_tal_cual_y_el_desescapado():
    assert va.tokens("uno\\ndos") == {"uno", "ndos", "dos"}
    assert va.tokens("a%20b &amp; c") == {"a", "20b", "b", "amp", "c"}


def test_tokens_de_un_texto_vacio():
    assert va.tokens("") == set()
    assert va.tokens(" -- \n") == set()


def test_huella_es_el_sha256_del_token_en_utf8():
    assert va.huella("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    assert va.huella(CENTINELA) == hashlib.sha256(
        CENTINELA.encode("utf-8")).hexdigest()


def test_el_centinela_es_el_del_spec():
    assert va.CENTINELA == CENTINELA


# --------------------------------------------------------------------------
# huellas.txt, el fichero versionado
# --------------------------------------------------------------------------
def solo_el_centinela(ruta=HUELLAS):
    """Si el fichero de huellas lleva solo la del centinela.

    Es el `huellas.txt` del repositorio que se publica (D9): alli la
    comprobacion de verdad se hace antes de publicar, con las huellas del
    repositorio de desarrollo, y lo que exige la lista entera se salta.
    """
    return va.leer_huellas(ruta) == {va.huella(CENTINELA)}


_SOLO_EL_CENTINELA = ("huellas.txt lleva solo la huella del centinela (el "
                      "repositorio que se publica, D9): ")
# Lo que de verdad se queda sin verificar en cada sitio que se salta.
SIN_LA_LISTA = {
    "huellas.txt": _SOLO_EL_CENTINELA
    + "queda sin verificar que huellas.txt lleve la lista entera. En el "
      "repositorio que se publica es lo que toca; en el de desarrollo, "
      "falta regenerarlo con --regenerar --lista",
    "arbol": _SOLO_EL_CENTINELA
    + "queda sin verificar aqui que el arbol no lleva ninguna cadena de la "
      "lista (los secretos si se buscan: test_el_arbol_no_lleva_secretos). "
      "Esa comprobacion se hace antes de publicar, con "
      "scripts/verificar_anonimato.py, --huellas y las huellas del "
      "repositorio de desarrollo",
    "metadatos": _SOLO_EL_CENTINELA
    + "las claves de los metadatos de las imagenes se han comprobado, pero "
      "queda sin verificar aqui que sus valores no llevan ninguna cadena de "
      "la lista. El script no lee las imagenes: esos valores solo los mira "
      "la revision a mano declarada en tests/anonimato/README.md",
}


def _lleva_el_centinela(ruta):
    """Sobre un booleano, con mensaje: pytest enseñaria el conjunto de
    huellas leido (C5)."""
    leidas = va.leer_huellas(ruta)
    con_el_centinela = va.huella(CENTINELA) in leidas
    assert con_el_centinela, (f"{ruta.name} no lleva la huella del "
                              f"centinela ({len(leidas)} huellas leídas)")


def test_el_centinela_esta_en_huellas_txt():
    _lleva_el_centinela(HUELLAS)


def test_la_prueba_del_centinela_no_ensena_las_huellas(tmp_path):
    # Como D-9: si falla, pytest enseñaria el conjunto de huellas leido.
    ruta = tmp_path / "huellas.txt"
    datos = sorted(va.huella(f"{OTRO}{n}") for n in range(30))
    ruta.write_text("# cabecera\n" + "\n".join(datos) + "\n",
                    encoding="utf-8")
    with pytest.raises(AssertionError) as error:
        _lleva_el_centinela(ruta)
    assert "no lleva la huella del centinela" in str(error.value)
    assert not any(una[:12] in str(error.value) for una in datos)


def test_la_cabecera_de_huellas_txt_es_la_que_escribe_el_script():
    # Quien mantiene la lista regenera huellas.txt y tiene que salir
    # identico: la cabecera es, letra por letra, la del script (la del
    # repositorio que se publica, si lleva solo la del centinela).
    comentarios = [l for l in HUELLAS.read_text(encoding="utf-8-sig")
                   .splitlines() if l.startswith("#")]
    esperada = (va.CABECERA_SOLO_CENTINELA if solo_el_centinela()
                else va.CABECERA)
    assert comentarios == esperada.splitlines()


def test_la_cabecera_dice_como_se_regenera_en_cualquier_consola():
    # `VARIABLE=valor orden` es de bash: en PowerShell no funciona.
    assert "--regenerar --lista <lista en claro>" in va.CABECERA
    assert "ANONIMATO_LISTA=" not in va.CABECERA
    publica = va.CABECERA_SOLO_CENTINELA
    assert "repositorio que se publica" in publica
    assert "a propósito" in publica
    assert "--regenerar --solo-centinela" in publica
    assert "huellas del repositorio de desarrollo" in publica
    assert all(l.startswith("#") for l in publica.splitlines())


def _cabecera_y_huellas_ordenadas(ruta):
    """Lo que se exige a un fichero de huellas. Se lee como `leer_huellas`
    (admite la marca de orden de bytes). Las aserciones son sobre booleanos,
    con recuentos: comparar listas enseñaria las huellas si fallase (D-9)."""
    lineas = ruta.read_text(encoding="utf-8-sig").splitlines()
    con_cabecera = bool(lineas) and lineas[0].startswith("#")
    assert con_cabecera, "la primera línea no es un comentario de cabecera"
    datos = [l for l in lineas if l and not l.startswith("#")]
    bien_formadas = all(len(l) == 64 and set(l) <= set("0123456789abcdef")
                        for l in datos)
    assert bien_formadas, "hay líneas que no son huellas"
    ordenadas = datos == sorted(set(datos))
    assert ordenadas, (f"{len(datos)} líneas, {len(set(datos))} distintas: "
                       "van ordenadas y sin repetir")
    leidas = va.leer_huellas(ruta)
    iguales = set(datos) == leidas
    assert iguales, f"{len(leidas)} huellas leídas frente a {len(datos)} líneas"


def test_huellas_txt_lleva_cabecera_y_huellas_ordenadas_sin_repetir():
    _cabecera_y_huellas_ordenadas(HUELLAS)


def test_la_cabecera_se_lee_con_la_marca_de_orden_de_bytes(tmp_path):
    # Como `leer_huellas`: un huellas.txt guardado con marca de orden de
    # bytes (el editor de alguien, PowerShell) vale igual.
    ruta = _huellas_de_juguete(tmp_path)
    ruta.write_bytes(codecs.BOM_UTF8 + ruta.read_bytes())
    _cabecera_y_huellas_ordenadas(ruta)


@pytest.mark.parametrize("estropeo", ["desordenadas", "repetida"])
def test_la_prueba_de_la_cabecera_no_ensena_las_huellas(tmp_path, estropeo):
    # Si falla, dice cuantas lineas y cuantas distintas: nunca las huellas
    # (D-9), que pytest enseñaria al comparar dos listas.
    ruta = tmp_path / "huellas.txt"
    datos = sorted(va.huella(f"{OTRO}{n}") for n in range(30))
    datos = datos[::-1] if estropeo == "desordenadas" else datos + datos[:1]
    ruta.write_text("# cabecera\n" + "\n".join(datos) + "\n",
                    encoding="utf-8")
    with pytest.raises(AssertionError) as error:
        _cabecera_y_huellas_ordenadas(ruta)
    mensaje = str(error.value)
    assert {"desordenadas": "30 líneas, 30 distintas",
            "repetida": "31 líneas, 30 distintas"}[estropeo] in mensaje
    assert not any(una[:12] in mensaje for una in datos)


@pytest.mark.skipif(solo_el_centinela(), reason=SIN_LA_LISTA["huellas.txt"])
def test_huellas_txt_lleva_mas_que_el_centinela():
    # Antes era parte de la prueba de arriba («len(datos) > 1»). Sobre un
    # booleano: pytest enseñaria el conjunto leido.
    mas_que_el_centinela = len(va.leer_huellas(HUELLAS)) > 1
    assert mas_que_el_centinela, "falta regenerar"


def test_solo_el_centinela_reconoce_el_fichero_del_repositorio_publico(
        tmp_path):
    publico = tmp_path / "publico.txt"
    publico.write_text("# cabecera\n" + va.huella(CENTINELA) + "\n",
                       encoding="utf-8")
    assert solo_el_centinela(publico)
    assert not solo_el_centinela(_huellas_de_juguete(tmp_path))


@pytest.mark.parametrize("mala", [
    pytest.param(va.huella(OTRO).upper(), id="en_mayusculas"),
    pytest.param(OTRO, id="un_token_en_claro"),
    pytest.param(va.huella(OTRO)[:63], id="corta"),
])
def test_leer_huellas_exige_una_huella_por_linea(tmp_path, mala):
    ruta = tmp_path / "huellas.txt"
    ruta.write_text(f"# cabecera\n{va.huella(CENTINELA)}\n\n{mala}\n",
                    encoding="utf-8")
    with pytest.raises(ValueError) as error:
        va.leer_huellas(ruta)
    assert "línea 4" in str(error.value)
    assert mala not in str(error.value)
    assert OTRO not in str(error.value).lower()


def test_leer_huellas_acepta_la_marca_de_orden_de_bytes(tmp_path):
    ruta = tmp_path / "huellas.txt"
    ruta.write_text("# cabecera\n" + va.huella(CENTINELA) + "\n",
                    encoding="utf-8-sig")
    assert va.leer_huellas(ruta) == {va.huella(CENTINELA)}


def test_la_lista_en_claro_esta_ignorada_por_si_alguien_la_copia_dentro():
    lineas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "tests/anonimato/lista*.txt" in lineas
    assert not list((RAIZ / "tests" / "anonimato").glob("lista*.txt"))


# --------------------------------------------------------------------------
# La lista en claro y la regeneracion (con una lista de juguete)
# --------------------------------------------------------------------------
LISTA_DE_JUGUETE = """\
# comentario de cabecera
[Huellas]
# un grupo
Uno
dos   # lo que sigue a una almohadilla es comentario
tres

[sustituciones]
cuatro => cinco
"""


def test_leer_lista_da_solo_la_seccion_de_huellas(tmp_path):
    lista = tmp_path / "lista.txt"
    lista.write_text(LISTA_DE_JUGUETE, encoding="utf-8")
    assert va.leer_lista(lista) == ["Uno", "dos", "tres"]


def test_leer_lista_con_marca_de_orden_y_la_seccion_en_la_primera_linea(
        tmp_path):
    lista = tmp_path / "lista.txt"
    lista.write_text("[huellas]\nuno\n[HUELLAS]\ndos\n", encoding="utf-8-sig")
    assert va.leer_lista(lista) == ["uno", "dos"]


def test_regenerar_rechaza_lo_que_no_da_exactamente_un_token(tmp_path):
    destino = tmp_path / "huellas.txt"
    with pytest.raises(ValueError) as error:
        va.regenerar(["uno", "zorro-azul.test", "tres", "--"], destino)
    mensaje = str(error.value)
    assert "2" in mensaje and "4" in mensaje
    assert not {"zorro", "azul", "test"} & va.tokens(mensaje)
    assert not destino.exists()


def test_regenerar_sin_entradas_es_un_error(tmp_path):
    destino = tmp_path / "huellas.txt"
    with pytest.raises(ValueError):
        va.regenerar([], destino)
    assert not destino.exists()


def test_regenerar_escribe_las_huellas_ordenadas_y_la_del_centinela(tmp_path):
    destino = tmp_path / "anonimato" / "huellas.txt"
    n = va.regenerar(["Uno", "dos", "tres", "uno"], destino)
    esperadas = {va.huella(t) for t in ("uno", "dos", "tres", CENTINELA)}
    assert n == 4
    assert va.leer_huellas(destino) == esperadas
    texto = destino.read_text(encoding="utf-8")
    datos = [l for l in texto.splitlines() if l and not l.startswith("#")]
    assert datos == sorted(esperadas)
    assert texto.startswith(va.CABECERA)
    assert "\r" not in destino.read_bytes().decode("utf-8")
    # Ningun token en claro, salvo el centinela, que es publico y la cabecera
    # lo nombra. (La huella de un token corto se adivina probando: en el
    # repositorio que se publica, huellas.txt lleva solo la del centinela,
    # D9; la lista entera vive solo en el de desarrollo, que es privado.)
    for token in ("uno", "dos", "tres"):
        assert token not in va.tokens(texto)


# --------------------------------------------------------------------------
# El recorrido: el centinela escrito DENTRO de un arbol de juguete
# --------------------------------------------------------------------------
def _arbol_limpio(raiz):
    (raiz / "docs").mkdir(parents=True)
    (raiz / "docs" / "guia.md").write_text(
        "# Guía\n\nLa URL es https://n8n.ejemplo.test y nada más.\n",
        encoding="utf-8")
    (raiz / "codigo.py").write_text("x = 1\n", encoding="utf-8")
    (raiz / "figura.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\xff\xfe")
    return raiz


def _donde(hallazgos):
    """Fichero y linea de cada hallazgo: lo que dice una asercion que falla
    con las huellas de verdad (pytest enseñaria la huella entera, C5)."""
    return f"{len(hallazgos)} hallazgos: " + ", ".join(
        f"{h['fichero']}:{h['linea']}" for h in hallazgos)


def test_un_arbol_limpio_no_da_hallazgos(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    hallazgos = va.buscar_huellas(raiz, va.leer_huellas(HUELLAS))
    limpio = hallazgos == []
    assert limpio, _donde(hallazgos)
    assert va.buscar_secretos(raiz) == []


def test_detecta_el_centinela_dentro_del_recorrido(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "docs" / "nota.md").write_text(
        f"primera\nsegunda con {CENTINELA}.\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, va.leer_huellas(HUELLAS))
    solo_el_centinela_en_la_nota = hallazgos == [
        {"fichero": "docs/nota.md", "linea": 2,
         "huella": va.huella(CENTINELA), "origen": COPIA}]
    assert solo_el_centinela_en_la_nota, _donde(hallazgos)


# A2: cada asercion sobre las huellas de HUELLAS que se paso a booleano (C5),
# con un huellas.txt de juguete que lleva la huella de `ejemplo`, un token
# del contenido del arbol de juguete (linea 3 de `docs/guia.md`; no de un
# nombre, que saldria tapado por el principio de su huella): la prueba
# falla, y su mensaje no lleva nada de esa huella. Con la forma vieja,
# pytest la enseñaria entera.
@pytest.mark.parametrize("llamar, esperado", [
    pytest.param(lambda carpeta: test_el_centinela_esta_en_huellas_txt(),
                 "no lleva la huella del centinela", id="el_centinela_esta"),
    pytest.param(lambda carpeta: test_huellas_txt_lleva_mas_que_el_centinela(),
                 "falta regenerar", id="mas_que_el_centinela"),
    pytest.param(lambda carpeta: test_un_arbol_limpio_no_da_hallazgos(carpeta),
                 "1 hallazgos: docs/guia.md:3", id="arbol_limpio"),
    pytest.param(
        lambda carpeta: test_detecta_el_centinela_dentro_del_recorrido(carpeta),
        "1 hallazgos: docs/guia.md:3", id="centinela_en_el_recorrido"),
])
def test_las_aserciones_sobre_huellas_txt_no_ensenan_huellas(
        tmp_path, monkeypatch, llamar, esperado):
    de_juguete = tmp_path / "huellas.txt"
    de_juguete.write_text("# de juguete\n" + va.huella("ejemplo") + "\n",
                          encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "HUELLAS", de_juguete)
    with pytest.raises(AssertionError) as error:
        llamar(tmp_path / "prueba")
    assert esperado in str(error.value)
    assert va.huella("ejemplo")[:8] not in str(error.value)


def test_lo_detecta_con_mayusculas_tildes_y_pegado_a_separadores(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "a.txt").write_text(
        "red_CentinelaAnónimato7F3A-x\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"]) for h in hallazgos] == [("a.txt", 1)]


def test_el_hallazgo_nunca_lleva_el_token_en_claro(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "a.txt").write_text(CENTINELA + "\n", encoding="utf-8")
    (hallazgo,) = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert sorted(hallazgo) == ["fichero", "huella", "linea", "origen"]
    assert CENTINELA not in repr(hallazgo)


def test_el_nombre_del_fichero_tambien_se_tokeniza(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "docs" / f"{CENTINELA}.md").write_text(
        f"nada\ny {CENTINELA}\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [h["linea"] for h in hallazgos] == [0, 2]
    assert CENTINELA not in repr(hallazgos)
    # El nombre que sale es el publicable, el mismo en todos los hallazgos:
    # el TOKEN dentro del componente pasa al principio de su huella (R6).
    publicable = f"docs/<huella-{va.huella(CENTINELA)[:12]}>.md"
    assert [h["fichero"] for h in hallazgos] == [publicable, publicable]


def test_tres_hermanos_con_el_mismo_token_no_chocan(tmp_path, capsys):
    raiz = _arbol_limpio(tmp_path / "arbol")
    for nombre in (f"informe-{OTRO}.md", f"notas_{OTRO.upper()}.md",
                   f"{OTRO}.txt"):
        (raiz / "docs" / nombre).write_text("nada\n", encoding="utf-8")
    tapada = f"<huella-{va.huella(OTRO)[:12]}>"
    hallazgos = va.buscar_huellas(raiz, {va.huella(OTRO)})
    assert sorted(h["fichero"] for h in hallazgos) == sorted([
        f"docs/informe-{tapada}.md", f"docs/notas_{tapada}.md",
        f"docs/{tapada}.txt"])
    assert va.main(["--raiz", str(raiz),
                    "--huellas", str(_huellas_de_juguete(tmp_path))]) == 1
    salida = capsys.readouterr().out
    assert "huellas: 3 en 3 ficheros" in salida
    assert OTRO not in salida.lower()


def test_un_secreto_en_el_nombre_del_fichero_es_un_hallazgo(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    clave = _secretos()["clave_de_api_akia"]
    (raiz / "docs" / f"config-{clave}.txt").write_text("x\n",
                                                       encoding="utf-8")
    (raiz / "figura-{}.png".format(clave)).write_bytes(b"\x89PNG\x00")
    hallazgos = va.buscar_secretos(raiz, huellas=set())
    assert hallazgos == [
        {"fichero": "docs/config-<secreto>.txt", "linea": 0,
         "clase": "clave_de_api_akia", "origen": COPIA},
        {"fichero": "figura-<secreto>.png", "linea": 0,
         "clase": "clave_de_api_akia", "origen": COPIA}]
    codigo, salida = _cli("--raiz", str(raiz),
                          "--huellas", str(_huellas_de_juguete(tmp_path)))
    assert codigo == 1
    assert clave not in salida
    assert "  figura-<secreto>.png" in salida


def test_el_nombre_publicable_tambien_en_los_secretos(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    carpeta = raiz / CENTINELA
    carpeta.mkdir()
    (carpeta / "config.txt").write_text(
        _secretos()["clave_de_api_akia"] + "\n", encoding="utf-8")
    (carpeta / ".env").write_text("X=1\n", encoding="utf-8")
    hallazgos = va.buscar_secretos(raiz, huellas={va.huella(CENTINELA)})
    tapada = f"<huella-{va.huella(CENTINELA)[:12]}>"
    assert [(h["fichero"], h["linea"], h["clase"]) for h in hallazgos] == [
        (f"{tapada}/.env", 0, "fichero_prohibido"),
        (f"{tapada}/config.txt", 1, "clave_de_api_akia")]
    assert CENTINELA not in repr(hallazgos)


def test_los_binarios_se_declaran_y_no_se_recorren(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "otra.png").write_bytes(
        b"\x89PNG\x00" + CENTINELA.encode("ascii") + b"\xff")
    assert va.es_texto(raiz / "codigo.py")
    assert not va.es_texto(raiz / "otra.png")
    assert [p.name for p in va.binarios(raiz)] == ["figura.png", "otra.png"]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []


_CON_TILDE = "CentinelaAnónimato7F3A"       # el centinela, escrito con tilde


@pytest.mark.parametrize("datos", [
    pytest.param(f"uno\ncon {CENTINELA}\n".encode("utf-16"),
                 id="utf16_con_marca"),
    pytest.param(f"uno\ncon {CENTINELA}\n".encode("utf-16-be"),
                 id="utf16be_sin_marca_es_binario"),
    pytest.param(b"\xfe\xff" + f"uno\ncon {CENTINELA}\n".encode("utf-16-be"),
                 id="utf16be_con_marca"),
    pytest.param(f"uno\ncon {CENTINELA}\n".encode("utf-32"),
                 id="utf32_con_marca"),
    pytest.param(f"Canción\ncon {_CON_TILDE}\n".encode("latin-1"),
                 id="latin1"),
    pytest.param(f"Canción\ncon {_CON_TILDE}".encode("utf-8") + b" \x96 fin\n",
                 id="utf8_con_un_byte_cp1252_suelto"),
])
def test_el_texto_que_no_es_utf8_tambien_se_recorre(tmp_path, datos):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "tabla.csv").write_bytes(datos)
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    if b"\0" in datos and not datos.startswith((b"\xff\xfe", b"\xfe\xff")):
        # Bytes nulos sin marca de orden de bytes: binario, se declara.
        assert not va.es_texto(raiz / "tabla.csv")
        assert "tabla.csv" in [p.name for p in va.binarios(raiz)]
        assert hallazgos == []
        return
    assert va.es_texto(raiz / "tabla.csv")
    assert "tabla.csv" not in [p.name for p in va.binarios(raiz)]
    assert [(h["fichero"], h["linea"]) for h in hallazgos] == [
        ("tabla.csv", 2)]


# --------------------------------------------------------------------------
# Con git: lo que se publicaria (la copia de trabajo sin lo ignorado, el
# indice y, con --commit, el arbol del commit)
# --------------------------------------------------------------------------
hay_git = pytest.mark.skipif(shutil.which("git") is None,
                             reason="sin git en el PATH: queda sin verificar "
                                    "el recorrido de lo versionado y el "
                                    "commit")


def _git(raiz, *argumentos, **entorno):
    """git sobre el repositorio de juguete, sin la configuracion de nadie."""
    vacio = raiz.parent / "gitconfig-vacio"
    vacio.touch()
    limpio = {c: v for c, v in os.environ.items() if not c.startswith("GIT_")}
    limpio.update(GIT_CONFIG_GLOBAL=str(vacio), GIT_CONFIG_NOSYSTEM="1",
                  GIT_AUTHOR_NAME="Autor Neutro",
                  GIT_AUTHOR_EMAIL="autor@ejemplo.test",
                  GIT_COMMITTER_NAME="Autor Neutro",
                  GIT_COMMITTER_EMAIL="autor@ejemplo.test")
    limpio.update(entorno)
    hecho = subprocess.run(["git", "-C", str(raiz), *argumentos], check=True,
                           capture_output=True, env=limpio)
    return hecho.stdout.decode("utf-8")


def _repositorio(tmp_path):
    raiz = _arbol_limpio(tmp_path / "repo")
    _git(raiz, "init", "-q")
    # Una carpeta temporal larga no hace fallar las pruebas de nombres largos
    # (una rama con nombre de token, C2): git en Windows, sin esto, no pasa
    # de 260 caracteres.
    _git(raiz, "config", "core.longpaths", "true")
    _git(raiz, "add", "-A")
    return raiz


@hay_git
def test_en_un_repositorio_se_recorre_lo_versionado_y_lo_no_ignorado(
        tmp_path):
    # Antes: «se recorre solo lo versionado». Lo que no tiene seguimiento y
    # no esta ignorado tambien se publica (`git add -A` lo anade): se recorre.
    raiz = _repositorio(tmp_path)
    (raiz / ".gitignore").write_text("ignorado.txt\n", encoding="utf-8")
    (raiz / "ignorado.txt").write_text(CENTINELA + "\n", encoding="utf-8")
    (raiz / "sin_versionar.txt").write_text(CENTINELA + "\n",
                                            encoding="utf-8")
    nombres = [p.relative_to(raiz).as_posix()
               for p in va.ficheros_versionados(raiz)]
    assert nombres == [".gitignore", "codigo.py", "docs/guia.md",
                       "figura.png", "sin_versionar.txt"]
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("sin_versionar.txt", 1, COPIA)]

    (raiz / "docs" / "guia.md").write_text(f"ahora sí: {CENTINELA}\n",
                                           encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("docs/guia.md", 1, COPIA), ("sin_versionar.txt", 1, COPIA)]


@hay_git
def test_un_repositorio_recien_creado_sin_add_se_recorre(tmp_path):
    raiz = _arbol_limpio(tmp_path / "repo")
    _git(raiz, "init", "-q")
    (raiz / "docs" / "nota.md").write_text(f"primera\ncon {CENTINELA}\n",
                                           encoding="utf-8")
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == [
        {"fichero": "docs/nota.md", "linea": 2,
         "huella": va.huella(CENTINELA), "origen": COPIA}]


@hay_git
def test_la_cli_sobre_un_arbol_vacio_no_dice_limpio(tmp_path, capsys):
    huellas = str(_huellas_de_juguete(tmp_path))
    vacio = tmp_path / "vacio"
    vacio.mkdir()
    _git(vacio, "init", "-q")
    sin_git = tmp_path / "sin_git"
    sin_git.mkdir()
    for raiz in (vacio, sin_git):
        assert va.main(["--raiz", str(raiz), "--huellas", huellas]) == 1
        salida = capsys.readouterr().out
        assert "ficheros recorridos: 0" in salida
        assert salida.splitlines()[-1].startswith("NO publicar: no se "
                                                  "recorrió ningún fichero")


@hay_git
def test_lo_preparado_y_limpiado_despues_en_disco_sale_del_indice(tmp_path):
    raiz = _repositorio(tmp_path)
    guia = raiz / "docs" / "guia.md"
    limpio = guia.read_bytes()
    guia.write_text(f"uno\ncon {CENTINELA}\n", encoding="utf-8")
    _git(raiz, "add", "docs/guia.md")
    guia.write_bytes(limpio)
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == [
        {"fichero": "docs/guia.md", "linea": 2,
         "huella": va.huella(CENTINELA), "origen": INDICE}]


@hay_git
def test_lo_preparado_y_borrado_del_disco_se_recorre(tmp_path):
    raiz = _repositorio(tmp_path)
    nota = raiz / "nota.md"
    nota.write_text(f"{CENTINELA}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    nota.unlink()
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("nota.md", 1, INDICE)]


@hay_git
def test_con_commit_se_recorre_el_arbol_del_commit(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    nota = raiz / "nota.md"
    nota.write_text(f"uno\n{CENTINELA} y {OTRO}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    _git(raiz, "commit", "-q", "-m", "arbol")
    nota.write_text("uno\nya limpio\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")            # copia e indice, limpios

    huellas = {va.huella(CENTINELA)}
    assert va.buscar_huellas(raiz, huellas) == []
    assert va.buscar_huellas(raiz, huellas, commit="HEAD") == [
        {"fichero": "nota.md", "linea": 2,
         "huella": va.huella(CENTINELA), "origen": COMMIT}]

    de_juguete = str(_huellas_de_juguete(tmp_path))
    assert va.main(["--raiz", str(raiz), "--huellas", de_juguete]) == 0
    capsys.readouterr()
    assert va.main(["--raiz", str(raiz), "--huellas", de_juguete,
                    "--commit", "HEAD"]) == 1
    salida = capsys.readouterr().out
    assert f"nota.md:2: huella {va.huella(OTRO)[:12]} (commit)" in salida
    assert OTRO not in salida.lower()


@hay_git
def test_un_mismo_contenido_se_recorre_una_sola_vez(tmp_path):
    raiz = _repositorio(tmp_path)
    (raiz / "nota.md").write_text(f"{CENTINELA}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    _git(raiz, "commit", "-q", "-m", "arbol")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)},
                                  commit="HEAD")
    assert [(h["fichero"], h["origen"]) for h in hallazgos] == [
        ("nota.md", COPIA)]


@hay_git
def test_una_subcarpeta_de_un_repositorio_se_recorre_entera(tmp_path):
    # No es la raiz de un repositorio: se recorre todo lo que hay debajo,
    # tambien lo ignorado (es el arbol que alguien copiaria para publicar).
    raiz = _repositorio(tmp_path)
    (raiz / ".gitignore").write_text("docs/ignorado.md\n", encoding="utf-8")
    (raiz / "docs" / "ignorado.md").write_text(f"{CENTINELA}\n",
                                               encoding="utf-8")
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []
    hallazgos = va.buscar_huellas(raiz / "docs", {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("ignorado.md", 1, COPIA)]
    assert [p.name for p in va.ficheros_versionados(raiz / "docs")] == [
        "guia.md", "ignorado.md"]


@hay_git
def test_las_ordenes_de_git_no_heredan_el_repositorio_del_entorno(
        tmp_path, monkeypatch):
    raiz = _repositorio(tmp_path)
    (raiz / ".gitignore").write_text("ignorado.md\n", encoding="utf-8")
    (raiz / "ignorado.md").write_text(f"{CENTINELA}\n", encoding="utf-8")
    nota = raiz / "nota.md"
    nota.write_text(f"{CENTINELA}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    nota.unlink()                       # solo queda en el indice

    otro = _arbol_limpio(tmp_path / "otro")
    _git(otro, "init", "-q")
    _git(otro, "add", "-A")
    monkeypatch.setenv("GIT_DIR", str(otro / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(otro))
    monkeypatch.setenv("GIT_INDEX_FILE", str(otro / ".git" / "index"))

    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"], h["origen"]) for h in hallazgos] == [
        ("nota.md", 1, INDICE)]


def _no_recorrido(fichero, origen):
    return {"fichero": fichero, "linea": 0, "clase": "no_recorrido",
            "origen": origen}


@hay_git
def test_un_submodulo_no_se_recorre_en_silencio(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "uno")
    sha = _git(raiz, "rev-parse", "HEAD").strip()
    _git(raiz, "update-index", "--add", "--cacheinfo",
         f"160000,{sha},vendor/otro")
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("vendor/otro", INDICE)]

    _git(raiz, "commit", "-q", "-m", "con submodulo")
    assert va.buscar_secretos(raiz, huellas=set(), commit="HEAD") == [
        _no_recorrido("vendor/otro", INDICE)]
    assert va.main(["--raiz", str(raiz),
                    "--huellas", str(_huellas_de_juguete(tmp_path))]) == 1
    salida = capsys.readouterr().out
    assert "vendor/otro:0: no_recorrido (indice)" in salida


@hay_git
def test_un_enlace_simbolico_del_indice_no_se_recorre_en_silencio(tmp_path):
    # Se prepara con git, sin crear el enlace en disco: vale tambien en una
    # maquina que no deja crear enlaces simbolicos.
    raiz = _repositorio(tmp_path)
    (raiz / "destino.txt").write_text("docs/guia.md", encoding="utf-8")
    sha = _git(raiz, "hash-object", "-w", "destino.txt").strip()
    (raiz / "destino.txt").unlink()
    _git(raiz, "update-index", "--add", "--cacheinfo", f"120000,{sha},enlace")
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("enlace", INDICE)]


@hay_git
def test_otro_repositorio_dentro_sin_seguimiento_no_se_recorre(tmp_path):
    raiz = _repositorio(tmp_path)
    dentro = raiz / "vendor" / "otro"
    dentro.mkdir(parents=True)
    _git(dentro, "init", "-q")
    (dentro / "nota.md").write_text(f"{CENTINELA}\n", encoding="utf-8")
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("vendor/otro", COPIA)]


def _enlazar(enlace, destino):
    try:
        os.symlink(destino, enlace)
    except (OSError, NotImplementedError) as error:
        pytest.skip("esta maquina no deja crear enlaces simbolicos "
                    f"({error.__class__.__name__}): queda sin verificar que "
                    "un enlace simbolico en disco se declara no_recorrido")


@pytest.mark.parametrize("con_git", [
    pytest.param(False, id="sin_git"),
    pytest.param(True, id="con_git", marks=hay_git),
])
def test_un_enlace_simbolico_en_disco_no_se_recorre_en_silencio(tmp_path,
                                                               con_git):
    raiz = _repositorio(tmp_path) if con_git else _arbol_limpio(
        tmp_path / "repo")
    fuera = tmp_path / "fuera.md"
    fuera.write_text(f"{CENTINELA}\n", encoding="utf-8")
    _enlazar(raiz / "enlace.md", fuera)
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("enlace.md", COPIA)]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []


def test_un_fichero_que_no_se_puede_leer_no_se_recorre_en_silencio(
        tmp_path, monkeypatch):
    raiz = _arbol_limpio(tmp_path / "arbol")
    leer = Path.read_bytes

    def leer_salvo_la_guia(ruta):
        if ruta.name == "guia.md":
            raise PermissionError(13, "acceso denegado")
        return leer(ruta)

    monkeypatch.setattr(Path, "read_bytes", leer_salvo_la_guia)
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("docs/guia.md", COPIA)]


@pytest.mark.parametrize("con_git", [
    pytest.param(False, id="sin_git"),
    pytest.param(True, id="con_git", marks=hay_git),
])
def test_lo_que_el_disco_dice_que_es_un_enlace_no_se_recorre(
        tmp_path, monkeypatch, con_git):
    # La misma rama que la prueba de arriba, en una maquina sin enlaces: un
    # fichero normal que `_es_enlace` declara enlace.
    raiz = _repositorio(tmp_path) if con_git else _arbol_limpio(
        tmp_path / "repo")
    (raiz / "enlace.md").write_text(f"{CENTINELA}\n", encoding="utf-8")
    monkeypatch.setattr(va, "_es_enlace",
                        lambda ruta: Path(ruta).name == "enlace.md")
    assert va.buscar_secretos(raiz, huellas=set()) == [
        _no_recorrido("enlace.md", COPIA)]
    assert "enlace.md" not in [p.name for p in va.ficheros_versionados(raiz)]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []


def test_sin_repositorio_se_recorre_todo_salvo_la_carpeta_de_git(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / ".git").mkdir()
    (raiz / ".git" / "config").write_text(CENTINELA, encoding="utf-8")
    nombres = [p.relative_to(raiz).as_posix()
               for p in va.ficheros_versionados(raiz)]
    assert nombres == ["codigo.py", "docs/guia.md", "figura.png"]


@hay_git
def test_verificar_commit_mira_autor_quien_confirma_y_mensaje(tmp_path):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "primer commit", "-m", "sin nada")
    huellas = {va.huella(CENTINELA)}
    assert va.commits(raiz) == 1
    assert va.verificar_commit(raiz, huellas=huellas) == []

    (raiz / "codigo.py").write_text("x = 2\n", encoding="utf-8")
    _git(raiz, "commit", "-q", "-a", "-m", "segundo",
         "-m", f"cuerpo con {CENTINELA}",
         "-m", f"Co-Authored-By: Alguien <alguien@{CENTINELA}.test>",
         GIT_AUTHOR_NAME=f"Nombre {CENTINELA.upper()}",
         GIT_COMMITTER_NAME=f"Quien {CENTINELA}",
         GIT_COMMITTER_EMAIL=f"{CENTINELA}@ejemplo.test")
    assert va.commits(raiz) == 2
    hallazgos = va.verificar_commit(raiz, "HEAD", huellas=huellas)
    assert [(h["campo"], h["linea"]) for h in hallazgos] == [
        ("autor", 0), ("quien_confirma", 0), ("correo_de_quien_confirma", 0),
        ("mensaje", 3), ("mensaje", 5)]
    assert all(h["huella"] == va.huella(CENTINELA) for h in hallazgos)
    assert CENTINELA not in repr(hallazgos).lower()
    assert va.verificar_commit(raiz, "HEAD~1", huellas=huellas) == []


@hay_git
def test_una_revision_que_no_existe_no_saca_el_token(tmp_path):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol")
    huellas = {va.huella(OTRO)}
    for funcion in (va.verificar_commit, va.cabeceras_del_commit):
        with pytest.raises(SystemExit) as error:
            funcion(raiz, f"inexistente-{OTRO}", huellas=huellas)
        assert OTRO not in str(error.value).lower()
        assert "inexistente-<huella-" in str(error.value)


@hay_git
def test_la_rama_de_un_repositorio_sin_commits_tambien_se_mira(tmp_path):
    # `git init` y nada mas: la rama a la que va HEAD aun no existe como
    # referencia, pero su nombre se publica con el primer push.
    raiz = _arbol_limpio(tmp_path / "repo")
    _git(raiz, "init", "-q")
    _git(raiz, "symbolic-ref", "HEAD", f"refs/heads/informe-{OTRO}")
    tapada = f"informe-<huella-{va.huella(OTRO)[:12]}>"
    assert va.verificar_referencias(raiz, {va.huella(OTRO)}) == [
        {"referencia": "rama", "nombre": tapada, "huella": va.huella(OTRO)}]


def _commit_a_mano(raiz, *cabeceras_de_mas):
    """Apunta HEAD a un commit escrito a mano (`git hash-object`) con el
    arbol de HEAD, un autor neutro y las cabeceras que se pasen: asi se
    prueba un commit firmado sin ninguna clave."""
    arbol = _git(raiz, "rev-parse", "HEAD^{tree}").strip()
    firma = "Autor Neutro <autor@ejemplo.test> 1700000000 +0000"
    crudo = raiz.parent / "commit-a-mano.txt"
    crudo.write_bytes((f"tree {arbol}\nauthor {firma}\ncommitter {firma}\n"
                       + "".join(cabeceras_de_mas)
                       + "\narbol escrito a mano\n").encode("utf-8"))
    sha = _git(raiz, "hash-object", "-t", "commit", "-w", str(crudo)).strip()
    _git(raiz, "update-ref", "HEAD", sha)


@hay_git
def test_una_cabecera_de_mas_en_el_commit_es_un_hallazgo(tmp_path):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol")
    huellas = str(_huellas_de_juguete(tmp_path))
    firma = ("gpgsig -----BEGIN PGP SIGNATURE-----\n \n"
             " firma de juguete\n -----END PGP SIGNATURE-----\n")
    _commit_a_mano(raiz, firma)
    assert va.cabeceras_del_commit(raiz, "HEAD", huellas=set()) == [
        {"campo": "gpgsig", "linea": 0, "clase": "cabecera_del_commit"}]
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit")
    assert codigo == 1
    assert "commit HEAD: gpgsig: cabecera_del_commit" in salida
    assert "juguete" not in salida and "PGP" not in salida

    _commit_a_mano(raiz)                        # el mismo, sin la firma
    assert va.cabeceras_del_commit(raiz, "HEAD", huellas=set()) == []
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit")
    assert codigo == 0, salida
    assert "commit HEAD: 0" in salida


@hay_git
def test_con_un_solo_commit_un_padre_es_una_cabecera_de_mas(tmp_path):
    # Un commit con padre no es el unico: con --un-solo-commit, `parent` es
    # un hallazgo; con --commit a secas, no (el repositorio de desarrollo).
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "uno")
    assert va.cabeceras_del_commit(raiz, huellas=set(),
                                   un_solo_commit=True) == []
    _git(raiz, "commit", "-q", "--allow-empty", "-m", "dos")
    assert va.cabeceras_del_commit(raiz, huellas=set()) == []
    assert va.cabeceras_del_commit(raiz, huellas=set(),
                                   un_solo_commit=True) == [
        {"campo": "parent", "linea": 0, "clase": "cabecera_del_commit"}]


# --------------------------------------------------------------------------
# Secretos. Se componen al correr: ver el docstring del fichero.
# --------------------------------------------------------------------------
def _secretos():
    return {
        "token_de_bot_de_telegram": _token_de_bot(),
        "clave_de_api_sk": "sk" + "-" + "proj" + "-" + "a1B2" * 6,
        "clave_de_api_akia": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "clave_de_api_ghp": "gh" + "p_" + "a1B2" * 9,
        "clave_de_api_github_pat": "github" + "_pat_" + "a1B2_" * 6,
        "jwt": ".".join(["ey" + "J" + "hbGciOiJIUzI1NiJ9",
                         "ey" + "J" + "zdWIiOiIxMjM0NTY3ODkwIn0",
                         "dozjgNryP4J3jVmNHl0w5N"]),
        "contrasena_en_url": "postgresql://usuario" + ":" + "S3creta!"
                             + "@" + "bd.ejemplo.test:5432/base",
        "clave_de_api_aiza": "AI" + "za"
                             + "SyA1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6q",
        "clave_de_api_gho": "gh" + "o_" + "a1B2" * 9,
        "clave_de_api_ghs": "gh" + "s_" + "a1B2" * 9,
        "clave_de_api_asia": "AS" + "IA" + "ABCDEFGHIJKLMNOP",
        "clave_privada": "-----BEGIN " + "OPENSSH PRIV" + "ATE KEY-----",
        "cabecera_authorization": "Author" + "ization: Bearer "
                                  + "a1B2c3D4" * 3,
        "asignacion_de_secreto": "PASS" + "WORD=" + "a1B2c3D4e5F6g7H8",
    }


def _token_de_bot(cifras="123456789"):
    return cifras + ":" + "AAH" + "x" * 32


# Valores de juguete con forma de secreto. Sin la clave delante: la linea que
# los define no es una asignacion.
_LITERAL = "a1B2c3D4" + "e5F6g7H8"
_CON_LLAVES = "S3cr{" + "eta}9x"
_CON_CORCHETES = "Ab[12]" + "cdefg"
_CON_PARENTESIS = "Kq9)" + "w2Lm4z"


# Otras formas de las mismas clases: (id de la prueba, clase, secreto).
_VARIANTES = [
    ("telegram_en_url", "token_de_bot_de_telegram",
     "curl https://api.telegram.org/bot" + _token_de_bot() + "/setWebhook"),
    ("telegram_en_expresion_de_n8n", "token_de_bot_de_telegram",
     "=https://api.telegram.org/bot" + _token_de_bot()
     + "/sendMessage?chat_id={{ $json.chat_id }}"),
    ("telegram_id_de_10_cifras_en_url", "token_de_bot_de_telegram",
     "https://api.telegram.org/bot" + _token_de_bot("1234567890") + "/getMe"),
    ("telegram_id_de_12_cifras", "token_de_bot_de_telegram",
     _token_de_bot("123456789012")),
    ("clave_privada_rsa", "clave_privada",
     "-----BEGIN " + "RSA PRIV" + "ATE KEY-----"),
    ("clave_privada_sin_tipo", "clave_privada",
     "-----BEGIN " + "PRIV" + "ATE KEY-----"),
    ("authorization_basic", "cabecera_authorization",
     "-H 'author" + "ization: basic " + "dXN1YXJpbzpTM2NyZXRhMTIzNDU2'"),
    ("asignacion_en_un_compose", "asignacion_de_secreto",
     "POSTGRES_" + "PASSWORD: " + "a1B2c3D4e5F6g7H8"),
    ("asignacion_fuera_de_un_env", "asignacion_de_secreto",
     "COPILOTO_BD_" + "PASSWORD=" + "a1B2c3D4e5F6g7H8"),
    ("asignacion_de_secret_token", "asignacion_de_secreto",
     "secret" + "_token=" + "0123456789abcdef" * 2),
    ("asignacion_de_api_key_en_json", "asignacion_de_secreto",
     '"api' + '_key": "' + "a1B2c3D4e5F6g7H8" + '"'),
    ("asignacion_de_passwd_entre_comillas", "asignacion_de_secreto",
     "db_pass" + "wd = 'Zq9" + "x7Kw2Lm4'"),
    ("url_sin_usuario", "contrasena_en_url",
     "redis://" + ":" + "S3creta!" + "@" + "cache.ejemplo.test:6379/0"),
    ("url_con_dolar_que_no_es_variable", "contrasena_en_url",
     "postgresql://u" + ":" + "$uperS3creta9" + "@" + "bd.ejemplo.test/b"),
    ("url_con_angulos_que_no_son_marcador", "contrasena_en_url",
     "postgresql://u" + ":" + "<S3:creta>" + "@" + "bd.ejemplo.test/b"),
    # R4: las formas de este proyecto que no saltaban.
    ("url_con_barra_en_la_contrasena", "contrasena_en_url",
     "postgresql://u" + ":" + "S3cr/eta+9w==" + "@" + "bd.ejemplo.test/b"),
    ("url_con_valor_por_defecto", "contrasena_en_url",
     "postgresql://u" + ":" + "${PGPASS:-S3creta!}" + "@" + "bd.ejemplo.test"),
    ("asignacion_con_subindice", "asignacion_de_secreto",
     'os.environ["COPILOTO_BD_' + 'PASSWORD"] = "' + "a1B2c3D4e5F6g7H8" + '"'),
    ("asignacion_con_llamada", "asignacion_de_secreto",
     'monkeypatch.setenv("COPILOTO_BD_' + 'PASSWORD", "' + "a1B2c3D4e5F6g7H8"
     + '")'),
    ("clave_que_acaba_en_key_con_subindice", "asignacion_de_secreto",
     # El valor, por una llamada: con las comillas mezcladas, el propio
     # codigo de la prueba formaria un literal.
     "os.environ['KAGGLE" + "_KEY'] = '" + "".join(["0123456789abcdef"] * 2)
     + "'"),
    ("clave_que_acaba_en_key", "asignacion_de_secreto",
     "AWS_ACCESS" + "_KEY=" + "a1B2c3D4e5F6g7H8"),
    ("clave_privada_en_una_variable", "asignacion_de_secreto",
     "PRIVATE" + "_KEY: " + "a1B2c3D4e5F6g7H8"),
    ("asignacion_en_json_escapado", "asignacion_de_secreto",
     '"source": ["pass' + 'word=\\"' + "a1B2c3D4e5F6g7H8" + '\\"\\n"]'),
    ("valor_por_defecto_de_una_variable", "asignacion_de_secreto",
     "COPILOTO_BD_PASS" + "WORD: ${COPILOTO_BD_PASSWORD:-" + "a1B2c3D4e5F6g7H8"
     + "}"),
    # A1: la terminacion `_KEY` cuenta escrita en mayusculas; en minusculas,
    # solo con unos pocos nombres delante.
    ("key_en_mayusculas", "asignacion_de_secreto",
     "KAGGLE" + "_KEY=" + _LITERAL),
    ("access_key_en_un_compose", "asignacion_de_secreto",
     "AWS_ACCESS" + "_KEY: " + _LITERAL),
    ("private_key_en_minusculas", "asignacion_de_secreto",
     "private" + '_key = "' + _LITERAL + '"'),
    ("signing_key_en_minusculas", "asignacion_de_secreto",
     "signing" + "_key: '" + _LITERAL + "'"),
    # A2: entre comillas, un parentesis, un corchete o una llave no hacen
    # una expresion (regresion de la ronda 2).
    ("entre_comillas_con_llaves", "asignacion_de_secreto",
     "pass" + 'word = "' + _CON_LLAVES + '"'),
    ("entre_comillas_con_corchetes_en_json", "asignacion_de_secreto",
     '"pass' + 'word": "' + _CON_CORCHETES + '"'),
    ("entre_comillas_con_parentesis", "asignacion_de_secreto",
     "PASS" + "WORD: '" + _CON_PARENTESIS + "'"),
    # A4: lo de antes de los dos puntos no parece un host, asi que no es un
    # puerto y una ruta.
    ("url_con_contrasena_que_empieza_por_cifras", "contrasena_en_url",
     "postgresql://u" + ":" + "2024/Secreta9x" + "@" + "host/base"),
    # A5: `Bot` en mayusculas y los dos puntos escapados.
    ("telegram_con_bot_capitalizado", "token_de_bot_de_telegram",
     "https://api.telegram.org/Bot" + _token_de_bot() + "/getMe"),
    ("telegram_con_bot_en_mayusculas", "token_de_bot_de_telegram",
     "https://api.telegram.org/BOT" + _token_de_bot() + "/getMe"),
    ("telegram_con_los_dos_puntos_escapados", "token_de_bot_de_telegram",
     _token_de_bot().replace(":", "%3A")),
    ("telegram_con_los_dos_puntos_escapados_en_minusculas",
     "token_de_bot_de_telegram",
     "https://api.telegram.org/bot" + _token_de_bot().replace(":", "%3a")
     + "/getMe"),
]


def _casos_de_secreto():
    return ([pytest.param(c, s, id=c) for c, s in sorted(_secretos().items())]
            + [pytest.param(c, s, id=i) for i, c, s in _VARIANTES])


@pytest.mark.parametrize("clase, secreto", _casos_de_secreto())
def test_buscar_secretos_encuentra_cada_clase_sin_imprimirla(tmp_path, clase,
                                                            secreto):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "config.txt").write_text(f"uno\ndos\nVALOR = \"{secreto}\"\n",
                                     encoding="utf-8")
    hallazgos = va.buscar_secretos(raiz)
    assert hallazgos == [{"fichero": "config.txt", "linea": 3,
                          "clase": clase, "origen": COPIA}]
    assert secreto not in repr(hallazgos)


def test_las_contrasenas_de_ejemplo_en_url_se_permiten(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    valores = ["prueba", "cambiar-esto", "clave", "token", "<contraseña>",
               "...", "%s", "$CLAVE", "${COPILOTO_BD_PASSWORD}"]
    assert set(valores[:4]) | {"...", "%s"} <= set(va.CONTRASENAS_DE_EJEMPLO)
    (raiz / "guia.md").write_text(
        "".join("postgresql://usuario" + ":" + v + "@" + "host:5432/base\n"
                for v in valores), encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


def test_una_url_sin_contrasena_no_es_un_hallazgo(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "guia.md").write_text(
        "git clone https://github.com/<cuenta>/copiloto-triaje.git\n"
        "correo: alguien@ejemplo.test, http://127.0.0.1:8000/salud\n"
        "ssh://git@ejemplo.test:22/repo.git\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


@pytest.mark.parametrize("nombre", [
    ".env", "servidor/.env", ".env.local", "kaggle.json", "claves/servidor.pem",
    "privada.key", "id_rsa", "id_rsa.pub", "certificado.p12",
    "id_ed25519", "id_ecdsa", "id_dsa.pub", "produccion.env", ".envrc",
    "putty.ppk", "certificado.pfx", "credentials.json",
    ".pgpass", ".netrc", ".git-credentials",
    "client_secret_1234.apps.googleusercontent.com.json",
    # Los nombres no distinguen mayusculas.
    ".ENV", "servidor.PEM", "Kaggle.json", "ID_RSA"])
def test_los_ficheros_prohibidos_son_hallazgos(tmp_path, nombre):
    raiz = _arbol_limpio(tmp_path / "arbol")
    ruta = raiz / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("X=1\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == [
        {"fichero": nombre, "linea": 0, "clase": "fichero_prohibido",
         "origen": COPIA}]


def test_lo_que_este_proyecto_escribe_de_tokens_y_contrasenas_no_salta(
        tmp_path):
    # Las formas que el arbol usa de verdad: variables, marcadores, valores
    # de ejemplo y codigo. Ninguna es un valor literal que parezca secreto.
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "notas.md").write_text("\n".join([
        'token = os.environ.get("TELEGRAM_TOKEN_AVISOS")',
        'monkeypatch.setenv("TELEGRAM_TOKEN_AVISOS", "T0K3N")',
        "COPILOTO_BD_PASSWORD=cambiar-esto",
        "POSTGRES_PASSWORD: ${COPILOTO_BD_PASSWORD:?falta la contraseña}",
        "TELEGRAM_SECRET_PRUEBA=x python -m pytest",
        'DSN = "host=127.0.0.1 user=postgres password=verifica"',
        '"CRED_SECRETO_PACIENTE": "id-de-ejemplo-secreto-paciente",',
        "$s = Read-Host 'secret_token'; secret_token=$s",
        "password = $(Read-Host 'contraseña')",
        "Authorization: Bearer ${TOKEN_DEL_BOT}",
        "Authorization: Bearer <token>",
        'headers = {"Authorization": f"Bearer {token}"}',
        'api_key = config["api_key"]',
        "secretos: 2 (clave_de_api_akia: 1)",
        "X-Telegram-Bot-Api-Secret-Token: {{ $json.secreto }}",
        # R4: una expresion no es un literal; ni una variable.
        "token = partes[1]",
        "token = sys.argv[1]",
        '"token": "={{ $env.X_2 }}"',
        "Authorization: Bearer <TOKEN_DEL_BOT>",
        "COPILOTO_BD_PASSWORD: ${COPILOTO_BD_PASSWORD:-cambiar-esto}",
        # Un puerto y una ruta con arroba no son una contrasena.
        "https://ejemplo.test:8443/paquete/@ambito/x",
    ]) + "\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


@pytest.mark.parametrize("linea", [
    # A1: una clave que acaba en `_key` en minusculas no nombra un secreto,
    # salvo unas pocas (`private_key`, `access_key`...).
    pytest.param('cache_key = "modelo_v2_2026"', id="cache_key"),
    pytest.param('primary_key="id_consulta_01"', id="primary_key"),
    pytest.param('model_key = "densenet121"', id="model_key"),
    pytest.param('sort_key = "fecha_2026"', id="sort_key"),
    pytest.param('{"cache_key": "modelo_v2_2026"}', id="cache_key_en_json"),
    # A2: una expresion sigue sin ser un literal: suelta, con parentesis,
    # corchetes o llaves; entre comillas, con `{{`, `${`, `$(` o `=` delante.
    pytest.param("token = partes[1]", id="subindice_suelto"),
    pytest.param("token = sys.argv[1]", id="argumento_suelto"),
    pytest.param('"token": "={{ $env.X_2 }}"', id="expresion_de_n8n"),
    pytest.param('"secret": "={{ $credentials.x1 }}"',
                 id="credencial_de_n8n"),
    pytest.param('password = "${CLAVE_2}"', id="variable_entre_comillas"),
    pytest.param('password = "$(Read-Host clave_2)"',
                 id="orden_entre_comillas"),
    pytest.param("Authorization: Bearer <TOKEN_DEL_BOT>", id="marcador"),
    # A3: con subindice o detras de una coma, el valor sin comillas es una
    # variable.
    pytest.param('os.environ["X_TOKEN"] = variable2', id="subindice_variable"),
    pytest.param('setenv("X_PASSWORD", valor_2)', id="coma_variable"),
    pytest.param('setenv("X_PASSWORD", variable2, prepend=None)',
                 id="coma_variable_y_otro_argumento"),
    # A4: un host (con punto, o localhost), un puerto y una ruta con arroba.
    pytest.param("https://ejemplo.test:8443/ruta/@ambito", id="puerto_y_ruta"),
    pytest.param("http://localhost:8000/x@y", id="localhost"),
])
def test_estas_formas_no_son_un_secreto(linea):
    assert va._clases_de_secreto(linea) == []


# A7: el patron de las asignaciones es cuadratico en las tiradas de letras,
# cifras, puntos y guiones; no se aplica a la linea que no lleva ninguna de
# sus palabras clave (ni el de la URL a la que no lleva `://`).
@pytest.mark.parametrize("linea", [
    pytest.param("-" * 100_000, id="guiones"),
    pytest.param("uno.dos.tres.cuatro." * 5_000, id="palabras_con_puntos"),
])
def test_una_linea_larguisima_no_cuesta_segundos(linea):
    assert len(linea) == 100_000
    inicio = time.perf_counter()
    va._clases_de_secreto(linea)
    assert time.perf_counter() - inicio < 2


def test_un_secreto_al_final_de_una_linea_larga_sigue_saltando():
    relleno = "-" * 2_000 + " "
    assert va._clases_de_secreto(relleno + "PASS" + "WORD=" + _LITERAL) == [
        "asignacion_de_secreto"]
    assert va._clases_de_secreto(
        relleno + "postgresql://u" + ":" + "S3creta9x" + "@" + "bd.ejemplo.test"
    ) == ["contrasena_en_url"]


def test_el_env_de_ejemplo_se_permite(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / ".env.ejemplo").write_text(
        "COPILOTO_BD_PASSWORD=cambiar-esto\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


# --------------------------------------------------------------------------
# La linea de ordenes
# --------------------------------------------------------------------------
def _huellas_de_juguete(tmp_path):
    destino = tmp_path / "huellas.txt"
    va.regenerar([OTRO], destino)
    return destino


def _cli(*argumentos, cwd=None):
    """El script como lo corre una persona: codigo de salida y TODA la
    salida (la normal y la de errores, juntas)."""
    entorno = {c: v for c, v in os.environ.items() if c != "ANONIMATO_LISTA"}
    entorno["PYTHONIOENCODING"] = "utf-8"
    hecho = subprocess.run([sys.executable, "-B", str(SCRIPT), *argumentos],
                           cwd=cwd, capture_output=True, env=entorno)
    salida = (hecho.stdout + hecho.stderr).decode("utf-8", errors="replace")
    return hecho.returncode, salida


def test_la_cli_sale_con_0_sobre_un_arbol_limpio(tmp_path, capsys):
    raiz = _arbol_limpio(tmp_path / "arbol")
    # El centinela es publico (el spec lo nombra): en el arbol no cuenta.
    (raiz / "spec.md").write_text(f"el token `{CENTINELA}`\n",
                                  encoding="utf-8")
    codigo = va.main(["--raiz", str(raiz),
                      "--huellas", str(_huellas_de_juguete(tmp_path))])
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "huellas: 0" in salida and "secretos: 0" in salida
    assert "binarios sin recorrer: 1" in salida
    assert "figura.png" in salida


def test_con_binarios_sin_recorrer_no_dice_limpio_a_secas(tmp_path, capsys):
    raiz = _arbol_limpio(tmp_path / "arbol")          # con figura.png
    huellas = str(_huellas_de_juguete(tmp_path))
    assert va.main(["--raiz", str(raiz), "--huellas", huellas]) == 0
    ultima = capsys.readouterr().out.splitlines()[-1]
    assert ultima != "limpio"
    assert ultima.startswith("limpio lo recorrido")
    assert "1 binario" in ultima and "a mano" in ultima

    (raiz / "figura.png").unlink()
    assert va.main(["--raiz", str(raiz), "--huellas", huellas]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "limpio"


def test_la_cli_sale_con_1_y_resume_por_clase(tmp_path, capsys):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "a.md").write_text(f"x\n{OTRO}\n{OTRO.upper()}\n",
                               encoding="utf-8")
    (raiz / "b.md").write_text(_secretos()["clave_de_api_akia"] + "\n",
                               encoding="utf-8")
    codigo = va.main(["--raiz", str(raiz),
                      "--huellas", str(_huellas_de_juguete(tmp_path))])
    salida = capsys.readouterr().out
    assert codigo == 1
    assert "a.md:2: huella " + va.huella(OTRO)[:12] in salida
    assert "b.md:1: clave_de_api_akia" in salida
    assert "huellas: 2 en 1 ficheros" in salida
    assert "secretos: 1 (clave_de_api_akia: 1)" in salida
    assert OTRO not in salida.lower()
    assert _secretos()["clave_de_api_akia"] not in salida


def test_la_cli_con_solo_el_centinela_no_dice_limpio(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    publico = tmp_path / "publico.txt"
    publico.write_text("# cabecera\n" + va.huella(CENTINELA) + "\n",
                       encoding="utf-8")
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", str(publico))
    assert codigo == 1
    assert "solo la huella del centinela" in salida
    assert "--huellas" in salida and "repositorio de desarrollo" in salida
    assert "limpio" not in salida.splitlines()
    assert "Traceback" not in salida


def test_la_cli_con_huellas_mal_formadas_dice_la_linea_y_no_su_contenido(
        tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    malo = tmp_path / "malo.txt"
    malo.write_text(f"# cabecera\n{va.huella(OTRO)}\n{OTRO}\n",
                    encoding="utf-8")
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", str(malo))
    assert codigo == 1
    assert "línea 3" in salida
    assert OTRO not in salida.lower()
    assert "Traceback" not in salida


def _sin_rutas_absolutas(salida, *carpetas):
    for carpeta in (*carpetas, RAIZ):
        for forma in (str(carpeta), carpeta.as_posix()):
            assert forma.lower() not in salida.lower()


@hay_git
def test_la_cli_no_imprime_rutas_absolutas(tmp_path):
    raiz = _repositorio(tmp_path)
    (raiz / "docs" / "nota.md").write_text(
        f"{OTRO}\n{_secretos()['clave_de_api_akia']}\n", encoding="utf-8")
    _huellas_de_juguete(tmp_path)
    codigo, salida = _cli("--raiz", "repo", "--huellas", "huellas.txt",
                          "--commit", "--un-solo-commit", cwd=tmp_path)
    assert codigo == 1
    _sin_rutas_absolutas(salida, tmp_path)

    sin_git = tmp_path / "sin_git"
    sin_git.mkdir()
    codigo, salida = _cli("--raiz", str(sin_git), "--huellas", "huellas.txt",
                          "--commit", cwd=tmp_path)
    assert codigo == 1
    _sin_rutas_absolutas(salida, tmp_path)
    for funcion in (va.commits, va.verificar_commit):
        with pytest.raises(SystemExit) as error:
            funcion(sin_git)
        _sin_rutas_absolutas(str(error.value), tmp_path)


def test_la_ruta_de_las_huellas_sale_como_se_paso(tmp_path, monkeypatch):
    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    (tmp_path / "lista.txt").write_text("[huellas]\nuno\n", encoding="utf-8")
    codigo, salida = _cli("--regenerar", "--lista", "lista.txt",
                          "--huellas", "sub/huellas.txt", cwd=tmp_path)
    assert codigo == 0
    assert "en sub/huellas.txt" in salida
    _sin_rutas_absolutas(salida, tmp_path)

    # Lo que no se puede leer (una carpeta) tampoco saca la ruta absoluta
    # en una traza de Python.
    arbol = _arbol_limpio(tmp_path / "arbol")
    for orden in (["--raiz", "arbol", "--huellas", "sub"],
                  ["--regenerar", "--lista", "sub",
                   "--huellas", "otra/huellas.txt"]):
        codigo, salida = _cli(*orden, cwd=tmp_path)
        assert codigo == 1
        assert "Traceback" not in salida
        _sin_rutas_absolutas(salida, tmp_path)

    # La de por defecto sale relativa al repositorio.
    publico = tmp_path / "publico.txt"
    publico.write_text(va.huella(CENTINELA) + "\n", encoding="utf-8")
    monkeypatch.setattr(va, "HUELLAS_POR_DEFECTO", publico)
    with pytest.raises(SystemExit) as error:
        va.main(["--raiz", str(arbol)])
    assert "tests/anonimato/huellas.txt" in str(error.value)
    _sin_rutas_absolutas(str(error.value), tmp_path)


def test_la_cli_no_imprime_el_token_ni_en_los_nombres(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    carpeta = raiz / f"Informes-{OTRO.upper()}"
    carpeta.mkdir()
    (carpeta / f"nota_{OTRO}.md").write_text(
        f"uno\n{OTRO}\n{_secretos()['clave_de_api_akia']}\n",
        encoding="utf-8")
    (carpeta / "figura.png").write_bytes(b"\x89PNG\x00\x00")
    codigo, salida = _cli("--raiz", str(raiz),
                          "--huellas", str(_huellas_de_juguete(tmp_path)))
    assert codigo == 1
    assert OTRO not in salida.lower()
    assert _secretos()["clave_de_api_akia"] not in salida
    tapada = f"<huella-{va.huella(OTRO)[:12]}>"
    nota = f"Informes-{tapada}/nota_{tapada}.md"
    assert f"{nota}:0: huella " in salida
    assert f"{nota}:2: huella " in salida
    assert f"{nota}:3: clave_de_api_akia" in salida
    assert f"  Informes-{tapada}/figura.png" in salida
    # La nota da dos hallazgos (nombre y linea 2) y la figura uno (su
    # carpeta): tres, en dos ficheros distintos.
    assert "huellas: 3 en 2 ficheros" in salida


@hay_git
def test_la_cli_verifica_el_commit_y_que_sea_uno_solo(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    huellas = str(_huellas_de_juguete(tmp_path))
    _git(raiz, "commit", "-q", "-m", "arbol anonimizado")
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--commit", "--un-solo-commit"]) == 0
    salida = capsys.readouterr().out
    assert "commit HEAD: 0" in salida and "commits: 1" in salida

    (raiz / "codigo.py").write_text("x = 2\n", encoding="utf-8")
    _git(raiz, "commit", "-q", "-a", "-m", "otro",
         GIT_AUTHOR_EMAIL=f"alguien@{OTRO}.test")
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--commit", "HEAD", "--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert "commit HEAD: correo_de_autor: huella " in salida
    assert "commits: 2" in salida
    assert OTRO not in salida.lower()


@hay_git
def test_un_solo_commit_mira_todas_las_ramas(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    huellas = str(_huellas_de_juguete(tmp_path))
    _git(raiz, "commit", "-q", "-m", "arbol anonimizado")
    orden = ["--raiz", str(raiz), "--huellas", huellas, "--un-solo-commit"]
    assert va.main(orden) == 0
    salida = capsys.readouterr().out
    assert "commits: 1" in salida and "ramas: 1" in salida
    assert "etiquetas: 0" in salida

    # Otra rama, con un commit que HEAD no alcanza.
    _git(raiz, "checkout", "-q", "-b", "otra")
    (raiz / "codigo.py").write_text("x = 2\n", encoding="utf-8")
    _git(raiz, "commit", "-q", "-a", "-m", "en otra rama")
    _git(raiz, "checkout", "-q", "-")
    assert va.main(orden) == 1
    salida = capsys.readouterr().out
    assert "commits: 2" in salida and "ramas: 2" in salida
    assert va.commits(raiz) == 2


@hay_git
def test_un_solo_commit_no_admite_etiquetas(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol anonimizado")
    _git(raiz, "tag", "-a", "v1", "-m", "una etiqueta anotada")
    assert va.main(["--raiz", str(raiz),
                    "--huellas", str(_huellas_de_juguete(tmp_path)),
                    "--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert "commits: 1" in salida and "ramas: 1" in salida
    assert "etiquetas: 1" in salida


@hay_git
@pytest.mark.parametrize("referencia", ["rama", "etiqueta"])
def test_los_nombres_de_ramas_y_etiquetas_se_comparan_con_las_huellas(
        tmp_path, capsys, referencia):
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol")
    nombre = f"informe-{OTRO}"
    if referencia == "rama":
        _git(raiz, "branch", "-m", nombre)      # la unica, a la que va HEAD
    else:
        _git(raiz, "tag", nombre)
    tapada = f"informe-<huella-{va.huella(OTRO)[:12]}>"
    assert va.verificar_referencias(raiz, {va.huella(OTRO)}) == [
        {"referencia": referencia, "nombre": tapada,
         "huella": va.huella(OTRO)}]
    huellas = str(_huellas_de_juguete(tmp_path))
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit", "HEAD", "--un-solo-commit")
    assert codigo == 1
    assert OTRO not in salida.lower()
    assert f"{referencia} {tapada}: huella {va.huella(OTRO)[:12]}" in salida

    # La revision que se pasa a --commit sale tapada (R6), exista o no.
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--commit", nombre]) == 1
    salida = capsys.readouterr().out
    assert f"commit {tapada}: 0" in salida
    assert OTRO not in salida.lower()
    with pytest.raises(SystemExit) as error:
        va.main(["--raiz", str(raiz), "--huellas", huellas,
                 "--commit", f"inexistente-{OTRO}"])
    assert OTRO not in str(error.value).lower()
    assert "inexistente-<huella-" in str(error.value)


@hay_git
def test_un_secreto_en_el_nombre_de_una_rama_es_un_hallazgo(tmp_path):
    # Un nombre de rama no admite `:`, pero si el token con `%3A`.
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol")
    bot = _token_de_bot().replace(":", "%3A")
    _git(raiz, "branch", "-m", "bot" + bot)
    assert va.verificar_referencias(raiz, set()) == [
        {"referencia": "rama", "nombre": "bot<secreto>",
         "clase": "token_de_bot_de_telegram"}]
    codigo, salida = _cli("--raiz", str(raiz),
                          "--huellas", str(_huellas_de_juguete(tmp_path)),
                          "--commit", "HEAD")
    assert codigo == 1
    assert "rama bot<secreto>: token_de_bot_de_telegram" in salida
    assert bot not in salida and bot[-35:] not in salida


@hay_git
def test_un_secreto_en_el_commit_es_un_hallazgo(tmp_path):
    raiz = _repositorio(tmp_path)
    huellas = str(_huellas_de_juguete(tmp_path))
    bot = _token_de_bot()
    _git(raiz, "commit", "-q", "-m", "arbol", "-m", f"el bot es {bot}")
    assert va.verificar_commit(raiz, huellas=set()) == [
        {"campo": "mensaje", "linea": 3, "clase": "token_de_bot_de_telegram"}]
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit", "HEAD")
    assert codigo == 1
    assert bot not in salida
    assert "commit HEAD: mensaje:3: token_de_bot_de_telegram" in salida

    literal = "a1B2c3D4e5F6g7H8"
    clave = _secretos()["clave_de_api_akia"]
    _git(raiz, "commit", "-q", "--allow-empty", "-m", "otro",
         "-m", "PASS" + "WORD=" + literal, GIT_AUTHOR_NAME=clave)
    assert [(h["campo"], h["linea"], h["clase"])
            for h in va.verificar_commit(raiz, huellas=set())] == [
        ("autor", 0, "clave_de_api_akia"),
        ("mensaje", 3, "asignacion_de_secreto")]
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", huellas,
                          "--commit", "HEAD")
    assert codigo == 1
    assert literal not in salida and clave not in salida
    assert "commit HEAD: autor: clave_de_api_akia" in salida


@hay_git
def test_un_solo_commit_mira_el_arbol_del_commit(tmp_path, capsys):
    raiz = _repositorio(tmp_path)
    nota = raiz / "nota.md"
    nota.write_text(f"{OTRO}\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")
    _git(raiz, "commit", "-q", "-m", "arbol")
    nota.write_text("limpia\n", encoding="utf-8")
    _git(raiz, "add", "nota.md")            # copia e indice, limpios
    huellas = str(_huellas_de_juguete(tmp_path))
    assert va.main(["--raiz", str(raiz), "--huellas", huellas]) == 0
    capsys.readouterr()
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert f"nota.md:1: huella {va.huella(OTRO)[:12]} (commit)" in salida
    assert "commits: 1" in salida and "ramas: 1" in salida
    assert "etiquetas: 0" in salida


def _sin_ninguna_huella(salida, huellas):
    for una in huellas:
        assert una[:12] not in salida


@hay_git
def test_un_solo_commit_no_publica_las_huellas_de_la_lista(
        tmp_path, tmp_path_factory, capsys):
    # V-1: el arbol que se publica lleva un huellas.txt con solo la del
    # centinela (D9). Publicar el del repositorio de desarrollo es publicar,
    # para quien tenga un diccionario, buena parte de la lista.
    huellas = tmp_path / "huellas.txt"
    va.regenerar([OTRO, OTRO_MAS], huellas)     # dos de juguete y el centinela
    todas = va.leer_huellas(huellas)
    # Bajo una carpeta de nombre corto (`v0`, no la de la prueba, de 31
    # caracteres): el fichero con nombre de huella, de 67, cabe en los 260
    # de Windows aunque la carpeta temporal sea larga (A3).
    raiz = _repositorio(tmp_path_factory.mktemp("v"))
    publicado = raiz / "tests" / "anonimato" / "huellas.txt"
    publicado.parent.mkdir(parents=True)
    shutil.copyfile(huellas, publicado)
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "arbol")
    orden = ["--raiz", str(raiz), "--huellas", str(huellas),
             "--un-solo-commit"]

    assert va.main(orden) == 1
    salida = capsys.readouterr().out
    de_la_lista = [n for n, linea in enumerate(
        publicado.read_text(encoding="utf-8").splitlines(), 1)
        if linea in va.huellas_de_la_lista(todas)]
    assert len(de_la_lista) == 2                # la del centinela no cuenta
    for n in de_la_lista:
        assert f"tests/anonimato/huellas.txt:{n}: huella_publicada" in salida
    assert "huellas publicadas: 2" in salida
    assert salida.splitlines()[-1] == "NO publicar: hay hallazgos"
    _sin_ninguna_huella(salida, todas)
    # Sin --un-solo-commit no se mira: el repositorio de desarrollo lleva su
    # propio huellas.txt.
    assert va.main(orden[:-1]) == 0
    capsys.readouterr()

    # Con solo la del centinela, como se publica: limpio.
    assert va.main(["--regenerar", "--solo-centinela",
                    "--huellas", str(publicado)]) == 0
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "--amend", "-m", "arbol")
    capsys.readouterr()
    assert va.main(orden) == 0
    salida = capsys.readouterr().out
    assert "huellas publicadas: 0" in salida

    # Una huella de la lista copiada en otro fichero (un informe), o en su
    # nombre: tambien se publicaria.
    (raiz / "docs" / "informe.md").write_text(
        f"# Informe\n\nla huella {va.huella(OTRO).upper()} y nada mas\n",
        encoding="utf-8")
    # En la raiz y no en una carpeta: un nombre de 67 caracteres, con una
    # carpeta temporal larga, pasaria de los 260 de Windows (C2).
    (raiz / f"{va.huella(OTRO_MAS)}.md").write_text("nada\n",
                                                    encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "--amend", "-m", "arbol")
    assert va.main(orden) == 1
    salida = capsys.readouterr().out
    assert "docs/informe.md:3: huella_publicada" in salida
    assert "<huella-publicada>.md:0: huella_publicada" in salida.splitlines()
    assert "huellas publicadas: 2" in salida
    _sin_ninguna_huella(salida, todas)
    _sin_ninguna_huella(salida.lower(), todas)


@hay_git
def test_un_solo_commit_mira_las_huellas_del_mensaje_y_de_las_ramas(
        tmp_path, capsys):
    # C6: el mensaje del commit y los nombres de las ramas y de las
    # etiquetas tambien se publican.
    huellas = tmp_path / "huellas.txt"
    va.regenerar([OTRO, OTRO_MAS], huellas)
    todas = va.leer_huellas(huellas)
    raiz = _repositorio(tmp_path)
    _git(raiz, "commit", "-q", "-m", "arbol",
         "-m", f"la huella {va.huella(OTRO)}")
    _git(raiz, "branch", "-m", f"informe-{va.huella(OTRO_MAS)}")
    _git(raiz, "tag", f"v-{va.huella(OTRO)}")
    orden = ["--raiz", str(raiz), "--huellas", str(huellas)]

    assert va.main(orden + ["--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert "commit HEAD: mensaje:3: huella_publicada" in salida
    assert ("rama informe-<huella-publicada>: huella_publicada"
            in salida.splitlines())
    assert ("etiqueta v-<huella-publicada>: huella_publicada"
            in salida.splitlines())
    _sin_ninguna_huella(salida, todas)
    # Con --commit a secas no se miran: el repositorio de desarrollo puede
    # citar una huella en un commit o en una rama.
    assert va.main(orden + ["--commit"]) == 0
    salida = capsys.readouterr().out
    assert "huella_publicada" not in salida
    _sin_ninguna_huella(salida, todas)


@hay_git
def test_un_solo_commit_da_por_hallazgo_la_cabecera_parent(tmp_path, capsys):
    # Por la linea de ordenes: `main` pasa --un-solo-commit a las cabeceras.
    # En un clon superficial el recuento de commits da 1 y el padre es lo
    # unico que avisa.
    raiz = _repositorio(tmp_path)
    huellas = str(_huellas_de_juguete(tmp_path))
    _git(raiz, "commit", "-q", "-m", "uno")
    _git(raiz, "commit", "-q", "--allow-empty", "-m", "dos")
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--un-solo-commit"]) == 1
    salida = capsys.readouterr().out
    assert "commit HEAD: parent: cabecera_del_commit" in salida.splitlines()
    assert va.main(["--raiz", str(raiz), "--huellas", huellas,
                    "--commit"]) == 0
    assert "cabecera_del_commit" not in capsys.readouterr().out


def test_la_cli_regenera_desde_la_variable_o_desde_lista(tmp_path, capsys,
                                                        monkeypatch):
    lista = tmp_path / "lista.txt"
    lista.write_text(LISTA_DE_JUGUETE, encoding="utf-8")
    destino = tmp_path / "huellas.txt"
    esperadas = {va.huella(t) for t in ("uno", "dos", "tres", CENTINELA)}

    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    assert va.main(["--regenerar", "--lista", str(lista),
                    "--huellas", str(destino)]) == 0
    assert va.leer_huellas(destino) == esperadas
    assert "4 huellas" in capsys.readouterr().out

    destino.unlink()
    monkeypatch.setenv("ANONIMATO_LISTA", str(lista))
    assert va.main(["--regenerar", "--huellas", str(destino)]) == 0
    assert va.leer_huellas(destino) == esperadas


def test_la_cli_no_regenera_con_una_entrada_mala_ni_dice_cual(tmp_path,
                                                             monkeypatch):
    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    lista = tmp_path / "lista.txt"
    lista.write_text(f"[huellas]\nuno\nzorro-{OTRO}\n", encoding="utf-8")
    destino = tmp_path / "huellas.txt"
    with pytest.raises(SystemExit) as salida:
        va.main(["--regenerar", "--lista", str(lista),
                 "--huellas", str(destino)])
    assert "2" in str(salida.value)
    assert OTRO not in str(salida.value).lower()
    assert "zorro" not in str(salida.value).lower()
    assert not destino.exists()

    lista.write_text("[huellas]\n# nada\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        va.main(["--regenerar", "--lista", str(lista),
                 "--huellas", str(destino)])
    assert not destino.exists()


def test_la_cli_sin_lista_dice_que_variable_falta(tmp_path, monkeypatch):
    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    with pytest.raises(SystemExit) as salida:
        va.main(["--regenerar", "--huellas", str(tmp_path / "h.txt")])
    assert "ANONIMATO_LISTA" in str(salida.value)
    assert not (tmp_path / "h.txt").exists()


def test_la_cli_escribe_el_huellas_txt_del_repositorio_que_se_publica(
        tmp_path, monkeypatch, capsys):
    # Sin lista: con --solo-centinela no se lee ni --lista ni la variable
    # (aqui apunta a un fichero que no existe).
    monkeypatch.setenv("ANONIMATO_LISTA", str(tmp_path / "no-existe.txt"))
    destino = tmp_path / "publico" / "huellas.txt"
    assert va.main(["--regenerar", "--solo-centinela",
                    "--huellas", str(destino)]) == 0
    assert "1 huella escrita" in capsys.readouterr().out
    assert va.leer_huellas(destino) == {va.huella(CENTINELA)}
    assert solo_el_centinela(destino)
    _cabecera_y_huellas_ordenadas(destino)
    # Con SU cabecera, que dice que lleva solo la del centinela a proposito.
    assert destino.read_text(encoding="utf-8") == (
        va.CABECERA_SOLO_CENTINELA + va.huella(CENTINELA) + "\n")


def test_la_cli_con_solo_centinela_no_escribe_donde_no_se_le_dice(
        tmp_path, monkeypatch):
    # Sin --huellas escribiria encima del huellas.txt de este repositorio,
    # que en el de desarrollo lleva la lista entera (aqui, uno de juguete que
    # no existe); con --lista, o sin --regenerar, la orden no tiene sentido.
    # Ninguna escribe nada.
    por_defecto = tmp_path / "por_defecto" / "huellas.txt"
    monkeypatch.setattr(va, "HUELLAS_POR_DEFECTO", por_defecto)
    lista = tmp_path / "lista.txt"
    lista.write_text("[huellas]\nuno\n", encoding="utf-8")
    destino = tmp_path / "huellas.txt"
    for orden in (["--regenerar", "--solo-centinela"],
                  ["--regenerar", "--solo-centinela", "--lista", str(lista),
                   "--huellas", str(destino)],
                  ["--solo-centinela", "--huellas", str(destino)]):
        with pytest.raises(SystemExit) as error:
            va.main(orden)
        assert "--solo-centinela" in str(error.value)
        assert not por_defecto.exists() and not destino.exists()


# --------------------------------------------------------------------------
# La excepcion de los nombres (spec de SP5-C2, D5): los del equipo y de la
# tutora pueden ir en README.md, LICENSE y docs/planificacion.md, y en ningun
# otro fichero. Los declara el README; el script no los guarda.
# --------------------------------------------------------------------------
# Nombres INVENTADOS: este fichero es de los de fuera, y en el no pueden ir los
# de verdad. Sus tokens van en unas huellas de juguete.
NOMBRES_DE_JUGUETE = ("Personaz Inventadaz", "Otraz Ficticiaz")
TOKENS_DE_LOS_NOMBRES = ("personaz", "inventadaz", "otraz", "ficticiaz")
DECLARACION_DE_JUGUETE = ("<!-- nombres-publicos: "
                          + "; ".join(NOMBRES_DE_JUGUETE) + " -->")
CON_LOS_NOMBRES = "Autores: " + " y ".join(NOMBRES_DE_JUGUETE) + ".\n"
README_DE_VERDAD = RAIZ / "README.md"


def _huellas_con_nombres(tmp_path):
    """Huellas de juguete: las de los tokens de los nombres y la de OTRO, que
    no es un nombre."""
    destino = tmp_path / "huellas-con-nombres.txt"
    va.regenerar([*TOKENS_DE_LOS_NOMBRES, OTRO], destino)
    return va.huellas_de_la_lista(va.leer_huellas(destino)), destino


def _arbol_con_nombres(raiz, declaracion=DECLARACION_DE_JUGUETE):
    """El arbol de juguete con los nombres en los tres ficheros de D5 (el
    README, con la declaracion en su linea 3) y en uno mas, `docs/otro.md`
    (linea 3)."""
    _arbol_limpio(raiz)
    (raiz / "README.md").write_text(f"# Proyecto\n\n{declaracion}\n\n"
                                    f"{CON_LOS_NOMBRES}", encoding="utf-8")
    (raiz / "LICENSE").write_text(f"Copyright (c) 2026 {CON_LOS_NOMBRES}",
                                  encoding="utf-8")
    (raiz / "docs" / "planificacion.md").write_text(
        f"# Plan\n\n{CON_LOS_NOMBRES}", encoding="utf-8")
    (raiz / "docs" / "otro.md").write_text(f"# Otro\n\n{CON_LOS_NOMBRES}",
                                           encoding="utf-8")
    return raiz


def _ficheros_con_hallazgos(raiz, huellas, commit=None):
    return sorted({h["fichero"] for h in va.buscar_huellas(raiz, huellas,
                                                           commit)})


def test_los_nombres_declarados_solo_se_admiten_en_sus_tres_ficheros(tmp_path):
    raiz = _arbol_con_nombres(tmp_path / "arbol")
    huellas, _ruta = _huellas_con_nombres(tmp_path)
    hallazgos = va.buscar_huellas(raiz, huellas)
    assert sorted({(h["fichero"], h["linea"]) for h in hallazgos}) == [
        ("docs/otro.md", 3)]
    assert sorted(h["huella"] for h in hallazgos) == sorted(
        va.huella(t) for t in TOKENS_DE_LOS_NOMBRES)
    assert va.FICHEROS_CON_NOMBRES == ("README.md", "LICENSE",
                                       "docs/planificacion.md")


def test_en_sus_tres_ficheros_cualquier_otra_huella_sigue_siendo_hallazgo(
        tmp_path):
    # La excepcion es la de los nombres, no la de los ficheros.
    raiz = _arbol_con_nombres(tmp_path / "arbol")
    for nombre in va.FICHEROS_CON_NOMBRES:
        with open(raiz / nombre, "a", encoding="utf-8") as fichero:
            fichero.write(f"Y una cadena de la lista: {OTRO}.\n")
    huellas, _ruta = _huellas_con_nombres(tmp_path)
    hallazgos = va.buscar_huellas(raiz, huellas)
    con_otro = sorted(h["fichero"] for h in hallazgos
                      if h["huella"] == va.huella(OTRO))
    assert con_otro == sorted(va.FICHEROS_CON_NOMBRES)
    assert {h["fichero"] for h in hallazgos
            if h["huella"] != va.huella(OTRO)} == {"docs/otro.md"}


@pytest.mark.parametrize("declaracion", [
    pytest.param("", id="sin_declaracion"),
    pytest.param(f"Texto {DECLARACION_DE_JUGUETE} en medio de una linea",
                 id="en_medio_de_una_linea"),
    pytest.param(DECLARACION_DE_JUGUETE.replace("nombres-publicos",
                                                "nombres publicos"),
                 id="con_otra_marca"),
    pytest.param("```\n" + DECLARACION_DE_JUGUETE.replace("<!--", "<!- -")
                 + "\n```", id="mal_formada"),
])
def test_sin_una_declaracion_en_su_linea_no_hay_excepcion(tmp_path,
                                                          declaracion):
    raiz = _arbol_con_nombres(tmp_path / "arbol", declaracion)
    huellas, _ruta = _huellas_con_nombres(tmp_path)
    assert _ficheros_con_hallazgos(raiz, huellas) == [
        "LICENSE", "README.md", "docs/otro.md", "docs/planificacion.md"]


def test_la_declaracion_solo_cuenta_en_el_readme_de_la_raiz(tmp_path):
    raiz = _arbol_con_nombres(tmp_path / "arbol", declaracion="")
    (raiz / "docs" / "README.md").write_text(DECLARACION_DE_JUGUETE + "\n",
                                             encoding="utf-8")
    with open(raiz / "docs" / "planificacion.md", "a",
              encoding="utf-8") as fichero:
        fichero.write(DECLARACION_DE_JUGUETE + "\n")
    huellas, _ruta = _huellas_con_nombres(tmp_path)
    assert _ficheros_con_hallazgos(raiz, huellas) == [
        "LICENSE", "README.md", "docs/README.md", "docs/otro.md",
        "docs/planificacion.md"]


@pytest.mark.parametrize("nombre", [
    "docs/LICENSE", "otra/README.md", "docs/sub/planificacion.md",
    "planificacion.md", "README.md.orig", "LICENSE.txt",
    "docs/planificacion.md.bak",
])
def test_los_tres_ficheros_son_rutas_exactas(tmp_path, nombre):
    raiz = _arbol_con_nombres(tmp_path / "arbol")
    ruta = raiz / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(CON_LOS_NOMBRES, encoding="utf-8")
    huellas, _ruta = _huellas_con_nombres(tmp_path)
    assert _ficheros_con_hallazgos(raiz, huellas) == sorted(
        ["docs/otro.md", nombre])


def test_los_nombres_publicos_se_leen_de_la_linea_de_la_declaracion():
    texto = (f"uno\n  {DECLARACION_DE_JUGUETE}  \n"
             "<!-- nombres-publicos: ;  Tercera Inventadaz ; -->\n"
             f"dos {DECLARACION_DE_JUGUETE}\n")
    assert va.nombres_publicos(texto) == [*NOMBRES_DE_JUGUETE,
                                          "Tercera Inventadaz"]
    assert va.nombres_publicos("sin declaracion\n") == []


@hay_git
def test_un_nombre_anadido_en_otra_version_del_readme_no_amplia_la_excepcion(
        tmp_path):
    # El README de la copia de trabajo declara los dos nombres; el del indice
    # y el del commit, solo el primero. Solo se admite lo que declaran todas
    # las versiones que se publicarian.
    raiz = _repositorio(tmp_path)
    primero, segundo = NOMBRES_DE_JUGUETE
    (raiz / "README.md").write_text(
        f"# P\n\n<!-- nombres-publicos: {primero} -->\n\n{primero}\n",
        encoding="utf-8")
    (raiz / "LICENSE").write_text(f"Copyright (c) 2026 {CON_LOS_NOMBRES}",
                                  encoding="utf-8")
    _git(raiz, "add", "-A")
    _git(raiz, "commit", "-q", "-m", "uno")
    (raiz / "README.md").write_text(
        f"# P\n\n{DECLARACION_DE_JUGUETE}\n\n{CON_LOS_NOMBRES}",
        encoding="utf-8")
    huellas, _ruta = _huellas_con_nombres(tmp_path)
    del_primero = {va.huella(t) for t in va.tokens(primero)}
    del_segundo = {va.huella(t) for t in va.tokens(segundo)}

    def comprobar(commit=None):
        hallazgos = va.buscar_huellas(raiz, huellas, commit)
        assert not any(h["huella"] in del_primero for h in hallazgos)
        con_el_segundo = {h["fichero"] for h in hallazgos
                          if h["huella"] in del_segundo}
        assert con_el_segundo == {"LICENSE", "README.md"}

    comprobar()                          # la copia frente al indice
    _git(raiz, "add", "README.md")
    assert va.buscar_huellas(raiz, huellas) == []   # ya son la misma
    comprobar("HEAD")                    # la copia frente al commit


def test_la_cli_cuenta_los_nombres_admitidos_sin_ensenarlos(tmp_path):
    raiz = _arbol_con_nombres(tmp_path / "arbol")
    huellas, ruta = _huellas_con_nombres(tmp_path)
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", str(ruta))
    assert codigo == 1
    assert "docs/otro.md:3: huella " in salida
    (raiz / "docs" / "otro.md").unlink()
    codigo, salida = _cli("--raiz", str(raiz), "--huellas", str(ruta))
    assert codigo == 0, salida
    assert "huellas: 0 en 0 ficheros" in salida
    # README: 4 tokens en la declaracion y 4 en el texto; LICENSE y el plan, 4.
    assert ("nombres declarados en el README, admitidos (D5): 16 en "
            "LICENSE, README.md, docs/planificacion.md") in salida
    for token in TOKENS_DE_LOS_NOMBRES:
        assert token not in salida.lower()
    _sin_ninguna_huella(salida, huellas)


def test_el_readme_declara_los_dos_integrantes_y_la_tutora():
    """D5 en el README de verdad: tres nombres (los dos integrantes y la
    tutora), con ocho tokens entre todos, y cada uno se ve en el README, no
    solo en la declaracion. Un nombre de mas en la declaracion hace fallar
    esta prueba: la excepcion no crece sin que alguien lo decida aqui. Los
    nombres no se escriben en esta prueba, que es de los ficheros de fuera."""
    texto = README_DE_VERDAD.read_text(encoding="utf-8")
    nombres = va.nombres_publicos(texto)
    tres_nombres = len(nombres) == 3
    assert tres_nombres, f"el README declara {len(nombres)} nombres"
    ocho_tokens = len({t for n in nombres for t in va.tokens(n)}) == 8
    assert ocho_tokens, "los nombres declarados no dan los ocho tokens"
    visible = "\n".join(linea for linea in texto.splitlines()
                        if not linea.strip().startswith("<!--"))
    se_ven = all(nombre in visible for nombre in nombres)
    assert se_ven, "un nombre declarado no aparece fuera de la declaracion"


@pytest.mark.skipif(solo_el_centinela(), reason=SIN_LA_LISTA["arbol"])
def test_los_nombres_del_readme_fuera_de_sus_tres_ficheros_son_hallazgo(
        tmp_path):
    """Con las huellas de verdad: lo que declara el README esta en la lista
    (si no, la excepcion sobraria), y escrito en cualquier otro fichero es
    un hallazgo; en las copias de los tres ficheros, no. Las aserciones van
    sobre booleanos y dicen fichero y linea: nunca una huella (C5)."""
    raiz = tmp_path / "arbol"
    (raiz / "docs").mkdir(parents=True)
    for nombre in va.FICHEROS_CON_NOMBRES:
        shutil.copyfile(RAIZ / nombre, raiz / nombre)
    nombres = va.nombres_publicos(README_DE_VERDAD.read_text(encoding="utf-8"))
    (raiz / "docs" / "otro.md").write_text("\n".join(nombres) + "\n",
                                           encoding="utf-8")
    huellas = va.huellas_de_la_lista(va.leer_huellas(HUELLAS))
    hallazgos = va.buscar_huellas(raiz, huellas)
    solo_en_otro = {h["fichero"] for h in hallazgos} == {"docs/otro.md"}
    assert solo_en_otro, _donde(hallazgos)
    cada_nombre = {h["linea"] for h in hallazgos} == set(
        range(1, len(nombres) + 1))
    assert cada_nombre, _donde(hallazgos)
    admitidas = va.huellas_de_los_nombres(va._piezas(raiz), huellas)
    todos_en_la_lista = len(admitidas) == len(
        {t for n in nombres for t in va.tokens(n)})
    assert todos_en_la_lista, (f"{len(admitidas)} de los tokens de los "
                               "nombres declarados estan en la lista")


# --------------------------------------------------------------------------
# El arbol de verdad. Exige la anonimizacion hecha (tareas 1 a 6 del plan).
# --------------------------------------------------------------------------
def _por_fichero(hallazgos, que):
    """`fichero: N (lineas a, b, c)`, sin tokens ni secretos."""
    agrupados = {}
    for h in hallazgos:
        agrupados.setdefault(h["fichero"], []).append(h)
    lineas = []
    for fichero, suyos in sorted(agrupados.items()):
        donde = sorted({h["linea"] for h in suyos})
        corte = 12 if que == "huella" else None
        clases = sorted({h[que][:corte] for h in suyos})
        lineas.append(f"  {fichero}: {len(suyos)} "
                      f"(lineas {', '.join(map(str, donde))}; "
                      f"{que} {', '.join(clases)})")
    return lineas


NO_ES_UN_REPOSITORIO = "no es la raiz de un repositorio de git"


def _fuera_de_git(raiz):
    """La linea que añade el fallo de una prueba del arbol fuera de la raiz
    de un repositorio (C4): alli se recorre la carpeta entera, tambien lo que
    git ignoraria, y lo que salga puede no publicarse."""
    if va._es_la_raiz_de_un_repositorio(raiz):
        return []
    return [f"Ojo: esta carpeta {NO_ES_UN_REPOSITORIO} (una copia descargada "
            "en ZIP, o git fuera del PATH), asi que se ha recorrido entera, "
            "tambien lo que git ignoraria (un .env de esta copia, por "
            "ejemplo): lo que sale aqui puede no publicarse."]


def _el_arbol_no_lleva_secretos(raiz, ruta_de_huellas, minimo=100):
    """La busqueda de secretos en el arbol. No necesita la lista, asi que
    corre siempre, tambien con solo la huella del centinela (V-3): las
    huellas solo tapan los nombres del mensaje. Un recorrido vacio (menos
    de `minimo` ficheros) no es un arbol limpio."""
    huellas = va.huellas_de_la_lista(va.leer_huellas(ruta_de_huellas))
    recorridos = len(va.ficheros_versionados(raiz))
    assert recorridos > minimo, "no se ha recorrido el arbol"
    de_secreto = va.buscar_secretos(raiz, huellas)
    if de_secreto:
        pytest.fail("\n".join(
            [f"El arbol no se puede publicar: {len(de_secreto)} secretos. La "
             "linea 0 es el nombre del fichero."]
            + _fuera_de_git(raiz)
            + _por_fichero(de_secreto, "clase")), pytrace=False)


def test_el_arbol_no_lleva_secretos():
    _el_arbol_no_lleva_secretos(RAIZ, HUELLAS)


def test_la_busqueda_de_secretos_del_arbol_no_se_salta():
    # C1: la prueba de V-3 vigila el ayudante; esta, la prueba del arbol. Un
    # `skipif` encima (la forma exacta que tenia el defecto) la saltaria en
    # el repositorio que se publica, y la suite seguiria en verde.
    marcas = {m.name for m in
              getattr(test_el_arbol_no_lleva_secretos, "pytestmark", [])}
    assert not marcas & {"skip", "skipif", "xfail"}, sorted(marcas)


def test_la_busqueda_de_secretos_del_arbol_no_se_salta_por_dentro(
        tmp_path, monkeypatch):
    # A4: la de arriba lee las marcas; esta, el cuerpo. Con solo la huella
    # del centinela, como en el repositorio que se publica, la prueba del
    # arbol corre: un `pytest.skip()` dentro, condicionado a eso, la
    # saltaria en verde.
    publico = tmp_path / "huellas.txt"
    va.regenerar_solo_centinela(publico)
    modulo = sys.modules[__name__]
    monkeypatch.setattr(modulo, "HUELLAS", publico)
    monkeypatch.setattr(modulo, "solo_el_centinela", lambda ruta=publico: True)
    try:
        test_el_arbol_no_lleva_secretos()
    except pytest.skip.Exception:
        pytest.fail("con solo la huella del centinela, "
                    "test_el_arbol_no_lleva_secretos se salta", pytrace=False)


def _el_arbol_no_lleva_huellas(raiz, ruta_de_huellas, minimo=100):
    """La busqueda de huellas en el arbol: fichero, linea y el principio de
    la huella (no el token). Un recorrido vacio no es un arbol limpio."""
    huellas = va.huellas_de_la_lista(va.leer_huellas(ruta_de_huellas))
    recorridos = len(va.ficheros_versionados(raiz))
    assert recorridos > minimo, "no se ha recorrido el arbol"
    de_huella = va.buscar_huellas(raiz, huellas)
    if de_huella:
        ficheros = len({h["fichero"] for h in de_huella})
        pytest.fail("\n".join(
            [f"El arbol no se puede publicar: {len(de_huella)} huellas en "
             f"{ficheros} ficheros. La linea 0 es el nombre del fichero."]
            + _fuera_de_git(raiz)
            + _por_fichero(de_huella, "huella")), pytrace=False)


@pytest.mark.skipif(solo_el_centinela(), reason=SIN_LA_LISTA["arbol"])
def test_el_arbol_no_lleva_huellas():
    """En el repositorio que se publica `huellas.txt` lleva solo la del
    centinela (D9) y esta prueba se salta diciendolo: alli no comprobaria
    nada."""
    _el_arbol_no_lleva_huellas(RAIZ, HUELLAS)


def test_con_solo_el_centinela_los_secretos_del_arbol_se_buscan(tmp_path):
    # V-3: antes, el salto por «solo el centinela» se llevaba tambien la
    # busqueda de secretos del arbol, que no necesita la lista.
    publico = tmp_path / "publico.txt"
    publico.write_text("# cabecera\n" + va.huella(CENTINELA) + "\n",
                       encoding="utf-8")
    assert solo_el_centinela(publico)
    raiz = _arbol_limpio(tmp_path / "arbol")

    def buscar():
        # Un salto aqui es justo el fallo de V-3: que no se salte en verde.
        try:
            _el_arbol_no_lleva_secretos(raiz, publico, minimo=1)
        except pytest.skip.Exception as salto:
            raise AssertionError("con solo la huella del centinela se ha "
                                 "saltado la busqueda de secretos") from salto

    buscar()
    secreto = "PASS" + "WORD=" + _LITERAL
    (raiz / "docs" / "nota.md").write_text(f"uno\n{secreto}\n",
                                           encoding="utf-8")
    with pytest.raises(pytest.fail.Exception) as error:
        buscar()
    assert "docs/nota.md: 1 (lineas 2; clase asignacion_de_secreto)" in str(
        error.value)
    assert _LITERAL not in str(error.value)


# --------------------------------------------------------------------------
# Lo que no es texto: revisado a mano y declarado
# --------------------------------------------------------------------------
FUERA_DE_GIT = ("esta carpeta no es la raiz de un repositorio de git (una "
                "copia descargada en ZIP, o git fuera del PATH): no se sabe "
                "que se publicaria, y queda sin verificar que los binarios "
                "son los revisados a mano (BINARIOS_REVISADOS)")


def test_los_binarios_versionados_son_los_revisados():
    """Lo que no es texto no lo recorre la prueba de huellas: se mira a mano y
    se declara. Si esta prueba falla, hay un binario que nadie ha mirado (o
    uno sin seguimiento y sin ignorar en la carpeta, que se publicaria con un
    `git add -A`).

    Fuera de un repositorio de git se recorre la carpeta entera, con lo que
    git ignoraria (los `.pyc` que escribe el propio pytest): se salta."""
    if not va._es_la_raiz_de_un_repositorio(RAIZ):
        pytest.skip(FUERA_DE_GIT)
    hallados = sorted(p.relative_to(RAIZ).as_posix() for p in va.binarios(RAIZ))
    assert hallados == sorted(BINARIOS_REVISADOS)


def _binarios_que_cambiaron(raiz, huellas):
    """Los nombres de `huellas` cuyo fichero, bajo `raiz`, falta o ya no tiene ese
    SHA-256. Solo nombres: ni los bytes ni las huellas."""
    return sorted(
        nombre for nombre, huella in huellas.items()
        if not (raiz / nombre).is_file()
        or hashlib.sha256((raiz / nombre).read_bytes()).hexdigest() != huella)


def test_todo_binario_declarado_de_app_tiene_su_huella():
    """Un binario de `app/assets/`, de `docs/interfaz/` (las capturas de la interfaz) o de
    `results/figures/` (las figuras de la evaluación) no se declara solo por su nombre:
    lleva su SHA-256 en HUELLAS_DE_LOS_BINARIOS, y esa lista no lleva huellas de binarios
    que no estén declarados."""
    declarados = {n for n in BINARIOS_REVISADOS if n.startswith(CARPETAS_CON_HUELLA)}
    sin_huella = sorted(declarados - set(HUELLAS_DE_LOS_BINARIOS))
    sin_declarar = sorted(set(HUELLAS_DE_LOS_BINARIOS) - declarados)
    if sin_huella or sin_declarar:
        pytest.fail(f"binarios de {', '.join(CARPETAS_CON_HUELLA)} declarados sin su "
                    f"SHA-256 en HUELLAS_DE_LOS_BINARIOS: {', '.join(sin_huella) or '-'}; "
                    "huellas de binarios que no están en BINARIOS_REVISADOS: "
                    f"{', '.join(sin_declarar) or '-'}", pytrace=False)


def test_los_binarios_de_app_son_los_revisados_byte_a_byte():
    cambiados = _binarios_que_cambiaron(RAIZ, HUELLAS_DE_LOS_BINARIOS)
    if cambiados:
        pytest.fail("binarios que ya no son los revisados (su SHA-256 es otro, o "
                    f"faltan): {', '.join(cambiados)}. Hay que volver a mirarlos y, "
                    "solo después, rehacer su huella aquí y su fila de "
                    "tests/anonimato/README.md", pytrace=False)


def test_un_binario_cambiado_o_ausente_se_nombra_sin_volcar_sus_bytes(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"uno")
    (tmp_path / "b.bin").write_bytes(b"dos")
    huellas = {nombre: hashlib.sha256(datos).hexdigest()
               for nombre, datos in (("a.bin", b"uno"), ("b.bin", b"dos"),
                                     ("c.bin", b"tres"))}
    assert _binarios_que_cambiaron(tmp_path, huellas) == ["c.bin"]      # c.bin falta
    (tmp_path / "b.bin").write_bytes(b"dos con un trozo de mas")
    assert _binarios_que_cambiaron(tmp_path, huellas) == ["b.bin", "c.bin"]
    assert _binarios_que_cambiaron(tmp_path, {}) == []


def _mirar_imagen(datos, nombre):
    """Mira una imagen (un PNG versionado, o una incrustada en un notebook):
    las claves de sus metadatos tienen que estar en METADATOS_PERMITIDOS.
    Devuelve su formato y el texto de los valores, que se mira despues
    contra las huellas. Si falla, dice la imagen y la clave, nunca el
    valor. Los metadatos, TODOS: sin `load()` PIL no ve los trozos de texto
    que van detras de los datos de la imagen (E3)."""
    from PIL import Image
    with Image.open(io.BytesIO(datos)) as imagen:
        imagen.load()
        formato, info = imagen.format, dict(imagen.info)
    de_mas = sorted(str(c) for c in set(info) - METADATOS_PERMITIDOS)
    if de_mas:
        pytest.fail(f"{nombre}: metadatos que no son los revisados: "
                    f"{', '.join(de_mas)}", pytrace=False)
    return formato, " ".join(str(v) for v in info.values())


def _sin_huellas_en_los_valores(textos):
    """(nombre, texto de los valores de los metadatos): ninguno lleva una
    cadena de la lista. Con solo la huella del centinela no se puede mirar,
    y se dice (V-3)."""
    if solo_el_centinela():
        pytest.skip(SIN_LA_LISTA["metadatos"])
    huellas = va.huellas_de_la_lista(va.leer_huellas(HUELLAS))
    con_huella = [nombre for nombre, texto in textos
                  if {va.huella(t) for t in va.tokens(texto)} & huellas]
    assert not con_huella, "metadatos con una cadena de la lista"


def test_cada_binario_revisado_es_un_png_o_un_dicom():
    """Las pruebas de metadatos miran PNG y DICOM: otra clase de binario se les
    escaparía a las dos, y no se puede declarar sin una prueba que lo mire."""
    de_mas = [n for n in BINARIOS_REVISADOS if not n.endswith((".png", ".dcm"))]
    assert de_mas == []


def test_los_png_no_llevan_metadatos_que_identifiquen():
    textos = []
    for nombre in BINARIOS_REVISADOS:
        if not nombre.endswith(".png"):
            continue
        formato, texto = _mirar_imagen((RAIZ / nombre).read_bytes(), nombre)
        assert formato == "PNG", nombre
        textos.append((nombre, texto))
    _sin_huellas_en_los_valores(textos)


def _png_de_juguete(*textos):
    """Un PNG de 1x1 compuesto a mano, con un trozo `tEXt` por cada
    (clave, valor) DETRAS de los datos de la imagen (`IDAT`). Cada trozo es
    longitud, tipo, datos y CRC."""
    def trozo(tipo, datos):
        return (struct.pack(">I", len(datos)) + tipo + datos
                + struct.pack(">I", zlib.crc32(tipo + datos)))
    png = (b"\x89PNG\r\n\x1a\n"
           + trozo(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0))
           + trozo(b"IDAT", zlib.compress(b"\x00\x00")))
    for clave, valor in textos:
        png += trozo(b"tEXt", clave + b"\x00" + valor)
    return png + trozo(b"IEND", b"")


def test_un_metadato_detras_de_los_datos_de_la_imagen_tambien_se_mira(
        tmp_path):
    # E3: sin `load()`, PIL no ve los trozos de texto que van detras de los
    # datos de la imagen.
    assert _mirar_imagen(_png_de_juguete(), "limpia.png") == ("PNG", "")
    ruta = tmp_path / "juguete.png"
    ruta.write_bytes(_png_de_juguete((b"Author", b"Autor Neutro")))
    with pytest.raises(pytest.fail.Exception) as error:
        _mirar_imagen(ruta.read_bytes(), "juguete.png")
    assert "juguete.png" in str(error.value) and "Author" in str(error.value)
    assert "Neutro" not in str(error.value)


def _mirar_dicom(datos, nombre):
    """Mira un DICOM versionado: las etiquetas de su cabecera (la del `file_meta`
    y la del conjunto de datos) tienen que estar en ETIQUETAS_DICOM_PERMITIDAS, y
    sus nombres de persona, fechas y horas, vacíos. Devuelve el texto de sus
    valores, sin los píxeles, que se mira después contra las huellas. Si falla,
    dice el DICOM y la etiqueta, nunca el valor."""
    import pydicom
    ds = pydicom.dcmread(io.BytesIO(datos))
    elementos = list(ds.file_meta) + list(ds)
    de_mas = sorted(e.keyword or str(e.tag) for e in elementos
                    if e.keyword not in ETIQUETAS_DICOM_PERMITIDAS)
    if de_mas:
        pytest.fail(f"{nombre}: etiquetas DICOM que no son las revisadas: "
                    f"{', '.join(de_mas)}", pytrace=False)
    con_contenido = sorted(e.keyword for e in elementos
                           if e.VR in TIPOS_DICOM_SIEMPRE_VACIOS and str(e.value))
    if con_contenido:
        pytest.fail(f"{nombre}: nombres, fechas u horas con contenido: "
                    f"{', '.join(con_contenido)}", pytrace=False)
    return " ".join(str(e.value) for e in elementos
                    if e.keyword != "PixelData" and not isinstance(e.value, bytes))


def test_los_dicom_no_llevan_etiquetas_que_identifiquen():
    textos = [(nombre, _mirar_dicom((RAIZ / nombre).read_bytes(), nombre))
              for nombre in BINARIOS_REVISADOS if nombre.endswith(".dcm")]
    assert textos, "no hay ningún DICOM declarado: la prueba no ha mirado nada"
    _sin_huellas_en_los_valores(textos)


def _dicom_de_juguete(**de_mas):
    """Un DICOM de 2x2 con la cabecera mínima de los ejemplos, más los campos que
    se le pasen (`InstitutionName="..."`)."""
    from pydicom.dataset import Dataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian
    ds = Dataset()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
    ds.SOPInstanceUID = "2.25.1"
    ds.PatientName = ""
    ds.PatientID = "EJEMPLO-0"
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.Rows, ds.Columns = 2, 2
    ds.BitsAllocated, ds.BitsStored, ds.HighBit = 8, 8, 7
    ds.PixelRepresentation = 0
    ds.PixelData = bytes(4)
    for etiqueta, valor in de_mas.items():
        setattr(ds, etiqueta, valor)
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = ds.SOPClassUID
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    salida = io.BytesIO()
    ds.save_as(salida, enforce_file_format=True)
    return salida.getvalue()


def test_un_dicom_limpio_pasa_y_da_el_texto_de_sus_valores():
    texto = _mirar_dicom(_dicom_de_juguete(), "limpio.dcm")
    assert "EJEMPLO-0" in texto and "2.25.1" in texto


@pytest.mark.parametrize("de_mas,etiqueta", [
    pytest.param({"InstitutionName": "Centro Neutro"}, "InstitutionName", id="centro"),
    pytest.param({"StationName": "Equipo Neutro"}, "StationName", id="equipo"),
    pytest.param({"PatientBirthDate": "19900101"}, "PatientBirthDate", id="nacimiento"),
    pytest.param({"StudyDate": "20260101"}, "StudyDate", id="fecha_del_estudio"),
    pytest.param({"ImageComments": "Comentario Neutro"}, "ImageComments",
                 id="comentario"),
])
def test_una_etiqueta_dicom_de_mas_se_mira(de_mas, etiqueta):
    with pytest.raises(pytest.fail.Exception) as error:
        _mirar_dicom(_dicom_de_juguete(**de_mas), "juguete.dcm")
    assert "juguete.dcm" in str(error.value) and etiqueta in str(error.value)
    assert "Neutro" not in str(error.value) and "2026" not in str(error.value)


def test_un_nombre_de_persona_con_contenido_se_mira():
    with pytest.raises(pytest.fail.Exception) as error:
        _mirar_dicom(_dicom_de_juguete(PatientName="Apellido^Neutro"), "juguete.dcm")
    assert "juguete.dcm" in str(error.value) and "PatientName" in str(error.value)
    assert "Neutro" not in str(error.value)


def _notebooks_publicados(raiz=RAIZ):
    """{nombre: notebook} de cada `.ipynb` que se publicaria, no solo los de
    `notebooks/`."""
    return {p.relative_to(raiz).as_posix():
            json.loads(p.read_text(encoding="utf-8"))
            for p in va.ficheros_versionados(raiz) if p.suffix == ".ipynb"}


def _imagenes_del_notebook(notebook):
    """[(tipo, bytes)] de las imagenes incrustadas: las salidas `image/*` de
    las celdas (`outputs[].data`) y los adjuntos (`attachments`), ya
    decodificadas de base64 (una SVG es texto, no base64)."""
    imagenes = []
    for celda in notebook.get("cells", []):
        paquetes = [s.get("data", {}) for s in celda.get("outputs", [])]
        paquetes += list(celda.get("attachments", {}).values())
        for paquete in paquetes:
            for tipo, valor in sorted(paquete.items()):
                if not tipo.startswith("image/"):
                    continue
                texto = "".join(valor) if isinstance(valor, list) else valor
                imagenes.append((tipo, texto.encode("utf-8")
                                 if tipo == "image/svg+xml"
                                 else base64.b64decode(texto)))
    return imagenes


def test_las_imagenes_salen_de_las_salidas_y_de_los_adjuntos():
    png = _png_de_juguete()
    en_base64 = base64.b64encode(png).decode("ascii")
    notebook = {"cells": [
        {"cell_type": "markdown", "source": ["![a](attachment:a.png)"],
         "attachments": {"a.png": {"image/png": en_base64}}},
        {"cell_type": "code", "outputs": [
            {"output_type": "display_data",
             "data": {"text/plain": ["<Figure>"],
                      "image/png": [en_base64[:10], en_base64[10:]]}},
            {"output_type": "stream", "text": ["hola\n"]}]}]}
    assert _imagenes_del_notebook(notebook) == [("image/png", png)] * 2


def _las_imagenes_de_los_notebooks_son_las_declaradas(raiz, declaradas):
    """Los notebooks que se publicarian bajo `raiz` y las imagenes de cada
    uno (por su SHA-256) son exactamente los de `declaradas` (como
    IMAGENES_DE_LOS_NOTEBOOKS). Si no, falla diciendo el notebook y las
    huellas de las imagenes que no se han revisado (son de imagenes: se
    pueden publicar). Devuelve [(nombre, tipo, bytes)] de cada imagen, para
    mirar sus metadatos."""
    notebooks = _notebooks_publicados(raiz)
    problemas, imagenes = [], []
    for nombre in sorted(set(notebooks) | set(declaradas)):
        if nombre not in declaradas:
            problemas.append(f"{nombre}: no esta en IMAGENES_DE_LOS_NOTEBOOKS")
            continue
        if nombre not in notebooks:
            problemas.append(f"{nombre}: esta declarado y no se publicaria")
            continue
        suyas = _imagenes_del_notebook(notebooks[nombre])
        de_sus_imagenes = tuple(sorted(hashlib.sha256(d).hexdigest()
                                       for _tipo, d in suyas))
        if de_sus_imagenes != tuple(declaradas[nombre]):
            nuevas = sorted(set(de_sus_imagenes) - set(declaradas[nombre]))
            problemas.append(f"{nombre}: {len(de_sus_imagenes)} imagenes, "
                             f"{len(declaradas[nombre])} declaradas; sin "
                             f"revisar: {', '.join(nuevas) or 'ninguna'}")
        imagenes += [(f"{nombre}, imagen {n}", tipo, datos)
                     for n, (tipo, datos) in enumerate(suyas, 1)]
    if problemas:
        pytest.fail("\n".join(
            ["Las imagenes incrustadas no son las revisadas "
             "(IMAGENES_DE_LOS_NOTEBOOKS):"]
            + _fuera_de_git(raiz)
            + ["  " + p for p in problemas]), pytrace=False)
    return imagenes


def test_las_imagenes_de_los_notebooks_son_las_revisadas():
    """Las imagenes incrustadas no las lee ni la prueba de huellas ni el
    script (el base64 largo se quita sin mirarlo): se revisan a mano y se
    fijan aqui por su huella; sus metadatos se miran como los de los PNG."""
    textos = []
    for nombre, tipo, datos in _las_imagenes_de_los_notebooks_son_las_declaradas(
            RAIZ, IMAGENES_DE_LOS_NOTEBOOKS):
        if tipo != "image/svg+xml":             # el texto lo recorre el resto
            _formato, texto = _mirar_imagen(datos, nombre)
            textos.append((nombre, texto))
    _sin_huellas_en_los_valores(textos)


def _tiradas_de_base64_sin_declarar(raiz, declaradas):
    """(fichero, linea, motivo) de cada tirada de 120 o mas caracteres de
    base64 de un fichero de texto que se publicaria (la expresion `BASE64`
    del script: lo que la busqueda de huellas quita sin mirar) que,
    decodificada, no es una de las imagenes `declaradas` (por su SHA-256).
    Nunca la tirada. Un fichero que no se deja leer es un hallazgo de linea
    0 («no se pudo leer», A5): no se da por limpio, y sin traza."""
    sin_declarar = []
    for ruta in va.ficheros_versionados(raiz):
        relativo = ruta.relative_to(raiz).as_posix()
        try:
            texto = va._texto(ruta)
        except OSError:
            sin_declarar.append((relativo, 0, "no se pudo leer"))
            continue
        if texto is None:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            for m in va.BASE64.finditer(linea):
                try:
                    datos = base64.b64decode(m.group(), validate=True)
                except (binascii.Error, ValueError):
                    datos = None
                if (datos is None or hashlib.sha256(datos).hexdigest()
                        not in declaradas):
                    sin_declarar.append(
                        (relativo, n, "no es una imagen declarada"))
    return sin_declarar


def _toda_tirada_larga_es_una_imagen_declarada(raiz, declaradas):
    """Falla con el fichero, la linea y el motivo de cada tirada sin
    declarar (y de cada fichero ilegible), nunca con la tirada."""
    sin_declarar = _tiradas_de_base64_sin_declarar(raiz, declaradas)
    if sin_declarar:
        pytest.fail("\n".join(
            ["Tiradas de base64 de 120 o mas caracteres que no son una "
             "imagen declarada (IMAGENES_DE_LOS_NOTEBOOKS):"]
            + _fuera_de_git(raiz)
            + [f"  {fichero}:{n} ({motivo})"
               for fichero, n, motivo in sin_declarar]), pytrace=False)


def test_una_imagen_pegada_de_otra_forma_tambien_se_ve(tmp_path):
    # C3: pegada en el texto de una celda o de un .md (`data:image/png;
    # base64,...`) o en una salida `text/html`, la prueba de las imagenes de
    # los notebooks no la ve, y la de huellas quita el base64 sin mirarlo.
    raiz = _arbol_limpio(tmp_path / "arbol")
    imagen = _png_de_juguete((b"Author", b"Autor Neutro " * 8))
    en_base64 = base64.b64encode(imagen).decode("ascii")
    assert len(en_base64) >= 120
    (raiz / "notas.md").write_text(
        f"uno\n![figura](data:image/png;base64,{en_base64})\n",
        encoding="utf-8")
    notebook = {"cells": [{"cell_type": "code", "outputs": [
        {"output_type": "display_data", "data": {"text/html": [
            f'<img src="data:image/png;base64,{en_base64}">']}}]}]}
    (raiz / "cuaderno.ipynb").write_text(json.dumps(notebook, indent=1),
                                         encoding="utf-8")
    assert _imagenes_del_notebook(notebook) == []
    sin_declarar = _tiradas_de_base64_sin_declarar(raiz, set())
    assert ("notas.md", 2, "no es una imagen declarada") in sin_declarar
    assert sorted({f for f, _n, _motivo in sin_declarar}) == [
        "cuaderno.ipynb", "notas.md"]
    # Declarada, pasa; y una tirada que no es base64 valido no pasa.
    assert _tiradas_de_base64_sin_declarar(
        raiz, {hashlib.sha256(imagen).hexdigest()}) == []
    (raiz / "ruta.txt").write_text("/".join(["abcdefgh"] * 20) + "\n",
                                   encoding="utf-8")
    assert _tiradas_de_base64_sin_declarar(
        raiz, {hashlib.sha256(imagen).hexdigest()}) == [
        ("ruta.txt", 1, "no es una imagen declarada")]


def test_un_fichero_ilegible_es_un_hallazgo_de_las_tiradas(tmp_path,
                                                          monkeypatch):
    # A5: un fichero que no se deja leer (sin permiso, bloqueado) no rompe la
    # prueba de las tiradas con una traza: es un hallazgo, con el fichero.
    raiz = _arbol_limpio(tmp_path / "arbol")
    leer = Path.read_bytes

    def leer_salvo_la_guia(ruta):
        if ruta.name == "guia.md":
            raise PermissionError(13, "acceso denegado")
        return leer(ruta)

    monkeypatch.setattr(Path, "read_bytes", leer_salvo_la_guia)
    assert _tiradas_de_base64_sin_declarar(raiz, set()) == [
        ("docs/guia.md", 0, "no se pudo leer")]
    with pytest.raises(pytest.fail.Exception) as error:
        _toda_tirada_larga_es_una_imagen_declarada(raiz, set())
    assert "docs/guia.md:0 (no se pudo leer)" in str(error.value)
    assert "Traceback" not in str(error.value)
    assert "PermissionError" not in str(error.value)


def test_toda_tirada_larga_de_base64_es_una_imagen_declarada():
    """El base64 largo se quita sin mirarlo: solo puede ser una imagen de
    IMAGENES_DE_LOS_NOTEBOOKS, revisada a mano. Si falla, dice el fichero y
    la linea, no la tirada."""
    declaradas = {una for suyas in IMAGENES_DE_LOS_NOTEBOOKS.values()
                  for una in suyas}
    _toda_tirada_larga_es_una_imagen_declarada(RAIZ, declaradas)


def _mirar_metadatos_de_los_notebooks(notebooks, aviso=()):
    """Las claves de `metadata` de cada notebook, las de su `colab` (con
    `provenance` vacio) y las de cada celda son las revisadas. Si no, falla
    diciendo el notebook y la CLAVE, nunca el valor (y las lineas de
    `aviso`, si las hay)."""
    de_mas = []
    for nombre, notebook in sorted(notebooks.items()):
        metadatos = notebook.get("metadata", {})
        de_mas += [f"{nombre}: metadata.{c}"
                   for c in sorted(set(metadatos) - METADATOS_DEL_NOTEBOOK)]
        colab = metadatos.get("colab", {})
        de_mas += [f"{nombre}: metadata.colab.{c}"
                   for c in sorted(set(colab) - METADATOS_DE_COLAB)]
        if colab.get("provenance", []) != []:
            de_mas.append(f"{nombre}: metadata.colab.provenance no está vacía")
        for n, celda in enumerate(notebook.get("cells", []), 1):
            de_mas += [f"{nombre}: celda {n}, metadata.{c}"
                       for c in sorted(set(celda.get("metadata", {}))
                                       - METADATOS_DE_LA_CELDA)]
    if de_mas:
        pytest.fail("\n".join(
            ["Metadatos de notebook que no son los revisados (las huellas no "
             "los conocen: se miran a mano):"]
            + list(aviso) + ["  " + d for d in de_mas]), pytrace=False)


def _los_metadatos_de_los_notebooks_son_los_revisados(raiz):
    _mirar_metadatos_de_los_notebooks(_notebooks_publicados(raiz),
                                      aviso=_fuera_de_git(raiz))


def test_un_metadato_de_notebook_no_revisado_se_nombra_sin_su_valor():
    valor = "cuenta-de-juguete-7q"
    notebook = {
        "metadata": {"kernelspec": {"name": "python3"}, "authors": [valor],
                     "colab": {"name": "x.ipynb", "include_colab_link": True,
                               "provenance": [{"file_id": valor}]}},
        "cells": [{"metadata": {"execution": {}}},
                  {"metadata": {"id": valor, "tags": []}}]}
    _mirar_metadatos_de_los_notebooks({"limpio.ipynb": {
        "metadata": {"colab": {"name": "x.ipynb", "provenance": []}},
        "cells": [{"metadata": {"execution": {}}}]}})
    with pytest.raises(pytest.fail.Exception) as error:
        _mirar_metadatos_de_los_notebooks({"sucio.ipynb": notebook})
    mensaje = str(error.value)
    for clave in ("sucio.ipynb: metadata.authors",
                  "sucio.ipynb: metadata.colab.include_colab_link",
                  "sucio.ipynb: metadata.colab.provenance no está vacía",
                  "sucio.ipynb: celda 2, metadata.id",
                  "sucio.ipynb: celda 2, metadata.tags"):
        assert clave in mensaje
    assert valor not in mensaje


def test_los_metadatos_de_los_notebooks_son_los_revisados():
    _los_metadatos_de_los_notebooks_son_los_revisados(RAIZ)


@pytest.mark.parametrize("con_git", [
    pytest.param(False, id="sin_git"),
    pytest.param(True, id="con_git", marks=hay_git),
])
def test_fuera_de_git_el_fallo_del_arbol_lo_dice(tmp_path, con_git):
    # C4 y A1: fuera de la raiz de un repositorio se recorre la carpeta
    # entera, tambien lo que git ignoraria (un `.env` de la copia de alguien,
    # un notebook de `.ipynb_checkpoints/`): todas las pruebas que recorren
    # el arbol lo dicen al fallar.
    raiz = _repositorio(tmp_path) if con_git else _arbol_limpio(
        tmp_path / "repo")
    (raiz / ".env").write_text("X=1\n", encoding="utf-8")
    (raiz / "nota.md").write_text(f"{OTRO}\n", encoding="utf-8")
    # Un notebook con una imagen que nadie ha declarado y una clave de
    # metadatos que nadie ha revisado.
    imagen = base64.b64encode(_png_de_juguete((b"Software", b"x" * 80)))
    cuaderno = {"metadata": {"authors": ["de juguete"]}, "cells": [
        {"cell_type": "code", "metadata": {}, "outputs": [
            {"output_type": "display_data",
             "data": {"image/png": imagen.decode("ascii")}}]}]}
    (raiz / "cuaderno.ipynb").write_text(json.dumps(cuaderno, indent=1),
                                         encoding="utf-8")
    de_juguete = _huellas_de_juguete(tmp_path)
    comprobaciones = {
        "secretos": lambda: _el_arbol_no_lleva_secretos(raiz, de_juguete,
                                                        minimo=1),
        "huellas": lambda: _el_arbol_no_lleva_huellas(raiz, de_juguete,
                                                      minimo=1),
        "tiradas": lambda: _toda_tirada_larga_es_una_imagen_declarada(
            raiz, set()),
        "imagenes": lambda: _las_imagenes_de_los_notebooks_son_las_declaradas(
            raiz, {}),
        "metadatos": lambda: _los_metadatos_de_los_notebooks_son_los_revisados(
            raiz),
    }
    for que, comprobar in comprobaciones.items():
        with pytest.raises(pytest.fail.Exception) as error:
            comprobar()
        assert (NO_ES_UN_REPOSITORIO in str(error.value)) is not con_git, que
        assert OTRO not in str(error.value).lower(), que
