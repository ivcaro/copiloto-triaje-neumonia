"""Pruebas del anonimato del repositorio (spec de SP5 §6.1).

El repositorio se publica, y lo que se publica no puede llevar ninguna cadena
que identifique al cliente, a la empresa, a la maquina ni a los integrantes.
La lista de esas cadenas NO vive aqui: el repositorio lleva solo
`tests/anonimato/huellas.txt`, con el sha256 de cada token. Por eso estas
pruebas corren siempre, sin la lista: se prueban a si mismas con un token
publico, el centinela, cuya huella va siempre en el fichero.

Los secretos de ejemplo se COMPONEN al correr (`"sk" + "-" + ...`): este
fichero tambien se recorre, y un secreto de ejemplo escrito entero haria
saltar la misma prueba que lo usa.
"""
import hashlib
import importlib.util
import os
import shutil
import subprocess
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
def test_el_centinela_esta_en_huellas_txt():
    assert va.huella(CENTINELA) in va.leer_huellas(HUELLAS)


def test_huellas_txt_lleva_cabecera_y_huellas_ordenadas_sin_repetir():
    lineas = HUELLAS.read_text(encoding="utf-8").splitlines()
    assert lineas[0].startswith("#")
    datos = [l for l in lineas if l and not l.startswith("#")]
    assert len(datos) > 1, "solo esta el centinela: falta regenerar"
    assert all(len(l) == 64 and set(l) <= set("0123456789abcdef")
               for l in datos)
    assert datos == sorted(set(datos))
    assert set(datos) == va.leer_huellas(HUELLAS)


def test_la_lista_en_claro_esta_ignorada_por_si_alguien_la_copia_dentro():
    lineas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "tests/anonimato/lista*.txt" in lineas
    assert not list((RAIZ / "tests" / "anonimato").glob("lista*.txt"))


# --------------------------------------------------------------------------
# La lista en claro y la regeneracion (con una lista de juguete)
# --------------------------------------------------------------------------
LISTA_DE_JUGUETE = """\
# comentario de cabecera
[huellas]
# un grupo
Uno-Dos
tres

[sustituciones]
cuatro => cinco
"""


def test_leer_lista_da_solo_la_seccion_de_huellas(tmp_path):
    lista = tmp_path / "lista.txt"
    lista.write_text(LISTA_DE_JUGUETE, encoding="utf-8")
    assert va.leer_lista(lista) == ["Uno-Dos", "tres"]


def test_regenerar_escribe_las_huellas_ordenadas_y_la_del_centinela(tmp_path):
    destino = tmp_path / "anonimato" / "huellas.txt"
    n = va.regenerar(["Uno-Dos", "tres", "uno"], destino)
    esperadas = {va.huella(t) for t in ("uno", "dos", "tres", CENTINELA)}
    assert n == 4
    assert va.leer_huellas(destino) == esperadas
    texto = destino.read_text(encoding="utf-8")
    datos = [l for l in texto.splitlines() if l and not l.startswith("#")]
    assert datos == sorted(esperadas)
    assert texto.startswith("#")
    assert "\r" not in destino.read_bytes().decode("utf-8")
    # El fichero se publica: ningun token en claro, salvo el centinela, que
    # es publico y la cabecera lo nombra.
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
                          "huella": va.huella(CENTINELA)}]


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
    assert sorted(hallazgo) == ["fichero", "huella", "linea"]
    assert CENTINELA not in repr(hallazgo)


def test_el_nombre_del_fichero_tambien_se_tokeniza(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "docs" / f"{CENTINELA}.md").write_text("nada\n", encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [h["linea"] for h in hallazgos] == [0]
    assert CENTINELA not in repr(hallazgos)
    assert hallazgos[0]["fichero"].startswith("docs/")


def test_los_binarios_se_declaran_y_no_se_recorren(tmp_path):
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "otra.png").write_bytes(
        b"\x89PNG\x00" + CENTINELA.encode("ascii") + b"\xff")
    assert va.es_texto(raiz / "codigo.py")
    assert not va.es_texto(raiz / "otra.png")
    assert [p.name for p in va.binarios(raiz)] == ["figura.png", "otra.png"]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []


# --------------------------------------------------------------------------
# Con git: solo lo versionado
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
    subprocess.run(["git", "-C", str(raiz), *argumentos], check=True,
                   capture_output=True, env=limpio)


