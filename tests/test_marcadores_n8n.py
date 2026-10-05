# -*- coding: utf-8 -*-
"""scripts/marcadores_n8n.py: poner y quitar los valores reales de los workflows.

Los exports de `n8n/` se versionan con marcadores (spec de SP5 §6.1) y ya no
son identicos byte a byte a lo desplegado. Aqui se prueba la herramienta que
media entre los dos, sin n8n y sin red: con valores inventados.
"""
import importlib.util
import json
import os
import pathlib
import stat

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
N8N = RAIZ / "n8n"
EJEMPLO = N8N / "valores.ejemplo.json"

# Las pruebas que comparan lo escrito con lo versionado lo hacen sobre un
# booleano: pytest enseñaria la linea que difiere, y si en lo versionado se
# colara un valor (un `chat_equipo` relleno) saldria en la salida.
IGUAL_A_LO_VERSIONADO = ("lo escrito no es letra por letra lo versionado: "
                         "miralo con git diff")


def _cargar():
    ruta = RAIZ / "scripts" / "marcadores_n8n.py"
    spec = importlib.util.spec_from_file_location("marcadores_n8n", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def mn():
    return _cargar()


@pytest.fixture()
def valores(mn):
    """Un valor inventado por marcador, distinto de los de ejemplo."""
    v = {m: f"valor-{i:02d}-inventado" for i, m in enumerate(mn.MARCADORES)}
    v[mn.URL_N8N] = "https://flujos.inventado.test"
    return v


TEXTO = ('{\n  "url": "https://n8n.ejemplo.test/webhook/copiloto-paciente",\n'
         '  "credentials": {"telegramApi": {"id": "CRED_TELEGRAM_PACIENTE", '
         '"name": "bot-paciente"}}\n}\n')

# Lo mismo que TEXTO, pero con forma de workflow y escrito como se versiona:
# es lo que `--retirar` acepta (TEXTO no es un workflow).
FLUJO = json.dumps({
    "name": "flujo de juguete",
    "active": False,
    "nodes": [
        {"name": "Sonda", "type": "n8n-nodes-base.httpRequest",
         "parameters": {"url": "https://n8n.ejemplo.test/webhook/copiloto-paciente"}},
        {"name": "Responder", "type": "n8n-nodes-base.telegram",
         "credentials": {"telegramApi": {"id": "CRED_TELEGRAM_PACIENTE",
                                         "name": "bot-paciente"}}},
    ],
    "connections": {},
    "settings": {},
}, ensure_ascii=False, indent=2) + "\n"


# --------------------------------------------------------------------------
# Las tres funciones
# --------------------------------------------------------------------------
def test_los_marcadores_son_los_del_contrato(mn):
    assert mn.URL_N8N == "https://n8n.ejemplo.test"
    assert set(mn.MARCADORES) == {
        "https://n8n.ejemplo.test",
        "CRED_TELEGRAM_PACIENTE", "CRED_TELEGRAM_PROFESIONAL",
        "CRED_TELEGRAM_AVISOS", "CRED_POSTGRES_COPILOTO",
        "CRED_SECRETO_PACIENTE", "CRED_SECRETO_PROFESIONAL",
        "bot-paciente", "bot-profesional", "bot-avisos"}
    assert len(mn.MARCADORES) == len(set(mn.MARCADORES))


def test_marcadores_de_dice_los_presentes(mn):
    assert mn.marcadores_de(TEXTO) == {
        "https://n8n.ejemplo.test", "CRED_TELEGRAM_PACIENTE", "bot-paciente"}
    assert mn.marcadores_de("nada que ver") == set()


def test_aplicar_pone_los_valores_y_retirar_los_quita(mn, valores):
    puesto = mn.aplicar(TEXTO, valores)
    assert '"url": "https://flujos.inventado.test/webhook/copiloto-paciente"' in puesto
    assert f'"id": "{valores["CRED_TELEGRAM_PACIENTE"]}"' in puesto
    assert f'"name": "{valores["bot-paciente"]}"' in puesto
    assert mn.marcadores_de(puesto) == set()
    assert mn.retirar(puesto, valores) == TEXTO


def test_aplicar_solo_pide_los_valores_de_los_marcadores_presentes(mn, valores):
    solo = {m: valores[m] for m in mn.marcadores_de(TEXTO)}
    assert mn.aplicar(TEXTO, solo) == mn.aplicar(TEXTO, valores)


def test_la_sustitucion_es_de_una_sola_pasada(mn, valores):
    """Lo que se acaba de poner no se vuelve a sustituir, ni de ida ni de
    vuelta: el texto de alrededor no cambia."""
    texto = "antes https://n8n.ejemplo.test/webhook/x despues bot-avisos."
    puesto = mn.aplicar(texto, valores)
    assert puesto == ("antes https://flujos.inventado.test/webhook/x despues "
                      + valores["bot-avisos"] + ".")
    assert mn.retirar(puesto, valores) == texto


# --------------------------------------------------------------------------
# Los errores
# --------------------------------------------------------------------------
def test_falta_el_valor_de_un_marcador_presente(mn, valores):
    del valores["CRED_TELEGRAM_PACIENTE"]
    with pytest.raises(mn.ErrorDeMarcadores, match="CRED_TELEGRAM_PACIENTE"):
        mn.aplicar(TEXTO, valores)


def test_retirar_exige_el_valor_de_todos_los_marcadores(mn, valores):
    """El que falte no se podria buscar: el export saldria con el en claro."""
    del valores["bot-avisos"]
    with pytest.raises(mn.ErrorDeMarcadores, match="bot-avisos"):
        mn.retirar(TEXTO, valores)


def test_dos_marcadores_no_pueden_compartir_valor(mn, valores):
    valores["CRED_TELEGRAM_AVISOS"] = valores["CRED_TELEGRAM_PACIENTE"]
    for funcion in (mn.aplicar, mn.retirar):
        with pytest.raises(mn.ErrorDeMarcadores, match="comparten valor") as e:
            funcion(TEXTO, valores)
        assert "CRED_TELEGRAM_AVISOS" in str(e.value)
        assert "CRED_TELEGRAM_PACIENTE" in str(e.value)


def test_queda_un_valor_real_tras_retirar(mn, valores):
    """Escrito de otra forma -en mayusculas, o el host sin el esquema- la
    sustitucion exacta no lo ve. Se dice la linea y el marcador, no el valor."""
    en_mayusculas = TEXTO + valores["bot-paciente"].upper() + "\n"
    with pytest.raises(mn.ErrorDeMarcadores, match="quedan valores reales") as e:
        mn.retirar(en_mayusculas, valores)
    assert "bot-paciente en la linea 5" in str(e.value)
    assert valores["bot-paciente"].upper() not in str(e.value)

    solo_el_host = TEXTO + "  visita flujos.inventado.test\n"
    with pytest.raises(mn.ErrorDeMarcadores, match="quedan valores reales") as e:
        mn.retirar(solo_el_host, valores)
    assert "https://n8n.ejemplo.test en la linea 5" in str(e.value)


def test_aplicar_no_acepta_una_entrada_que_ya_lleva_valores_reales(mn, valores):
    mezcla = TEXTO + valores["CRED_POSTGRES_COPILOTO"] + "\n"
    with pytest.raises(mn.ErrorDeMarcadores, match="ya lleva valores reales"):
        mn.aplicar(mezcla, valores)


@pytest.mark.parametrize("malo, dice", [
    ("", "vacio"),
    ("   ", "vacio"),
    (' con-espacio', "espacios"),
    ('con"comilla', "comillas"),
    ("con\\barra", "comillas"),
    ("con\nsalto", "comillas"),
])
def test_un_valor_que_romperia_el_json_no_se_acepta(mn, valores, malo, dice):
    valores["bot-paciente"] = malo
    with pytest.raises(mn.ErrorDeMarcadores, match=dice):
        mn.aplicar(TEXTO, valores)


def test_un_valor_que_no_es_texto_no_se_acepta(mn, valores):
    valores["bot-paciente"] = 7
    with pytest.raises(mn.ErrorDeMarcadores, match="vacio"):
        mn.aplicar(TEXTO, valores)
    with pytest.raises(mn.ErrorDeMarcadores, match="objeto JSON"):
        mn.aplicar(TEXTO, ["lista"])


@pytest.mark.parametrize("errata, parecido", [
    ("CRED_TELEGRAM_PACEINTE", "CRED_TELEGRAM_PACIENTE"),
    ("bot-pacinete", "bot-paciente"),
])
def test_un_marcador_desconocido_en_los_valores_es_un_error(mn, valores, errata, parecido):
    """Se dice cuantas claves no son marcadores y, de las que tienen forma de
    marcador, el conocido mas parecido; nunca la clave tal como viene: una con
    forma `bot-...` puede ser el nombre real de un bot."""
    valores[errata] = "errata"
    with pytest.raises(mn.ErrorDeMarcadores, match="desconocid") as e:
        mn.aplicar(TEXTO, valores)
    assert parecido in str(e.value)
    assert "1 clave" in str(e.value)
    assert errata not in str(e.value)


def test_con_los_valores_al_reves_el_error_no_imprime_ninguno(mn, valores):
    """El despiste natural es escribir {valor real: marcador}, que es el
    sentido en que trabaja `retirar`. El error no puede repetir las claves:
    serian todos los valores reales, en la consola de quien despliega."""
    al_reves = {v: m for m, v in valores.items()}
    for funcion in (mn.aplicar, mn.retirar):
        with pytest.raises(mn.ErrorDeMarcadores, match="al reves") as e:
            funcion(TEXTO, al_reves)
        for valor in valores.values():
            assert valor not in str(e.value)
        assert f"{len(valores)} claves que no son marcadores" in str(e.value)
    # una errata entre valores reales: se dice el marcador que se parece a la
    # errata, y de lo demas, cuantas; ni la errata ni los valores
    mezcla = dict(al_reves, CRED_TELEGRAM_PACEINTE="errata")
    with pytest.raises(mn.ErrorDeMarcadores, match="CRED_TELEGRAM_PACIENTE") as e:
        mn.aplicar(TEXTO, mezcla)
    assert all(valor not in str(e.value) for valor in valores.values())
    assert "CRED_TELEGRAM_PACEINTE" not in str(e.value)
    assert f"{len(valores)} claves que no son marcadores" in str(e.value)


@pytest.mark.parametrize("url", [
    "https://flujos.inventado.test/", "flujos.inventado.test", "ftp://x.test",
    # esquema y host, y nada mas: una ruta acabaria delante de /webhook/
    "https://flujos.inventado.test/n8n", "https://flujos.inventado.test/n8n/",
    "https://flujos.inventado.test?x=1", "https://flujos.inventado.test#arriba",
    "https://", "https://:5678", "https://flujos inventado.test",
    "https://alguien@flujos.inventado.test"])
def test_la_url_va_con_esquema_y_sin_barra_final(mn, valores, url):
    valores[mn.URL_N8N] = url
    with pytest.raises(mn.ErrorDeMarcadores, match="URL base"):
        mn.aplicar(TEXTO, valores)


@pytest.mark.parametrize("url", [
    "https://flujos.inventado.test", "http://flujos.inventado.test:5678"])
def test_la_url_con_esquema_host_y_puerto_se_acepta(mn, valores, url):
    valores[mn.URL_N8N] = url
    assert f'"url": "{url}/webhook/copiloto-paciente"' in mn.aplicar(TEXTO, valores)


def test_un_valor_no_puede_confundirse_con_un_marcador_ni_con_otro_valor(mn, valores):
    malo = dict(valores, **{"bot-paciente": "CRED_TELEGRAM_AVISOS"})
    with pytest.raises(mn.ErrorDeMarcadores, match="se confunde con el marcador"):
        mn.aplicar(TEXTO, malo)
    malo = dict(valores, **{"bot-paciente": "paciente"})
    with pytest.raises(mn.ErrorDeMarcadores, match="se confunde con el marcador"):
        mn.aplicar(TEXTO, malo)
    malo = dict(valores, **{"bot-paciente": valores["bot-avisos"][:-3]})
    with pytest.raises(mn.ErrorDeMarcadores, match="contenido en el de bot-avisos"):
        mn.aplicar(TEXTO, malo)


# --------------------------------------------------------------------------
# La linea de comandos
# --------------------------------------------------------------------------
@pytest.fixture()
def carpeta(tmp_path, valores):
    (tmp_path / "valores.json").write_text(json.dumps(valores), encoding="utf-8")
    (tmp_path / "entrada.json").write_bytes(FLUJO.replace("\n", "\r\n").encode("utf-8"))
    return tmp_path


def test_la_cli_pone_y_quita_y_escribe_en_lf(mn, carpeta, valores, capsys):
    argumentos = ["--valores", str(carpeta / "valores.json")]
    assert mn.main(argumentos + ["--entrada", str(carpeta / "entrada.json"),
                                 "--salida", str(carpeta / "sub" / "puesto.json")]) == 0
    dicho = capsys.readouterr().out
    assert "CRED_TELEGRAM_PACIENTE: 1" in dicho
    assert "valores puestos: 3 sustituciones" in dicho
    crudo = (carpeta / "sub" / "puesto.json").read_bytes()
    assert b"\r" not in crudo
    assert crudo.decode("utf-8") == mn.aplicar(FLUJO, valores)

    assert mn.main(argumentos + ["--retirar",
                                 "--entrada", str(carpeta / "sub" / "puesto.json"),
                                 "--salida", str(carpeta / "vuelta.json")]) == 0
    assert "valores retirados: 3 sustituciones" in capsys.readouterr().out
    assert (carpeta / "vuelta.json").read_bytes() == FLUJO.encode("utf-8")


def test_la_cli_lee_ficheros_con_marca_de_orden_de_bytes(mn, carpeta, valores, capsys):
    """PowerShell 5.1 escribe los JSON con la marca (`Out-File`, `Set-Content
    -Encoding utf8`): los valores y la entrada se leen igual con ella."""
    (carpeta / "valores-bom.json").write_text(json.dumps(valores), encoding="utf-8-sig")
    (carpeta / "entrada-bom.json").write_text(FLUJO, encoding="utf-8-sig")
    assert mn.main(["--valores", str(carpeta / "valores-bom.json"),
                    "--entrada", str(carpeta / "entrada-bom.json"),
                    "--salida", str(carpeta / "puesto.json")]) == 0, capsys.readouterr().err
    assert (carpeta / "puesto.json").read_bytes() == mn.aplicar(FLUJO, valores).encode("utf-8")
    assert mn.leer_valores(carpeta / "valores-bom.json") == valores


def test_la_cli_no_pone_valores_reales_encima_de_la_entrada(mn, carpeta, capsys):
    antes = (carpeta / "entrada.json").read_bytes()
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "entrada.json")]) == 1
    assert "la salida no puede ser la entrada" in capsys.readouterr().err
    assert (carpeta / "entrada.json").read_bytes() == antes


