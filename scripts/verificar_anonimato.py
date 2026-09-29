"""Comprueba que el repositorio se puede publicar (spec de SP5 §6.1).

Uso, desde la raiz del repositorio:

    python scripts/verificar_anonimato.py
    python scripts/verificar_anonimato.py --raiz <arbol> --commit --un-solo-commit
    ANONIMATO_LISTA=<lista en claro> python scripts/verificar_anonimato.py --regenerar

Busca dos cosas en los ficheros versionados:

1. HUELLAS. La lista de cadenas que identifican al cliente, a la empresa, a la
   maquina o a los integrantes NO vive en el repositorio. El repositorio lleva
   solo `tests/anonimato/huellas.txt`: el sha256 de cada token. Cada fichero
   de texto se tokeniza igual que la lista (minusculas, sin tildes, particion
   por todo lo que no sea [a-z0-9]) y se compara huella con huella.
2. SECRETOS, por patron: token de bot de Telegram, claves de API, contrasena
   dentro de una URL, y ficheros que no deben viajar (`.env`, claves).

Ninguna salida lleva el token ni el secreto en claro: fichero, linea y huella
o clase. La salida tambien se puede publicar.

Sale con 0 si no hay hallazgos y con 1 si los hay. Lo usa
`tests/test_anonimato.py`, que lo carga por ruta.
"""
import argparse
import fnmatch
import hashlib
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HUELLAS_POR_DEFECTO = REPO / "tests" / "anonimato" / "huellas.txt"
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
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn")


def tokens(texto):
    """Los tokens de un texto: la misma regla para la lista y los ficheros."""
    texto = BASE64.sub(" ", texto)
    return set(NO_TOKEN.split(_sin_tildes(texto).lower())) - {""}


