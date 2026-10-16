"""Pruebas de scripts/preparar_publicacion.py (SP5-C3, P7), el guion que deja
listo el repositorio que se publica con su historia real limpia.

Todo es de juguete: una lista de juguete (un cliente, otra empresa, una
maquina y dos nombres declarados en el README, D5), sus huellas, y una
historia con el merge de cada subproyecto. La lista de verdad no la abre
ninguna prueba.

Las de la limpieza de un texto y las de las negativas corren siempre. Las que
reescriben una historia necesitan git-filter-repo, de la version que fija el
guion, y se saltan sin el diciendo como instalarlo.
"""
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "preparar_publicacion.py"


def _cargar_script():
    """Importa el guion por ruta: no es un modulo del paquete."""
    especificacion = importlib.util.spec_from_file_location(
        "preparar_publicacion", SCRIPT)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


pp = _cargar_script()
v = pp.v

# La lista de juguete.
CLIENTE, OTRA, MAQUINA = "zorroazul", "linceverde", "maquina7"
NOMBRE, APELLIDO = "ada", "tortuga"
LISTA = frozenset({CLIENTE, OTRA, MAQUINA, NOMBRE, APELLIDO})
NOMBRES = frozenset({NOMBRE, APELLIDO})
HUELLAS = frozenset(v.huella(t) for t in LISTA)
PREFIJOS = pp.prefijos_de(HUELLAS)
IDENTIDAD = "Equipo del copiloto <equipo-copiloto@users.noreply.github.com>"
M = pp.MARCA

con_filter_repo = pytest.mark.skipif(
    importlib.util.find_spec("git_filter_repo") is None,
    reason="sin git-filter-repo no se puede reescribir una historia: las "
           "pruebas de punta a punta del guion de publicación se quedan sin "
           "correr. Para correrlas: pip install "
           f"git-filter-repo=={pp.VERSION_DE_FILTER_REPO}")


def _limpio(texto, prohibidos=LISTA):
    return pp.limpiar_texto(texto, prohibidos, PREFIJOS).texto


# --------------------------------------------------------------------------
# La limpieza de un texto: lo que el verificador veria, y nada mas
# --------------------------------------------------------------------------
def test_sin_mayusculas_ni_tildes_como_el_verificador():
    assert _limpio("Cliente: ZórroAzul S.A.\n") == f"Cliente: {M} S.A.\n"
    assert _limpio("ruta C:\\Users\\MAQUINA7\\x") == f"ruta C:\\Users\\{M}\\x"
    assert _limpio("ada.tortuga@zorroazul.test") == f"{M}.{M}@{M}.test"


def test_detras_de_un_escape():
    assert _limpio('"a;\\nzorroazul();"') == f'"a;\\n{M}();"'
    assert _limpio("x=%20linceverde") == f"x=%20{M}"
    assert _limpio("&#122;orroazul y &#x7a;orroazul") == f"{M} y {M}"
    assert _limpio("\\u007aorroazul") == M
    assert _limpio("Zorro&aacute;zul") == M


def test_con_caracteres_de_formato_dentro_o_como_separador():
    assert _limpio("zorro\u200bazul") == M
    assert _limpio("alfa\u200bzorroazul") == f"alfa\u200b{M}"
    assert _limpio("zorroazu\u0301l") == M


def test_lo_que_el_verificador_no_ve_no_se_toca():
    # Pegado a otras letras, el verificador no lo ve: tampoco se sustituye.
    assert _limpio("prefijozorroazul") == "prefijozorroazul"
    # Dentro de una tirada de base64 (una imagen), el verificador no mira.
    tirada = "A" * 60 + CLIENTE + "A" * 60
    assert _limpio(f"img: {tirada}\n") == f"img: {tirada}\n"


def test_las_huellas_y_sus_prefijos():
    una = v.huella(CLIENTE)
    assert _limpio(f"huella {una[:12]} en x") == f"huella {M} en x"
    assert _limpio(f"<huella-{una[:12]}>") == f"<huella-{M}>"
    assert _limpio(una.upper()) == M
    otra = v.huella("nadaquever")
    assert _limpio(f"sha {otra} y {otra[:12]}") == f"sha {otra} y {otra[:12]}"


