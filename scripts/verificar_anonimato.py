"""Comprueba que el repositorio se puede publicar (spec de SP5 §6.1).

Uso, desde la raiz del repositorio:

    python scripts/verificar_anonimato.py
    python scripts/verificar_anonimato.py --raiz <arbol> --huellas <huellas> --un-solo-commit
    python scripts/verificar_anonimato.py --regenerar --lista <lista en claro>
    python scripts/verificar_anonimato.py --regenerar --solo-centinela --huellas <destino>

Mira lo que se publicaria: la copia de trabajo (en un repositorio, lo que
tiene seguimiento y lo que no lo tiene ni esta ignorado), lo preparado en el
indice que no es lo que hay en disco y, con --commit (o --un-solo-commit,
que lo implica), el arbol de ese commit, su autor, quien lo confirma, su
mensaje y sus cabeceras, y los nombres de las ramas y de las etiquetas.
Busca:

1. HUELLAS. La lista de cadenas que identifican al cliente, a la empresa, a la
   maquina o a los integrantes NO vive en el repositorio. El repositorio lleva
   solo `tests/anonimato/huellas.txt`: el sha256 de cada token (en el de
   desarrollo, la lista entera; en el que se publica, solo la del centinela,
   D9). Cada fichero de texto se tokeniza igual que la lista (minusculas, sin
   tildes, particion por todo lo que no sea [a-z0-9], tambien desescapado) y
   se compara huella con huella.
2. SECRETOS, por patron: token de bot de Telegram, claves de API, claves
   privadas, cabeceras Authorization, contrasena dentro de una URL,
   asignaciones de contrasenas, tokens y claves, y ficheros que no deben
   viajar (`.env`, claves). Una asignacion se reconoce por el NOMBRE de la
   clave (lleva `password`, `passwd`, `secret`, `token` o `api_key`; o acaba
   en `_KEY` escrito en mayusculas, o en `access_key`, `private_key`,
   `encryption_key`, `signing_key`, `client_key` o `master_key`) y cuenta si
   su valor es un literal con forma de secreto: entre comillas, salvo una
   expresion (`{{`, `${`, `$(`, o `=` delante); suelto, si no lleva
   parentesis, corchetes ni llaves; con subindice o detras de una coma, solo
   entre comillas. Un enlace simbolico o un submodulo es un hallazgo
   `no_recorrido`. Los nombres de las ramas y de las etiquetas se miran
   tambien contra estos patrones.
3. Con --commit, las CABECERAS del commit: la que no sea `tree`, `author` ni
   `committer` es un hallazgo (una firma lleva el identificador de la clave
   de quien firma); `parent`, solo con --un-solo-commit.
4. Con --un-solo-commit (la orden de publicar), las HUELLAS PUBLICADAS: una
   huella de la lista escrita en el arbol que se publica (su `huellas.txt`
   tiene que llevar solo la del centinela: ver --solo-centinela).

Ninguna salida lleva el token ni el secreto en claro: fichero, linea y huella
o clase. En los nombres (de fichero, de rama, de etiqueta, la revision) el
token sale tapado por el principio de su huella, el secreto por
`<secreto>` y una huella de la lista por `<huella-publicada>`; las rutas
salen relativas a la raiz que se recorre (la de las huellas, como se paso).

Sale con 0 si no hay hallazgos y con 1 si los hay, si no se ha recorrido
ningun fichero de texto o si las huellas son solo la del centinela. Con
binarios sin recorrer, la ultima linea no dice «limpio» a secas: se revisan a
mano. Lo usa `tests/test_anonimato.py`, que lo carga por ruta.
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
def _normalizados(texto):
    """El texto con la normalizacion de compatibilidad (NFKD: descompone las
    tildes y el ancho completo) y sin las marcas de combinacion (Mn).

    Los caracteres de formato (Cf: U+200B, U+00AD...) se tratan de las dos
    maneras, y se devuelven los dos textos: BORRADOS (`to<U+200B>ken` da
    `token`) y como SEPARADOR (`alfa<U+200B>token` da `token`).
    """
    if texto.isascii():                 # ni Mn ni Cf: nada que normalizar
        return (texto,)
    borrados, partidos, hay_formato = [], [], False
    for c in unicodedata.normalize("NFKD", texto):
        categoria = unicodedata.category(c)
        if categoria == "Mn":
            continue
        if categoria == "Cf":
            hay_formato = True
            partidos.append(" ")
            continue
        borrados.append(c)
        partidos.append(c)
    if hay_formato:
        return "".join(borrados), "".join(partidos)
    return ("".join(borrados),)


def _partir(texto):
    hallados = set()
    for normal in _normalizados(BASE64.sub(" ", texto)):
        hallados |= set(NO_TOKEN.split(normal.lower()))
    return hallados - {""}


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
    return _escribir_huellas(todas, destino)


def regenerar_solo_centinela(destino):
    """Escribe el `huellas.txt` del repositorio que se publica (D9): la
    cabecera y la huella del centinela, sin lista."""
    return _escribir_huellas({huella(CENTINELA)}, destino)


def _escribir_huellas(todas, destino):
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


def _arbol_del_commit(raiz, revision, huellas=()):
    """{nombre: (modo, sha)} del arbol de `revision`, bajo `raiz`."""
    salida = _git(raiz, "ls-tree", "-r", "-z", revision, "--")
    if salida is None:
        raise SystemExit("No se pudo leer el árbol del commit "
                         f"{_publicable(revision, huellas)}: ¿es un "
                         "repositorio de git con commits?")
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


def _piezas(raiz, commit=None, huellas=()):
    """Lo que se publicaria bajo `raiz`, sin recorrer dos veces un contenido.

    1. La copia de trabajo (en un repositorio, lo que tiene seguimiento y lo
       que no lo tiene ni esta ignorado).
    2. El indice: lo preparado que no es lo que hay en disco, o cuyo fichero
       ya no esta en disco.
    3. Con `commit`, el arbol de ese commit.

    Un enlace simbolico, un submodulo (o otro repositorio dentro, sin
    seguimiento) y un contenido que git no entrega no se recorren, pero no
    en silencio: son piezas con `recorrida=False`. Las `huellas` solo sirven
    para tapar la revision en un mensaje de error.
    """
    raiz = Path(raiz)
    en_git = _en_git(raiz)
    arbol = ({} if commit is None
             else _arbol_del_commit(raiz, commit, huellas))
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
    return _huellas_en(_piezas(raiz, commit, huellas), huellas)


# Un token de 64 hexadecimales: lo que es una huella escrita en un fichero.
TOKEN_HEXADECIMAL = re.compile(r"(?<![A-Za-z0-9])[0-9A-Fa-f]{64}(?![A-Za-z0-9])")


def _huellas_publicadas_en(piezas, huellas):
    """Las huellas de la lista (`huellas`, ya sin la del centinela) escritas
    en lo que se publica: fichero, linea, clase `huella_publicada` y origen.
    La huella no sale nunca.

    Solo para el arbol que se publica (--un-solo-commit): el de desarrollo
    lleva su propio `huellas.txt` con la lista entera. Publicarlo es
    publicar, para quien tenga un diccionario, buena parte de la lista (D9).
    """
    huellas = set(huellas)
    hallazgos = []

    def mirar(texto, fichero, linea, origen):
        for m in TOKEN_HEXADECIMAL.finditer(texto):
            if m.group().lower() in huellas:
                hallazgos.append({"fichero": fichero, "linea": linea,
                                  "clase": "huella_publicada",
                                  "origen": origen})

    for pieza in piezas:
        fichero = _publicable(pieza.nombre, huellas)
        if pieza.primera:
            mirar(pieza.nombre, fichero, 0, pieza.origen)
        if pieza.texto is None:
            continue
        for n, linea in enumerate(pieza.texto.splitlines(), 1):
            mirar(linea, fichero, n, pieza.origen)
    return hallazgos


def _tapar_tokens(parte, huellas):
    """El componente con cada token de la lista cambiado por `<huella-...>`,
    el principio de su huella; lo demas se queda (`informe-<huella-...>.md`),
    para que dos nombres distintos no salgan iguales. Un token que ES una
    huella de la lista pasa a `<huella-publicada>`: no se imprime.

    Recorre el texto original: los caracteres que normalizados dan
    `[a-z0-9]` forman el token; los que no dan nada (marcas, formato) van
    dentro; cualquier otro lo corta.
    """
    salida, tramo, token = [], [], []

    def cerrar():
        if tramo:
            una = huella("".join(token))
            if una in huellas:
                salida.append(f"<huella-{una[:12]}>")
            elif "".join(token) in huellas:
                salida.append("<huella-publicada>")
            else:
                salida.append("".join(tramo))
            tramo.clear()
            token.clear()

    for c in parte:
        normal = _normalizados(c)[0].lower()
        if not normal:
            (tramo if tramo else salida).append(c)
        elif NO_TOKEN.search(normal) is None:
            tramo.append(c)
            token.append(normal)
        else:
            cerrar()
            salida.append(c)
    cerrar()
    return "".join(salida)


def _publicable(fichero, huellas):
    """El nombre que puede salir en una salida: en cada componente de la
    ruta, el token de la lista pasa a `<huella-...>` (ver `_tapar_tokens`) y
    el secreto a `<secreto>`.

    Si aun asi el componente da un token o un secreto (uno que solo se ve
    desescapado, por ejemplo), se tapa el componente entero.
    """
    huellas = set(huellas)
    partes = []
    for parte in fichero.split("/"):
        tapada = _tapar_tokens(_tapar_secretos(parte), huellas)
        quedan = sorted({huella(t) for t in tokens(tapada)} & huellas)
        if quedan:
            tapada = "<huella-" + "+".join(h[:12] for h in quedan) + ">"
        elif _clases_de_secreto(tapada):
            tapada = "<secreto>"
        partes.append(tapada)
    return "/".join(partes)


# --------------------------------------------------------------------------
# Secretos
# --------------------------------------------------------------------------
PATRONES_DE_SECRETO = {
    # Suelto, o pegado a `bot` (o `Bot`, `BOT`) como va en la URL de la API
    # de Telegram; los dos puntos, tal cual o escapados (`%3A`).
    "token_de_bot_de_telegram": re.compile(
        r"(?:(?<=[bB][oO][tT])|(?<![0-9A-Za-z]))\d{8,12}(?::|%3[aA])"
        r"[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"),
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

# Esquema, dos barras, usuario (puede ir vacio), dos puntos, contrasena
# (puede llevar `/`: la de base64 casi siempre la lleva), arroba y host.
URL_CON_CONTRASENA = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]*://(?P<usuario>[^\s/:@]*):"
    r"(?P<contrasena>[^\s@]+)@")
# Lo que en esa forma no es una contrasena sino un puerto y una ruta
# (`https://ejemplo.test:8443/ruta/@ambito`): cifras y `/`, detras de algo
# que parece un host (lleva un punto, o es `localhost`). Detras de un
# usuario, `u:2024/Secreta9x@host` es una contrasena que empieza por cifras.
PUERTO_Y_RUTA = re.compile(r"\d{1,5}/.*")
PARECE_UN_HOST = re.compile(r"(?i)localhost|[^.]+(?:\.[^.]+)+")

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

# Una clave que nombra un secreto, y su valor.
#
# La clave lleva `password`, `passwd`, `secret`, `token` o `api_key` (sin
# distinguir mayusculas), o ACABA en `_KEY` escrito en mayusculas (la
# convencion de las variables de entorno: `KAGGLE_KEY`, `AWS_ACCESS_KEY`)
# o, en minusculas, en uno de unos pocos nombres (`access_key`,
# `private_key`, `encryption_key`, `signing_key`, `client_key`,
# `master_key`). `cache_key`, `primary_key` o `model_key` no nombran un
# secreto.
#
# El valor va detras de `=` o `:`; con subindice
# (`os.environ["X_PASSWORD"] = ...`, grupo `subindice`); o, si la clave va
# entre comillas, detras de una coma (`setenv("X_PASSWORD", ...)`, grupo
# `coma`). Va entre comillas (`doble`, `simple`), es `${...}` entero
# (`llaves`) o va suelto hasta el primer blanco, comilla, coma o `;`
# (`suelto`). Con subindice o detras de una coma, solo cuenta entre
# comillas: suelto es una variable (ver `_secretos_de_la_linea`).
ASIGNACION = re.compile(
    r"(?i)(?<![A-Za-z0-9_])(?P<comilla>[\"'])?"
    r"[A-Za-z0-9_.-]*(?:(?:password|passwd|secret|token|api[_-]?key)"
    r"[A-Za-z0-9_.-]*"
    r"|(?:(?:access|private|encryption|signing|client|master)_key"
    r"|(?-i:_KEY))(?![A-Za-z0-9_.-]))"
    r"(?:[\"']?\s*(?P<subindice>\])?\s*[:=]"
    r"|(?(comilla)(?P=comilla)\s*(?P<coma>,)|(?!)))\s*"
    r"(?:\"(?P<doble>[^\"]*)\"|'(?P<simple>[^']*)'"
    r"|(?P<llaves>\$\{[^{}]*\})|(?P<suelto>[^\s\"',;]+))")
VALOR_DE_LA_ASIGNACION = ("doble", "simple", "llaves", "suelto")
# La linea que no lleva ninguna de estas palabras no puede llevar una
# asignacion de secreto, y no se le aplica ASIGNACION: en una tirada larga de
# letras, cifras, puntos y guiones su coste es cuadratico (A7).
PALABRA_DE_LA_ASIGNACION = re.compile(r"(?i)password|passwd|secret|token|key")
# Lo que parece un secreto en una asignacion: 8 o mas caracteres, con letras
# Y cifras. Deja pasar los nombres de variable, las palabras de ejemplo
# (`cambiar-esto`, `verifica`) y los ids de ejemplo; y tambien, sin remedio,
# una contrasena hecha solo de letras.
LITERAL_QUE_PARECE_SECRETO = re.compile(
    r"(?=.*[A-Za-z])(?=.*[0-9]).{8,}")
# Una expresion no es un literal: una llamada, un subindice, una expresion
# de n8n (`={{ ... }}`). Suelta, la delata cualquier parentesis, corchete o
# llave; entre comillas, solo `{{`, `${`, `$(` o un `=` delante (la de
# n8n): `"S3cr{eta}9x"` es un literal.
EXPRESION = re.compile(r"[()\[\]{}]")
EXPRESION_ENTRE_COMILLAS = re.compile(r"\{\{|\$\{|\$\(|^=")
# `${NOMBRE:-valor}` (o `-`, `:=`, `=`): lo de detras es un literal.
CON_VALOR_POR_DEFECTO = re.compile(
    r"\$\{[A-Za-z_][A-Za-z0-9_]*:?[-=](?P<valor>[^{}]*)\}")

FICHEROS_PROHIBIDOS = (".env*", "*.env", "kaggle.json", "credentials.json",
                       "client_secret*.json", ".pgpass", ".netrc",
                       ".git-credentials",
                       "*.pem", "*.key", "*.p12", "*.pfx", "*.ppk",
                       "id_rsa*", "id_dsa*", "id_ecdsa*", "id_ed25519*")
FICHEROS_PERMITIDOS = (".env.ejemplo",)


def _es_de_ejemplo(contrasena):
    por_defecto = CON_VALOR_POR_DEFECTO.fullmatch(contrasena)
    if por_defecto is not None:
        return _es_de_ejemplo(por_defecto.group("valor"))
    return (contrasena.lower() in CONTRASENAS_DE_EJEMPLO
            or CONTRASENA_MARCADOR.fullmatch(contrasena) is not None)


def _es_un_literal_secreto(valor, entre_comillas=False):
    """El valor de una asignacion es un secreto si es un LITERAL (no una
    variable ni una expresion) que no es de ejemplo y lo parece."""
    por_defecto = CON_VALOR_POR_DEFECTO.fullmatch(valor)
    if por_defecto is not None:
        valor = por_defecto.group("valor")
    expresion = EXPRESION_ENTRE_COMILLAS if entre_comillas else EXPRESION
    return (LITERAL_QUE_PARECE_SECRETO.fullmatch(valor) is not None
            and expresion.search(valor) is None
            and not _es_de_ejemplo(valor))


def _secretos_de_la_linea(linea):
    """(clase, inicio, fin) de cada secreto de la linea; el tramo es el del
    secreto (en una URL o en una asignacion, el del valor)."""
    for clase, patron in PATRONES_DE_SECRETO.items():
        for m in patron.finditer(linea):
            yield clase, m.start(), m.end()
    if "://" in linea:                  # si no, no hay URL: no se busca (A7)
        for m in URL_CON_CONTRASENA.finditer(linea):
            contrasena = m.group("contrasena")
            puerto = (PUERTO_Y_RUTA.fullmatch(contrasena)
                      and PARECE_UN_HOST.fullmatch(m.group("usuario")))
            if not (_es_de_ejemplo(contrasena) or puerto):
                yield ("contrasena_en_url", m.start("contrasena"),
                       m.end("contrasena"))
    if PALABRA_DE_LA_ASIGNACION.search(linea) is None:
        return
    for m in ASIGNACION.finditer(linea):
        grupo = next(g for g in VALOR_DE_LA_ASIGNACION
                     if m.group(g) is not None)
        entre_comillas = grupo in ("doble", "simple")
        if (m.group("subindice") or m.group("coma")) and not entre_comillas:
            continue                    # `os.environ["X"] = variable`
        if _es_un_literal_secreto(m.group(grupo), entre_comillas):
            yield "asignacion_de_secreto", m.start(grupo), m.end(grupo)


def _clases_de_secreto(linea):
    """Las clases de secreto de una linea, sin repetir. Tambien con `\\"`
    convertido en `"`: el texto de un JSON escapado (una celda de un
    notebook, el codigo de un nodo de n8n)."""
    variantes = [linea]
    if '\\"' in linea:
        variantes.append(linea.replace('\\"', '"'))
    clases = []
    for texto in variantes:
        for clase, _inicio, _fin in _secretos_de_la_linea(texto):
            if clase not in clases:
                clases.append(clase)
    return clases


def _tapar_secretos(texto):
    """El texto con cada secreto cambiado por `<secreto>`."""
    tramos = sorted((inicio, fin) for _clase, inicio, fin
                    in _secretos_de_la_linea(texto))
    salida, hasta = [], 0
    for inicio, fin in tramos:
        if inicio >= hasta:
            salida.append(texto[hasta:inicio])
            salida.append("<secreto>")
            hasta = fin
        elif fin > hasta:                       # tramos que se solapan
            hasta = fin
    salida.append(texto[hasta:])
    return "".join(salida)


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
        prohibido = (pieza.recorrida
                     and _prohibido(pieza.nombre.rsplit("/", 1)[-1]))
        # La linea 0 es el fichero entero: lo que no se ha mirado (enlace
        # simbolico, submodulo, ilegible) no puede darse por limpio; y el
        # nombre, que tambien viaja, puede ser el de un fichero prohibido o
        # llevar un secreto.
        clases = [] if pieza.recorrida else ["no_recorrido"]
        if pieza.primera:
            clases += ["fichero_prohibido"] if prohibido else []
            for parte in pieza.nombre.split("/"):
                clases += [c for c in _clases_de_secreto(parte)
                           if c not in clases]
        hallazgos += [{"fichero": fichero, "linea": 0, "clase": clase,
                       "origen": pieza.origen} for clase in clases]
        if not pieza.recorrida or prohibido or pieza.texto is None:
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
    return _secretos_en(_piezas(raiz, commit, huellas), huellas)


# --------------------------------------------------------------------------
# El commit
# --------------------------------------------------------------------------
CAMPOS_DEL_COMMIT = ("autor", "correo_de_autor", "quien_confirma",
                     "correo_de_quien_confirma", "mensaje")


def verificar_commit(raiz, revision="HEAD", huellas=None):
    """Autor, quien confirma, sus correos y el mensaje, contra las huellas y
    contra los patrones de secretos.

    Devuelve `campo`, `linea` (la del mensaje; 0 en los demas) y `huella`
    o `clase` (la del secreto). Sin `huellas`, las del repositorio donde
    vive el script.
    """
    if huellas is None:
        huellas = huellas_de_la_lista(leer_huellas(HUELLAS_POR_DEFECTO))
    huellas = set(huellas)
    salida = _git(raiz, "log", "-1",
                  "--format=%an%x00%ae%x00%cn%x00%ce%x00%B", revision, "--")
    if salida is None:
        raise SystemExit("No se pudo leer el commit "
                         f"{_publicable(revision, huellas)} del árbol que se "
                         "comprueba: ¿es un repositorio de git con commits?")
    valores = salida.decode("utf-8", errors="replace").split("\0", 4)
    hallazgos = []
    for campo, valor in zip(CAMPOS_DEL_COMMIT, valores):
        lineas = valor.splitlines() if campo == "mensaje" else [valor]
        for n, linea in enumerate(lineas, 1):
            donde = n if campo == "mensaje" else 0
            for una in sorted({huella(t) for t in tokens(linea)} & huellas):
                hallazgos.append({"campo": campo, "linea": donde,
                                  "huella": una})
            for clase in _clases_de_secreto(linea):
                hallazgos.append({"campo": campo, "linea": donde,
                                  "clase": clase})
    return hallazgos


# Las cabeceras que lleva un commit sin firma: su arbol, su autor y quien lo
# confirma (y `parent`, si no es el unico).
CABECERAS_DEL_COMMIT = ("tree", "author", "committer")


def cabeceras_del_commit(raiz, revision="HEAD", huellas=None,
                         un_solo_commit=False):
    """Las cabeceras del commit en crudo (`git cat-file commit`) que no son
    las de CABECERAS_DEL_COMMIT: `campo` (el NOMBRE de la cabecera, nunca su
    valor), `linea` 0 y clase `cabecera_del_commit`.

    Una firma (`gpgsig`) lleva el identificador de la clave de quien firma.
    `parent` solo es hallazgo con `un_solo_commit`: un commit con padre no es
    el unico. Sin `huellas`, las del repositorio donde vive el script (solo
    tapan la revision y los nombres).
    """
    if huellas is None:
        huellas = huellas_de_la_lista(leer_huellas(HUELLAS_POR_DEFECTO))
    huellas = set(huellas)
    crudo = _git(raiz, "cat-file", "commit", revision)
    if crudo is None:
        raise SystemExit("No se pudo leer el commit "
                         f"{_publicable(revision, huellas)} del árbol que se "
                         "comprueba: ¿es un repositorio de git con commits?")
    permitidas = CABECERAS_DEL_COMMIT + (() if un_solo_commit else ("parent",))
    hallazgos = []
    for linea in crudo.split(b"\n\n", 1)[0].split(b"\n"):
        if not linea or linea.startswith(b" "):     # la continuacion de otra
            continue
        nombre = linea.split(b" ", 1)[0].decode("utf-8", errors="replace")
        if nombre not in permitidas:
            hallazgos.append({"campo": _publicable(nombre, huellas),
                              "linea": 0, "clase": "cabecera_del_commit"})
    return hallazgos


def _nombres_de_referencias(raiz):
    """[(referencia, nombre)]: las ramas (con la de HEAD, aunque aun no
    tenga commits) y las etiquetas. Sus nombres se publican con el push."""
    nombres = [("rama", r[len("refs/heads/"):])
               for r in _referencias(raiz, "refs/heads/")]
    cabeza = _git(raiz, "symbolic-ref", "-q", "HEAD")
    if cabeza is not None:
        rama = cabeza.decode("utf-8", errors="replace").strip()
        if rama.startswith("refs/heads/"):
            rama = ("rama", rama[len("refs/heads/"):])
            if rama not in nombres:
                nombres.append(rama)
    nombres += [("etiqueta", r[len("refs/tags/"):])
                for r in _referencias(raiz, "refs/tags/")]
    return nombres


def verificar_referencias(raiz, huellas):
    """Los nombres de las ramas y de las etiquetas, contra las huellas y
    contra los patrones de secretos (cada componente, como el nombre de un
    fichero).

    Devuelve `referencia` (`rama` o `etiqueta`), `nombre` (el publicable,
    con el token y el secreto tapados) y `huella` o `clase`.
    """
    huellas = set(huellas)
    hallazgos = []
    for referencia, nombre in _nombres_de_referencias(raiz):
        publicable = _publicable(nombre, huellas)
        for una in sorted({huella(t) for t in tokens(nombre)} & huellas):
            hallazgos.append({"referencia": referencia,
                              "nombre": publicable, "huella": una})
        clases = []
        for parte in nombre.split("/"):
            clases += [c for c in _clases_de_secreto(parte)
                       if c not in clases]
        hallazgos += [{"referencia": referencia, "nombre": publicable,
                       "clase": clase} for clase in clases]
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
                            help="comprueba también el árbol, el autor, "
                                 "quien confirma, el mensaje y las cabeceras "
                                 "de ese commit (HEAD), y los nombres de "
                                 "ramas y etiquetas")
    analizador.add_argument("--un-solo-commit", action="store_true",
                            help="exige que el repositorio entero tenga un "
                                 "solo commit, una sola rama y ninguna "
                                 "etiqueta, y que el árbol no lleve ninguna "
                                 "huella de la lista; implica --commit HEAD")
    analizador.add_argument("--regenerar", action="store_true",
                            help="escribe el fichero de huellas desde la "
                                 f"lista en claro ({VARIABLE_DE_LA_LISTA} o "
                                 "--lista)")
    analizador.add_argument("--lista", type=Path, default=None,
                            help="la lista en claro, fuera del repositorio")
    analizador.add_argument("--solo-centinela", action="store_true",
                            help="con --regenerar, escribe en --huellas el "
                                 "huellas.txt del repositorio que se publica: "
                                 "la cabecera y la huella del centinela, sin "
                                 "lista")
    return analizador.parse_args(argv)


def _las_huellas(args):
    """La ruta del fichero de huellas y como se dice en las salidas: como se
    paso, o relativa al repositorio si es la de por defecto."""
    if args.huellas is None:
        return HUELLAS_POR_DEFECTO, HUELLAS_MOSTRADAS
    return Path(args.huellas), args.huellas


def _solo_centinela(args):
    """El `huellas.txt` del repositorio que se publica (D9). No lee ni
    --lista ni ANONIMATO_LISTA. Exige --huellas: la de por defecto es la de
    este repositorio, que en el de desarrollo lleva la lista entera."""
    if args.lista is not None:
        raise SystemExit("--solo-centinela no lleva lista: escribe solo la "
                         "huella del centinela. Quita --lista.")
    if args.huellas is None:
        raise SystemExit(
            "Con --solo-centinela, di dónde se escribe con --huellas (el "
            "huellas.txt del árbol que se publica): el de este repositorio, "
            "en el de desarrollo, lleva la lista entera.")
    destino, mostrado = _las_huellas(args)
    try:
        regenerar_solo_centinela(destino)
    except OSError:
        raise SystemExit(f"No se pudieron escribir las huellas en {mostrado}.")
    print(f"1 huella escrita en {mostrado} (solo la del centinela).")
    return 0


def _regenerar(args):
    if args.solo_centinela:
        return _solo_centinela(args)
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
    if args.solo_centinela:
        raise SystemExit("--solo-centinela va con --regenerar: escribe el "
                         "huellas.txt del repositorio que se publica.")

    huellas = _huellas_de_la_cli(*_las_huellas(args))
    if args.un_solo_commit and args.commit is None:
        args.commit = "HEAD"            # lo que se publica es ese commit
    revision = (None if args.commit is None
                else _publicable(args.commit, huellas))
    piezas = _piezas(args.raiz, args.commit, huellas)
    de_huella = _huellas_en(piezas, huellas)
    de_secreto = _secretos_en(piezas, huellas)
    # En el arbol que se publica, ninguna huella de la lista (D9).
    publicadas = (_huellas_publicadas_en(piezas, huellas)
                  if args.un_solo_commit else [])

    def de_donde(h):
        return "" if h["origen"] == COPIA else f" ({h['origen']})"

    def que(h):
        return (f"huella {h['huella'][:12]}" if "huella" in h
                else h["clase"])

    for h in de_huella + de_secreto + publicadas:
        print(f"{h['fichero']}:{h['linea']}: {que(h)}" + de_donde(h))

    del_commit, de_referencia = [], []
    if args.commit is not None:
        del_commit = (verificar_commit(args.raiz, args.commit, huellas=huellas)
                      + cabeceras_del_commit(
                          args.raiz, args.commit, huellas,
                          un_solo_commit=args.un_solo_commit))
        for h in del_commit:
            donde = (f"{h['campo']}:{h['linea']}" if h["linea"]
                     else h["campo"])
            print(f"commit {revision}: {donde}: {que(h)}")
        # El nombre de las ramas y de las etiquetas se publica con el push.
        de_referencia = verificar_referencias(args.raiz, huellas)
        for h in de_referencia:
            print(f"{h['referencia']} {h['nombre']}: {que(h)}")

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
    if args.un_solo_commit:
        print(f"huellas publicadas: {len(publicadas)}")
    mal = (len(de_huella) + len(de_secreto) + len(publicadas)
           + len(del_commit) + len(de_referencia))
    if args.commit is not None:
        print(f"commit {revision}: {len(del_commit)}")
        print(f"nombres de ramas y etiquetas: {len(de_referencia)}")
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
    if mal:
        print("NO publicar: hay hallazgos")
        return 1
    if sin_recorrer:
        # Lo que no se ha recorrido no se da por limpio: se revisa a mano.
        n = len(sin_recorrer)
        print(f"limpio lo recorrido; {n} "
              + ("binario sin recorrer, que se revisa" if n == 1
                 else "binarios sin recorrer, que se revisan")
              + " a mano")
    else:
        print("limpio")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    raise SystemExit(main())