def test_la_cli_no_pone_valores_reales_dentro_del_repositorio(
        mn, carpeta, monkeypatch, capsys):
    """Ni encima de otro export ni en un fichero nuevo: lo que se escribe
    dentro del repositorio esta a un `git add` de distancia. El repositorio
    de esta prueba es una carpeta temporal: si la guarda faltara, la prueba
    escribiria ahi y no en el de verdad."""
    repositorio = carpeta / "repositorio"
    (repositorio / "n8n").mkdir(parents=True)
    (repositorio / "n8n" / "otro-export.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(mn, "REPO", repositorio)
    for destino in (repositorio / "n8n" / "otro-export.json",
                    repositorio / "n8n" / "nuevo.json", repositorio / "nuevo.json"):
        antes = destino.read_bytes() if destino.exists() else None
        assert mn.main(["--valores", str(carpeta / "valores.json"),
                        "--entrada", str(carpeta / "entrada.json"),
                        "--salida", str(destino)]) == 1
        assert "FUERA del repositorio" in capsys.readouterr().err
        assert (destino.read_bytes() if destino.exists() else None) == antes
    # fuera del repositorio, si
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "fuera.json")]) == 0


def test_la_cli_retira_encima_de_la_entrada(mn, carpeta, valores):
    (carpeta / "export.json").write_text(mn.aplicar(FLUJO, valores), encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"), "--retirar",
                    "--entrada", str(carpeta / "export.json"),
                    "--salida", str(carpeta / "export.json")]) == 0
    assert (carpeta / "export.json").read_bytes() == FLUJO.encode("utf-8")