def test_la_linea_entera_como_ultimo_recurso():
    # Un escape encadenado (`\u0025` da `%`, y `%7A` da `z`) que el verificador
    # desescapa y la sustitucion por tramos no: la linea se retira entera.
    limpio = pp.limpiar_texto("x \\u00257Aorroazul y\nbien\n", LISTA, PREFIJOS)
    assert limpio.texto == f"{M}\nbien\n"
    assert limpio.lineas_enteras == 1


def test_los_nombres_de_d5_solo_si_no_se_prohiben():
    assert _limpio("Ada Tortuga y zorroazul", LISTA - NOMBRES) == \
        f"Ada Tortuga y {M}"
    assert _limpio("Ada Tortuga y zorroazul") == f"{M} {M} y {M}"


def test_bytes_que_no_son_utf8_se_conservan():
    nuevos, _ = pp.limpiar_bytes(b"firma: Tortug\xe1\n", LISTA, PREFIJOS)
    assert nuevos == f"firma: {M}\n".encode()
    nuevos, _ = pp.limpiar_bytes(b"precio 5\x80 zorroazul\n", LISTA, PREFIJOS)
    assert nuevos == b"precio 5\x80 " + M.encode() + b"\n"


def test_utf16_con_marca_de_orden():
    datos = b"\xff\xfe" + "hola ZorroAzul\n".encode("utf-16-le")
    nuevos, _ = pp.limpiar_bytes(datos, LISTA, PREFIJOS)
    assert nuevos == b"\xff\xfe" + f"hola {M}\n".encode("utf-16-le")


def test_lo_binario_y_lo_limpio_no_cambian():
    binario = b"\x89PNG\x00zorroazul\x00"
    assert pp.limpiar_bytes(binario, LISTA, PREFIJOS) == (binario, 0)
    limpio = b"nada que quitar\n"
    assert pp.limpiar_bytes(limpio, LISTA, PREFIJOS) == (limpio, 0)


def test_las_rutas():
    assert pp.limpiar_ruta("notas/ZorroAzul/informe-maquina7.md", LISTA,
                           PREFIJOS) == "notas/retirado/informe-retirado.md"
    assert pp.limpiar_ruta("docs/plan.md", LISTA, PREFIJOS) == "docs/plan.md"


def test_la_version_de_filter_repo_se_comprueba(monkeypatch):
    monkeypatch.setattr(pp.importlib.metadata, "version", lambda _n: "2.45.0")
    with pytest.raises(SystemExit, match=pp.VERSION_DE_FILTER_REPO):
        pp.comprobar_filter_repo()


# --------------------------------------------------------------------------
# Repositorios de juguete
# --------------------------------------------------------------------------
AUTOR = ("Ada Tortuga", "ada@zorroazul.test")


def _git(repo, *argumentos, entrada=None):
    entorno = {c: x for c, x in os.environ.items() if c not in v.NO_HEREDADAS}
    entorno.update({
        "GIT_AUTHOR_NAME": AUTOR[0], "GIT_AUTHOR_EMAIL": AUTOR[1],
        "GIT_COMMITTER_NAME": AUTOR[0], "GIT_COMMITTER_EMAIL": AUTOR[1],
        "GIT_AUTHOR_DATE": "2026-10-01T12:00:00", "GIT_COMMITTER_DATE":
        "2026-10-01T12:00:00"})
    hecho = subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c",
         "core.autocrlf=false", "-c", "init.defaultBranch=main",
         *argumentos], input=entrada, capture_output=True, env=entorno)
    assert hecho.returncode == 0, hecho.stderr.decode("utf-8", "replace")
    return hecho.stdout


def _escribir(repo, ruta, contenido):
    ruta = Path(repo) / ruta
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(contenido, str):
        contenido = contenido.encode("utf-8")
    ruta.write_bytes(contenido)


def _commit(repo, mensaje, ficheros=None, borrar=()):
    for ruta, contenido in (ficheros or {}).items():
        _escribir(repo, ruta, contenido)
    for ruta in borrar:
        _git(repo, "rm", "-q", "-r", ruta)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", mensaje)


