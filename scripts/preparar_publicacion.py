"""Prepara el repositorio que se publica: un clon NUEVO de la rama `main` del
repositorio de desarrollo, con su historia real, limpia (SP5-C3, P7).

Uso, desde la raiz del repositorio de desarrollo:

    python scripts/preparar_publicacion.py --origen . --destino <carpeta nueva>
        --lista <lista en claro> --identidad "Nombre <correo noreply>"

La lista tambien puede ir en la variable de entorno ANONIMATO_LISTA, sin
--lista. Sale con 0 solo si TODO esta limpio. El procedimiento entero (crear el
repositorio privado, subirlo, el release con los pesos), en docs/desarrollo.md,
seccion «Publicar».

Que hace, sobre un clon que hace el mismo en --destino (una carpeta que no
existe o esta vacia, fuera de cualquier repositorio). El repositorio de origen
solo se lee:

1. Quita de TODOS los commits las rutas de RUTAS_QUE_NO_SE_PUBLICAN: las dos
   tablas con una fila por paciente y la huella de la segunda (decision del
   5-oct-2026, data/README.md).
2. Pone en TODOS los commits, en lugar de tests/anonimato/huellas.txt, el del
   repositorio que se publica: solo la huella del centinela, con su cabecera
   (lo escribe `regenerar_solo_centinela` de verificar_anonimato.py, lo mismo
   que `--regenerar --solo-centinela`).
3. Reescribe el autor y quien confirma de TODOS los commits con la unica
   identidad que da el operador (--identidad).
4. Sustituye, en el texto de todos los ficheros y en todos los mensajes, cada
   token de la lista de anonimato EN CLARO por «[retirado]» (en los nombres de
   las rutas, por «retirado»), tal como lo ve el verificador: sin mayusculas
   ni tildes, y tambien detras de un escape (`\\n`, `\\uXXXX`, `%XX`, `&#NN;`).
   Hace lo mismo con las huellas de la lista y con sus prefijos (de 8 a 64
   cifras hexadecimales): la salida del verificador, que ensena el principio
   de cada huella, se pego en algun documento de la historia. Los nombres que
   declara el README (excepcion D5) se conservan solo en el texto de
   README.md, LICENSE y docs/planificacion.md, y solo en los commits cuyo
   README los declara: es exactamente lo que el verificador admite en cada
   commit. Lo binario no se toca (el verificador no lo lee: se revisa a mano).
5. Etiqueta el merge de cada subproyecto (v0.1-sp1 ... v0.5-sp5c2, ver
   `etiquetas_de_los_subproyectos`) y la punta (v1.0), y deja una sola rama,
   `main`, sin remoto.
6. Comprueba CADA commit de la historia con el verificador
   (`verificar_anonimato.py --commit <rev> --huellas <huellas.txt completo
   del repositorio de desarrollo>`, sobre un repositorio auxiliar vacio que ve
   los objetos del destino: solo cuenta el commit) y, ademas, la copia de
   trabajo del destino con los nombres de la rama y de las etiquetas, que
   ningun commit lleve las rutas quitadas ni otro huellas.txt, que haya una
   sola identidad, que ningun fichero ni mensaje de la historia lleve una
   huella o un prefijo de huella, que no quede remoto ni otras referencias, y
   que los objetos de la historia vieja ya no esten en la carpeta. Sale con 0
   solo si todo esta limpio.

La lista NO se escribe nunca en disco ni se imprime: el guion la lee y la
tiene en memoria, y las sustituciones son funciones de Python que filter-repo
llama (no un fichero de --replace-text). Con --por-huellas, en lugar de
--lista, no hace falta la lista: se sustituyen los tokens de la historia cuya
huella esta en el huellas.txt completo, que son los mismos si las huellas se
regeneraron con la lista de hoy (con --lista, el guion comprueba ademas que
casan, y se niega si no). Ninguna salida lleva tokens de la
lista, huellas ni prefijos de huella: solo recuentos, rutas del repositorio,
nombres de etiquetas y hashes de commit. Las salidas de filter-repo y del
verificador se recogen y no se imprimen; con --detalle, las del verificador
salen sin huellas ni prefijos.

Requiere git-filter-repo 2.47.0, que se usa como biblioteca
(`pip install git-filter-repo==2.47.0`): con otra version, el guion se niega.
Usa funciones de scripts/verificar_anonimato.py (la tokenizacion, la lectura
de la lista y de las huellas, la declaracion de los nombres) para ver el texto
exactamente como lo ve el verificador.
"""
import argparse
import codecs
import contextlib
import functools
import html
import importlib.metadata
import importlib.util
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NamedTuple

REPO = Path(__file__).resolve().parents[1]
VERIFICADOR = Path(__file__).resolve().parent / "verificar_anonimato.py"

VERSION_DE_FILTER_REPO = "2.47.0"

# Lo que no se publica, de ningun commit (data/README.md, «Que NO esta en el
# repositorio»): las dos tablas con una fila por paciente y la huella de la
# segunda. Si el inventario anade algo, va aqui.
RUTAS_QUE_NO_SE_PUBLICAN = (
    "docs/eda/metadatos_eda.csv",
    "docs/validacion-semisintetica/crudas_prueba.csv",
    "docs/validacion-semisintetica/crudas_prueba.sha256",
)
HUELLAS_DEL_REPOSITORIO = "tests/anonimato/huellas.txt"
RAMA_PUBLICADA = "main"

MARCA = "[retirado]"            # en el texto y en los mensajes
MARCA_EN_RUTAS = "retirado"     # en los nombres de las rutas

# Las etiquetas de version: el merge de cada subproyecto en la historia de
# primer padre de main. Casi todos se llaman «Merge: SPn...» (o «merge:»); el
# de SP2 no, y se busca por su mensaje. SP5-C3 en adelante, si su merge esta,
# se etiqueta igual (v0.5-sp5c3). La punta lleva ademas v1.0.
MERGE_DE_SUBPROYECTO = re.compile(r"(?i)^merge: (sp(\d+)(?:-([a-z]\d*))?)\b")
MERGE_DE_SP2 = re.compile(r"(?i)^feat\(sp2\): servidor mcp\b")
SUBPROYECTOS_OBLIGATORIOS = ("sp1", "sp2", "sp3", "sp4", "sp5-a", "sp5-b1",
                             "sp5-b2", "sp5-b3", "sp5-b4", "sp5-c1", "sp5-c2")
ETIQUETA_DE_LA_PUNTA = "v1.0"

# Un token de 8 a 64 cifras hexadecimales: una huella o su principio.
HEXADECIMAL = re.compile(r"(?<![0-9A-Fa-f])[0-9A-Fa-f]{8,64}(?![0-9A-Fa-f])")
LONGITUD_MINIMA_DEL_PREFIJO = 8

IDENTIDAD = re.compile(
    r"^\s*(?P<nombre>[^<>]*[^<>\s])\s*<(?P<correo>[^<>\s@]+@[^<>\s@]+)>\s*$")
CORREO_NOREPLY = "users.noreply.github.com"


def _cargar_verificador():
    especificacion = importlib.util.spec_from_file_location(
        "verificar_anonimato", VERIFICADOR)
    modulo = importlib.util.module_from_spec(especificacion)
    especificacion.loader.exec_module(modulo)
    return modulo