def test_escribir_no_deja_el_destino_a_medias(mn, tmp_path):
    """Se escribe a un temporal junto al destino y se pone en su sitio al
    final: si la escritura falla, el destino queda como estaba y el temporal
    no se queda en la carpeta. Un sustituto suelto no se puede escribir en
    UTF-8."""
    destino = tmp_path / "flujo.json"
    destino.write_bytes(b'{"antes": true}\n')
    with pytest.raises(UnicodeEncodeError):
        mn.escribir(destino, '{"nota": "a medias \ud800"}\n')
    assert destino.read_bytes() == b'{"antes": true}\n'
    assert [p.name for p in tmp_path.iterdir()] == ["flujo.json"]

    mn.escribir(destino, '{"despues": true}\n')
    assert destino.read_bytes() == b'{"despues": true}\n'
    assert [p.name for p in tmp_path.iterdir()] == ["flujo.json"]


def test_con_el_destino_de_solo_lectura_el_temporal_no_se_queda(mn, tmp_path, monkeypatch):
    """Al PONER valores, el temporal lleva los valores reales: si la escritura
    falla, no puede quedarse en la carpeta. Windows se niega a reemplazar un
    fichero de solo lectura, y el temporal, que copio sus permisos, tampoco se
    dejaba borrar. En los demas sistemas el reemplazo pisaria el fichero: alli
    se simula la negativa."""
    destino = tmp_path / "flujo.json"
    destino.write_bytes(b'{"antes": true}\n')
    os.chmod(destino, stat.S_IREAD)
    if os.name != "nt":
        def negarse(*a, **k):
            raise PermissionError("el destino es de solo lectura")
        monkeypatch.setattr(mn.os, "replace", negarse)
    try:
        with pytest.raises(OSError):
            mn.escribir(destino, '{"despues": "valor-real"}\n')
        assert [p.name for p in tmp_path.iterdir()] == ["flujo.json"]
        assert destino.read_bytes() == b'{"antes": true}\n'
    finally:
        os.chmod(destino, stat.S_IREAD | stat.S_IWRITE)