# Lo que lleva cada subproyecto de juguete: (rama, asunto del merge, ficheros).
TABLAS = {"docs/eda/metadatos_eda.csv": "id,edad\n1,30\n",
          "docs/validacion-semisintetica/crudas_prueba.csv": "id,cruda\n1,0.5\n",
          "docs/validacion-semisintetica/crudas_prueba.sha256": "0" * 64 + "\n"}
FLUJO = ('{"jsCode": "const a = 1;\\nzorroazul();\\n", '
         '"url": "https://n8n.zorroazul.test/%20linceverde", '
         '"html": "&#122;orroazul &amp; maquina7"}\n')
FLUJO_LIMPIO = (f'{{"jsCode": "const a = 1;\\n{M}();\\n", '
                f'"url": "https://n8n.{M}.test/%20{M}", '
                f'"html": "{M} &amp; {M}"}}\n')
TIRADA = "A" * 60 + CLIENTE + "A" * 60
BINARIO = b"\x89PNG\x00zorroazul\x00"
CP1252 = b"firma: Tortug\xe1\n"
UTF16 = b"\xff\xfe" + "hola ZorroAzul\n".encode("utf-16-le")


def _plan():
    return (f"huella {v.huella(CLIENTE)[:12]}\n{v.huella(OTRA)}\n")


SUBPROYECTOS = (
    ("sp1", "Merge: SP1 núcleo de imagen",
     {"n8n/flujo.json": FLUJO,
      "docs/notas.md": "Cliente: ZórroAzul\nMáquina: C:\\Users\\maquina7\\x\n"}),
    ("sp2", "feat(sp2): servidor MCP + REST en Docker",
     {"docs/imagen.bin": BINARIO, "docs/incrustada.md": f"img: {TIRADA}\n"}),
    ("sp3", "merge: SP3 cerrado, los dos bots",
     {"docs/firma.txt": CP1252, "docs/saludo.txt": UTF16}),
    ("sp4", "merge: SP4, combinación bayesiana",
     {"docs/plan.md": _plan(),
      "docs/eda/metadatos_eda.csv": "id,edad\n1,30\n2,41\n"}),
    ("sp5a", "merge: SP5-A, generador", {"docs/a.md": "sin nada\n"}),
    ("sp5b1", "merge: SP5-B1, métricas", {"docs/b1.md": "sin nada\n"}),
    ("sp5b2", "Merge: SP5-B2, la anonimización", {"docs/b2.md": "sin nada\n"}),
    ("sp5b3", "Merge: SP5-B3, los residuos", {"docs/b3.md": "sin nada\n"}),
    ("sp5c1", "Merge: SP5-C1, la interfaz", {"docs/c1.md": "sin nada\n"}),
    ("sp5b4", "Merge: SP5-B4, el motor", {"docs/b4.md": "sin nada\n"}),
)
ETIQUETAS = {"v0.1-sp1", "v0.2-sp2", "v0.3-sp3", "v0.4-sp4", "v0.5-sp5a",
             "v0.5-sp5b1", "v0.5-sp5b2", "v0.5-sp5b3", "v0.5-sp5c1",
             "v0.5-sp5b4", "v0.5-sp5c2", "v1.0"}
DECLARACION = "<!-- nombres-publicos: Ada Tortuga -->\n"


