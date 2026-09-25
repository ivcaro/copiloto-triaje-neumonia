# -*- coding: utf-8 -*-
"""Alta y baja de profesionales en la lista blanca (§11 del spec de SP3).

Existe como script y no como una linea de comando porque una consulta con
comillas anidadas dentro de PowerShell es terreno minado: se las come y el
error que sale habla de sintaxis de Python, que manda a mirar donde no es.

Necesita `COPILOTO_BD_DSN` en el entorno, en formato CLAVE-VALOR y no de URL:

    host=127.0.0.1 port=15433 dbname=copiloto user=copiloto password=...

El de URL se rompe si la contrasena lleva `/`, `+`, `:` o `@` -lo que
`openssl rand -base64` produce casi siempre- y el sintoma no es un error de
autenticacion sino `getaddrinfo failed`.

Uso:
    python pruebas/profesionales.py                      # los ultimos intentos
    python pruebas/profesionales.py --listar             # quien esta de alta
    python pruebas/profesionales.py --alta 123 "Dra. X"  # dar de alta
    python pruebas/profesionales.py --baja 123           # dar de baja
"""
import argparse
import os
import sys


def _conectar():
    dsn = os.environ.get("COPILOTO_BD_DSN")
    if not dsn:
        sys.exit("falta COPILOTO_BD_DSN en el entorno (y el tunel SSH abierto)")
    try:
        import psycopg
    except ImportError:
        sys.exit("falta psycopg: pip install 'psycopg[binary]'")
    return psycopg.connect(dsn, autocommit=True, connect_timeout=10)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--listar", action="store_true", help="quien esta de alta")
    p.add_argument("--alta", nargs=2, metavar=("CHAT_ID", "NOMBRE"))
    p.add_argument("--baja", metavar="CHAT_ID")
    args = p.parse_args()

    with _conectar() as c:
        if args.alta:
            chat_id, nombre = int(args.alta[0]), args.alta[1]
            c.execute(
                "INSERT INTO profesionales (chat_id, nombre) VALUES (%s, %s)"
                " ON CONFLICT (chat_id) DO UPDATE SET activo = true,"
                " baja_en = NULL, nombre = EXCLUDED.nombre",
                (chat_id, nombre))
            print(f"alta: {chat_id} — {nombre}")
            return 0

        if args.baja:
            # El nombre se sustituye al dar de baja: es el unico dato personal
            # directo del esquema y deja de hacer falta (§5.4).
            n = c.execute(
                "UPDATE profesionales SET activo = false, baja_en = now(),"
                " nombre = '(dado de baja)' WHERE chat_id = %s",
                (int(args.baja),)).rowcount
            print(f"baja: {args.baja}" if n else f"no existia: {args.baja}")
            return 0

        if args.listar:
            filas = c.execute(
                "SELECT chat_id, nombre, activo, alta_en FROM profesionales"
                " ORDER BY alta_en").fetchall()
            if not filas:
                print("la lista blanca esta vacia: nadie puede usar el bot")
            for chat_id, nombre, activo, alta in filas:
                print(f"  {chat_id:<14} {'activo ' if activo else 'de baja'}"
                      f"  {nombre}  (alta {alta:%Y-%m-%d %H:%M})")
            return 0

        # Por defecto: los intentos recientes de gente NO autorizada, que es de
        # donde se leen los chat_id para dar de alta (§11).
        filas = c.execute(
            "SELECT chat_id, max(creado_en) AS ultimo, count(*) AS intentos"
            " FROM consultas WHERE error LIKE 'no_autorizado%'"
            " GROUP BY chat_id ORDER BY ultimo DESC LIMIT 10").fetchall()
        if not filas:
            print("ningun intento no autorizado todavia.")
            print("Escribele /start al bot y vuelve a correr esto.")
        for chat_id, ultimo, intentos in filas:
            print(f"  chat_id {chat_id:<14} ultimo {ultimo:%Y-%m-%d %H:%M}"
                  f"  ({intentos} intento{'s' if intentos > 1 else ''})")
            print(f"      alta:  python pruebas/profesionales.py --alta "
                  f"{chat_id} \"Dr./Dra. Apellido\"")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