v = _cargar_verificador()


class NoSePuedeLimpiar(Exception):
    """Un texto que, limpio, el verificador seguiria viendo sucio."""


# --------------------------------------------------------------------------
# La limpieza de un texto (paso 4)
# --------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def _normal(c):
    """Lo que el verificador ve de un caracter: su forma NFKD sin marcas de
    combinacion, en minusculas ('' si no deja nada: una tilde suelta, un
    caracter de formato)."""
    return v._normalizados(c)[0].lower()


def _es_formato(c):
    return unicodedata.category(c) == "Cf"


ENTIDAD_HTML = re.compile(               # la que reconoce html.unescape
    r"&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\t\n\f <&#;]{1,32};?)")
PORCENTAJES = re.compile(r"(?:%[0-9A-Fa-f]{2})+")
ESCAPE_UNICODE = re.compile(r"\\u([0-9A-Fa-f]{4})")


def _unidades_crudas(linea):
    """(inicio, fin, caracter) de cada caracter de la linea."""
    return [(i, i + 1, c) for i, c in enumerate(linea)]


def _unidades_desescapadas(linea):
    """(inicio, fin, caracter) de la linea desescapada como la desescapa el
    verificador: `\\n`, `\\t` y `\\r` son un espacio; `\\uXXXX`, `%XX` (en
    tiradas, como UTF-8) y las entidades HTML, su caracter. Cada caracter
    lleva el tramo del escape del que sale."""
    unidades, i, n = [], 0, len(linea)
    while i < n:
        c = linea[i]
        if c == "\\" and i + 1 < n and linea[i + 1] in "ntr":
            unidades.append((i, i + 2, " "))
            i += 2
            continue
        if c == "\\":
            m = ESCAPE_UNICODE.match(linea, i)
            if m:
                unidades.append((i, m.end(), chr(int(m.group(1), 16))))
                i = m.end()
                continue
        if c == "%":
            m = PORCENTAJES.match(linea, i)
            if m:
                texto = urllib.parse.unquote(m.group(), errors="replace")
                unidades += [(i, m.end(), x) for x in texto]
                i = m.end()
                continue
        if c == "&":
            m = ENTIDAD_HTML.match(linea, i)
            if m:
                texto = html.unescape(m.group())
                if texto != m.group():
                    unidades += [(i, m.end(), x) for x in texto]
                    i = m.end()
                    continue
        unidades.append((i, i + 1, c))
        i += 1
    return unidades


def _tramos_de_tokens(unidades, prohibidos):
    """Los tramos (inicio, fin) de la linea original que forman un token de
    `prohibidos`, con la regla del verificador: un token es una tirada de
    caracteres que normalizados dan [a-z0-9]; los que no dan nada van dentro;
    los caracteres de formato se miran tambien como separador; una tirada de
    base64 de 120 o mas caracteres no se mira (el verificador la quita)."""
    texto = "".join(u[2] for u in unidades)
    en_base64 = set()
    for m in v.BASE64.finditer(texto):
        en_base64.update(range(m.start(), m.end()))
    # Indice de caracter del texto unido -> indice de unidad (una unidad es un
    # caracter: coinciden).
    tramos, corrida = [], []

    def anadir(trozo):
        tramos.append((trozo[0][0], trozo[-1][1]))

    def cerrar():
        if not corrida:
            return
        if "".join(u[2] for u in corrida) in prohibidos:
            anadir(corrida)
        elif any(u[3] for u in corrida):
            parte = []
            for u in corrida + [(None, None, "", True)]:
                if u[3]:
                    if parte and "".join(p[2] for p in parte) in prohibidos:
                        anadir(parte)
                    parte = []
                elif u[2]:
                    parte.append(u)
        corrida.clear()

    for k, (inicio, fin, c) in enumerate(unidades):
        if k in en_base64:
            cerrar()
            continue
        normal = _normal(c)
        if not normal:
            if corrida:
                corrida.append((inicio, fin, "", _es_formato(c)))
        elif v.NO_TOKEN.search(normal) is None:
            corrida.append((inicio, fin, normal, False))
        else:
            cerrar()
    cerrar()
    return tramos


def _tramos_hexadecimales(linea, prefijos):
    return [(m.start(), m.end()) for m in HEXADECIMAL.finditer(linea)
            if m.group().lower() in prefijos]


def _hay_algo(texto, prohibidos, prefijos):
    """Si el verificador veria en `texto` un token de `prohibidos`, o si
    lleva una huella o un prefijo de huella."""
    if prohibidos and v.tokens(texto) & prohibidos:
        return True
    return any(m.group().lower() in prefijos
               for m in HEXADECIMAL.finditer(texto))


def _aplicar(texto, tramos, marca):
    """El texto con cada tramo (unidos los que se solapan) cambiado por la
    marca."""
    salida, hasta = [], 0
    for inicio, fin in sorted(tramos):
        if inicio >= hasta:
            salida.append(texto[hasta:inicio])
            salida.append(marca)
            hasta = fin
        elif fin > hasta:
            hasta = fin
    salida.append(texto[hasta:])
    return "".join(salida)


FIN_DE_LINEA = re.compile(r"(?:\r\n|[\n\r\v\f\x1c\x1d\x1e\x85  ])$")


def _sin_fin(linea):
    m = FIN_DE_LINEA.search(linea)
    return (linea, "") if m is None else (linea[:m.start()], m.group())


class Limpieza(NamedTuple):
    texto: str
    cambiado: bool
    lineas_enteras: int     # lineas que se retiraron enteras (ultimo recurso)


def limpiar_texto(texto, prohibidos, prefijos, marca=MARCA, vista=None):
    """El texto sin los tokens de `prohibidos` ni las huellas o prefijos de
    `prefijos`, linea a linea (como mira el verificador).

    `vista` es el texto tal como lo lee el verificador, si no es el mismo (el
    de un fichero que no es UTF-8 del todo): se busca en la vista y se
    sustituye en `texto`, que tiene los caracteres en las mismas posiciones.
    Si una linea, sustituidos sus tokens, aun da uno (un escape encadenado,
    por ejemplo), se retira entera.
    """
    vista = texto if vista is None else vista
    if not _hay_algo(vista, prohibidos, prefijos):
        return Limpieza(texto, False, 0)
    lineas_t = texto.splitlines(keepends=True)
    lineas_v = vista.splitlines(keepends=True)
    if len(lineas_t) != len(lineas_v):
        raise NoSePuedeLimpiar("la vista del verificador no casa con el texto")
    salida, enteras = [], 0
    for lt, lv in zip(lineas_t, lineas_v):
        cuerpo_v, fin = _sin_fin(lv)
        cuerpo_t = lt[:len(cuerpo_v)]
        if not _hay_algo(cuerpo_v, prohibidos, prefijos):
            salida.append(lt)
            continue
        tramos = _tramos_de_tokens(_unidades_crudas(cuerpo_v), prohibidos)
        if v.HAY_ESCAPE.search(cuerpo_v):
            tramos += _tramos_de_tokens(_unidades_desescapadas(cuerpo_v),
                                        prohibidos)
        tramos += _tramos_hexadecimales(cuerpo_v, prefijos)
        nuevo_v = _aplicar(cuerpo_v, tramos, marca)
        nuevo_t = _aplicar(cuerpo_t, tramos, marca)
        if _hay_algo(nuevo_v, prohibidos, prefijos):
            nuevo_t, enteras = marca, enteras + 1
        salida.append(nuevo_t + lt[len(cuerpo_v):])
    return Limpieza("".join(salida), True, enteras)