def _crear_origen(carpeta):
    """Un repositorio de desarrollo de juguete, con su historia sucia."""
    origen = Path(carpeta) / "origen"
    origen.mkdir(parents=True)
    _git(origen, "init", "-q")
    huellas = origen / pp.HUELLAS_DEL_REPOSITORIO
    v.regenerar(sorted(LISTA), huellas)
    _commit(origen, "Primer commit para ZorroAzul", {
        "README.md": "# Juguete\n\nPara zorroazul.\n",
        "notas/ZorroAzul/informe.md": "informe\n", **TABLAS})
    for rama, asunto, ficheros in SUBPROYECTOS:
        _git(origen, "checkout", "-q", "-b", f"rama-{rama}")
        _commit(origen, f"trabajo de {rama}, notas de linceverde\n\n"
                        "Co-Authored-By: Ada Tortuga <ada@zorroazul.test>",
                ficheros)
        if rama == "sp5b2":             # se borra la ruta que lleva un token
            _commit(origen, "fuera las notas", borrar=["notas"])
        _git(origen, "checkout", "-q", "main")
        _git(origen, "merge", "-q", "--no-ff", f"rama-{rama}", "-m", asunto)
    # SP5-C2: los nombres llegan a LICENSE y a planificacion ANTES de que el
    # README los declare (como en la historia de verdad); en otro fichero,
    # nunca se admiten.
    _git(origen, "checkout", "-q", "-b", "rama-sp5c2")
    _commit(origen, "licencia", {
        "LICENSE": "Copyright (c) 2026 Ada Tortuga\n",
        "docs/planificacion.md": "Equipo: Ada Tortuga\n",
        "docs/equipo.md": "Hecho por Ada Tortuga\n"})
    _commit(origen, "el README declara los nombres", {
        "README.md": f"# Juguete\n\n{DECLARACION}\nHecho por Ada Tortuga.\n"})
    _git(origen, "checkout", "-q", "main")
    _git(origen, "merge", "-q", "--no-ff", "rama-sp5c2", "-m",
         "Merge: SP5-C2, la estructura")
    _git(origen, "tag", "vieja")
    return origen


def _lista(carpeta, tokens=LISTA):
    ruta = Path(carpeta) / "fuera" / "lista.txt"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text("[huellas]\n" + "".join(t + "\n" for t in sorted(tokens)),
                    encoding="utf-8")
    return ruta


def _correr(*argumentos):
    entorno = {c: x for c, x in os.environ.items() if c not in v.NO_HEREDADAS}
    entorno.pop(v.VARIABLE_DE_LA_LISTA, None)
    entorno["PYTHONIOENCODING"] = "utf-8"
    hecho = subprocess.run([sys.executable, str(SCRIPT), *map(str, argumentos)],
                           capture_output=True, env=entorno)
    return (hecho.returncode,
            (hecho.stdout + hecho.stderr).decode("utf-8", "replace"))


def _no_filtra(salida):
    """Ninguna salida lleva un token de la lista, una huella o un prefijo."""
    assert not v.tokens(salida) & LISTA, "la salida lleva un token de la lista"
    assert not [m for m in pp.HEXADECIMAL.findall(salida)
                if m.lower() in PREFIJOS], "la salida lleva una huella"


# --------------------------------------------------------------------------
# De punta a punta, con una historia de juguete
# --------------------------------------------------------------------------
class Publicado:
    def __init__(self, carpeta):
        self.origen = _crear_origen(carpeta)
        self.punta_del_origen = _git(self.origen, "rev-parse", "HEAD")
        self.refs_del_origen = _git(self.origen, "for-each-ref")
        self.destino = Path(carpeta) / "publicado"
        self.codigo, self.salida = _correr(
            "--origen", self.origen, "--destino", self.destino,
            "--lista", _lista(carpeta), "--identidad", IDENTIDAD, "--hilos", 4)

    def git(self, *argumentos):
        return _git(self.destino, *argumentos).decode("utf-8", "replace")

    def blob(self, revision, ruta):
        return _git(self.destino, "cat-file", "blob", f"{revision}:{ruta}")

    def commits(self):
        return self.git("rev-list", "--all").split()


@pytest.fixture(scope="module")
def publicado(tmp_path_factory):
    if importlib.util.find_spec("git_filter_repo") is None:
        pytest.skip("sin git-filter-repo")
    return Publicado(tmp_path_factory.mktemp("publicar"))


@con_filter_repo
def test_sale_con_cero_y_no_imprime_nada_de_la_lista(publicado):
    assert publicado.codigo == 0, publicado.salida
    assert "LISTO para publicar" in publicado.salida
    assert "0 de " in publicado.salida
    _no_filtra(publicado.salida)


@con_filter_repo
def test_el_origen_no_se_toca(publicado):
    assert _git(publicado.origen, "rev-parse", "HEAD") == \
        publicado.punta_del_origen
    assert _git(publicado.origen, "for-each-ref") == publicado.refs_del_origen
    assert not _git(publicado.origen, "status", "--porcelain").strip()


