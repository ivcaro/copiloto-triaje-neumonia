"""Comprueba que el repositorio se puede publicar (spec de SP5 §6.1).

Uso, desde la raiz del repositorio:

    python scripts/verificar_anonimato.py
    python scripts/verificar_anonimato.py --raiz <arbol> --commit --un-solo-commit
    ANONIMATO_LISTA=<lista en claro> python scripts/verificar_anonimato.py --regenerar

Mira lo que se publicaria: la copia de trabajo (en un repositorio, lo que
tiene seguimiento y lo que no lo tiene ni esta ignorado), lo preparado en el
indice que no es lo que hay en disco y, con --commit, el arbol de ese commit.
Busca dos cosas:

1. HUELLAS. La lista de cadenas que identifican al cliente, a la empresa, a la
   maquina o a los integrantes NO vive en el repositorio. El repositorio lleva
   solo `tests/anonimato/huellas.txt`: el sha256 de cada token (en el de
   desarrollo, la lista entera; en el que se publica, solo la del centinela,
   D9). Cada fichero de texto se tokeniza igual que la lista (minusculas, sin
   tildes, particion por todo lo que no sea [a-z0-9], tambien desescapado) y
   se compara huella con huella.
2. SECRETOS, por patron: token de bot de Telegram, claves de API, claves
   privadas, cabeceras Authorization, asignaciones de contrasenas y tokens,
   contrasena dentro de una URL, y ficheros que no deben viajar (`.env`,
   claves). Un enlace simbolico o un submodulo es un hallazgo `no_recorrido`.

Ninguna salida lleva el token ni el secreto en claro: fichero, linea y huella
o clase. Los nombres de fichero que llevan un token salen tapados, y las
rutas salen relativas a la raiz que se recorre (la de las huellas, como se
paso).

Sale con 0 si no hay hallazgos y con 1 si los hay, si no se ha recorrido
ningun fichero o si las huellas son solo la del centinela. Lo usa
`tests/test_anonimato.py`, que lo carga por ruta.
"""
import argparse
import codecs
import fnmatch
import hashlib
import html
import os
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from pathlib import Path
from typing import NamedTuple, Optional

REPO = Path(__file__).resolve().parents[1]
HUELLAS_POR_DEFECTO = REPO / "tests" / "anonimato" / "huellas.txt"
HUELLAS_MOSTRADAS = "tests/anonimato/huellas.txt"   # en las salidas
VARIABLE_DE_LA_LISTA = "ANONIMATO_LISTA"

# El centinela es PUBLICO: el spec lo nombra. Su huella va siempre en
# huellas.txt para que la prueba se pruebe a si misma sin la lista. Por eso
# mismo no cuenta como hallazgo en el arbol (ver `huellas_de_la_lista`).
CENTINELA = "centinelaanonimato7f3a"

# Las imagenes incrustadas de los notebooks: una tirada asi, troceada por
# `+`, `/` y `=`, da tokens al azar que pueden coincidir con uno corto.
BASE64 = re.compile(r"[A-Za-z0-9+/=]{120,}")
NO_TOKEN = re.compile(r"[^a-z0-9]+")

CABECERA = """\
# Huellas del anonimato (spec de SP5 §6.1): el sha256 de cada token de la
# lista negra, que vive FUERA del repositorio. Una por línea, ordenadas.
# Incluye siempre la del centinela público `centinelaanonimato7f3a`.
# No se edita a mano. Se regenera con:
#   ANONIMATO_LISTA=<lista en claro> python scripts/verificar_anonimato.py --regenerar
"""