def test_la_cli_dice_el_error_si_lo_retirado_no_se_puede_escribir(
        mn, carpeta, valores, capsys):
    """Una descarga con un sustituto suelto escapado (`\\ud800`) en una nota:
    al reescribirla como se versiona sale el caracter, que no cabe en UTF-8.
    La orden sale con 1 y el destino, que existia, sigue como estaba."""
    flujo = json.loads(mn.aplicar(FLUJO, valores))
    flujo["nodes"][0]["notes"] = "a medias \ud800"
    (carpeta / "descarga.json").write_text(json.dumps(flujo), encoding="utf-8")
    (carpeta / "destino.json").write_bytes(b"lo de antes\n")
    assert mn.main(["--valores", str(carpeta / "valores.json"), "--retirar",
                    "--entrada", str(carpeta / "descarga.json"),
                    "--salida", str(carpeta / "destino.json")]) == 1
    assert capsys.readouterr().err.startswith("ERROR: UnicodeEncodeError")
    assert (carpeta / "destino.json").read_bytes() == b"lo de antes\n"
    assert sorted(p.name for p in carpeta.iterdir()) == [
        "descarga.json", "destino.json", "entrada.json", "valores.json"]


def test_la_cli_dice_que_hacer_si_no_hay_fichero_de_valores(mn, carpeta, capsys):
    assert mn.main(["--valores", str(carpeta / "no-existe.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "salida.json")]) == 1
    error = capsys.readouterr().err
    assert "ERROR" in error and "valores.ejemplo.json" in error
    assert not (carpeta / "salida.json").exists()


def test_la_cli_no_escribe_nada_si_hay_un_error(mn, carpeta, valores, capsys):
    del valores["bot-paciente"]
    (carpeta / "valores.json").write_text(json.dumps(valores), encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "salida.json")]) == 1
    assert "bot-paciente" in capsys.readouterr().err
    assert not (carpeta / "salida.json").exists()

    (carpeta / "roto.json").write_text("{ esto no es json", encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "roto.json"),
                    "--salida", str(carpeta / "salida.json")]) == 1
    assert "no es un JSON valido" in capsys.readouterr().err


def test_la_cli_dice_el_error_si_un_fichero_no_se_puede_leer(mn, carpeta, capsys):
    argumentos = ["--valores", str(carpeta / "valores.json"),
                  "--salida", str(carpeta / "salida.json")]
    assert mn.main(argumentos + ["--entrada", str(carpeta / "no-existe.json")]) == 1
    assert capsys.readouterr().err.startswith("ERROR: FileNotFoundError")
    (carpeta / "latin1.json").write_bytes('{"nota": "señal"}'.encode("latin-1"))
    assert mn.main(argumentos + ["--entrada", str(carpeta / "latin1.json")]) == 1
    assert capsys.readouterr().err.startswith("ERROR: UnicodeDecodeError")
    assert not (carpeta / "salida.json").exists()


def test_los_valores_por_defecto_son_los_locales_y_git_los_ignora(mn):
    assert mn.VALORES_LOCALES == N8N / "valores.local.json"
    ignorados = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "n8n/valores.local.json" in ignorados


def test_los_valores_de_ejemplo_son_validos_y_cubren_todos_los_marcadores(mn):
    ejemplo = mn.leer_valores(EJEMPLO)
    assert set(ejemplo) == set(mn.MARCADORES)
    assert mn.retirar(mn.aplicar(TEXTO, ejemplo), ejemplo) == TEXTO


