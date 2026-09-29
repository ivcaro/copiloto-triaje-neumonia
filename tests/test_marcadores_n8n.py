# -*- coding: utf-8 -*-
"""scripts/marcadores_n8n.py: poner y quitar los valores reales de los workflows.

Los exports de `n8n/` se versionan con marcadores (spec de SP5 §6.1) y ya no
son identicos byte a byte a lo desplegado. Aqui se prueba la herramienta que
media entre los dos, sin n8n y sin red: con valores inventados.
"""
import importlib.util
import json
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
N8N = RAIZ / "n8n"
EJEMPLO = N8N / "valores.ejemplo.json"


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


def test_un_marcador_desconocido_en_los_valores_es_un_error(mn, valores):
    valores["CRED_TELEGRAM_PACIENT"] = "errata"
    with pytest.raises(mn.ErrorDeMarcadores, match="desconocidos.*CRED_TELEGRAM_PACIENT"):
        mn.aplicar(TEXTO, valores)


@pytest.mark.parametrize("url", [
    "https://flujos.inventado.test/", "flujos.inventado.test", "ftp://x.test"])
def test_la_url_va_con_esquema_y_sin_barra_final(mn, valores, url):
    valores[mn.URL_N8N] = url
    with pytest.raises(mn.ErrorDeMarcadores, match="URL base"):
        mn.aplicar(TEXTO, valores)


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
    (tmp_path / "entrada.json").write_bytes(TEXTO.replace("\n", "\r\n").encode("utf-8"))
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
    assert crudo.decode("utf-8") == mn.aplicar(TEXTO, valores)

    assert mn.main(argumentos + ["--retirar",
                                 "--entrada", str(carpeta / "sub" / "puesto.json"),
                                 "--salida", str(carpeta / "vuelta.json")]) == 0
    assert "valores retirados: 3 sustituciones" in capsys.readouterr().out
    assert (carpeta / "vuelta.json").read_bytes() == TEXTO.encode("utf-8")


def test_la_cli_no_pone_valores_reales_encima_de_la_entrada(mn, carpeta, capsys):
    antes = (carpeta / "entrada.json").read_bytes()
    assert mn.main(["--valores", str(carpeta / "valores.json"),
                    "--entrada", str(carpeta / "entrada.json"),
                    "--salida", str(carpeta / "entrada.json")]) == 1
    assert "la salida no puede ser la entrada" in capsys.readouterr().err
    assert (carpeta / "entrada.json").read_bytes() == antes


def test_la_cli_retira_encima_de_la_entrada(mn, carpeta, valores):
    (carpeta / "export.json").write_text(mn.aplicar(TEXTO, valores), encoding="utf-8")
    assert mn.main(["--valores", str(carpeta / "valores.json"), "--retirar",
                    "--entrada", str(carpeta / "export.json"),
                    "--salida", str(carpeta / "export.json")]) == 0
    assert (carpeta / "export.json").read_bytes() == TEXTO.encode("utf-8")


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

# Lo que no es de la instancia y por eso se queda como esta: el copiloto se
# llama por el nombre de su servicio en la red de Docker.
URL_INTERNA = "http://copiloto-mcp:8000/"


def _nodos(fichero):
    return json.loads((N8N / fichero).read_text(encoding="utf-8"))["nodes"]


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_credenciales_de_los_workflows_son_marcadores(mn, fichero):
    vistas = {}
    for n in _nodos(fichero):
        for tipo, c in (n.get("credentials") or {}).items():
            assert set(c) == {"id", "name"}, (n["name"], c)
            vistas.setdefault(tipo, []).append((c["id"], c["name"]))
    esperadas = CREDENCIALES[fichero]
    assert set(vistas) == set(esperadas)
    for tipo, (ident, nombre, cuantos) in esperadas.items():
        assert vistas[tipo] == [(ident, nombre)] * cuantos, (fichero, tipo)
        assert ident in mn.MARCADORES


@pytest.mark.parametrize("fichero", FLUJOS)
def test_las_url_de_los_nodos_http_son_el_marcador_o_la_interna(mn, fichero):
    for n in _nodos(fichero):
        if n["type"] != "n8n-nodes-base.httpRequest":
            continue
        url = n["parameters"]["url"]
        assert (url.startswith(mn.URL_N8N + "/webhook/")
                or url.startswith(URL_INTERNA)), (fichero, n["name"], url)


def test_las_dos_sondas_apuntan_al_marcador(mn):
    sondas = {n["name"]: n["parameters"]["url"]
              for n in _nodos("copiloto-mantenimiento.json")
              if n["type"] == "n8n-nodes-base.httpRequest"
              and "/webhook/" in n["parameters"]["url"]}
    assert sondas == {
        "Webhook del paciente": "https://n8n.ejemplo.test/webhook/copiloto-paciente",
        "Webhook del profesional": "https://n8n.ejemplo.test/webhook/copiloto-profesional",
    }


@pytest.mark.parametrize("fichero, ruta, token", [
    ("copiloto-paciente.json", "copiloto-paciente", "<TOKEN>"),
    ("copiloto-profesional.json", "copiloto-profesional",
     "<TOKEN_DEL_BOT_DEL_PROFESIONAL>"),
])
def test_la_nota_del_webhook_registra_con_el_marcador(fichero, ruta, token):
    (nota,) = [n["notes"] for n in _nodos(fichero)
               if n["type"] == "n8n-nodes-base.webhook"]
    assert (f'"https://api.telegram.org/bot{token}/setWebhook" '
            f"-d url=https://n8n.ejemplo.test/webhook/{ruta} ") in nota


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
def test_la_cli_da_la_vuelta_a_un_workflow_entero(mn, fichero, tmp_path):
    valores = ["--valores", str(EJEMPLO)]
    assert mn.main(valores + ["--entrada", str(N8N / fichero),
                              "--salida", str(tmp_path / "puesto.json")]) == 0
    assert mn.main(valores + ["--retirar",
                              "--entrada", str(tmp_path / "puesto.json"),
                              "--salida", str(tmp_path / "vuelta.json")]) == 0
    assert (tmp_path / "vuelta.json").read_text(encoding="utf-8") \
        == mn.leer(N8N / fichero)