# Las marcas de orden de bytes, en el orden en que las mira el verificador
# (la de UTF-32 LE antes que la de UTF-16 LE, que es su principio).
MARCAS_DE_ORDEN = ((codecs.BOM_UTF32_LE, "utf-32-le"),
                   (codecs.BOM_UTF32_BE, "utf-32-be"),
                   (codecs.BOM_UTF8, "utf-8"),
                   (codecs.BOM_UTF16_LE, "utf-16-le"),
                   (codecs.BOM_UTF16_BE, "utf-16-be"))
SUSTITUTO_DE_BYTE = re.compile("[\udc80-\udcff]")


def _decodificado(datos):
    """(texto, vista, codificar): el texto de los bytes de forma reversible
    (lo que no es UTF-8 queda como sustitutos), la vista del verificador
    (esos bytes como cp1252, o U+FFFD tras una marca de orden) y la funcion
    que vuelve a dar los bytes. None si no se puede."""
    for marca, codificacion in MARCAS_DE_ORDEN:
        if datos.startswith(marca):
            errores = ("surrogateescape" if codificacion == "utf-8"
                       else "surrogatepass")
            try:
                texto = datos[len(marca):].decode(codificacion, errors=errores)
            except UnicodeDecodeError:
                return None
            vista = SUSTITUTO_DE_BYTE.sub("�", texto)
            return (texto, vista,
                    lambda t: marca + t.encode(codificacion, errors=errores))
    texto = datos.decode("utf-8", errors="surrogateescape")
    vista = SUSTITUTO_DE_BYTE.sub(
        lambda m: bytes([ord(m.group()) - 0xDC00]).decode("cp1252",
                                                          errors="replace"),
        texto)
    return texto, vista, lambda t: t.encode("utf-8", errors="surrogateescape")


def limpiar_bytes(datos, prohibidos, prefijos, marca=MARCA):
    """(bytes, lineas_enteras) del contenido de un fichero limpio; los mismos
    bytes si no hay nada que quitar o si es binario (el verificador no lo lee:
    se revisa a mano). NoSePuedeLimpiar si, limpio, el verificador seguiria
    viendo algo."""
    vista = v._texto_de(datos)
    if vista is None or not _hay_algo(vista, prohibidos, prefijos):
        return datos, 0
    decodificado = _decodificado(datos)
    if decodificado is None:
        raise NoSePuedeLimpiar("un texto que no se deja decodificar")
    texto, vista_propia, codificar = decodificado
    limpio = limpiar_texto(texto, prohibidos, prefijos, marca, vista_propia)
    nuevos = codificar(limpio.texto)
    comprobacion = v._texto_de(nuevos)
    if comprobacion is None or any(
            _hay_algo(linea, prohibidos, prefijos)
            for linea in comprobacion.splitlines()):
        raise NoSePuedeLimpiar("el texto limpio sigue dando un token")
    return nuevos, limpio.lineas_enteras


def limpiar_ruta(ruta, prohibidos, prefijos):
    """La ruta (texto, con `/`) con cada componente limpio («retirado»); si
    un componente aun da un token, el componente entero."""
    partes = []
    for parte in ruta.split("/"):
        if _hay_algo(parte, prohibidos, prefijos):
            parte = limpiar_texto(parte, prohibidos, prefijos,
                                  MARCA_EN_RUTAS).texto
            if _hay_algo(parte, prohibidos, prefijos):
                parte = MARCA_EN_RUTAS
        partes.append(parte)
    return "/".join(partes)


def prefijos_de(huellas):
    """Todas las formas en que se puede escribir el principio de una huella
    de la lista: sus prefijos de 8 a 64 cifras, en minusculas."""
    return frozenset(h[:n] for h in huellas
                     for n in range(LONGITUD_MINIMA_DEL_PREFIJO, len(h) + 1))


# --------------------------------------------------------------------------
# Git
# --------------------------------------------------------------------------
NO_HEREDADAS = v.NO_HEREDADAS


def _entorno():
    entorno = {c: x for c, x in os.environ.items() if c not in NO_HEREDADAS}
    entorno["LC_ALL"] = "C"
    entorno["GIT_TERMINAL_PROMPT"] = "0"
    return entorno


def _git(repo, *argumentos, entrada=None, comprobar=True):
    """La salida de git (bytes). Con `comprobar`, SystemExit si falla, con la
    orden (sin sus argumentos: podrian llevar una ruta) y no su salida."""
    hecho = subprocess.run(["git", "-C", str(repo), *argumentos],
                           input=entrada, capture_output=True, env=_entorno())
    if comprobar and hecho.returncode != 0:
        raise SystemExit(f"Falló «git {argumentos[0]}» (código "
                         f"{hecho.returncode}).")
    return hecho.stdout if hecho.returncode == 0 else None


def _texto_git(repo, *argumentos):
    return _git(repo, *argumentos).decode("utf-8", errors="replace")


def _borrar(carpeta):
    """Borra una carpeta temporal, tambien los ficheros de solo lectura que
    deja git en Windows."""
    def de_nuevo(funcion, ruta, *_error):
        try:
            os.chmod(ruta, 0o700)
            funcion(ruta)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(carpeta, onexc=de_nuevo)
    else:                                               # pragma: no cover
        shutil.rmtree(carpeta, onerror=de_nuevo)