# --------------------------------------------------------------------------
# Los tres workflows versionados
# --------------------------------------------------------------------------
FLUJOS = ("copiloto-paciente.json", "copiloto-profesional.json",
          "copiloto-mantenimiento.json")

# Por fichero y por tipo de credencial: (id, name, cuantos nodos la usan).
CREDENCIALES = {
    "copiloto-paciente.json": {
        "telegramApi": ("CRED_TELEGRAM_PACIENTE", "bot-paciente", 12),
        "postgres": ("CRED_POSTGRES_COPILOTO", "copiloto-bd", 5),
        "httpHeaderAuth": ("CRED_SECRETO_PACIENTE",
                           "copiloto-paciente: secret_token del webhook", 1),
    },
    "copiloto-profesional.json": {
        "telegramApi": ("CRED_TELEGRAM_PROFESIONAL", "bot-profesional", 9),
        "postgres": ("CRED_POSTGRES_COPILOTO", "copiloto-bd", 5),
        "httpHeaderAuth": ("CRED_SECRETO_PROFESIONAL",
                           "copiloto-profesional: secret_token del webhook", 1),
    },
    "copiloto-mantenimiento.json": {
        "telegramApi": ("CRED_TELEGRAM_AVISOS", "bot-avisos", 1),
        "postgres": ("CRED_POSTGRES_COPILOTO", "copiloto-bd", 4),
    },
}

# Cuantas veces aparece cada marcador en cada workflow. Un marcador de mas es
# una cadena nueva que `aplicar` sustituiria sin avisar al desplegar: si cae
# en el `jsCode` de un nodo, cambia el programa del bot.
VECES = {
    "copiloto-paciente.json": {
        "https://n8n.ejemplo.test": 1, "CRED_TELEGRAM_PACIENTE": 12,
        "CRED_POSTGRES_COPILOTO": 5, "CRED_SECRETO_PACIENTE": 1, "bot-paciente": 12},
    "copiloto-profesional.json": {
        "https://n8n.ejemplo.test": 1, "CRED_TELEGRAM_PROFESIONAL": 9,
        "CRED_POSTGRES_COPILOTO": 5, "CRED_SECRETO_PROFESIONAL": 1, "bot-profesional": 9},
    "copiloto-mantenimiento.json": {
        "https://n8n.ejemplo.test": 2, "CRED_TELEGRAM_AVISOS": 1,
        "CRED_POSTGRES_COPILOTO": 4, "bot-avisos": 2},
}

# Lo que no es de la instancia y por eso se queda como esta: el copiloto se
# llama por el nombre de su servicio en la red de Docker.
URL_INTERNA = "http://copiloto-mcp:8000/"


def _nodos(fichero):
    return json.loads((N8N / fichero).read_text(encoding="utf-8"))["nodes"]


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_credenciales_de_los_workflows_son_marcadores(mn, fichero):
    # Si falla se dice el nodo, y no la credencial que lleva: lo que imprime
    # una prueba tambien se puede publicar.
    vistas = {}
    for n in _nodos(fichero):
        for tipo, c in (n.get("credentials") or {}).items():
            assert set(c) == {"id", "name"}, (n["name"], sorted(c))
            vistas.setdefault(tipo, []).append((n["name"], c["id"], c["name"]))
    esperadas = CREDENCIALES[fichero]
    assert set(vistas) == set(esperadas)
    for tipo, (ident, nombre, cuantos) in esperadas.items():
        con_otra = [nodo for nodo, i, nm in vistas[tipo] if (i, nm) != (ident, nombre)]
        assert con_otra == [], (fichero, tipo)
        nodos = len(vistas[tipo])
        assert nodos == cuantos, (fichero, tipo)
        assert ident in mn.MARCADORES


@pytest.mark.parametrize("fichero", FLUJOS)
def test_cada_marcador_aparece_las_veces_previstas(mn, fichero):
    texto = mn.leer(N8N / fichero)
    assert {m: texto.count(m) for m in mn.marcadores_de(texto)} == VECES[fichero]


@pytest.mark.parametrize("fichero", FLUJOS)
def test_los_workflows_se_versionan_solo_con_sus_cinco_claves(mn, fichero):
    """Una descarga de n8n trae ademas el `id` del workflow, su `versionId`,
    la huella de la instancia (`meta`), `pinData` y `tags`: son de la
    instancia, como el dominio. Y lo versionado esta escrito de una sola
    manera, la de `como_se_versiona`."""
    texto = mn.leer(N8N / fichero)
    assert tuple(json.loads(texto)) == mn.CLAVES_DEL_WORKFLOW
    assert mn.como_se_versiona(json.loads(texto)) == (texto, [])


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_url_de_los_nodos_http_son_el_marcador_o_la_interna(mn, fichero):
    for n in _nodos(fichero):
        if n["type"] != "n8n-nodes-base.httpRequest":
            continue
        url = n["parameters"]["url"]
        conocida = (url.startswith(mn.URL_N8N + "/webhook/")
                    or url.startswith(URL_INTERNA))
        assert conocida, (fichero, n["name"])


def test_las_dos_sondas_apuntan_al_marcador(mn):
    sondas = {n["name"]: n["parameters"]["url"]
              for n in _nodos("copiloto-mantenimiento.json")
              if n["type"] == "n8n-nodes-base.httpRequest"
              and "/webhook/" in n["parameters"]["url"]}
    esperadas = {
        "Webhook del paciente": "https://n8n.ejemplo.test/webhook/copiloto-paciente",
        "Webhook del profesional": "https://n8n.ejemplo.test/webhook/copiloto-profesional",
    }
    assert sorted(sondas) == sorted(esperadas)
    a_otro_sitio = [nombre for nombre in esperadas if sondas[nombre] != esperadas[nombre]]
    assert a_otro_sitio == []


