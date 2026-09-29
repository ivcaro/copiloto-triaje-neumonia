# -*- coding: utf-8 -*-
"""Pone y quita los valores reales de los workflows de n8n.

Los tres exports de `n8n/` se versionan con MARCADORES en vez de los valores
de la instancia donde corren (spec de SP5 §6.1): la URL publica de n8n y los
`id` y nombres de sus credenciales. Por eso un export del repositorio ya no es
identico byte a byte al desplegado, y entre uno y otro media este script.

USO
    Del repositorio a n8n (antes de importar o desplegar):
        python scripts/marcadores_n8n.py --entrada n8n/copiloto-paciente.json --salida <carpeta-temporal>/copiloto-paciente.json

    De n8n al repositorio (antes de versionar un export):
        python scripts/marcadores_n8n.py --retirar --entrada <carpeta-temporal>/export.json --salida n8n/copiloto-paciente.json

Los valores salen de `n8n/valores.local.json` (ignorado por git: marcador ->
valor real), que se crea copiando `n8n/valores.ejemplo.json` y cambiando los
valores de ejemplo por los de la instancia. Con `--valores` se lee otro.

Al poner los valores no reformatea: sustituye texto y deja lo demas como
estaba, con los finales de linea en LF. Al retirarlos de un workflow, ademas,
lo deja como se versiona: solo con las cinco claves que se versionan (`name`,
`active`, `nodes`, `connections`, `settings`) y escrito como los de `n8n/`.
Una descarga de n8n trae tambien el `id` del workflow, su `versionId`, la
huella de la instancia (`meta`), datos de ejecuciones (`pinData`) y etiquetas:
identifican la instancia y no se versionan. No usa la red ni habla con n8n.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VALORES_LOCALES = REPO / "n8n" / "valores.local.json"
VALORES_DE_EJEMPLO = REPO / "n8n" / "valores.ejemplo.json"

URL_N8N = "https://n8n.ejemplo.test"
MARCADORES = (
    URL_N8N,
    "CRED_TELEGRAM_PACIENTE",
    "CRED_TELEGRAM_PROFESIONAL",
    "CRED_TELEGRAM_AVISOS",
    "CRED_POSTGRES_COPILOTO",
    "CRED_SECRETO_PACIENTE",
    "CRED_SECRETO_PROFESIONAL",
    "bot-paciente",
    "bot-profesional",
    "bot-avisos",
)

# Lo que se versiona de un workflow, y en este orden. Lo demas que trae una
# descarga de n8n es de la instancia.
CLAVES_DEL_WORKFLOW = ("name", "active", "nodes", "connections", "settings")

# Un valor con alguno de estos caracteres romperia el JSON al sustituirlo.
_PROHIBIDOS = re.compile(r'["\\\x00-\x1f]')

# La forma de un marcador. Una clave de los valores que NO la tiene no se
# repite en ningun mensaje: puede ser un valor real.
_FORMA_DE_MARCADOR = re.compile(
    r"CRED_[A-Z0-9_]+|bot-[a-z]+|https?://[A-Za-z0-9.-]*ejemplo\.test")


class ErrorDeMarcadores(ValueError):
    """Los valores o la entrada no permiten una sustitucion sin ambiguedad."""


def marcadores_de(texto: str) -> set:
    """Los marcadores conocidos que aparecen en `texto`."""
    return {m for m in MARCADORES if m in texto}


def _nombres(marcadores) -> str:
    return ", ".join(sorted(marcadores))


def _validar(valores: dict) -> None:
    if not isinstance(valores, dict):
        raise ErrorDeMarcadores("los valores tienen que ser un objeto JSON "
                                "{marcador: valor}")
    desconocidos = set(valores) - set(MARCADORES)
    if desconocidos:
        # Solo se repiten las claves con forma de marcador (una errata). Las
        # demas pueden ser valores reales: con el fichero escrito al reves,
        # {valor real: marcador}, el mensaje los imprimiria todos.
        erratas = {d for d in desconocidos
                   if isinstance(d, str) and _FORMA_DE_MARCADOR.fullmatch(d)}
        mensaje = "marcadores desconocidos en los valores: "
        mensaje += _nombres(erratas) if erratas else "ninguno tiene forma de marcador"
        otras = len(desconocidos) - len(erratas)
        if otras:
            mensaje += (f" ({otras} claves que no son marcadores y no se "
                        "repiten aqui: las claves son los marcadores y los "
                        "valores, los de la instancia; ¿esta el fichero al "
                        "reves?)")
        raise ErrorDeMarcadores(mensaje)
    for marcador, valor in valores.items():
        if not isinstance(valor, str) or not valor.strip():
            raise ErrorDeMarcadores(f"el valor de {marcador} esta vacio")
        if valor != valor.strip() or _PROHIBIDOS.search(valor):
            raise ErrorDeMarcadores(
                f"el valor de {marcador} lleva espacios en los extremos, "
                "comillas, barras invertidas o caracteres de control")
    url = valores.get(URL_N8N)
    if url is not None and (not re.match(r"https?://[^/]+", url)
                            or url.endswith("/")):
        raise ErrorDeMarcadores(
            f"el valor de {URL_N8N} tiene que ser la URL base de n8n, con "
            "esquema y sin barra final")
    por_valor = {}
    for marcador, valor in valores.items():
        por_valor.setdefault(valor.lower(), []).append(marcador)
    for repetidos in por_valor.values():
        if len(repetidos) > 1:
            raise ErrorDeMarcadores(
                f"comparten valor: {_nombres(repetidos)}")
    for marcador, valor in valores.items():
        v = valor.lower()
        for otro in MARCADORES:
            if v in otro.lower() or otro.lower() in v:
                raise ErrorDeMarcadores(
                    f"el valor de {marcador} se confunde con el marcador {otro}")
        for otro, su_valor in valores.items():
            if otro != marcador and v in su_valor.lower():
                raise ErrorDeMarcadores(
                    f"el valor de {marcador} esta contenido en el de {otro}")


def _sustituir(texto: str, pares: dict) -> str:
    """Una sola pasada, de la cadena mas larga a la mas corta: lo que se acaba
    de poner no se vuelve a sustituir."""
    if not pares:
        return texto
    claves = sorted(pares, key=len, reverse=True)
    patron = re.compile("|".join(re.escape(c) for c in claves))
    return patron.sub(lambda m: pares[m.group(0)], texto)


def _restos(texto: str, valores: dict) -> list:
    """[(marcador, linea)] de cada valor real que sigue en `texto`, sin
    distinguir mayusculas; de la URL se busca tambien el host a secas."""
    hallados = []
    lineas = texto.lower().split("\n")
    for marcador, valor in valores.items():
        buscados = {valor.lower()}
        if "://" in valor:
            buscados.add(valor.lower().split("://", 1)[1].split("/", 1)[0])
        for numero, linea in enumerate(lineas, 1):
            if any(b in linea for b in buscados):
                hallados.append((marcador, numero))
    return hallados


def _decir_restos(restos: list) -> str:
    return "; ".join(f"el de {m} en la linea {n}" for m, n in restos)


def aplicar(texto: str, valores: dict) -> str:
    """Marcador -> valor real. Falla si falta el valor de un marcador presente
    o si la entrada ya lleva algun valor real."""
    _validar(valores)
    presentes = marcadores_de(texto)
    faltan = presentes - set(valores)
    if faltan:
        raise ErrorDeMarcadores(
            f"faltan en los valores: {_nombres(faltan)}")
    restos = _restos(texto, valores)
    if restos:
        raise ErrorDeMarcadores(
            "la entrada ya lleva valores reales: " + _decir_restos(restos))
    return _sustituir(texto, {m: valores[m] for m in presentes})


def retirar(texto: str, valores: dict) -> str:
    """Valor real -> marcador. Exige el valor de TODOS los marcadores (el que
    falte no se podria buscar) y falla si tras sustituir queda alguno."""
    _validar(valores)
    faltan = set(MARCADORES) - set(valores)
    if faltan:
        raise ErrorDeMarcadores(
            f"faltan en los valores: {_nombres(faltan)}")
    resultado = _sustituir(texto, {v: m for m, v in valores.items()})
    restos = _restos(resultado, valores)
    if restos:
        raise ErrorDeMarcadores(
            "quedan valores reales tras retirar (escritos de otra forma): "
            + _decir_restos(restos))
    return resultado


def leer(ruta) -> str:
    """El fichero en UTF-8 con los finales de linea en LF, venga como venga."""
    with io.open(ruta, encoding="utf-8", newline="") as f:
        return f.read().replace("\r\n", "\n")


def escribir(ruta, texto: str) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with io.open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


def leer_valores(ruta) -> dict:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorDeMarcadores(
            f"no existe {ruta}: copia n8n/valores.ejemplo.json a "
            "n8n/valores.local.json y pon los valores de tu instancia")
    try:
        return json.loads(leer(ruta))
    except json.JSONDecodeError as e:
        raise ErrorDeMarcadores(f"{ruta} no es un JSON valido: {e}") from e


def como_se_versiona(datos) -> tuple:
    """(texto, claves quitadas) de un workflow tal como se versiona: solo con
    `CLAVES_DEL_WORKFLOW`, en ese orden, y escrito como los de `n8n/`. Lo que
    no es un workflow (no tiene `nodes`) no se toca: devuelve (None, [])."""
    if not isinstance(datos, dict) or "nodes" not in datos:
        return None, []
    sobran = sorted(set(datos) - set(CLAVES_DEL_WORKFLOW))
    limpio = {c: datos[c] for c in CLAVES_DEL_WORKFLOW if c in datos}
    return json.dumps(limpio, ensure_ascii=False, indent=2) + "\n", sobran


def _dentro_del_repositorio(ruta: Path) -> bool:
    try:
        ruta.resolve().relative_to(REPO)
    except ValueError:
        return False
    return True


def convertir(entrada, salida, valores: dict, quitar: bool = False) -> dict:
    """Lee `entrada`, pone o quita los valores y escribe `salida`. Devuelve
    {marcador: veces} de lo sustituido; al retirar, ademas, en la clave
    `"claves quitadas"`, las del nivel superior que no se versionan."""
    entrada, salida = Path(entrada), Path(salida)
    if not quitar and entrada.resolve() == salida.resolve():
        raise ErrorDeMarcadores(
            "la salida no puede ser la entrada al poner los valores reales: "
            "el export versionado se quedaria con ellos")
    if not quitar and _dentro_del_repositorio(salida):
        raise ErrorDeMarcadores(
            "al poner los valores reales la salida tiene que quedar FUERA del "
            "repositorio (una carpeta temporal): dentro estaria a un `git "
            "add` de distancia")
    texto = leer(entrada)
    try:
        datos = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorDeMarcadores(f"{entrada} no es un JSON valido: {e}") from e
    if quitar:
        versionable, quitadas = como_se_versiona(datos)
        if versionable is not None:
            texto = versionable
        resultado = retirar(texto, valores)
        veces = {m: texto.count(v) for m, v in valores.items() if v in texto}
        veces["claves quitadas"] = quitadas
    else:
        resultado = aplicar(texto, valores)
        veces = {m: texto.count(m) for m in marcadores_de(texto)}
    json.loads(resultado)
    escribir(salida, resultado)
    return veces


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Pone (o, con --retirar, quita) los valores reales de un "
                    "workflow de n8n versionado con marcadores.")
    p.add_argument("--entrada", required=True, help="el JSON que se lee")
    p.add_argument("--salida", required=True, help="el JSON que se escribe")
    p.add_argument("--valores", default=str(VALORES_LOCALES),
                   help="JSON {marcador: valor real} "
                        "(por defecto n8n/valores.local.json)")
    p.add_argument("--retirar", action="store_true",
                   help="valor real -> marcador, para versionar un export")
    a = p.parse_args(argv)
    try:
        veces = convertir(a.entrada, a.salida, leer_valores(a.valores),
                          quitar=a.retirar)
    except ErrorDeMarcadores as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except (OSError, UnicodeDecodeError) as e:
        # un fichero que no existe, que no se puede escribir o que no es UTF-8
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    quitadas = veces.pop("claves quitadas", [])
    verbo = "retirados" if a.retirar else "puestos"
    for marcador in MARCADORES:
        if marcador in veces:
            print(f"{marcador}: {veces[marcador]}")
    if quitadas:
        print("claves de la instancia que no se versionan, quitadas: "
              + ", ".join(quitadas))
    print(f"valores {verbo}: {sum(veces.values())} sustituciones -> {a.salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
