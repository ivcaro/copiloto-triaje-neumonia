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
import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
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

# De donde sale lo que se recorre (clave `origen` de cada hallazgo).
COPIA, INDICE, COMMIT = "copia de trabajo", "indice", "commit"


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
    assert va.tokens("name: ${RED_N8N:-x_y_network}") == {
        "name", "red", "n8n", "x", "y", "network"}


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


SIN_LA_LISTA = ("huellas.txt lleva solo la huella del centinela (el "
                "repositorio que se publica, D9): queda sin verificar aqui "
                "que el arbol no lleva ninguna cadena de la lista. Esa "
                "comprobacion se hace antes de publicar, con --huellas y las "
                "huellas del repositorio de desarrollo")


def test_el_centinela_esta_en_huellas_txt():
    assert va.huella(CENTINELA) in va.leer_huellas(HUELLAS)


def test_huellas_txt_lleva_cabecera_y_huellas_ordenadas_sin_repetir():
    lineas = HUELLAS.read_text(encoding="utf-8").splitlines()
    assert lineas[0].startswith("#")
    datos = [l for l in lineas if l and not l.startswith("#")]
    assert all(len(l) == 64 and set(l) <= set("0123456789abcdef")
               for l in datos)
    assert datos == sorted(set(datos))
    assert set(datos) == va.leer_huellas(HUELLAS)


@pytest.mark.skipif(solo_el_centinela(), reason=SIN_LA_LISTA)
def test_huellas_txt_lleva_mas_que_el_centinela():
    # Antes era parte de la prueba de arriba («len(datos) > 1»).
    assert len(va.leer_huellas(HUELLAS)) > 1, "falta regenerar"


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
    assert texto.startswith("#")
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


def test_un_arbol_limpio_no_da_hallazgos(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    assert va.buscar_huellas(raiz, va.leer_huellas(HUELLAS)) == []
    assert va.buscar_secretos(raiz) == []


def test_detecta_el_centinela_dentro_del_recorrido(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "docs" / "nota.md").write_text(
        f"primera\nsegunda con {CENTINELA}.\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, va.leer_huellas(HUELLAS))
    assert hallazgos == [{"fichero": "docs/nota.md", "linea": 2,
                          "huella": va.huella(CENTINELA), "origen": COPIA}]


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
    # el componente que lleva el token pasa al principio de su huella.
    publicable = f"docs/<huella-{va.huella(CENTINELA)[:12]}>"
    assert [h["fichero"] for h in hallazgos] == [publicable, publicable]


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
    ]) + "\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == []


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
    assert f"{tapada}/{tapada}:0: huella " in salida
    assert f"{tapada}/{tapada}:2: huella " in salida
    assert f"{tapada}/{tapada}:3: clave_de_api_akia" in salida
    assert f"  {tapada}/figura.png" in salida
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


@pytest.mark.skipif(solo_el_centinela(), reason=SIN_LA_LISTA)
def test_el_arbol_esta_limpio():
    """En el repositorio que se publica `huellas.txt` lleva solo la del
    centinela (D9) y esta prueba se salta diciendolo: alli no comprobaria
    nada. Y un recorrido vacio no es un arbol limpio."""
    huellas = va.huellas_de_la_lista(va.leer_huellas(HUELLAS))
    recorridos = len(va.ficheros_versionados(RAIZ))
    assert recorridos > 100, "no se ha recorrido el arbol"
    de_huella = va.buscar_huellas(RAIZ, huellas)
    de_secreto = va.buscar_secretos(RAIZ, huellas)
    if de_huella or de_secreto:
        ficheros = len({h["fichero"] for h in de_huella})
        pytest.fail("\n".join(
            [f"El arbol no se puede publicar: {len(de_huella)} huellas en "
             f"{ficheros} ficheros y {len(de_secreto)} secretos. La linea 0 "
             "es el nombre del fichero."]
            + _por_fichero(de_huella, "huella")
            + _por_fichero(de_secreto, "clase")), pytrace=False)