@pytest.mark.parametrize("fichero, ruta, token", [
    ("copiloto-paciente.json", "copiloto-paciente", "<TOKEN>"),
    ("copiloto-profesional.json", "copiloto-profesional",
     "<TOKEN_DEL_BOT_DEL_PROFESIONAL>"),
])
def test_la_nota_del_webhook_registra_con_el_marcador(fichero, ruta, token):
    (nota,) = [n["notes"] for n in _nodos(fichero)
               if n["type"] == "n8n-nodes-base.webhook"]
    con_el_marcador = (f'"https://api.telegram.org/bot{token}/setWebhook" '
                       f"-d url=https://n8n.ejemplo.test/webhook/{ruta} ") in nota
    assert con_el_marcador, fichero


def test_cada_marcador_aparece_en_algun_workflow_y_al_reves(mn):
    import re
    ejemplo = mn.leer_valores(EJEMPLO)
    presentes, con_forma_de_marcador = set(), set()
    for fichero in FLUJOS:
        texto = mn.leer(N8N / fichero)
        presentes |= mn.marcadores_de(texto)
        con_forma_de_marcador |= set(re.findall(r"\bCRED_[A-Z0-9_]+", texto))
        con_forma_de_marcador |= set(
            re.findall(r"https?://[A-Za-z0-9.-]*ejemplo\.test", texto))
        con_forma_de_marcador |= set(re.findall(r"\bbot-[a-z]+", texto))
    assert presentes == set(mn.MARCADORES) == set(ejemplo)
    assert con_forma_de_marcador == set(mn.MARCADORES)


@pytest.mark.parametrize("fichero", FLUJOS)
def test_ida_y_vuelta_con_los_valores_de_ejemplo(mn, fichero):
    ejemplo = mn.leer_valores(EJEMPLO)
    texto = mn.leer(N8N / fichero)
    puesto = mn.aplicar(texto, ejemplo)
    assert puesto != texto
    assert mn.marcadores_de(puesto) == set()
    assert len(json.loads(puesto)["nodes"]) == len(json.loads(texto)["nodes"])
    assert mn.retirar(puesto, ejemplo) == texto