def _repositorio(tmp_path):
    raiz = _arbol_limpio(tmp_path / "repo")
    _git(raiz, "init", "-q")
    _git(raiz, "add", "-A")
    return raiz


@hay_git
def test_en_un_repositorio_se_recorre_solo_lo_versionado(tmp_path):
    raiz = _repositorio(tmp_path)
    (raiz / "sin_versionar.txt").write_text(CENTINELA + "\n",
                                            encoding="utf-8")
    nombres = [p.relative_to(raiz).as_posix()
               for p in va.ficheros_versionados(raiz)]
    assert nombres == ["codigo.py", "docs/guia.md", "figura.png"]
    assert va.buscar_huellas(raiz, {va.huella(CENTINELA)}) == []

    (raiz / "docs" / "guia.md").write_text(f"ahora sí: {CENTINELA}\n",
                                           encoding="utf-8")
    hallazgos = va.buscar_huellas(raiz, {va.huella(CENTINELA)})
    assert [(h["fichero"], h["linea"]) for h in hallazgos] == [
        ("docs/guia.md", 1)]


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
         GIT_AUTHOR_NAME=f"Nombre {CENTINELA.upper()}",
         GIT_COMMITTER_EMAIL=f"{CENTINELA}@ejemplo.test")
    assert va.commits(raiz) == 2
    hallazgos = va.verificar_commit(raiz, "HEAD", huellas=huellas)
    assert [(h["campo"], h["linea"]) for h in hallazgos] == [
        ("autor", 0), ("correo_de_quien_confirma", 0), ("mensaje", 3)]
    assert all(h["huella"] == va.huella(CENTINELA) for h in hallazgos)
    assert CENTINELA not in repr(hallazgos).lower()
    assert va.verificar_commit(raiz, "HEAD~1", huellas=huellas) == []


# --------------------------------------------------------------------------
# Secretos. Se componen al correr: ver el docstring del fichero.
# --------------------------------------------------------------------------
def _secretos():
    return {
        "token_de_bot_de_telegram": "123456789" + ":" + "AAH" + "x" * 32,
        "clave_de_api_sk": "sk" + "-" + "proj" + "-" + "a1B2" * 6,
        "clave_de_api_akia": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
        "clave_de_api_ghp": "gh" + "p_" + "a1B2" * 9,
        "clave_de_api_github_pat": "github" + "_pat_" + "a1B2_" * 6,
        "jwt": ".".join(["ey" + "J" + "hbGciOiJIUzI1NiJ9",
                         "ey" + "J" + "zdWIiOiIxMjM0NTY3ODkwIn0",
                         "dozjgNryP4J3jVmNHl0w5N"]),
        "contrasena_en_url": "postgresql://usuario" + ":" + "S3creta!"
                             + "@" + "bd.ejemplo.test:5432/base",
    }


@pytest.mark.parametrize("clase", sorted(_secretos()))
def test_buscar_secretos_encuentra_cada_clase_sin_imprimirla(tmp_path, clase):
    secreto = _secretos()[clase]
    raiz = _arbol_limpio(tmp_path / "arbol")
    (raiz / "config.txt").write_text(f"uno\ndos\nVALOR = \"{secreto}\"\n",
                                     encoding="utf-8")
    hallazgos = va.buscar_secretos(raiz)
    assert hallazgos == [{"fichero": "config.txt", "linea": 3,
                          "clase": clase}]


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
    "privada.key", "id_rsa", "id_rsa.pub", "certificado.p12"])
def test_los_ficheros_prohibidos_son_hallazgos(tmp_path, nombre):
    raiz = _arbol_limpio(tmp_path / "arbol")
    ruta = raiz / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("X=1\n", encoding="utf-8")
    assert va.buscar_secretos(raiz) == [
        {"fichero": nombre, "linea": 0, "clase": "fichero_prohibido"}]


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


def test_la_cli_sin_lista_dice_que_variable_falta(tmp_path, monkeypatch):
    monkeypatch.delenv("ANONIMATO_LISTA", raising=False)
    with pytest.raises(SystemExit) as salida:
        va.main(["--regenerar", "--huellas", str(tmp_path / "h.txt")])
    assert "ANONIMATO_LISTA" in str(salida.value)
    assert not (tmp_path / "h.txt").exists()