@con_filter_repo
def test_paso_1_las_tablas_fuera_de_todos_los_commits(publicado):
    for commit in publicado.commits():
        rutas = publicado.git("ls-tree", "-r", "--name-only", commit).split()
        assert not set(rutas) & set(pp.RUTAS_QUE_NO_SE_PUBLICAN), commit


@con_filter_repo
def test_paso_2_huellas_solo_del_centinela_en_todos(publicado):
    centinela = publicado.blob("main", pp.HUELLAS_DEL_REPOSITORIO)
    assert centinela.decode().startswith(v.CABECERA_SOLO_CENTINELA)
    lineas = [x for x in centinela.decode().splitlines()
              if x and not x.startswith("#")]
    assert lineas == [v.huella(v.CENTINELA)]
    for commit in publicado.commits():
        assert publicado.blob(commit, pp.HUELLAS_DEL_REPOSITORIO) == centinela


@con_filter_repo
def test_paso_3_una_sola_identidad(publicado):
    identidades = set(publicado.git(
        "log", "--all", "--format=%an <%ae>%n%cn <%ce>").splitlines()) - {""}
    assert identidades == {IDENTIDAD}


@con_filter_repo
def test_paso_4_ni_un_token_salvo_los_nombres_donde_d5_los_admite(publicado):
    for commit in publicado.commits():
        readme = publicado.blob(commit, "README.md").decode()
        declara = bool(v.nombres_publicos(readme))
        mensaje = publicado.git("log", "-1", "--format=%B", commit)
        assert not v.tokens(mensaje) & LISTA, commit
        for ruta in publicado.git("ls-tree", "-r", "--name-only",
                                  commit).splitlines():
            assert not v.tokens(ruta) & LISTA, ruta
            texto = v._texto_de(publicado.blob(commit, ruta))
            if texto is None:
                continue
            admitidos = (NOMBRES if declara and ruta in v.FICHEROS_CON_NOMBRES
                         else frozenset())
            for linea in texto.splitlines():
                assert not (v.tokens(linea) & LISTA) - admitidos, (commit, ruta)


@con_filter_repo
def test_paso_4_lo_que_se_sustituye_y_lo_que_no(publicado):
    b = publicado.blob
    assert b("main", "n8n/flujo.json").decode() == FLUJO_LIMPIO
    assert b("main", "docs/notas.md").decode() == \
        f"Cliente: {M}\nMáquina: C:\\Users\\{M}\\x\n"
    assert b("main", "docs/incrustada.md").decode() == f"img: {TIRADA}\n"
    assert b("main", "docs/imagen.bin") == BINARIO
    assert b("main", "docs/firma.txt") == f"firma: {M}\n".encode()
    assert b("main", "docs/saludo.txt") == \
        b"\xff\xfe" + f"hola {M}\n".encode("utf-16-le")
    assert b("main", "docs/plan.md").decode() == f"huella {M}\n{M}\n"
    assert b("main", "README.md").decode() == \
        f"# Juguete\n\n{DECLARACION}\nHecho por Ada Tortuga.\n"
    assert b("main", "LICENSE").decode() == "Copyright (c) 2026 Ada Tortuga\n"
    assert b("main", "docs/equipo.md").decode() == f"Hecho por {M} {M}\n"


@con_filter_repo
def test_paso_4_los_nombres_antes_de_la_declaracion_se_retiran(publicado):
    """En los commits cuyo README no declara los nombres, ni LICENSE ni
    planificacion los llevan: el verificador no los admitiria ahi."""
    vistos = set()
    for commit in publicado.commits():
        if "LICENSE" not in publicado.git("ls-tree", "--name-only",
                                          commit).split():
            continue
        declara = bool(v.nombres_publicos(
            publicado.blob(commit, "README.md").decode()))
        esperado = ("Copyright (c) 2026 Ada Tortuga\n" if declara
                    else f"Copyright (c) 2026 {M} {M}\n")
        assert publicado.blob(commit, "LICENSE").decode() == esperado
        vistos.add(declara)
    assert vistos == {True, False}