@pytest.mark.parametrize("fichero", FLUJOS)
def test_retirar_una_descarga_de_n8n_quita_lo_que_es_de_la_instancia(
        mn, fichero, tmp_path, capsys):
    """Como lo descarga n8n: con su id, su version, la huella de la instancia,
    datos de una ejecucion y etiquetas; con las claves en otro orden y con
    otra sangria. Lo que sale es, letra por letra, lo versionado."""
    ejemplo = mn.leer_valores(EJEMPLO)
    versionado = mn.leer(N8N / fichero)
    desplegado = json.loads(mn.aplicar(versionado, ejemplo))
    descarga = {"id": "wf-de-la-instancia", "versionId": "version-de-la-instancia",
                "meta": {"instanceId": "huella-de-la-instancia"},
                "pinData": {"Un nodo": [{"json": {"dato": "de-una-ejecucion"}}]},
                "tags": [{"id": "etiqueta-de-la-instancia", "name": "produccion"}]}
    descarga.update({c: desplegado[c] for c in reversed(mn.CLAVES_DEL_WORKFLOW)})
    (tmp_path / "descarga.json").write_text(
        json.dumps(descarga, ensure_ascii=False, indent=4), encoding="utf-8")

    assert mn.main(["--valores", str(EJEMPLO), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 0

    # sobre un booleano: pytest enseñaria la linea que difiere, y en lo
    # versionado podria ir un valor (un chat_equipo relleno)
    igual = mn.leer(tmp_path / "versionable.json") == versionado
    assert igual, IGUAL_A_LO_VERSIONADO
    dicho = capsys.readouterr().out
    assert "quitadas: id, meta, pinData, tags, versionId" in dicho
    for de_la_instancia in ("wf-de-la-instancia", "version-de-la-instancia",
                            "huella-de-la-instancia", "de-una-ejecucion",
                            "etiqueta-de-la-instancia"):
        assert de_la_instancia not in dicho
        assert de_la_instancia not in mn.leer(tmp_path / "versionable.json")


def _descarga(mn, fichero, valores, **en_la_instancia):
    """Un workflow versionado como lo descarga n8n de una instancia con estos
    `valores`: puestos, con las claves de la instancia y lo que se le pase."""
    desplegado = json.loads(mn.aplicar(mn.leer(N8N / fichero), valores))
    desplegado.update({"id": "wf-de-la-instancia",
                       "versionId": "version-de-la-instancia"}, **en_la_instancia)
    return desplegado


def _chat_equipo(flujo):
    """Las asignaciones `chat_equipo` del nodo `Configuracion`."""
    return [a for n in flujo["nodes"] if n["name"] == "Configuracion"
            for a in n["parameters"]["assignments"]["assignments"]
            if a["name"] == "chat_equipo"]


def test_retirar_el_mantenimiento_vacia_el_chat_del_equipo(mn, valores, tmp_path, capsys):
    """Desplegado, `chat_equipo` va relleno en n8n (§5 del manual): es el
    chat_id de una persona y no se versiona. Al retirar se vacia, y la orden
    lo dice sin repetirlo."""
    chat = "4455667788"   # inventado
    descarga = _descarga(mn, "copiloto-mantenimiento.json", valores)
    (asignacion,) = _chat_equipo(descarga)
    asignacion["value"] = chat
    (tmp_path / "valores.json").write_text(json.dumps(valores), encoding="utf-8")
    (tmp_path / "descarga.json").write_text(json.dumps(descarga, indent=4),
                                            encoding="utf-8")

    assert mn.main(["--valores", str(tmp_path / "valores.json"), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 0

    escrito = mn.leer(tmp_path / "versionable.json")
    igual = escrito == mn.leer(N8N / "copiloto-mantenimiento.json")
    assert igual, IGUAL_A_LO_VERSIONADO
    dicho = capsys.readouterr()
    assert "chat_equipo: vaciado" in dicho.out
    assert chat not in escrito and chat not in dicho.out + dicho.err


def test_el_chat_del_equipo_del_mantenimiento_versionado_va_vacio():
    """El manual manda correr este fichero despues de retirar un export: asi
    caza un `chat_equipo` relleno sin tener que nombrar
    `tests/test_mantenimiento.py`. Si falla no enseña el valor."""
    flujo = json.loads((N8N / "copiloto-mantenimiento.json").read_text(encoding="utf-8"))
    asignaciones = _chat_equipo(flujo)
    assert len(asignaciones) == 1
    vacio = asignaciones[0]["value"] == ""
    assert vacio, ("chat_equipo va relleno en n8n/copiloto-mantenimiento.json: "
                   "retira el export con scripts/marcadores_n8n.py, que lo vacia")


@pytest.mark.parametrize("fichero", FLUJOS)
def test_retirar_con_otros_valores_que_los_de_la_descarga_no_escribe(
        mn, fichero, valores, tmp_path, capsys):
    """Con unos valores que no son los de la instancia (los de ejemplo, un
    `valores.local.json` anticuado) no se sustituye nada, y el workflow se
    escribiria en `n8n/` con los identificadores de la instancia. Tras
    retirar, las credenciales y las URL de los webhooks tienen que ser
    marcadores: si no, no se escribe, y el error dice el nodo y no el valor."""
    ejemplo = mn.leer_valores(EJEMPLO)
    (tmp_path / "descarga.json").write_text(
        json.dumps(_descarga(mn, fichero, valores), indent=4), encoding="utf-8")

    assert mn.main(["--valores", str(EJEMPLO), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 1

    assert not (tmp_path / "versionable.json").exists()
    dicho = capsys.readouterr()
    for valor in list(valores.values()) + list(ejemplo.values()):
        assert valor not in dicho.err + dicho.out
    assert "no son marcadores" in dicho.err
    # el nodo, que es del workflow versionado
    telegram = {"copiloto-paciente.json": "Pedir consentimiento",
                "copiloto-profesional.json": "Pedir codigo",
                "copiloto-mantenimiento.json": "Avisar al equipo"}[fichero]
    assert telegram in dicho.err
    if fichero == "copiloto-mantenimiento.json":
        assert "Webhook del paciente" in dicho.err


# Una sola clave anticuada cada vez: el marcador cuyo valor esta mal en los
# valores con los que se retira, la frase del error de ESA condicion y un nodo
# que la lleva. Si una de las condiciones se quitara, su caso caeria.
ANTICUADAS = [
    ("copiloto-paciente.json", "CRED_POSTGRES_COPILOTO",
     "el id de su credencial postgres", "Leer sesion"),
    ("copiloto-paciente.json", "CRED_SECRETO_PACIENTE",
     "el id de su credencial httpHeaderAuth", "Webhook Telegram (paciente)"),
    ("copiloto-paciente.json", "CRED_TELEGRAM_PACIENTE",
     "el id de su credencial telegramApi", "Pedir consentimiento"),
    ("copiloto-paciente.json", "bot-paciente",
     "el nombre de su credencial telegramApi", "Pedir consentimiento"),
    # la URL solo esta en la nota del nodo webhook
    ("copiloto-paciente.json", "https://n8n.ejemplo.test",
     "la URL de su webhook", "Webhook Telegram (paciente)"),
    ("copiloto-profesional.json", "CRED_POSTGRES_COPILOTO",
     "el id de su credencial postgres", "Leer sesion y permiso"),
    ("copiloto-profesional.json", "CRED_SECRETO_PROFESIONAL",
     "el id de su credencial httpHeaderAuth", "Webhook Telegram (profesional)"),
    ("copiloto-profesional.json", "CRED_TELEGRAM_PROFESIONAL",
     "el id de su credencial telegramApi", "Pedir codigo"),
    ("copiloto-profesional.json", "bot-profesional",
     "el nombre de su credencial telegramApi", "Pedir codigo"),
    ("copiloto-profesional.json", "https://n8n.ejemplo.test",
     "la URL de su webhook", "Webhook Telegram (profesional)"),
    ("copiloto-mantenimiento.json", "CRED_POSTGRES_COPILOTO",
     "el id de su credencial postgres", "Limpieza"),
    ("copiloto-mantenimiento.json", "CRED_TELEGRAM_AVISOS",
     "el id de su credencial telegramApi", "Avisar al equipo"),
    ("copiloto-mantenimiento.json", "bot-avisos",
     "el nombre de su credencial telegramApi", "Avisar al equipo"),
    ("copiloto-mantenimiento.json", "https://n8n.ejemplo.test",
     "la URL de su webhook", "Webhook del paciente"),
]


@pytest.mark.parametrize("fichero, marcador, frase, nodo", ANTICUADAS,
                         ids=[f"{f.split('-')[1][:-5]}-{m}" for f, m, _, _ in ANTICUADAS])
def test_retirar_con_una_sola_clave_anticuada_no_escribe(
        mn, fichero, marcador, frase, nodo, valores, tmp_path, capsys):
    """El `valores.local.json` anticuado de verdad: todo bien menos UN valor
    (una credencial que se volvio a crear, una errata en la URL). Lo que no se
    sustituye se quedaria en `n8n/`: la herramienta se niega, sin escribir,
    diciendo la condicion y el nodo, y ningun valor."""
    anticuados = dict(valores)
    anticuados[marcador] = ("https://anticuada.inventado.test"
                            if marcador == mn.URL_N8N else "valor-99-anticuado")
    (tmp_path / "valores.json").write_text(json.dumps(anticuados), encoding="utf-8")
    (tmp_path / "descarga.json").write_text(
        json.dumps(_descarga(mn, fichero, valores), indent=4), encoding="utf-8")

    assert mn.main(["--valores", str(tmp_path / "valores.json"), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 1

    assert not (tmp_path / "versionable.json").exists()
    dicho = capsys.readouterr()
    con_valores = [m for m, v in list(valores.items()) + list(anticuados.items())
                   if v in dicho.out + dicho.err]
    assert con_valores == [], "la salida lleva el valor de estos marcadores"
    assert f"«{nodo}»: {frase}" in dicho.err


@pytest.mark.parametrize("fichero, nodo", [
    ("copiloto-paciente.json", "Webhook Telegram (paciente)"),
    ("copiloto-mantenimiento.json", "Webhook del paciente"),
])
def test_una_url_que_solo_empieza_como_el_marcador_no_es_el_marcador(
        mn, fichero, nodo, valores, tmp_path, capsys):
    """El marcador va seguido de `/webhook/`: un host que solo EMPIEZA como el
    del marcador es otro host."""
    otro_host = "https://n8n.ejemplo.test.otro"
    texto = mn.aplicar(mn.leer(N8N / fichero), valores).replace(
        valores[mn.URL_N8N], otro_host)
    (tmp_path / "valores.json").write_text(json.dumps(valores), encoding="utf-8")
    (tmp_path / "descarga.json").write_text(texto, encoding="utf-8")

    assert mn.main(["--valores", str(tmp_path / "valores.json"), "--retirar",
                    "--entrada", str(tmp_path / "descarga.json"),
                    "--salida", str(tmp_path / "versionable.json")]) == 1

    assert not (tmp_path / "versionable.json").exists()
    dicho = capsys.readouterr()
    assert f"«{nodo}»: la URL de su webhook" in dicho.err
    sin_el_host = "ejemplo.test.otro" not in dicho.out + dicho.err
    assert sin_el_host


@pytest.mark.parametrize("entrada, dice", [
    ([], "una lista"),
    (["un workflow", "otro"], "una lista"),
    ({"name": "sin nodos", "connections": {}}, "no es un workflow"),
    (json.loads(TEXTO), "no es un workflow"),
])
def test_lo_que_no_es_un_workflow_no_se_retira(mn, carpeta, entrada, dice, capsys):
    """La linea de ordenes de n8n exporta una LISTA de workflows; y un JSON
    sin `nodes` no es un workflow. `--retirar` no los reescribe ni los pasa
    por buenos: se niega, dice que se pase un workflow cada vez, y no escribe
    nada."""
    (carpeta / "export.json").write_text(json.dumps(entrada), encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"), "--retirar",
                    "--entrada", str(carpeta / "export.json"),
                    "--salida", str(carpeta / "salida.json")]) == 1
    error = capsys.readouterr().err
    assert dice in error and "un workflow cada vez" in error
    assert not (carpeta / "salida.json").exists()
    # `como_se_versiona` no los toca
    assert mn.como_se_versiona(entrada) == (None, [])


# Las claves de `settings` que llevan hoy los tres workflows. Una que la
# instancia añada al descargar no pasa sin que alguien lo decida: la de
# `errorWorkflow`, por ejemplo, lleva el `id` de otro workflow de la instancia.
CLAVES_DE_SETTINGS = {
    "executionOrder", "executionTimeout", "saveDataErrorExecution",
    "saveDataSuccessExecution", "saveExecutionProgress", "saveManualExecutions",
    "timezone"}


def _settings_que_sobran(flujo):
    """Los NOMBRES de las claves de `settings` que no estan en la lista; los
    valores no, que pueden ser de la instancia."""
    return sorted(set(flujo["settings"]) - CLAVES_DE_SETTINGS)


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_claves_de_settings_son_las_de_hoy(fichero):
    flujo = json.loads((N8N / fichero).read_text(encoding="utf-8"))
    assert _settings_que_sobran(flujo) == [], fichero
    # y la comprobacion caza la que lleva el id de otro workflow
    con_error = dict(flujo, settings=dict(flujo["settings"],
                                          errorWorkflow="wf-de-la-instancia"))
    assert _settings_que_sobran(con_error) == ["errorWorkflow"]


@pytest.mark.parametrize("fichero", FLUJOS)
def test_la_cli_da_la_vuelta_a_un_workflow_entero(mn, fichero, tmp_path):
    valores = ["--valores", str(EJEMPLO)]
    assert mn.main(valores + ["--entrada", str(N8N / fichero),
                              "--salida", str(tmp_path / "puesto.json")]) == 0
    assert mn.main(valores + ["--retirar",
                              "--entrada", str(tmp_path / "puesto.json"),
                              "--salida", str(tmp_path / "vuelta.json")]) == 0
    igual = (tmp_path / "vuelta.json").read_text(encoding="utf-8") \
        == mn.leer(N8N / fichero)
    assert igual, IGUAL_A_LO_VERSIONADO