class LectorDeObjetos:
    """Un `git cat-file --batch` abierto: el contenido de un objeto por su
    nombre, sin un proceso por objeto."""

    def __init__(self, repo):
        self._proceso = subprocess.Popen(
            ["git", "-C", str(repo), "cat-file", "--batch"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, env=_entorno())

    def leer(self, nombre):
        nombre = nombre if isinstance(nombre, bytes) else nombre.encode()
        self._proceso.stdin.write(nombre + b"\n")
        self._proceso.stdin.flush()
        cabecera = self._proceso.stdout.readline().split()
        if len(cabecera) != 3:
            return None                 # «<nombre> missing»
        tamano = int(cabecera[2])
        datos = self._proceso.stdout.read(tamano)
        self._proceso.stdout.read(1)
        return datos

    def cerrar(self):
        if self._proceso.poll() is None:
            self._proceso.stdin.close()
            self._proceso.wait()


def _mismo_o_dentro(ruta, carpeta):
    """Si `ruta` es `carpeta` o esta dentro (sin distinguir mayusculas donde
    el sistema no las distingue)."""
    ruta = os.path.normcase(os.path.realpath(ruta))
    carpeta = os.path.normcase(os.path.realpath(carpeta))
    return ruta == carpeta or ruta.startswith(carpeta.rstrip(os.sep) + os.sep)


def _raiz_de_repositorio(ruta):
    """La raiz del arbol de trabajo de git que contiene `ruta` (o su primer
    antecesor que exista), o None."""
    ruta = Path(os.path.realpath(ruta))
    while not ruta.exists():
        ruta = ruta.parent
    hecho = subprocess.run(["git", "-C", str(ruta), "rev-parse",
                            "--show-toplevel"], capture_output=True,
                           env=_entorno())
    if hecho.returncode != 0:
        return None
    return Path(hecho.stdout.decode("utf-8").strip())


# --------------------------------------------------------------------------
# Lo que se comprueba antes de empezar
# --------------------------------------------------------------------------
class Preparacion(NamedTuple):
    lista: frozenset        # los tokens de la lista, en claro
    huellas: frozenset      # las de la lista completa (sin la del centinela)
    prefijos: frozenset     # sus prefijos de 8 a 64 cifras
    nombre: str
    correo: str
    ensayo: bool


def leer_lista(ruta):
    """Los tokens de la seccion [huellas] de la lista. Cada entrada tiene que
    dar un token (como exige --regenerar); si no, SystemExit con los NUMEROS
    de entrada, nunca su contenido."""
    try:
        entradas = v.leer_lista(ruta)
    except OSError:
        raise SystemExit("No se pudo leer la lista en claro que se ha pasado.")
    if not entradas:
        raise SystemExit("La sección [huellas] de la lista no tiene entradas.")
    tokens, malas = set(), []
    for n, entrada in enumerate(entradas, 1):
        suyos = v.tokens(entrada)
        if len(suyos) == 1:
            tokens |= suyos
        else:
            malas.append(n)
    if malas:
        raise SystemExit(
            f"{len(malas)} entradas de la lista no dan exactamente un token "
            f"(números de entrada: {', '.join(map(str, malas))}).")
    return frozenset(tokens)


def leer_identidad(texto):
    m = IDENTIDAD.fullmatch(texto or "")
    if m is None:
        raise SystemExit('--identidad tiene que ser "Nombre <correo>".')
    return m.group("nombre"), m.group("correo")


def comprobar_destino_nuevo(destino, origen):
    """El destino tiene que ser una carpeta que no existe o esta vacia, fuera
    del repositorio de origen, del de este guion y de cualquier otro."""
    destino = Path(destino)
    for repo, cual in ((origen, "el repositorio de origen"),
                       (REPO, "el repositorio de este guion")):
        if _mismo_o_dentro(destino, repo) or _mismo_o_dentro(repo, destino):
            raise SystemExit(f"El destino no puede ser {cual} ni estar dentro "
                             "de él (ni contenerlo): tiene que ser una carpeta "
                             "nueva, fuera.")
    if destino.exists() and (not destino.is_dir() or any(destino.iterdir())):
        raise SystemExit("El destino ya existe y no es una carpeta vacía: el "
                         "guion solo trabaja sobre un clon nuevo que hace él.")
    if _raiz_de_repositorio(destino) is not None:
        raise SystemExit("El destino está dentro de otro repositorio de git: "
                         "elige una carpeta fuera de cualquier repositorio.")


def comprobar_origen(origen, rama):
    raiz = _raiz_de_repositorio(origen)
    if raiz is None or not os.path.samefile(raiz, origen):
        raise SystemExit("--origen tiene que ser la raíz de un repositorio de "
                         "git (el de desarrollo).")
    if _git(origen, "rev-parse", "-q", "--verify", f"refs/heads/{rama}",
            comprobar=False) is None:
        raise SystemExit(f"El repositorio de origen no tiene la rama {rama}.")


def preparar(args, origen, huellas_completas):
    """Lee y cruza la lista, las huellas y la identidad. No imprime nada de
    la lista. Con --por-huellas no hay lista: `lista` es None hasta que se
    sacan de la historia los tokens con huella (`tokens_de_la_historia`)."""
    huellas = leer_huellas_completas(huellas_completas)
    if args.por_huellas:
        if args.lista is not None:
            raise SystemExit("--por-huellas no lleva lista: quita --lista.")
        lista, de_la_lista = None, set()
    else:
        lista = _leer_la_lista(args, origen)
        de_la_lista = {v.huella(t) for t in lista} - {v.huella(v.CENTINELA)}
    if lista is not None and de_la_lista != huellas:
        sin_huella = len(de_la_lista - huellas)
        sin_entrada = len(huellas - de_la_lista)
        mensaje = (f"La lista y el huellas.txt completo no casan: "
                   f"{sin_huella} tokens de la lista sin su huella y "
                   f"{sin_entrada} huellas sin su token en la lista.")
        if not args.ensayo:
            raise SystemExit(mensaje + " Regenera las huellas o pasa la lista "
                             "buena. (Para un ensayo con una lista de juguete, "
                             "--ensayo.)")
        print("ENSAYO. " + mensaje + " Lo que no está en la lista no se "
              "sustituye, y el verificador lo verá.")

    nombre, correo = leer_identidad(args.identidad)
    identidad = f"{nombre} <{correo}>"
    if (v.tokens(identidad) & (lista or set())
            or {v.huella(t) for t in v.tokens(identidad)} & huellas):
        raise SystemExit(
            "La identidad lleva un token de la lista (puede ser el usuario de "
            "GitHub del correo noreply): el verificador lo daría como hallazgo "
            "en todos los commits. Usa un nombre y un correo sin tokens de la "
            "lista (docs/desarrollo.md, «Publicar»).")
    if not correo.lower().endswith("@" + CORREO_NOREPLY):
        print(f"Aviso: el correo de la identidad no es de {CORREO_NOREPLY}.")
    for token in v.tokens(MARCA) | v.tokens(MARCA_EN_RUTAS):
        if token in (lista or set()) or v.huella(token) in huellas:
            raise SystemExit("La marca de sustitución está en la lista.")
    prefijos = prefijos_de(huellas | de_la_lista)
    return Preparacion(lista, frozenset(huellas), prefijos, nombre, correo,
                       args.ensayo)


def _leer_la_lista(args, origen):
    ruta_lista = args.lista or os.environ.get(v.VARIABLE_DE_LA_LISTA)
    if not ruta_lista:
        raise SystemExit(f"Falta la lista en claro: pasa --lista o define "
                         f"{v.VARIABLE_DE_LA_LISTA}. Vive fuera del "
                         "repositorio.")
    ruta_lista = Path(ruta_lista)
    if not ruta_lista.is_file():
        raise SystemExit("No existe la lista en claro que se ha pasado.")
    for repo in (origen, REPO, args.destino):
        if _mismo_o_dentro(ruta_lista, repo):
            raise SystemExit("La lista en claro está dentro de un repositorio "
                             "o del destino: tiene que vivir fuera.")
    return leer_lista(ruta_lista)


def tokens_de_la_historia(repo, huellas, lector):
    """Los tokens de la historia del clon cuya huella esta en `huellas`: en
    el texto de cada fichero, en los nombres de las rutas y en los mensajes,
    vistos como los ve el verificador. Son los de la lista que aparecen, sin
    la lista (--por-huellas). Se quedan en memoria."""
    vistos, encontrados = set(), set()

    def mirar(texto):
        for token in v.tokens(texto) - vistos:
            vistos.add(token)
            if v.huella(token) in huellas:
                encontrados.add(token)

    rutas, blobs = set(), set()
    for linea in _texto_git(repo, "rev-list", "--objects",
                            "--all").splitlines():
        nombre, _, ruta = linea.partition(" ")
        blobs.add(nombre)
        if ruta:
            rutas.add(ruta)
    for ruta in rutas:
        mirar(ruta)
    tipos = _texto_git_entrada(repo, "".join(b + "\n" for b in blobs),
                               formato="%(objectname) %(objecttype)")
    for linea in tipos.splitlines():
        nombre, tipo = linea.split()
        if tipo == "blob":
            texto = v._texto_de(lector.leer(nombre) or b"")
            if texto is not None:
                mirar(texto)
    for mensaje in _texto_git(repo, "log", "--all",
                              "--format=%B%x00").split("\0"):
        mirar(mensaje)
    return frozenset(encontrados)


def leer_huellas_completas(ruta):
    try:
        huellas = v.huellas_de_la_lista(v.leer_huellas(ruta))
    except (OSError, ValueError):
        raise SystemExit("No se pudo leer el huellas.txt completo del "
                         "repositorio de desarrollo (--huellas).")
    if not huellas:
        raise SystemExit("El huellas.txt que se ha pasado lleva solo la del "
                         "centinela: hace falta el completo, el del "
                         "repositorio de desarrollo.")
    return frozenset(huellas)


def comprobar_filter_repo():
    """El modulo git_filter_repo, de la version fijada, o SystemExit."""
    try:
        version = importlib.metadata.version("git-filter-repo")
    except importlib.metadata.PackageNotFoundError:
        version = None
    if version != VERSION_DE_FILTER_REPO:
        raise SystemExit(
            f"Hace falta git-filter-repo {VERSION_DE_FILTER_REPO} "
            f"(está: {version or 'ninguna'}): pip install "
            f"git-filter-repo=={VERSION_DE_FILTER_REPO}")
    import git_filter_repo
    return git_filter_repo


# --------------------------------------------------------------------------
# La historia original: lo que hace falta saber de cada commit (paso 4)
# --------------------------------------------------------------------------
class Commit(NamedTuple):
    padres: tuple
    declarados: frozenset   # tokens de los nombres que declara su README
    de_d5: dict             # {ruta: (modo, blob)} de los ficheros de D5


def leer_historia(repo, lista, lector):
    """{commit: Commit} de toda la historia del clon, ANTES de reescribirla.

    De cada commit, los nombres que declara su README (D5) que estan en la
    lista, y los blobs de README.md, LICENSE y docs/planificacion.md: en esos
    ficheros los nombres declarados se conservan solo en los commits que los
    declaran."""
    historia, declarados_de = {}, {}
    for linea in _texto_git(repo, "rev-list", "--all", "--parents").split("\n"):
        if not linea:
            continue
        commit, *padres = linea.split()
        de_d5 = {}
        salida = _git(repo, "ls-tree", "-z", commit, "--",
                      *v.FICHEROS_CON_NOMBRES)
        for entrada in salida.split(b"\0"):
            if not entrada:
                continue
            cabecera, ruta = entrada.split(b"\t", 1)
            modo, tipo, blob = cabecera.split()
            if tipo == b"blob":
                de_d5[ruta.decode("utf-8")] = (modo, blob)
        declarados = frozenset()
        readme = de_d5.get(v.README_DE_LOS_NOMBRES)
        if readme is not None:
            blob = readme[1]
            if blob not in declarados_de:
                texto = v._texto_de(lector.leer(blob) or b"") or ""
                declarados_de[blob] = frozenset(
                    {t for nombre in v.nombres_publicos(texto)
                     for t in v.tokens(nombre)} & lista)
            declarados = declarados_de[blob]
        historia[commit] = Commit(tuple(padres), declarados, de_d5)
    return historia


# --------------------------------------------------------------------------
# La reescritura (pasos 1 a 4), con git filter-repo como biblioteca
# --------------------------------------------------------------------------
class Recuento:
    def __init__(self):
        self.blobs = 0              # contenidos distintos que cambian
        self.mensajes = 0
        self.rutas = set()          # rutas renombradas
        self.lineas_enteras = 0
        self.huellas_txt = 0        # commits en los que se cambia huellas.txt


def reescribir(destino, preparacion, historia, centinela, lector, fr):
    """Pasa filter-repo por el clon del destino. Devuelve el Recuento."""
    lista, prefijos = preparacion.lista, preparacion.prefijos
    recuento = Recuento()
    limpios = {}                # (blob, prohibidos) -> id del blob limpio
    filtro = None
    id_del_centinela = []

    def prohibidos_en(ruta, commit):
        if ruta in v.FICHEROS_CON_NOMBRES:
            return lista - historia[commit].declarados
        return lista

    def limpio(blob, prohibidos):
        clave = (blob, prohibidos)
        if clave not in limpios:
            datos = lector.leer(blob)
            if datos is None:
                raise NoSePuedeLimpiar("un blob que no está en el clon")
            nuevos, enteras = limpiar_bytes(datos, prohibidos, prefijos)
            if nuevos == datos:
                limpios[clave] = blob
            else:
                nuevo = fr.Blob(nuevos)
                filtro.insert(nuevo)
                limpios[clave] = nuevo.id
                recuento.blobs += 1
                recuento.lineas_enteras += enteras
        return limpios[clave]

    def el_centinela():
        if not id_del_centinela:
            blob = fr.Blob(centinela)
            filtro.insert(blob)
            id_del_centinela.append(blob.id)
        return id_del_centinela[0]

    def ruta_limpia(ruta):
        texto = ruta.decode("utf-8", errors="surrogateescape")
        nueva = limpiar_ruta(texto, lista, prefijos)
        if nueva != texto:
            recuento.rutas.add(nueva)
        return nueva.encode("utf-8", errors="surrogateescape")

    def al_commit(commit, _metadatos):
        original = commit.original_id.decode("ascii")
        vistas, de_donde = set(), {}
        for cambio in commit.file_changes:
            antes = cambio.filename
            cambio.filename = ruta_limpia(cambio.filename)
            if de_donde.setdefault(cambio.filename, antes) != antes:
                raise NoSePuedeLimpiar("dos rutas dan la misma al limpiarlas")
            ruta = cambio.filename.decode("utf-8", errors="surrogateescape")
            vistas.add(ruta)
            if cambio.type != b"M" or cambio.mode in (b"120000", b"160000"):
                continue                # borrado, enlace o submodulo
            if ruta == HUELLAS_DEL_REPOSITORIO:
                cambio.blob_id = el_centinela()
                recuento.huellas_txt += 1
            else:
                cambio.blob_id = limpio(cambio.blob_id,
                                        prohibidos_en(ruta, original))
        # Un fichero de D5 que este commit no toca, pero cuyo contenido
        # limpio cambia respecto al de su primer padre (el commit declara
        # nombres que el padre no declaraba, o al reves): se escribe aqui.
        info = historia[original]
        padre = historia.get(info.padres[0]) if info.padres else None
        for ruta, (modo, blob) in sorted(info.de_d5.items()):
            if ruta in vistas or padre is None or ruta not in padre.de_d5:
                continue
            aqui = limpio(blob, prohibidos_en(ruta, original))
            alli = limpio(padre.de_d5[ruta][1],
                          prohibidos_en(ruta, info.padres[0]))
            if aqui != alli:
                commit.file_changes.append(
                    fr.FileChange(b"M", ruta.encode("utf-8"), aqui, modo))

    def al_mensaje(mensaje):
        nuevo, _enteras = limpiar_bytes(mensaje, lista, prefijos)
        if nuevo != mensaje:
            recuento.mensajes += 1
        return nuevo

    nombre = preparacion.nombre.encode("utf-8")
    correo = preparacion.correo.encode("utf-8")
    # --quiet: el `git reset --hard` final no imprime el asunto de la punta.
    argumentos = ["--quiet", "--prune-degenerate", "never", "--invert-paths"]
    for ruta in RUTAS_QUE_NO_SE_PUBLICAN:
        argumentos += ["--path", ruta]
    opciones = fr.FilteringOptions.parse_args(argumentos)
    filtro = fr.RepoFilter(opciones,
                           commit_callback=al_commit,
                           message_callback=al_mensaje,
                           name_callback=lambda _n: nombre,
                           email_callback=lambda _c: correo)
    salida = io.StringIO()
    antes = os.getcwd()
    try:
        os.chdir(destino)
        # La salida de filter-repo (lleva, por ejemplo, la direccion del
        # remoto que quita) no se imprime.
        with contextlib.redirect_stdout(salida):
            filtro.run()
    except SystemExit as error:
        texto = limpiar_texto(str(error), lista, prefijos).texto
        raise SystemExit(f"filter-repo se detuvo: {texto}")
    finally:
        os.chdir(antes)
    return recuento


# --------------------------------------------------------------------------
# Ramas, remotos y etiquetas (paso 5)
# --------------------------------------------------------------------------
def dejar_una_rama(destino, rama):
    """Una sola rama, `main`; ni remotos ni otras referencias."""
    for remoto in _texto_git(destino, "remote").split():
        _git(destino, "remote", "remove", remoto)
    if rama != RAMA_PUBLICADA:
        _git(destino, "branch", "-m", rama, RAMA_PUBLICADA)
    _git(destino, "symbolic-ref", "HEAD", f"refs/heads/{RAMA_PUBLICADA}")
    for referencia in _texto_git(destino, "for-each-ref",
                                 "--format=%(refname)").split():
        if referencia != f"refs/heads/{RAMA_PUBLICADA}":
            _git(destino, "update-ref", "-d", referencia)


def etiquetas_de_los_subproyectos(destino):
    """[(etiqueta, commit)]: el merge de cada subproyecto en la historia de
    primer padre de main, y la punta (v1.0). SystemExit si falta uno de
    SUBPROYECTOS_OBLIGATORIOS o si uno sale dos veces."""
    encontrados = {}
    salida = _texto_git(destino, "log", "--first-parent", "--merges",
                        "--format=%H%x00%s", RAMA_PUBLICADA)
    for linea in salida.splitlines():
        commit, asunto = linea.split("\0", 1)
        m = MERGE_DE_SUBPROYECTO.match(asunto)
        clave = (m.group(1).lower() if m else
                 "sp2" if MERGE_DE_SP2.match(asunto) else None)
        if clave is None:
            continue
        if clave in encontrados:
            raise SystemExit(f"El merge de {clave.upper()} sale dos veces en la "
                             "historia de main: decide cuál se etiqueta.")
        encontrados[clave] = commit
    faltan = [s.upper() for s in SUBPROYECTOS_OBLIGATORIOS
              if s not in encontrados]
    if faltan:
        raise SystemExit(f"No se encuentra el merge de {', '.join(faltan)} "
                         "en la historia de primer padre de main.")

    def orden(clave):
        return int(_texto_git(destino, "rev-list", "--count",
                              encontrados[clave]).strip())

    etiquetas = []
    for clave in sorted(encontrados, key=orden):
        numero = re.match(r"sp(\d+)", clave).group(1)
        etiquetas.append((f"v0.{numero}-{clave.replace('-', '')}",
                          encontrados[clave]))
    punta = _texto_git(destino, "rev-parse", RAMA_PUBLICADA).strip()
    etiquetas.append((ETIQUETA_DE_LA_PUNTA, punta))
    return etiquetas


def etiquetar(destino, etiquetas):
    """Etiquetas ligeras: sin autor ni mensaje que revisar."""
    for etiqueta, commit in etiquetas:
        _git(destino, "tag", etiqueta, commit)


def compactar(destino):
    """Que la carpeta no guarde los objetos de la historia vieja."""
    _git(destino, "reflog", "expire", "--expire=now", "--all")
    _git(destino, "gc", "--prune=now", "--quiet")


# --------------------------------------------------------------------------
# La comprobacion (paso 6)
# --------------------------------------------------------------------------
def _entorno_del_verificador():
    entorno = _entorno()
    entorno["PYTHONIOENCODING"] = "utf-8"
    entorno["PYTHONUTF8"] = "1"
    return entorno


def _verificador(raiz, huellas, revision):
    """(codigo, salida) de verificar_anonimato.py --commit sobre `raiz`."""
    hecho = subprocess.run(
        [sys.executable, str(VERIFICADOR), "--raiz", str(raiz),
         "--huellas", str(huellas), "--commit", revision],
        capture_output=True, env=_entorno_del_verificador())
    salida = (hecho.stdout + hecho.stderr).decode("utf-8", errors="replace")
    return hecho.returncode, salida


def _hallazgos(salida):
    """Las lineas de hallazgo de una salida del verificador: las de antes de
    `--`; si no hay ninguna pero salio con error, la ultima linea."""
    lineas = salida.splitlines()
    if "--" in lineas:
        hallazgos = lineas[:lineas.index("--")]
    else:
        hallazgos = []
    return hallazgos or [lineas[-1] if lineas else "sin salida"]


TAPADA = re.compile(r"<huella-[0-9a-f+]*>")
HUELLA_EN_SALIDA = re.compile(r"huella [0-9a-f]{12}")


def sin_huellas(linea, preparacion):
    """Una linea del verificador sin principios de huella, ni tokens ni
    prefijos de la lista: se puede imprimir."""
    linea = TAPADA.sub("<token>", linea)
    linea = HUELLA_EN_SALIDA.sub("huella", linea)
    return limpiar_texto(linea, preparacion.lista, preparacion.prefijos).texto


def _clase(linea):
    """La clase de una linea de hallazgo del verificador: `huella`, la del
    secreto (`asignacion_de_secreto`...) u `otro`."""
    if ": huella " in linea:
        return "huella"
    m = re.search(r": ([a-z_]+)(?: \([^()]*\))?$", linea)
    return m.group(1) if m else "otro"


def verificar_commits(destino, huellas_completas, hilos):
    """{commit: [lineas de hallazgo]} de los commits que el verificador no da
    por limpios; todos los de la historia, uno a uno, sobre un repositorio
    auxiliar vacio que ve los objetos del destino (asi no cuentan ni su copia
    de trabajo ni su indice: solo el commit)."""
    auxiliar = Path(tempfile.mkdtemp(prefix="verificar-commits-"))
    try:
        _git(auxiliar, "init", "-q")
        objetos = (Path(destino).resolve() / ".git" / "objects").as_posix()
        # En bytes: en Windows, write_text pondria `\r\n`, y git leeria la
        # ruta con el `\r`.
        (auxiliar / ".git" / "objects" / "info" / "alternates").write_bytes(
            objetos.encode("utf-8") + b"\n")
        commits = _texto_git(destino, "rev-list", "--all").split()

        def uno(commit):
            codigo, salida = _verificador(auxiliar, huellas_completas, commit)
            return commit, codigo, salida

        sucios = {}
        with ThreadPoolExecutor(max_workers=hilos) as hilos_:
            for commit, codigo, salida in hilos_.map(uno, commits):
                if codigo != 0:
                    sucios[commit] = _hallazgos(salida)
        return commits, sucios
    finally:
        _borrar(auxiliar)


def comprobaciones_de_la_historia(destino, preparacion, centinela, origen_info):
    """Lo que el verificador no mira y tiene que estar bien en TODA la
    historia. Devuelve [(que, bien, detalle)], sin nada de la lista."""
    resultados = []
    commits = _texto_git(destino, "rev-list", "--all").split()

    # 1. Ninguna de las rutas quitadas, en ningun commit.
    con_rutas = _texto_git(destino, "log", "--all", "--format=%H", "--",
                           *RUTAS_QUE_NO_SE_PUBLICAN).split()
    resultados.append(("rutas quitadas, en ningún commit", not con_rutas,
                       f"{len(con_rutas)} commits las llevan"))
    lector = LectorDeObjetos(destino)
    try:
        quedan = sum(1 for blob in origen_info["blobs_quitados"]
                     if _git(destino, "cat-file", "-e", blob,
                             comprobar=False) is not None)
        resultados.append(("sus contenidos, fuera de la carpeta", quedan == 0,
                           f"{quedan} siguen en la carpeta"))
        # La historia vieja, fuera de la carpeta: ningun objeto suelto, y la
        # punta de antes ya no esta.
        sueltos = _texto_git(destino, "fsck", "--unreachable", "--no-reflogs",
                             "--no-progress").split("\n")
        sueltos = [s for s in sueltos if s.strip()]
        viejo = _git(destino, "cat-file", "-e", origen_info["punta"],
                     comprobar=False)
        resultados.append(("la historia vieja, fuera de la carpeta",
                           viejo is None and not sueltos,
                           f"{len(sueltos)} objetos sueltos"
                           + ("" if viejo is None else "; la punta vieja")))

        # 2. huellas.txt: el del centinela en todos los commits que lo llevan.
        consulta = "".join(f"{c}:{HUELLAS_DEL_REPOSITORIO}\n" for c in commits)
        salida = _texto_git_entrada(destino, consulta)
        del_centinela = _git(destino, "hash-object", "--stdin",
                             entrada=centinela).decode().strip()
        distintos = [linea for linea in salida.splitlines()
                     if not linea.endswith("missing")
                     and linea.split()[0] != del_centinela]
        llevan = sum(1 for linea in salida.splitlines()
                     if not linea.endswith("missing"))
        resultados.append((f"{HUELLAS_DEL_REPOSITORIO}, solo el centinela",
                           not distintos and llevan > 0,
                           f"{len(distintos)} de {llevan} commits llevan otro"))

        # 3. Una sola identidad, la dada.
        identidades = set(_texto_git(
            destino, "log", "--all",
            "--format=%an <%ae>%n%cn <%ce>").splitlines()) - {""}
        dada = f"{preparacion.nombre} <{preparacion.correo}>"
        resultados.append(("una sola identidad, la dada",
                           identidades == {dada},
                           f"{len(identidades)} identidades"))

        # 4. Ni huellas ni prefijos de huella en ningun fichero ni mensaje.
        blobs = set()
        for linea in _texto_git(destino, "rev-list", "--objects",
                                "--all").splitlines():
            blobs.add(linea.split(" ", 1)[0])
        tipos = _texto_git_entrada(destino, "".join(b + "\n" for b in blobs),
                                   formato="%(objectname) %(objecttype)")
        con_huellas, binarios = 0, set()
        for linea in tipos.splitlines():
            nombre, tipo = linea.split()
            if tipo != "blob":
                continue
            texto = v._texto_de(lector.leer(nombre) or b"")
            if texto is None:
                binarios.add(nombre)
            elif any(m.group().lower() in preparacion.prefijos
                     for m in HEXADECIMAL.finditer(texto)):
                con_huellas += 1
        mensajes = _texto_git(destino, "log", "--all", "--format=%B%x00")
        en_mensajes = sum(1 for m in mensajes.split("\0")
                          if any(x.group().lower() in preparacion.prefijos
                                 for x in HEXADECIMAL.finditer(m)))
        resultados.append(("huellas o prefijos de huella en la historia",
                           con_huellas == 0 and en_mensajes == 0,
                           f"{con_huellas} ficheros y {en_mensajes} mensajes "
                           "los llevan"))
        en_la_punta = {linea.split()[2] for linea in _texto_git(
            destino, "ls-tree", "-r", RAMA_PUBLICADA).splitlines()}
        viejos = len(binarios - en_la_punta)
    finally:
        lector.cerrar()

    # 5. Sin remoto; una rama, main; HEAD en ella; solo etiquetas ademas.
    remotos = _texto_git(destino, "remote").split()
    referencias = _texto_git(destino, "for-each-ref",
                             "--format=%(refname)").split()
    otras = [r for r in referencias if r != f"refs/heads/{RAMA_PUBLICADA}"
             and not r.startswith("refs/tags/")]
    cabeza = _texto_git(destino, "symbolic-ref", "HEAD").strip()
    resultados.append(("sin remoto, una sola rama (main) y etiquetas",
                       not remotos and not otras
                       and cabeza == f"refs/heads/{RAMA_PUBLICADA}",
                       f"{len(remotos)} remotos, {len(otras)} referencias de "
                       "más"))
    return resultados, viejos


def _texto_git_entrada(repo, entrada, formato=None):
    argumento = ("--batch-check" if formato is None
                 else f"--batch-check={formato}")
    return _git(repo, "cat-file", argumento,
                entrada=entrada.encode("utf-8")).decode("utf-8",
                                                        errors="replace")


# --------------------------------------------------------------------------
# La orden
# --------------------------------------------------------------------------
def _argumentos(argv):
    analizador = argparse.ArgumentParser(
        description="Prepara el repositorio que se publica: un clon nuevo con "
                    "la historia real limpia (SP5-C3).")
    analizador.add_argument("--origen", type=Path, required=True,
                            help="el repositorio de desarrollo (solo se lee)")
    analizador.add_argument("--destino", type=Path, required=True,
                            help="carpeta nueva (que no existe o está vacía) "
                                 "donde se hace el clon que se publica")
    analizador.add_argument("--lista", type=Path, default=None,
                            help="la lista en claro, fuera del repositorio "
                                 f"(o {v.VARIABLE_DE_LA_LISTA})")
    analizador.add_argument("--identidad", required=True,
                            help='autor y quien confirma de todos los commits: '
                                 '"Nombre <correo noreply de GitHub>"')
    analizador.add_argument("--huellas", type=Path, default=None,
                            help="el huellas.txt completo (por defecto, el de "
                                 "--origen)")
    analizador.add_argument("--rama", default=RAMA_PUBLICADA,
                            help="la rama del origen que se publica (main)")
    analizador.add_argument("--hilos", type=int,
                            default=max(1, min(8, os.cpu_count() or 1)),
                            help="verificaciones a la vez")
    analizador.add_argument("--por-huellas", action="store_true",
                            help="sin lista: sustituye los tokens de la "
                                 "historia cuya huella está en --huellas (el "
                                 "mismo conjunto si las huellas están al día; "
                                 "con --lista, el guion además lo comprueba)")
    analizador.add_argument("--ensayo", action="store_true",
                            help="admite una lista que no casa con las huellas "
                                 "(una de juguete): nunca para publicar")
    analizador.add_argument("--detalle", action="store_true",
                            help="imprime los hallazgos del verificador (sin "
                                 "huellas, prefijos ni tokens)")
    return analizador.parse_args(argv)


def main(argv=None):
    args = _argumentos(argv)
    inicio = time.monotonic()
    origen = Path(os.path.realpath(args.origen))
    destino = Path(os.path.abspath(args.destino))
    comprobar_origen(origen, args.rama)
    comprobar_destino_nuevo(destino, origen)
    huellas_completas = args.huellas or origen / HUELLAS_DEL_REPOSITORIO
    preparacion = preparar(args, origen, huellas_completas)
    fr = comprobar_filter_repo()
    if _git(origen, "status", "--porcelain", "--untracked-files=no").strip():
        print("Aviso: el origen tiene cambios sin confirmar; solo se publica "
              f"lo confirmado en {args.rama}.")

    # El centinela: lo escribe el verificador, como --regenerar --solo-centinela.
    temporal = Path(tempfile.mkdtemp(prefix="centinela-"))
    try:
        v.regenerar_solo_centinela(temporal / "huellas.txt")
        centinela = (temporal / "huellas.txt").read_bytes()
    finally:
        _borrar(temporal)

    # 1. El clon nuevo: solo la rama, sin etiquetas, sin compartir objetos.
    _git(origen.parent, "clone", "--no-local", "--single-branch", "--branch",
         args.rama, "--no-tags", "--quiet", str(origen), str(destino))
    punta_vieja = _texto_git(destino, "rev-parse", "HEAD").strip()
    blobs_quitados = set()
    for linea in _texto_git(destino, "rev-list", "--objects",
                            "--all").splitlines():
        partes = linea.split(" ", 1)
        if len(partes) == 2 and partes[1] in RUTAS_QUE_NO_SE_PUBLICAN:
            blobs_quitados.add(partes[0])
    total_viejo = len(_texto_git(destino, "rev-list", "--all").split())
    print(f"Clon nuevo de {args.rama}: {total_viejo} commits.")

    lector = LectorDeObjetos(destino)
    try:
        if preparacion.lista is None:           # --por-huellas
            preparacion = preparacion._replace(lista=tokens_de_la_historia(
                destino, preparacion.huellas, lector))
            print(f"Por huellas: {len(preparacion.lista)} tokens de la "
                  "historia tienen su huella en el huellas.txt completo.")
        historia = leer_historia(destino, preparacion.lista, lector)
        con_nombres = sum(1 for c in historia.values() if c.declarados)
        recuento = reescribir(destino, preparacion, historia, centinela,
                              lector, fr)
    except NoSePuedeLimpiar as error:
        raise SystemExit(f"No se pudo limpiar la historia ({error}). Borra el "
                         "destino; nada se ha publicado.")
    finally:
        lector.cerrar()

    dejar_una_rama(destino, args.rama)
    etiquetas = etiquetas_de_los_subproyectos(destino)
    etiquetar(destino, etiquetas)
    compactar(destino)
    total = len(_texto_git(destino, "rev-list", "--all").split())

    print(f"1. Quitadas de todos los commits: {len(RUTAS_QUE_NO_SE_PUBLICAN)} "
          "rutas.")
    print(f"2. {HUELLAS_DEL_REPOSITORIO}: el del centinela, en los "
          f"{recuento.huellas_txt} commits que lo cambian.")
    print("3. Una sola identidad en todos los commits.")
    print(f"4. Contenidos limpiados: {recuento.blobs}; mensajes: "
          f"{recuento.mensajes}; rutas renombradas: {len(recuento.rutas)}; "
          f"líneas retiradas enteras: {recuento.lineas_enteras}. Nombres de "
          f"D5 conservados en los {con_nombres} commits cuyo README los "
          "declara.")
    print(f"5. Rama {RAMA_PUBLICADA}, {total} commits; etiquetas: "
          + ", ".join(f"{e} {c[:7]}" for e, c in etiquetas) + ".")

    # 6. La comprobacion.
    commits, sucios = verificar_commits(destino, huellas_completas, args.hilos)
    print(f"6. Verificador, commit a commit: {len(sucios)} de {len(commits)} "
          "commits con hallazgos.")
    for commit in commits:
        if commit not in sucios:
            continue
        clases = {}
        for linea in sucios[commit]:
            clases[_clase(linea)] = clases.get(_clase(linea), 0) + 1
        print(f"   {commit[:7]}: {len(sucios[commit])} hallazgos ("
              + ", ".join(f"{c}: {n}" for c, n in sorted(clases.items()))
              + ")")
        if args.detalle:
            for linea in sucios[commit]:
                print("      " + sin_huellas(linea, preparacion))
    codigo, salida = _verificador(destino, huellas_completas, "HEAD")
    print("   Copia de trabajo, punta y nombres de la rama y las etiquetas: "
          + ("limpio" if codigo == 0 else
             f"{len(_hallazgos(salida))} hallazgos"))
    if codigo != 0 and args.detalle:
        for linea in _hallazgos(salida):
            print("      " + sin_huellas(linea, preparacion))
    resultados, viejos = comprobaciones_de_la_historia(
        destino, preparacion, centinela,
        {"punta": punta_vieja, "blobs_quitados": blobs_quitados})
    for que, bien, detalle in resultados:
        print(f"   {que}: " + ("bien" if bien else f"MAL ({detalle})"))
    if viejos:
        print(f"   Binarios de la historia que no están en la punta: {viejos} "
              "(nadie los recorre: se revisan a mano).")

    limpio = not sucios and codigo == 0 and all(b for _q, b, _d in resultados)
    minutos = (time.monotonic() - inicio) / 60
    if limpio and not preparacion.ensayo:
        print(f"LISTO para publicar ({minutos:.1f} min): falta la revisión a "
              "mano (docs/desarrollo.md, «Publicar»).")
        return 0
    print(f"NO publicar ({minutos:.1f} min): "
          + ("es un ensayo." if limpio else "hay hallazgos.")
          + " Borra el destino y mira docs/desarrollo.md, «Publicar».")
    return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        raise SystemExit(main())
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception as error:      # noqa: BLE001
        # El mensaje no se imprime: podria llevar contenido del repositorio.
        marco = error.__traceback__
        while marco.tb_next is not None:
            marco = marco.tb_next
        raise SystemExit(f"Error inesperado ({type(error).__name__}, línea "
                         f"{marco.tb_lineno}); el mensaje no se imprime porque "
                         "podría llevar contenido del repositorio. Borra el "
                         "destino; nada se ha publicado.")