@con_filter_repo
def test_paso_4_la_ruta_con_un_token_se_renombra_y_se_borra(publicado):
    primero = publicado.git("rev-list", "--max-parents=0", "main").strip()
    assert "notas/retirado/informe.md" in publicado.git(
        "ls-tree", "-r", "--name-only", primero).split()
    assert "notas/retirado/informe.md" not in publicado.git(
        "ls-tree", "-r", "--name-only", "main").split()


@con_filter_repo
def test_paso_5_etiquetas_una_rama_y_ningun_remoto(publicado):
    assert set(publicado.git("tag").split()) == ETIQUETAS
    assert publicado.git("branch", "--format=%(refname:short)").split() == \
        ["main"]
    assert not publicado.git("remote").strip()
    assert publicado.git("rev-parse", "v1.0") == publicado.git(
        "rev-parse", "main")
    asuntos = {f"v0.{re.match(r'sp(\d)', rama).group(1)}-{rama}": asunto
               for rama, asunto, _ficheros in SUBPROYECTOS}
    asuntos["v0.5-sp5c2"] = "Merge: SP5-C2, la estructura"
    assert set(asuntos) == ETIQUETAS - {"v1.0"}
    for etiqueta, asunto in asuntos.items():
        padres = publicado.git("log", "-1", "--format=%P", etiqueta).split()
        assert len(padres) == 2, etiqueta
        assert publicado.git("log", "-1", "--format=%s",
                             etiqueta).strip() == asunto, etiqueta


@con_filter_repo
def test_paso_6_la_historia_vieja_no_queda_en_la_carpeta(publicado):
    hecho = subprocess.run(["git", "-C", str(publicado.destino), "cat-file",
                            "-e", publicado.punta_del_origen.strip()],
                           capture_output=True)
    assert hecho.returncode != 0
    assert not publicado.git("fsck", "--unreachable", "--no-reflogs",
                             "--no-progress").strip()


@con_filter_repo
def test_por_huellas_da_la_misma_historia_que_con_la_lista(publicado,
                                                          tmp_path):
    """Sin la lista, con los tokens de la historia cuya huella esta en
    huellas.txt, sale exactamente la misma historia: los mismos commits."""
    destino = tmp_path / "por-huellas"
    codigo, salida = _correr("--origen", publicado.origen, "--destino",
                             destino, "--por-huellas", "--identidad",
                             IDENTIDAD, "--hilos", 4)
    assert codigo == 0, salida
    assert f"Por huellas: {len(LISTA)} tokens" in salida
    _no_filtra(salida)
    assert _git(destino, "rev-parse", "main") == _git(
        publicado.destino, "rev-parse", "main")
    assert _git(destino, "show-ref", "--tags") == _git(
        publicado.destino, "show-ref", "--tags")


@con_filter_repo
def test_paso_6_un_ensayo_con_una_lista_corta_da_hallazgos_y_no_los_imprime(
        tmp_path):
    """Con una lista que no lleva un token (como el ensayo con la lista de
    juguete sobre la historia de verdad), el verificador lo ve en los commits
    que lo llevan: sale con 1, dice cuantos y no imprime el token."""
    origen = _crear_origen(tmp_path)
    corta = _lista(tmp_path, LISTA - {MAQUINA})
    codigo, salida = _correr("--origen", origen, "--destino",
                             tmp_path / "publicado", "--lista", corta,
                             "--identidad", IDENTIDAD)
    assert "no casan" in salida and codigo != 0 and "--ensayo" in salida
    codigo, salida = _correr("--origen", origen, "--destino",
                             tmp_path / "publicado", "--lista", corta,
                             "--identidad", IDENTIDAD, "--ensayo", "--detalle")
    assert codigo == 1
    assert "NO publicar" in salida
    m = re.search(r"Verificador, commit a commit: (\d+) de (\d+)", salida)
    assert m and 0 < int(m.group(1)) <= int(m.group(2))
    assert "docs/notas.md:2: huella" in salida
    _no_filtra(salida)


# --------------------------------------------------------------------------
# Las negativas: antes de tocar nada
# --------------------------------------------------------------------------
@pytest.fixture
def pequeno(tmp_path):
    """Un origen de un commit y su lista: basta para las negativas."""
    origen = tmp_path / "origen"
    origen.mkdir()
    _git(origen, "init", "-q")
    v.regenerar(sorted(LISTA), origen / pp.HUELLAS_DEL_REPOSITORIO)
    _commit(origen, "uno", {"README.md": "hola\n"})
    return origen, _lista(tmp_path)