def huella(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def leer_huellas(ruta):
    """Las huellas de `huellas.txt`, sin la cabecera ni lineas vacias."""
    lineas = Path(ruta).read_text(encoding="utf-8").splitlines()
    return {l.strip() for l in lineas
            if l.strip() and not l.lstrip().startswith("#")}


def huellas_de_la_lista(huellas):
    """Las huellas sin la del centinela: lo que se busca en el arbol."""
    return set(huellas) - {huella(CENTINELA)}


def leer_lista(ruta):
    """Las entradas de la seccion `[huellas]` de la lista en claro."""
    entradas, dentro = [], False
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea.startswith("["):
            dentro = linea == "[huellas]"
        elif dentro and linea and not linea.startswith("#"):
            entradas.append(linea)
    return entradas


def regenerar(lista, destino):
    """Escribe las huellas de los tokens de `lista`, ordenadas, y las cuenta.

    Cada entrada se tokeniza: una entrada con separadores da varias huellas.
    La del centinela va siempre.
    """
    todas = {huella(CENTINELA)}
    for entrada in lista:
        todas |= {huella(t) for t in tokens(entrada)}
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8", newline="\n") as salida:
        salida.write(CABECERA)
        for una in sorted(todas):
            salida.write(una + "\n")
    return len(todas)


# --------------------------------------------------------------------------
# El recorrido
# --------------------------------------------------------------------------
def _git(raiz, *argumentos):
    """La salida de git en bytes, o None si git falla o no esta."""
    try:
        hecho = subprocess.run(["git", "-C", str(raiz), *argumentos],
                               capture_output=True, check=False)
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


def ficheros_versionados(raiz):
    """Los ficheros versionados bajo `raiz`, ordenados.

    Si `raiz` no es la raiz de un repositorio de git, todos los ficheros que
    hay debajo salvo la carpeta `.git/`.
    """
    raiz = Path(raiz)
    if _es_la_raiz_de_un_repositorio(raiz):
        salida = _git(raiz, "ls-files", "-z")
        if salida is not None:
            nombres = [n for n in salida.decode("utf-8").split("\0") if n]
            return [raiz / n for n in sorted(nombres) if (raiz / n).is_file()]
    hallados = []
    for carpeta, subcarpetas, nombres in os.walk(raiz):
        subcarpetas[:] = [s for s in subcarpetas if s != ".git"]
        hallados += [Path(carpeta) / n for n in nombres]
    return sorted(hallados, key=lambda p: p.relative_to(raiz).as_posix())


def _texto(ruta):
    """El texto del fichero, o None si no es texto."""
    datos = Path(ruta).read_bytes()
    if b"\0" in datos:
        return None
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        return None


def es_texto(ruta):
    """Es texto lo que se decodifica en UTF-8 y no lleva bytes nulos."""
    return _texto(ruta) is not None


def binarios(raiz):
    """Lo que no es texto: se declara y se revisa a mano, no se recorre."""
    return [p for p in ficheros_versionados(raiz) if not es_texto(p)]


def _relativo(ruta, raiz):
    return Path(ruta).relative_to(raiz).as_posix()


def buscar_huellas(raiz, huellas):
    """Las apariciones de alguna huella: fichero, linea y huella.

    La linea 0 es el nombre del fichero. El token en claro no sale nunca.
    """
    raiz, huellas = Path(raiz), set(huellas)
    hallazgos = []

    def mirar(texto, fichero, linea):
        for una in sorted({huella(t) for t in tokens(texto)} & huellas):
            hallazgos.append({"fichero": fichero, "linea": linea,
                              "huella": una})

    for ruta in ficheros_versionados(raiz):
        fichero = _relativo(ruta, raiz)
        mirar(fichero, _oculto(fichero, huellas), 0)
        texto = _texto(ruta)
        if texto is None:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            mirar(linea, fichero, n)
    return hallazgos


def _oculto(fichero, huellas):
    """El nombre del fichero, con los componentes que son hallazgo tapados."""
    partes = []
    for parte in fichero.split("/"):
        sucio = {huella(t) for t in tokens(parte)} & huellas
        partes.append("<nombre-con-huella>" if sucio else parte)
    return "/".join(partes)


# --------------------------------------------------------------------------
# Secretos
# --------------------------------------------------------------------------
PATRONES_DE_SECRETO = {
    "token_de_bot_de_telegram": re.compile(
        r"(?<![0-9A-Za-z])\d{8,10}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])"),
    "clave_de_api_sk": re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
    "clave_de_api_akia": re.compile(
        r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![0-9A-Z])"),
    "clave_de_api_ghp": re.compile(r"(?<![A-Za-z0-9])ghp_[A-Za-z0-9]{36}"),
    "clave_de_api_github_pat": re.compile(
        r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{22,}"),
    "jwt": re.compile(
        r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
}

# Esquema, dos barras, usuario, dos puntos, contrasena, arroba y host.
URL_CON_CONTRASENA = re.compile(
    r"[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]+:([^\s/@]+)@")

# Lo que puede ir en el sitio de la contrasena. Las palabras salen del
# inventario del arbol (28-sep): `prueba` es la del PostgreSQL desechable de
# las pruebas; `clave` y `token`, las de los ejemplos de las guias;
# `cambiar-esto`, el valor de ejemplo del spec.
CONTRASENAS_DE_EJEMPLO = ("prueba", "cambiar-esto", "clave", "token",
                          "...", "%s")
CONTRASENA_MARCADOR = re.compile(
    r"<[^<>]+>|\$[A-Za-z_][A-Za-z0-9_]*|\$\{[^{}]+\}")

FICHEROS_PROHIBIDOS = (".env", ".env.*", "kaggle.json", "*.pem", "*.key",
                       "id_rsa*", "*.p12")
FICHEROS_PERMITIDOS = (".env.ejemplo",)


def _es_de_ejemplo(contrasena):
    return (contrasena in CONTRASENAS_DE_EJEMPLO
            or CONTRASENA_MARCADOR.fullmatch(contrasena) is not None)


def _clases_de_secreto(linea):
    clases = [clase for clase, patron in PATRONES_DE_SECRETO.items()
              if patron.search(linea)]
    if any(not _es_de_ejemplo(m.group(1))
           for m in URL_CON_CONTRASENA.finditer(linea)):
        clases.append("contrasena_en_url")
    return clases


def _prohibido(nombre):
    return (nombre not in FICHEROS_PERMITIDOS
            and any(fnmatch.fnmatchcase(nombre, p)
                    for p in FICHEROS_PROHIBIDOS))


def buscar_secretos(raiz):
    """Secretos por patron y ficheros prohibidos: fichero, linea y clase.

    La linea 0 es el fichero entero. El secreto no sale nunca.
    """
    raiz = Path(raiz)
    hallazgos = []
    for ruta in ficheros_versionados(raiz):
        fichero = _relativo(ruta, raiz)
        if _prohibido(ruta.name):
            hallazgos.append({"fichero": fichero, "linea": 0,
                              "clase": "fichero_prohibido"})
            continue
        texto = _texto(ruta)
        if texto is None:
            continue
        for n, linea in enumerate(texto.splitlines(), 1):
            for clase in _clases_de_secreto(linea):
                hallazgos.append({"fichero": fichero, "linea": n,
                                  "clase": clase})
    return hallazgos


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
        raise SystemExit(f"No se pudo leer el commit {revision} de {raiz}: "
                         "¿es un repositorio de git con commits?")
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
    """Cuantos commits se alcanzan desde HEAD."""
    salida = _git(raiz, "rev-list", "--count", "HEAD")
    if salida is None:
        raise SystemExit(f"No se pudieron contar los commits de {raiz}: "
                         "¿es un repositorio de git con commits?")
    return int(salida.decode("ascii").strip())


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
    analizador.add_argument("--huellas", type=Path,
                            default=HUELLAS_POR_DEFECTO,
                            help="fichero de huellas (por defecto, "
                                 "tests/anonimato/huellas.txt)")
    analizador.add_argument("--commit", nargs="?", const="HEAD", default=None,
                            metavar="REV",
                            help="comprueba también autor, correo, quien "
                                 "confirma y mensaje de ese commit (HEAD)")
    analizador.add_argument("--un-solo-commit", action="store_true",
                            help="exige que el repositorio tenga un solo "
                                 "commit")
    analizador.add_argument("--regenerar", action="store_true",
                            help="escribe el fichero de huellas desde la "
                                 f"lista en claro ({VARIABLE_DE_LA_LISTA} o "
                                 "--lista)")
    analizador.add_argument("--lista", type=Path, default=None,
                            help="la lista en claro, fuera del repositorio")
    return analizador.parse_args(argv)


def _regenerar(args):
    lista = args.lista or os.environ.get(VARIABLE_DE_LA_LISTA)
    if not lista:
        raise SystemExit(
            f"Falta la lista en claro: define {VARIABLE_DE_LA_LISTA} o pasa "
            "--lista. Vive fuera del repositorio.")
    n = regenerar(leer_lista(lista), args.huellas)
    print(f"{n} huellas escritas en {args.huellas} (con la del centinela).")
    return 0


def main(argv=None):
    args = _argumentos(argv)
    if args.regenerar:
        return _regenerar(args)

    huellas = huellas_de_la_lista(leer_huellas(args.huellas))
    recorridos = ficheros_versionados(args.raiz)
    sin_recorrer = binarios(args.raiz)
    de_huella = buscar_huellas(args.raiz, huellas)
    de_secreto = buscar_secretos(args.raiz)

    for h in de_huella:
        print(f"{h['fichero']}:{h['linea']}: huella {h['huella'][:12]}")
    for h in de_secreto:
        print(f"{h['fichero']}:{h['linea']}: {h['clase']}")

    del_commit = []
    if args.commit is not None:
        del_commit = verificar_commit(args.raiz, args.commit, huellas=huellas)
        for h in del_commit:
            donde = (f"{h['campo']}:{h['linea']}" if h["linea"]
                     else h["campo"])
            print(f"commit {args.commit}: {donde}: "
                  f"huella {h['huella'][:12]}")

    print("--")
    print(f"ficheros recorridos: {len(recorridos) - len(sin_recorrer)}")
    print(f"binarios sin recorrer: {len(sin_recorrer)}")
    for ruta in sin_recorrer:
        print(f"  {_relativo(ruta, args.raiz)}")
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
        cuantos = commits(args.raiz)
        print(f"commits: {cuantos}")
        mal += cuantos != 1
    print("limpio" if not mal else "NO publicar: hay hallazgos")
    return 1 if mal else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    raise SystemExit(main())