# --------------------------------------------------------------------------
# Tokens y huellas
# --------------------------------------------------------------------------
def _sin_tildes(texto):
    """Normalizacion de compatibilidad (NFKD: descompone las tildes y el
    ancho completo) sin las marcas de combinacion (Mn) y sin los caracteres
    de formato (Cf: U+200B, U+00AD...), que se BORRAN en vez de partir el
    token."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto)
                   if unicodedata.category(c) not in ("Mn", "Cf"))


def _partir(texto):
    texto = BASE64.sub(" ", texto)
    return set(NO_TOKEN.split(_sin_tildes(texto).lower())) - {""}


# Los escapes pegan letras al token: `\n` delante da `n...`, `%20` da `20...`,
# `&#99;` parte la primera letra. Se tokeniza tambien el texto desescapado.
HAY_ESCAPE = re.compile(r"\\[ntru]|%[0-9A-Fa-f]{2}|&(?:#|[A-Za-z]+;)")
ESCAPE_DE_CONTROL = re.compile(r"\\[ntr]")
ESCAPE_UNICODE = re.compile(r"\\u([0-9A-Fa-f]{4})")


def _desescapado(texto):
    """`\\n`, `\\t` y `\\r` escritos con barra pasan a un espacio; `\\uXXXX`,
    `%XX` y las entidades HTML, a su caracter."""
    texto = ESCAPE_DE_CONTROL.sub(" ", texto)
    texto = ESCAPE_UNICODE.sub(lambda m: chr(int(m.group(1), 16)), texto)
    texto = urllib.parse.unquote(texto, errors="replace")
    return html.unescape(texto)


def tokens(texto):
    """Los tokens de un texto: la misma regla para la lista y los ficheros.

    La union de los del texto tal cual y los del texto desescapado.
    """
    hallados = _partir(texto)
    if HAY_ESCAPE.search(texto):
        hallados |= _partir(_desescapado(texto))
    return hallados


def huella(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


UNA_HUELLA = re.compile(r"[0-9a-f]{64}")


def leer_huellas(ruta):
    """Las huellas de `huellas.txt`, sin la cabecera ni lineas vacias.

    Cada linea que no sea comentario tiene que ser una huella: 64 caracteres
    hexadecimales en minusculas. Si no, ValueError con el NUMERO de la linea
    (nunca su contenido: podria ser un token en claro).
    """
    huellas = set()
    lineas = Path(ruta).read_text(encoding="utf-8-sig").splitlines()
    for n, linea in enumerate(lineas, 1):
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if not UNA_HUELLA.fullmatch(linea):
            raise ValueError(
                f"la línea {n} no es una huella (64 caracteres hexadecimales "
                "en minúsculas)")
        huellas.add(linea)
    return huellas


def huellas_de_la_lista(huellas):
    """Las huellas sin la del centinela: lo que se busca en el arbol."""
    return set(huellas) - {huella(CENTINELA)}


def leer_lista(ruta):
    """Las entradas de la seccion `[huellas]` de la lista en claro.

    Admite la marca de orden de bytes; los nombres de seccion no distinguen
    mayusculas; lo que sigue a un `#` en una linea es comentario.
    """
    entradas, dentro = [], False
    for linea in Path(ruta).read_text(encoding="utf-8-sig").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        if linea.startswith("["):
            dentro = linea.lower() == "[huellas]"
        elif dentro:
            entradas.append(linea)
    return entradas


def regenerar(lista, destino):
    """Escribe las huellas de los tokens de `lista`, ordenadas, y las cuenta.

    Cada entrada tiene que dar EXACTAMENTE un token (`zorro-azul.test` da
    tres: la lista se tokeniza a mano, un token por linea). Si alguna no, o
    si no hay entradas, ValueError con los NUMEROS de entrada (nunca su
    contenido) y no se escribe nada. La del centinela va siempre.
    """
    if not lista:
        raise ValueError("la sección [huellas] de la lista no tiene entradas")
    todas, malas = {huella(CENTINELA)}, []
    for n, entrada in enumerate(lista, 1):
        suyos = tokens(entrada)
        if len(suyos) == 1:
            todas |= {huella(t) for t in suyos}
        else:
            malas.append(n)
    if malas:
        raise ValueError(
            f"{len(malas)} entradas de [huellas] no dan exactamente un token "
            f"(números de entrada: {', '.join(map(str, malas))}); pon un "
            "token por línea")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as salida:
        salida.write(CABECERA)
        for una in sorted(todas):
            salida.write(una + "\n")
    return len(todas)


# --------------------------------------------------------------------------
# El recorrido: lo que se publicaria
# --------------------------------------------------------------------------
# De donde sale cada cosa que se recorre (clave `origen` de los hallazgos).
COPIA, INDICE, COMMIT = "copia de trabajo", "indice", "commit"


# Variables que harian que git mirase otro repositorio, otro indice u otra
# copia de trabajo que la de `raiz` (un gancho de git las pone, por ejemplo).
NO_HEREDADAS = ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE",
                "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE")


def _git(raiz, *argumentos, entrada=None):
    """La salida de git en bytes, o None si git falla o no esta.

    Sobre `raiz` y solo sobre ella: no hereda las variables de NO_HEREDADAS.
    """
    entorno = {c: v for c, v in os.environ.items() if c not in NO_HEREDADAS}
    try:
        hecho = subprocess.run(["git", "-C", str(raiz), *argumentos],
                               input=entrada, capture_output=True,
                               check=False, env=entorno)
    except OSError:
        return None
    return hecho.stdout if hecho.returncode == 0 else None


def _es_la_raiz_de_un_repositorio(raiz):
    cima = _git(raiz, "rev-parse", "--show-toplevel")
    if cima is None:
        return False
    try:
        return os.path.samefile(cima.decode("utf-8").strip(), raiz)
    except OSError:
        return False


def _partir_z(salida):
    return [n for n in salida.decode("utf-8", errors="replace").split("\0")
            if n]


def _indice(raiz):
    """Las entradas del indice: {nombre: [(modo, sha), ...]}, una por
    etapa."""
    salida = _git(raiz, "ls-files", "-s", "-z")
    if salida is None:
        return None
    indice = {}
    for linea in _partir_z(salida):
        cabecera, nombre = linea.split("\t", 1)
        modo, sha, _etapa = cabecera.split()
        indice.setdefault(nombre, []).append((modo, sha))
    return indice


def _sin_seguimiento(raiz):
    """Lo que no tiene seguimiento ni esta ignorado (`git add -A` lo anade).

    Una carpeta que es otro repositorio sale con `/` al final.
    """
    salida = _git(raiz, "ls-files", "-z", "--others", "--exclude-standard")
    return None if salida is None else _partir_z(salida)


def _arbol_del_commit(raiz, revision):
    """{nombre: (modo, sha)} del arbol de `revision`, bajo `raiz`."""
    salida = _git(raiz, "ls-tree", "-r", "-z", revision, "--")
    if salida is None:
        raise SystemExit(f"No se pudo leer el árbol del commit {revision}: "
                         "¿es un repositorio de git con commits?")
    arbol = {}
    for linea in _partir_z(salida):
        cabecera, nombre = linea.split("\t", 1)
        modo, _tipo, sha = cabecera.split()
        arbol[nombre] = (modo, sha)
    return arbol


def _blobs(raiz, shas):
    """{sha: contenido} de los blobs pedidos, con una sola llamada a git."""
    shas = sorted(set(shas))
    if not shas:
        return {}
    salida = _git(raiz, "cat-file", "--batch",
                  entrada=("\n".join(shas) + "\n").encode("ascii")) or b""
    blobs, i = {}, 0
    while i < len(salida):
        fin = salida.index(b"\n", i)
        cabecera = salida[i:fin].split()
        i = fin + 1
        if len(cabecera) != 3:                  # «<sha> missing»
            continue
        sha, tamano = cabecera[0].decode("ascii"), int(cabecera[2])
        blobs[sha] = salida[i:i + tamano]
        i += tamano + 1
    return blobs


def _en_git(raiz):
    """Indice y lo sin seguimiento, o None si `raiz` no es la raiz de un
    repositorio de git."""
    if not _es_la_raiz_de_un_repositorio(raiz):
        return None
    indice, otros = _indice(raiz), _sin_seguimiento(raiz)
    if indice is None or otros is None:
        return None
    return indice, otros


def _recorrer_carpeta(raiz):
    """Todo lo que hay debajo de `raiz` salvo las carpetas `.git/`: los
    ficheros, y aparte los enlaces simbolicos (que no se siguen)."""
    ficheros, enlaces = [], []
    for carpeta, subcarpetas, nombres in os.walk(raiz):
        carpeta = Path(carpeta)
        enlaces += [carpeta / s for s in subcarpetas
                    if _es_enlace(carpeta / s)]
        subcarpetas[:] = [s for s in subcarpetas
                          if s != ".git" and not _es_enlace(carpeta / s)]
        for n in nombres:
            (enlaces if _es_enlace(carpeta / n) else ficheros).append(
                carpeta / n)
    orden = lambda p: p.relative_to(raiz).as_posix()  # noqa: E731
    return sorted(ficheros, key=orden), sorted(enlaces, key=orden)


def _es_enlace(ruta):
    """Enlace simbolico (o, en Windows, union de carpetas): no se sigue."""
    es_union = getattr(os.path, "isjunction", lambda _ruta: False)
    return os.path.islink(ruta) or es_union(ruta)


def ficheros_versionados(raiz):
    """Los ficheros de la copia de trabajo que se publicarian, ordenados.

    En la raiz de un repositorio de git, los que tienen seguimiento y los que
    no lo tienen ni estan ignorados. Si `raiz` no es la raiz de un
    repositorio, todos los que hay debajo salvo la carpeta `.git/`. Los
    enlaces simbolicos no (no se recorren: ver `_piezas`).
    """
    raiz = Path(raiz)
    en_git = _en_git(raiz)
    if en_git is None:
        return _recorrer_carpeta(raiz)[0]
    indice, otros = en_git
    nombres = sorted(set(indice) | {n for n in otros if not n.endswith("/")})
    return [raiz / n for n in nombres
            if (raiz / n).is_file() and not _es_enlace(raiz / n)]


# La de UTF-32 antes que la de UTF-16: la de UTF-32 LE empieza por la otra.
MARCAS_DE_ORDEN = ((codecs.BOM_UTF32_LE, "utf-32"),
                   (codecs.BOM_UTF32_BE, "utf-32"),
                   (codecs.BOM_UTF8, "utf-8-sig"),
                   (codecs.BOM_UTF16_LE, "utf-16"),
                   (codecs.BOM_UTF16_BE, "utf-16"))


def _cp1252_suelto(error):
    """Lo que no es UTF-8 se lee como cp1252 (el CSV de Excel), byte a byte:
    un byte suelto no estropea las tildes del resto del fichero."""
    trozo = error.object[error.start:error.end]
    return trozo.decode("cp1252", errors="replace"), error.end


codecs.register_error("verificar_anonimato.cp1252", _cp1252_suelto)


def _texto_de(datos):
    """El texto de unos bytes, o None si no es texto.

    Con marca de orden de bytes, en su codificacion (UTF-8, UTF-16 o
    UTF-32). Sin ella: binario si lleva algun byte nulo; si no, UTF-8, y lo
    que no lo sea, cp1252 (lo que no se pueda decodificar se sustituye).
    """
    for marca, codificacion in MARCAS_DE_ORDEN:
        if datos.startswith(marca):
            return datos.decode(codificacion, errors="replace")
    if b"\0" in datos:
        return None
    return datos.decode("utf-8", errors="verificar_anonimato.cp1252")


def _texto(ruta):
    """El texto del fichero, o None si no es texto."""
    return _texto_de(Path(ruta).read_bytes())


def es_texto(ruta):
    """Es texto lo que tiene marca de orden de bytes o no lleva bytes nulos
    (ver `_texto_de`)."""
    return _texto(ruta) is not None


def binarios(raiz):
    """Lo que no es texto: se declara y se revisa a mano, no se recorre."""
    return [p for p in ficheros_versionados(raiz) if not es_texto(p)]


def _relativo(ruta, raiz):
    return Path(ruta).relative_to(raiz).as_posix()


class _Pieza(NamedTuple):
    """Una cosa que se publicaria: un contenido con su nombre y su origen."""
    nombre: str             # relativo a la raiz, con `/`
    origen: str             # COPIA, INDICE o COMMIT
    texto: Optional[str]    # None: binario, o no recorrida
    primera: bool           # la primera pieza de ese nombre: se mira el nombre
    recorrida: bool = True  # False: enlace simbolico, submodulo o ilegible


# Modos de git cuyo contenido no es el de un fichero: no se recorren.
ENLACE_SIMBOLICO, SUBMODULO = "120000", "160000"


def _piezas(raiz, commit=None):
    """Lo que se publicaria bajo `raiz`, sin recorrer dos veces un contenido.

    1. La copia de trabajo (en un repositorio, lo que tiene seguimiento y lo
       que no lo tiene ni esta ignorado).
    2. El indice: lo preparado que no es lo que hay en disco, o cuyo fichero
       ya no esta en disco.
    3. Con `commit`, el arbol de ese commit.

    Un enlace simbolico, un submodulo (o otro repositorio dentro, sin
    seguimiento) y un contenido que git no entrega no se recorren, pero no
    en silencio: son piezas con `recorrida=False`.
    """
    raiz = Path(raiz)
    en_git = _en_git(raiz)
    arbol = _arbol_del_commit(raiz, commit) if commit is not None else {}
    if en_git is None:
        indice = {}
        ficheros, enlaces = _recorrer_carpeta(raiz)
        en_disco = {_relativo(r, raiz) for r in ficheros}
        sin_mirar = {_relativo(r, raiz) for r in enlaces}
    else:
        indice, otros = en_git
        en_disco = set(indice) | {n for n in otros if not n.endswith("/")}
        sin_mirar = {n.rstrip("/") for n in otros if n.endswith("/")}

    especiales = (ENLACE_SIMBOLICO, SUBMODULO)
    del_indice = {nombre: {sha for _modo, sha in entradas}
                  for nombre, entradas in indice.items()}
    pedidos = [sha for entradas in indice.values()
               for modo, sha in entradas if modo not in especiales]
    pedidos += [sha for nombre, (modo, sha) in arbol.items()
                if modo not in especiales
                and sha not in del_indice.get(nombre, ())]
    blobs = _blobs(raiz, pedidos)

    piezas, vistos, nombres_vistos, no_recorridos = [], {}, set(), set()

    def primera(nombre):
        es_la_primera = nombre not in nombres_vistos
        nombres_vistos.add(nombre)
        return es_la_primera

    def poner(nombre, origen, datos):
        # El mismo contenido con otros finales de linea es el mismo contenido
        # (core.autocrlf): no se recorre dos veces.
        firma = hashlib.sha256(datos.replace(b"\r\n", b"\n")).digest()
        suyas = vistos.setdefault(nombre, set())
        if firma in suyas:
            return
        suyas.add(firma)
        piezas.append(_Pieza(nombre, origen, _texto_de(datos),
                             primera(nombre)))

    def no_recorrer(nombre, origen):
        if nombre not in no_recorridos:
            no_recorridos.add(nombre)
            piezas.append(_Pieza(nombre, origen, None, primera(nombre),
                                 recorrida=False))

    for nombre in sorted(en_disco | sin_mirar | set(indice) | set(arbol)):
        ruta = raiz / nombre
        if nombre in sin_mirar or (nombre in en_disco and _es_enlace(ruta)):
            no_recorrer(nombre, COPIA)
        elif nombre in en_disco and ruta.is_file():
            try:
                poner(nombre, COPIA, ruta.read_bytes())
            except OSError:                     # sin permiso, bloqueado...
                no_recorrer(nombre, COPIA)
        for modo, sha in indice.get(nombre, ()):
            if modo in especiales or sha not in blobs:
                no_recorrer(nombre, INDICE)
            else:
                poner(nombre, INDICE, blobs[sha])
        if nombre in arbol:
            modo, sha = arbol[nombre]
            if modo in especiales or (sha not in blobs and
                                      sha not in del_indice.get(nombre, ())):
                no_recorrer(nombre, COMMIT)
            elif sha not in del_indice.get(nombre, ()):
                poner(nombre, COMMIT, blobs[sha])
    return piezas


def _huellas_en(piezas, huellas):
    huellas = set(huellas)
    hallazgos = []

    def mirar(texto, fichero, linea, origen):
        for una in sorted({huella(t) for t in tokens(texto)} & huellas):
            hallazgos.append({"fichero": fichero, "linea": linea,
                              "huella": una, "origen": origen})

    for pieza in piezas:
        fichero = _publicable(pieza.nombre, huellas)
        if pieza.primera:
            mirar(pieza.nombre, fichero, 0, pieza.origen)
        if pieza.texto is None:
            continue
        for n, linea in enumerate(pieza.texto.splitlines(), 1):
            mirar(linea, fichero, n, pieza.origen)
    return hallazgos


def buscar_huellas(raiz, huellas, commit=None):
    """Las apariciones de alguna huella: fichero, linea, huella y origen.

    La linea 0 es el nombre del fichero. El token en claro no sale nunca.
    Con `commit`, tambien el arbol de ese commit.
    """
    return _huellas_en(_piezas(raiz, commit), huellas)


def _publicable(fichero, huellas):
    """El nombre que puede salir en una salida: cada componente de la ruta
    que lleva un token de la lista pasa a `<huella-...>`, el principio de la
    huella de ese token (de todos, si lleva varios)."""
    partes = []
    for parte in fichero.split("/"):
        suyas = sorted({huella(t) for t in tokens(parte)} & set(huellas))
        partes.append("<huella-" + "+".join(h[:12] for h in suyas) + ">"
                      if suyas else parte)
    return "/".join(partes)


# --------------------------------------------------------------------------
# Secretos
# --------------------------------------------------------------------------
PATRONES_DE_SECRETO = {
    # Suelto, o pegado a `bot` como va en la URL de la API de Telegram.
    "token_de_bot_de_telegram": re.compile(
        r"(?:(?<=bot)|(?<![0-9A-Za-z]))\d{8,12}:[A-Za-z0-9_-]{35}"
        r"(?![A-Za-z0-9_-])"),
    "clave_de_api_sk": re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    "clave_de_api_akia": re.compile(
        r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![0-9A-Z])"),
    "clave_de_api_asia": re.compile(
        r"(?<![A-Z0-9])ASIA[0-9A-Z]{16}(?![0-9A-Z])"),
    "clave_de_api_aiza": re.compile(
        r"(?<![A-Za-z0-9_-])AIza[0-9A-Za-z_-]{35}(?![0-9A-Za-z_-])"),
    "clave_de_api_ghp": re.compile(r"(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{36}"),
    "clave_de_api_gho": re.compile(r"(?<![A-Za-z0-9])gho_[A-Za-z0-9]{36}"),
    "clave_de_api_ghs": re.compile(r"(?<![A-Za-z0-9])ghs_[A-Za-z0-9]{36}"),
    "clave_de_api_github_pat": re.compile(
        r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
    "jwt": re.compile(
        r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
    # La cabecera de una clave privada (RSA, OPENSSH, EC, PGP, sin tipo...).
    "clave_privada": re.compile(r"-----BEGIN[A-Z0-9 ]*PRIVATE KEY"),
    # Con un valor literal largo: `${TOKEN}`, `<token>` o `{token}` no.
    "cabecera_authorization": re.compile(
        r"(?i)authorization[\"']?\s*[:=]\s*[\"']?(?:basic|bearer)\s+"
        r"[A-Za-z0-9._~+/=-]{20,}"),
}

# Esquema, dos barras, usuario (puede ir vacio), dos puntos, contrasena,
# arroba y host.
URL_CON_CONTRASENA = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]*:([^\s/@]+)@")

# Los valores de ejemplo que se permiten, en una URL o en una asignacion. Las
# palabras salen del inventario del arbol (28-sep): `prueba` es la del
# PostgreSQL desechable de las pruebas; `clave` y `token`, las de los
# ejemplos de las guias; `cambiar-esto`, el valor de ejemplo del spec.
CONTRASENAS_DE_EJEMPLO = ("prueba", "cambiar-esto", "clave", "token",
                          "...", "%s")
# Una variable es `$NOMBRE` o `${NOMBRE...}` ENTERO, con el nombre en
# mayusculas (`$uper...9` es una contrasena); un marcador `<...>` no lleva
# `:`, `/` ni `@` dentro.
CONTRASENA_MARCADOR = re.compile(
    r"<[^<>:/@]+>|\$[A-Z_][A-Z0-9_]*|\$\{[A-Z_][A-Z0-9_]*[^{}]*\}")

# Una clave que nombra un secreto, `=` o `:`, y su valor: entre comillas,
# `${...}` entero, o suelto hasta el primer blanco, comilla, coma o `;`.
ASIGNACION = re.compile(
    r"(?i)(?<![A-Za-z0-9_])"
    r"[A-Za-z0-9_.-]*(?:password|passwd|secret|token|api[_-]?key)"
    r"[A-Za-z0-9_.-]*[\"']?\s*[:=]\s*"
    r"(?:\"([^\"]*)\"|'([^']*)'|(\$\{[^{}]*\})|([^\s\"',;]+))")
# Lo que parece un secreto en una asignacion: 8 o mas caracteres, con letras
# Y cifras. Deja pasar los nombres de variable, el codigo (`os.environ...`),
# las palabras de ejemplo (`cambiar-esto`, `verifica`) y los ids de ejemplo;
# y tambien, sin remedio, una contrasena hecha solo de letras.
LITERAL_QUE_PARECE_SECRETO = re.compile(
    r"(?=.*[A-Za-z])(?=.*[0-9]).{8,}")

FICHEROS_PROHIBIDOS = (".env*", "*.env", "kaggle.json", "credentials.json",
                       "*.pem", "*.key", "*.p12", "*.pfx", "*.ppk",
                       "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*")
FICHEROS_PERMITIDOS = (".env.ejemplo",)


def _es_de_ejemplo(contrasena):
    return (contrasena.lower() in CONTRASENAS_DE_EJEMPLO
            or CONTRASENA_MARCADOR.fullmatch(contrasena) is not None)


def _asigna_un_secreto(linea):
    for m in ASIGNACION.finditer(linea):
        valor = next(v for v in m.groups() if v is not None)
        if (LITERAL_QUE_PARECE_SECRETO.fullmatch(valor)
                and not _es_de_ejemplo(valor)):
            return True
    return False


def _clases_de_secreto(linea):
    clases = [clase for clase, patron in PATRONES_DE_SECRETO.items()
              if patron.search(linea)]
    if any(not _es_de_ejemplo(m.group(1))
           for m in URL_CON_CONTRASENA.finditer(linea)):
        clases.append("contrasena_en_url")
    if _asigna_un_secreto(linea):
        clases.append("asignacion_de_secreto")
    return clases


def _prohibido(nombre):
    """Si el nombre es el de un fichero que no debe viajar. No distingue
    mayusculas."""
    nombre = nombre.lower()
    return (nombre not in FICHEROS_PERMITIDOS
            and any(fnmatch.fnmatchcase(nombre, p)
                    for p in FICHEROS_PROHIBIDOS))


def _secretos_en(piezas, huellas):
    hallazgos = []
    for pieza in piezas:
        fichero = _publicable(pieza.nombre, huellas)
        if not pieza.recorrida:
            # Enlace simbolico, submodulo o contenido ilegible: lo que no se
            # ha mirado no puede darse por limpio.
            hallazgos.append({"fichero": fichero, "linea": 0,
                              "clase": "no_recorrido",
                              "origen": pieza.origen})
            continue
        if _prohibido(pieza.nombre.rsplit("/", 1)[-1]):
            if pieza.primera:
                hallazgos.append({"fichero": fichero, "linea": 0,
                                  "clase": "fichero_prohibido",
                                  "origen": pieza.origen})
            continue
        if pieza.texto is None:
            continue
        for n, linea in enumerate(pieza.texto.splitlines(), 1):
            for clase in _clases_de_secreto(linea):
                hallazgos.append({"fichero": fichero, "linea": n,
                                  "clase": clase, "origen": pieza.origen})
    return hallazgos


def buscar_secretos(raiz, huellas=None, commit=None):
    """Secretos por patron y ficheros prohibidos: fichero, linea, clase y
    origen.

    La linea 0 es el fichero entero. El secreto no sale nunca. El nombre del
    fichero es el publicable (ver `_publicable`) con `huellas`; sin ellas,
    con las del repositorio donde vive el script. Con `commit`, tambien el
    arbol de ese commit.
    """
    if huellas is None:
        huellas = huellas_de_la_lista(leer_huellas(HUELLAS_POR_DEFECTO))
    return _secretos_en(_piezas(raiz, commit), huellas)


# --------------------------------------------------------------------------
# El commit
# --------------------------------------------------------------------------
CAMPOS_DEL_COMMIT = ("autor", "correo_de_autor", "quien_confirma",
                     "correo_de_quien_confirma", "mensaje")


def verificar_commit(raiz, revision="HEAD", huellas=None):
    """Autor, quien confirma, sus correos y el mensaje, contra las huellas.

    Devuelve `campo`, `linea` (la del mensaje; 0 en los demas) y `huella`.
    Sin `huellas`, las del repositorio donde vive el script.
    """
    if huellas is None:
        huellas = huellas_de_la_lista(leer_huellas(HUELLAS_POR_DEFECTO))
    huellas = set(huellas)
    salida = _git(raiz, "log", "-1",
                  "--format=%an%x00%ae%x00%cn%x00%ce%x00%B", revision, "--")
    if salida is None:
        raise SystemExit(f"No se pudo leer el commit {revision} del árbol "
                         "que se comprueba: ¿es un repositorio de git con "
                         "commits?")
    valores = salida.decode("utf-8", errors="replace").split("\0", 4)
    hallazgos = []
    for campo, valor in zip(CAMPOS_DEL_COMMIT, valores):
        lineas = valor.splitlines() if campo == "mensaje" else [valor]
        for n, linea in enumerate(lineas, 1):
            for una in sorted({huella(t) for t in tokens(linea)} & huellas):
                hallazgos.append({"campo": campo,
                                  "linea": n if campo == "mensaje" else 0,
                                  "huella": una})
    return hallazgos


def commits(raiz):
    """Cuantos commits tiene el repositorio entero: los que alcanza
    cualquier referencia (ramas, etiquetas, stash...), no solo HEAD."""
    salida = _git(raiz, "rev-list", "--count", "--all")
    if salida is None:
        raise SystemExit("No se pudieron contar los commits del árbol que "
                         "se comprueba: ¿es un repositorio de git?")
    return int(salida.decode("ascii").strip())


def _referencias(raiz, prefijo):
    salida = _git(raiz, "for-each-ref", "--format=%(refname)", prefijo)
    if salida is None:
        raise SystemExit("No se pudieron leer las referencias del árbol que "
                         "se comprueba: ¿es un repositorio de git?")
    return [r for r in salida.decode("utf-8", errors="replace").splitlines()
            if r]


def ramas(raiz):
    """Cuantas ramas locales hay."""
    return len(_referencias(raiz, "refs/heads/"))


def etiquetas(raiz):
    """Cuantas etiquetas hay (quien las crea y sus mensajes no se miran:
    en el repositorio que se publica no puede haber ninguna)."""
    return len(_referencias(raiz, "refs/tags/"))


# --------------------------------------------------------------------------
# La linea de ordenes
# --------------------------------------------------------------------------
def _argumentos(argv):
    analizador = argparse.ArgumentParser(
        description="Huellas de la lista negra y secretos en lo que se "
                    "publica (spec de SP5 §6.1).")
    analizador.add_argument("--raiz", type=Path, default=REPO,
                            help="árbol que se comprueba (por defecto, este "
                                 "repositorio)")
    # Como texto: en las salidas, la ruta de las huellas sale como se paso.
    analizador.add_argument("--huellas", default=None,
                            help="fichero de huellas (por defecto, "
                                 f"{HUELLAS_MOSTRADAS})")
    analizador.add_argument("--commit", nargs="?", const="HEAD", default=None,
                            metavar="REV",
                            help="comprueba también autor, correo, quien "
                                 "confirma y mensaje de ese commit (HEAD)")
    analizador.add_argument("--un-solo-commit", action="store_true",
                            help="exige que el repositorio entero tenga un "
                                 "solo commit, una sola rama y ninguna "
                                 "etiqueta")
    analizador.add_argument("--regenerar", action="store_true",
                            help="escribe el fichero de huellas desde la "
                                 f"lista en claro ({VARIABLE_DE_LA_LISTA} o "
                                 "--lista)")
    analizador.add_argument("--lista", type=Path, default=None,
                            help="la lista en claro, fuera del repositorio")
    return analizador.parse_args(argv)


def _las_huellas(args):
    """La ruta del fichero de huellas y como se dice en las salidas: como se
    paso, o relativa al repositorio si es la de por defecto."""
    if args.huellas is None:
        return HUELLAS_POR_DEFECTO, HUELLAS_MOSTRADAS
    return Path(args.huellas), args.huellas


def _regenerar(args):
    lista = args.lista or os.environ.get(VARIABLE_DE_LA_LISTA)
    if not lista:
        raise SystemExit(
            f"Falta la lista en claro: define {VARIABLE_DE_LA_LISTA} o pasa "
            "--lista. Vive fuera del repositorio.")
    destino, mostrado = _las_huellas(args)
    # La ruta de la lista no se imprime nunca: vive fuera del repositorio y
    # lleva el usuario de la maquina.
    try:
        n = regenerar(leer_lista(lista), destino)
    except FileNotFoundError:
        raise SystemExit("No existe la lista en claro que se ha pasado.")
    except OSError:
        raise SystemExit("No se pudo leer la lista en claro que se ha "
                         "pasado, o escribir las huellas.")
    except ValueError as error:
        raise SystemExit(f"No se escribe nada: {error}.")
    print(f"{n} huellas escritas en {mostrado} (con la del centinela).")
    return 0


def _huellas_de_la_cli(ruta, mostrado):
    """Las huellas que se buscan (sin la del centinela), o SystemExit.

    Con solo la del centinela no se comprueba nada: es el `huellas.txt` del
    repositorio que se publica (D9), y la comprobacion de verdad se hace con
    las del repositorio de desarrollo.
    """
    try:
        huellas = huellas_de_la_lista(leer_huellas(ruta))
    except FileNotFoundError:
        raise SystemExit(f"No existe el fichero de huellas {mostrado}.")
    except OSError:
        raise SystemExit(f"No se pudo leer el fichero de huellas {mostrado}.")
    except ValueError as error:
        raise SystemExit(f"El fichero de huellas {mostrado} no vale: "
                         f"{error}.")
    if not huellas:
        raise SystemExit(
            f"{mostrado} lleva solo la huella del centinela: así no se "
            "comprueba nada. Pasa --huellas con las huellas del repositorio "
            "de desarrollo (el que tiene la lista entera).")
    return huellas


def main(argv=None):
    args = _argumentos(argv)
    if args.regenerar:
        return _regenerar(args)

    huellas = _huellas_de_la_cli(*_las_huellas(args))
    piezas = _piezas(args.raiz, args.commit)
    de_huella = _huellas_en(piezas, huellas)
    de_secreto = _secretos_en(piezas, huellas)

    def de_donde(h):
        return "" if h["origen"] == COPIA else f" ({h['origen']})"

    for h in de_huella:
        print(f"{h['fichero']}:{h['linea']}: huella {h['huella'][:12]}"
              + de_donde(h))
    for h in de_secreto:
        print(f"{h['fichero']}:{h['linea']}: {h['clase']}" + de_donde(h))

    del_commit = []
    if args.commit is not None:
        del_commit = verificar_commit(args.raiz, args.commit, huellas=huellas)
        for h in del_commit:
            donde = (f"{h['campo']}:{h['linea']}" if h["linea"]
                     else h["campo"])
            print(f"commit {args.commit}: {donde}: "
                  f"huella {h['huella'][:12]}")

    recorridas = [p for p in piezas if p.texto is not None]
    sin_recorrer = [p for p in piezas if p.recorrida and p.texto is None]
    print("--")
    por_origen = {}
    for p in recorridas:
        por_origen[p.origen] = por_origen.get(p.origen, 0) + 1
    detalle = ", ".join(f"{o}: {por_origen[o]}"
                        for o in (COPIA, INDICE, COMMIT) if o in por_origen)
    print(f"ficheros recorridos: {len(recorridas)}"
          + (f" ({detalle})" if len(por_origen) > 1 else ""))
    print(f"binarios sin recorrer: {len(sin_recorrer)}")
    for p in sin_recorrer:
        print(f"  {_publicable(p.nombre, huellas)}"
              + ("" if p.origen == COPIA else f" ({p.origen})"))
    ficheros = len({h["fichero"] for h in de_huella})
    print(f"huellas: {len(de_huella)} en {ficheros} ficheros")
    por_clase = {}
    for h in de_secreto:
        por_clase[h["clase"]] = por_clase.get(h["clase"], 0) + 1
    detalle = ", ".join(f"{c}: {n}" for c, n in sorted(por_clase.items()))
    print(f"secretos: {len(de_secreto)}" + (f" ({detalle})" if detalle else ""))
    mal = len(de_huella) + len(de_secreto) + len(del_commit)
    if args.commit is not None:
        print(f"commit {args.commit}: {len(del_commit)}")
    if args.un_solo_commit:
        # Un commit, una rama y ninguna etiqueta: lo que sobre, es hallazgo.
        cuantos, cuantas, sueltas = (commits(args.raiz), ramas(args.raiz),
                                     etiquetas(args.raiz))
        print(f"commits: {cuantos}")
        print(f"ramas: {cuantas}")
        print(f"etiquetas: {sueltas}")
        mal += (cuantos != 1) + (cuantas != 1) + (sueltas != 0)
    if not recorridas:
        print("NO publicar: no se recorrió ningún fichero de texto, y lo que "
              "no se ha mirado no está limpio")
        return 1
    print("limpio" if not mal else "NO publicar: hay hallazgos")
    return 1 if mal else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    raise SystemExit(main())