def _negativa(argumentos, esperado):
    codigo, salida = _correr(*argumentos)
    assert codigo != 0 and esperado in salida, salida
    _no_filtra(salida)
    return salida


def test_el_destino_dentro_del_origen(pequeno):
    origen, lista = pequeno
    _negativa(["--origen", origen, "--destino", origen / "dentro", "--lista",
               lista, "--identidad", IDENTIDAD], "El destino no puede ser")
    assert not (origen / "dentro").exists()


def test_el_destino_es_el_repositorio_de_trabajo(pequeno, tmp_path):
    origen, lista = pequeno
    _negativa(["--origen", origen, "--destino", REPO, "--lista", lista,
               "--identidad", IDENTIDAD], "El destino no puede ser")


def test_el_destino_no_esta_vacio(pequeno, tmp_path):
    origen, lista = pequeno
    (tmp_path / "lleno").mkdir()
    (tmp_path / "lleno" / "algo.txt").write_text("x")
    _negativa(["--origen", origen, "--destino", tmp_path / "lleno", "--lista",
               lista, "--identidad", IDENTIDAD], "no es una carpeta vacía")


def test_el_destino_dentro_de_otro_repositorio(pequeno, tmp_path):
    origen, lista = pequeno
    otro = tmp_path / "otro"
    otro.mkdir()
    _git(otro, "init", "-q")
    _negativa(["--origen", origen, "--destino", otro / "publicado", "--lista",
               lista, "--identidad", IDENTIDAD], "dentro de otro repositorio")


def test_la_lista_dentro_del_origen(pequeno, tmp_path):
    origen, _lista_fuera = pequeno
    dentro = _lista(origen)
    _negativa(["--origen", origen, "--destino", tmp_path / "p", "--lista",
               dentro, "--identidad", IDENTIDAD], "tiene que vivir fuera")


def test_la_identidad_con_un_token_de_la_lista(pequeno, tmp_path):
    origen, lista = pequeno
    _negativa(["--origen", origen, "--destino", tmp_path / "p", "--lista",
               lista, "--identidad", "Ada <ada@users.noreply.github.com>"],
              "La identidad lleva un token de la lista")
    _negativa(["--origen", origen, "--destino", tmp_path / "p", "--lista",
               lista, "--identidad", "sin correo"], "Nombre <correo>")


def test_la_lista_no_casa_con_las_huellas(pequeno, tmp_path):
    origen, _lista_buena = pequeno
    corta = _lista(tmp_path / "corta", LISTA - {OTRA})
    _negativa(["--origen", origen, "--destino", tmp_path / "p", "--lista",
               corta, "--identidad", IDENTIDAD], "no casan")


def test_las_huellas_solo_del_centinela(pequeno, tmp_path):
    origen, lista = pequeno
    solo = tmp_path / "solo.txt"
    v.regenerar_solo_centinela(solo)
    _negativa(["--origen", origen, "--destino", tmp_path / "p", "--lista",
               lista, "--identidad", IDENTIDAD, "--huellas", solo],
              "solo la del centinela")


def test_por_huellas_no_lleva_lista(pequeno, tmp_path):
    origen, lista = pequeno
    _negativa(["--origen", origen, "--destino", tmp_path / "p", "--lista",
               lista, "--por-huellas", "--identidad", IDENTIDAD],
              "--por-huellas no lleva lista")
    _negativa(["--origen", origen, "--destino", tmp_path / "p",
               "--por-huellas", "--identidad",
               "Ada <ada@users.noreply.github.com>"],
              "La identidad lleva un token de la lista")


def test_una_entrada_de_la_lista_que_no_es_un_token(pequeno, tmp_path):
    origen, _lista_buena = pequeno
    mala = tmp_path / "mala.txt"
    mala.write_text("[huellas]\nzorro-azul\n", encoding="utf-8")
    _negativa(["--origen", origen, "--destino", tmp_path / "p", "--lista",
               mala, "--identidad", IDENTIDAD], "números de entrada: 1")
