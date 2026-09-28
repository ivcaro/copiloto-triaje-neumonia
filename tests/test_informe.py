"""validacion/informe.py: el documento de analisis, generado desde el JSON."""
import copy
import pathlib
import re

import pytest

from copiloto_triaje.validacion import informe

SECCIONES = [
    "Insumos y parámetros",
    "La imagen sola",
    "Escenario 0A: la aritmética",
    "Dependencia entre clínica e imagen",
    "La horquilla frente al oráculo",
    "Cuánto de su evidencia conserva la puntuación",
    "La rejilla completa",
    "Sensibilidad al previo",
    "0C: optimismo de la derivación (cálculo, no experimento)",
    "Lectura de los resultados",
    "Lo que esta simulación puede afirmar y lo que no",
    "Figuras",
    "Cómo se reproduce",
]


@pytest.fixture(scope="module")
def texto(resultados_minimos):
    return informe.redactar(resultados_minimos)


def _seccion(documento: str, titulo: str) -> str:
    """El cuerpo de la seccion `## titulo`, hasta la siguiente."""
    partes = documento.split(f"\n## {titulo}\n")
    assert len(partes) == 2, titulo
    return partes[1].split("\n## ")[0]


def test_los_formatos():
    assert informe.numero(0.70712, 3) == "0,707"
    assert informe.numero(-0.5, 2) == "−0,50"
    assert informe.numero(0.5, 2, signo=True) == "+0,50"
    assert informe.numero(-1.8e-17, 3) == "0,000"          # ni «-0,000» ni «+0,000»
    assert informe.numero(-1.8e-17, 3, signo=True) == "0,000"
    assert informe.numero(None, 3) == "n/d"
    assert informe.numero(float("nan"), 3) == "n/d"
    assert informe.numero(float("inf"), 3) == "n/d"
    assert informe.numero(1054.66, 1) == "1 054,7"
    assert informe.porcentaje(0.70712) == "70,7 %"
    assert informe.porcentaje(1.0) == "100,0 %"
    assert informe.porcentaje(None) == "n/d"
    assert informe.entero(3811) == "3 811"
    assert informe.entero(844) == "844"
    assert informe.entero(None) == "n/d"
    assert informe.rho(0.0) == "0" and informe.rho(0.15) == "0,15"
    assert informe.huella("414dd3a5cfc58320ac3f69ef090c9dcd") == "414dd3a5cfc5"


def test_el_titulo_lleva_el_rotulo_la_advertencia_y_la_nota(texto, resultados_minimos):
    lineas = texto.splitlines()
    assert lineas[0] == ("# Validación de la combinación de clínica e imagen: "
                         "simulación semisintética (SP5)")
    assert resultados_minimos["rotulo"] in lineas[0]
    assert f"**{resultados_minimos['advertencia']}**" in texto
    cabecera = texto.split("\n## ")[0]
    assert "scripts/validar_combinacion.py" in cabecera
    assert "resultados_simulacion.json" in cabecera
    assert "no se edita a mano" in cabecera
    assert texto.endswith("\n") and not texto.endswith("\n\n")
    assert "\r" not in texto


def test_las_secciones_van_en_el_orden_del_contrato(texto):
    assert [l[3:] for l in texto.splitlines() if l.startswith("## ")] == SECCIONES


def test_aparecen_las_cuatro_celdas(texto, resultados_minimos):
    nombres = [c["nombre"] for c in resultados_minimos["celdas"]]
    assert nombres == ["0A", "(0; 0,3)", "(0,3; 0)", "(0,3; 0,3)"]
    rejilla = _seccion(texto, "La rejilla completa")
    filas = [l for l in rejilla.splitlines() if l.startswith("| ")][2:]
    assert [f.split(" | ")[0][2:] for f in filas] == nombres
    # las tablas con intervalos solo llevan 0A y la destacada
    horquilla = _seccion(texto, "La horquilla frente al oráculo")
    assert "| (0,3; 0,3) | todos los concordantes |" in horquilla
    assert "| (0; 0,3) | todos los concordantes |" not in horquilla


def test_las_cifras_salen_formateadas_del_diccionario(texto, resultados_minimos):
    r = resultados_minimos
    insumos = _seccion(texto, "Insumos y parámetros")
    assert "3 811" in insumos and "844" in insumos and "0,2215" in insumos
    for clave in ("crudas_sha256", "pesos_sha256", "calibrador_sha256"):
        assert f"`{r['insumos'][clave][:12]}…`" in insumos
        assert r["insumos"][clave][:13] not in texto
    assert "ε = 0,015" in insumos
    assert "0,1466" in insumos
    imagen = _seccion(texto, "La imagen sola")
    for clave, decimales in (("auc", 3), ("brier", 3), ("pendiente", 2),
                             ("intercepto", 3), ("ece", 3)):
        assert informe.numero(r["imagen_sola"][clave], decimales) in imagen
    assert informe.numero(r["imagen_sola"]["suelo"]["p95"], 3) in imagen
    celda = r["celdas"][3]
    li, ls = celda["intervalos"]["horquilla.todos.contencion"]
    esperado = (f"{informe.porcentaje(celda['horquilla']['todos']['contencion'])} "
                f"(IC 95 %: {informe.numero(100 * li, 1)} a {informe.numero(100 * ls, 1)})")
    assert esperado in _seccion(texto, "La horquilla frente al oráculo")
    li, ls = celda["intervalos"]["pareadas.independencia.auc"]
    esperado = (f"{informe.numero(celda['pareadas']['independencia']['auc'], 3, signo=True)} "
                f"(IC 95 %: {informe.numero(li, 3, signo=True)} a "
                f"{informe.numero(ls, 3, signo=True)})")
    assert esperado in _seccion(texto, "Dependencia entre clínica e imagen")
    cero = _seccion(texto, "Escenario 0A: la aritmética")
    assert "tests/test_validacion_0a.py" in cero
    assert "100,0 %" in cero
    sensibilidad = _seccion(texto, "Sensibilidad al previo")
    s = celda["sensibilidad_al_previo"]
    assert informe.numero(s["previo"], 4) in sensibilidad
    assert informe.numero(s["modelos"]["independencia"]["intercepto"], 3, signo=True) in sensibilidad
    assert "intermedia→baja" in sensibilidad
    assert "El AUC no cambia" in sensibilidad
    assert "no recomienda configurar el despliegue" in sensibilidad
    optimismo = _seccion(texto, "0C: optimismo de la derivación (cálculo, no experimento)")
    assert "17,50" in optimismo and "8,33" in optimismo and "+0,74" in optimismo
    assert "cálculo, no un experimento" in optimismo


def test_cambiar_una_cifra_del_diccionario_cambia_el_texto(texto, resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    vieja = informe.numero(resultados_minimos["imagen_sola"]["auc"], 3)
    assert vieja in _seccion(texto, "La imagen sola")
    otro["imagen_sola"]["auc"] = 0.1234
    otro["insumos"]["placas"] = 9876
    otro["parametros"]["epsilon"] = 0.025
    otro["parametros"]["hipotesis_contencion"] = 0.8
    for celda in otro["celdas"]:
        celda["hipotesis"]["umbral"] = 0.8
    nuevo = informe.redactar(otro)
    assert nuevo != texto
    assert "0,123" in _seccion(nuevo, "La imagen sola")
    assert vieja not in _seccion(nuevo, "La imagen sola")
    insumos = _seccion(nuevo, "Insumos y parámetros")
    assert "9 876" in insumos and "3 811" not in insumos
    assert "3 811" in _seccion(texto, "Insumos y parámetros")
    assert "ε = 0,025" in nuevo and "ε = 0,015" not in nuevo
    assert "ε = 0,015" in texto
    assert "≥ 80 %" in nuevo and "90 %" not in nuevo
    assert "≥ 90 %" in texto
    assert informe.redactar(resultados_minimos) == texto      # no toca el diccionario


SIN_INTERVALO = " (estimación puntual, sin intervalo)"
NO_SE_PUEDE = ("no se puede decir: la estimación y su intervalo no quedan enteros a un lado "
               "del umbral")


def _veredictos(documento: str) -> dict:
    """{celda: veredicto}, leido de la tabla del veredicto."""
    horquilla = _seccion(documento, "La horquilla frente al oráculo")
    tabla = horquilla.split("| celda | contención | umbral | veredicto |\n")[1]
    filas = tabla.split("\n\n")[0].splitlines()
    assert filas[0] == "| :--- | ---: | ---: | :--- |"
    return {f.split(" | ")[0][2:]: f.split(" | ")[-1][:-2] for f in filas[1:]}


def _con_hipotesis(resultados, indice, contencion, intervalo):
    """Una copia con la contencion de una celda puesta a mano. El JSON lleva
    ademas `se_sostiene`, calculado sobre la estimacion sin redondear."""
    otro = copy.deepcopy(resultados)
    celda = otro["celdas"][indice]
    celda["hipotesis"]["se_sostiene"] = contencion is not None and contencion >= 0.9
    celda["hipotesis"]["contencion"] = contencion
    celda["horquilla"]["todos"]["contencion"] = contencion
    if intervalo is None:
        celda.get("intervalos", {}).pop("horquilla.todos.contencion", None)
    else:
        celda["intervalos"]["horquilla.todos.contencion"] = list(intervalo)
    return otro


def test_el_veredicto_lee_el_intervalo_y_dice_cuando_solo_hay_estimacion(
        texto, resultados_minimos):
    celda = resultados_minimos["celdas"][3]
    assert celda["hipotesis"]["se_sostiene"] is False
    assert celda["intervalos"]["horquilla.todos.contencion"][1] < 0.9
    assert "intervalos" not in resultados_minimos["celdas"][1]
    assert _veredictos(texto) == {
        "0A": "se sostiene",
        "(0; 0,3)": "no se sostiene" + SIN_INTERVALO,
        "(0,3; 0)": "no se sostiene" + SIN_INTERVALO,
        "(0,3; 0,3)": "no se sostiene"}
    casos = [
        (3, 0.95, (0.91, 0.97), "se sostiene"),
        (3, 0.95, (0.90, 0.97), "se sostiene"),                  # el umbral vale
        (3, 0.95, (0.8996, 0.97), "se sostiene"),                # se imprime «90,0»
        (3, 0.90, (0.90, 0.90), "se sostiene"),
        # restando en coma flotante, un 90 % exacto es 0,8999999999999999
        (3, 1.0 - 0.06 - 0.04, (0.91, 0.95), "se sostiene"),
        (3, 0.8996, (0.91, 0.95), "se sostiene"),                # se imprime «90,0 %»
        (3, 0.8996, None, "se sostiene" + SIN_INTERVALO),
        (3, 0.85, (0.80, 0.8996), NO_SE_PUEDE),                  # se imprime «90,0»
        (3, 0.91, (0.88, 0.97), NO_SE_PUEDE),                    # el intervalo lo cruza
        (3, 0.89, (0.85, 0.93), NO_SE_PUEDE),
        (3, 0.91, (0.80, 0.89), NO_SE_PUEDE),            # la estimacion, del otro lado
        (3, 0.89, (0.91, 0.95), NO_SE_PUEDE),            # y al reves
        (3, 0.85, (0.80, 0.89), "no se sostiene"),
        (3, 0.8994, (0.80, 0.8994), "no se sostiene"),           # se imprime «89,9»
        (3, 0.95, None, "se sostiene" + SIN_INTERVALO),
        (1, 0.913, None, "se sostiene" + SIN_INTERVALO),
        (1, 0.437, None, "no se sostiene" + SIN_INTERVALO),
        (3, None, (0.80, 0.89),
         "no se puede decir: no hay casos concordantes con horquilla"),
        (3, 0.85, (float("nan"), 0.89), "no se sostiene" + SIN_INTERVALO),
    ]
    for indice, contencion, intervalo, esperado in casos:
        otro = _con_hipotesis(resultados_minimos, indice, contencion, intervalo)
        nombre = otro["celdas"][indice]["nombre"]
        documento = informe.redactar(otro)
        assert _veredictos(documento)[nombre] == esperado, (contencion, intervalo)
        if contencion is not None and 0.8995 < contencion < 0.9:
            # lo que el lector ve al lado del veredicto
            assert f"| {nombre} | 90,0 % " in documento
    # junto a la tabla se dice con que se decide, y que el JSON va sin redondear
    horquilla = _seccion(texto, "La horquilla frente al oráculo")
    assert ("Se decide con la contención tal como se imprime (un «90,0 %» alcanza un umbral "
            "del 90 %); el campo `se_sostiene` del fichero de resultados se calcula sin "
            "redondear:") in horquilla


def test_el_umbral_se_imprime_con_los_decimales_con_que_se_compara(resultados_minimos):
    assert [informe._umbral(x) for x in (0.9, 0.905, 0.8, 0.9004, 1.0)] == [
        "90", "90,5", "80", "90", "100"]
    otro = copy.deepcopy(resultados_minimos)
    otro["parametros"]["hipotesis_contencion"] = 0.905
    for celda in otro["celdas"]:
        celda["hipotesis"]["umbral"] = 0.905
    otro["celdas"][3]["horquilla"]["todos"]["contencion"] = 0.902
    otro["celdas"][3]["intervalos"]["horquilla.todos.contencion"] = [0.88, 0.904]
    documento = informe.redactar(otro)
    # un 90,2 % no alcanza un 90,5 %, y la fila lo deja ver
    assert "| (0,3; 0,3) | 90,2 % (IC 95 %: 88,0 a 90,4) | ≥ 90,5 % | no se sostiene |" in documento
    assert "en ≥ 90,5 % de los concordantes»" in documento
    assert "(contención ≥ 90,5 % de los concordantes)" in documento
    assert "≥ 90 %" not in documento and "≥ 91 %" not in documento


def test_la_lectura_se_genera_desde_las_cifras(texto, resultados_minimos):
    lectura = _seccion(texto, "Lectura de los resultados")
    celda = resultados_minimos["celdas"][3]
    assert celda["modelos"]["independencia"]["pendiente"] < 1
    assert "menor que 1: 1 de 1: (0,3; 0,3), " in lectura
    assert informe.porcentaje(celda["horquilla"]["a_favor"]["bajo"]) in lectura
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][3]["modelos"]["independencia"]["pendiente"] = 1.25
    otro["celdas"][3]["intervalos"]["modelos.independencia.pendiente"] = [1.1, 1.4]
    nueva = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert "menor que 1: 0 de 1. Una pendiente menor que 1 es" in nueva


def _hipotesis(documento: str) -> str:
    """La frase de la hipotesis, de la lectura."""
    lectura = _seccion(documento, "Lectura de los resultados")
    frases = [l for l in lectura.splitlines() if l.startswith("- **La hipótesis de la horquilla**")]
    assert len(frases) == 1
    return frases[0]


def test_la_lectura_de_la_hipotesis_cuenta_0a_aparte_y_lee_los_intervalos(
        texto, resultados_minimos):
    # la precondicion: en la rejilla minima ninguna celda con dependencia
    # llega al umbral, ni de lejos
    assert [c["horquilla"]["todos"]["contencion"] < 0.8
            for c in resultados_minimos["celdas"][1:]] == [True] * 3
    assert _hipotesis(texto) == (
        "- **La hipótesis de la horquilla** (contención ≥ 90 % de los concordantes). "
        "0A es la comprobación de la métrica y se cuenta aparte. "
        "Celdas con dependencia: 3; con intervalo, 1. "
        "Donde hay intervalo decide el intervalo entero. "
        "Con intervalo, celdas en las que se sostiene: ninguna. "
        "Con intervalo, celdas en las que no se sostiene: 1, que es (0,3; 0,3). "
        "Con intervalo, celdas en las que no se puede decir, porque la estimación y su "
        "intervalo no quedan enteros a un lado del umbral: ninguna. "
        "Sin intervalo, 2: solo hay estimación puntual. "
        "Sin intervalo, celdas en las que la estimación alcanza el umbral: ninguna.")
    # cada cuenta dice de que celdas es: la tabla del veredicto tiene mas
    # filas «no se sostiene» que celdas con intervalo
    assert not re.search(r"(?<!intervalo, )celdas en las que", _hipotesis(texto))
    # ninguna frase pone «ninguna» detras de un verbo: «no se sostiene en
    # ninguna» diria lo contrario de lo que cuenta
    for documento in (texto, informe.redactar(resultados_minimos, {})):
        assert not re.search(r"\b(en|de) ninguna\b", documento)
    # 0A no cuenta aunque se sostenga; la que solo tiene estimacion se dice
    otro = _con_hipotesis(resultados_minimos, 1, 0.913, None)
    assert ("Sin intervalo, 2: solo hay estimación puntual. Sin intervalo, celdas en las "
            "que la estimación alcanza el umbral: 1, que es (0; 0,3).") in _hipotesis(
        informe.redactar(otro))
    assert "Con intervalo, celdas en las que se sostiene: ninguna." in _hipotesis(
        informe.redactar(otro))
    otro = _con_hipotesis(resultados_minimos, 3, 0.95, (0.91, 0.97))
    assert ("Con intervalo, celdas en las que se sostiene: 1, que es (0,3; 0,3). Con "
            "intervalo, celdas en las que no se sostiene: ninguna.") in _hipotesis(
        informe.redactar(otro))
    otro = _con_hipotesis(resultados_minimos, 3, 0.91, (0.88, 0.97))
    frase = _hipotesis(informe.redactar(otro))
    assert ("Con intervalo, celdas en las que se sostiene: ninguna. Con intervalo, celdas "
            "en las que no se sostiene: ninguna.") in frase
    assert "a un lado del umbral: 1, que es (0,3; 0,3)." in frase
    # sin bootstrap no hay intervalos que leer, y no se finge
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"]:
        celda.pop("intervalos", None)
    documento = informe.redactar(otro)
    frase = _hipotesis(documento)
    assert "Celdas con dependencia: 3; con intervalo, 0. Sin intervalo, 3:" in frase
    assert "Donde hay intervalo" not in frase
    assert "- **Los intervalos.**" not in documento
    assert "- **Los intervalos.**" in texto
    # todas con intervalo: no se habla de estimaciones sueltas
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"][1:3]:
        celda["intervalos"] = {"horquilla.todos.contencion": [0.4, 0.5]}
    frase = _hipotesis(informe.redactar(otro))
    assert "Celdas con dependencia: 3; con intervalo, 3." in frase
    assert "Sin intervalo" not in frase and "estimación alcanza" not in frase
    # una celda sin casos concordantes con horquilla se cuenta aparte
    otro = _con_hipotesis(resultados_minimos, 2, None, None)
    frase = _hipotesis(informe.redactar(otro))
    assert frase.endswith("Celdas sin casos concordantes con horquilla: 1, que es (0,3; 0).")
    assert "Sin intervalo, 1:" in frase
    assert "sin casos concordantes" not in _hipotesis(texto)
    # sin 0A no se habla de 0A
    otro = copy.deepcopy(resultados_minimos)
    del otro["celdas"][0]
    assert "0A" not in _hipotesis(informe.redactar(otro))


def test_la_lectura_cuenta_las_cifras_fuera_de_su_intervalo(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"]:
        for ruta, par in celda.get("intervalos", {}).items():
            valor = celda
            for clave in ruta.split("."):
                valor = valor[clave]
            par[0], par[1] = valor - 1.0, valor + 1.0
    total = sum(len(c.get("intervalos", {})) for c in otro["celdas"])
    assert total > 50
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert f"quedan fuera de su intervalo 0 de las {total} cifras que lo llevan" in lectura
    otro["celdas"][3]["intervalos"]["modelos.imagen.auc"] = [0.1, 0.2]
    otro["celdas"][0]["intervalos"]["modelos.imagen.auc"] = [0.99, 0.999]
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert f"quedan fuera de su intervalo 2 de las {total} cifras que lo llevan" in lectura
    assert "de 2 réplicas" in lectura


def test_los_ejes_de_la_lectura_van_en_orden_fijo(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"][1:]:
        celda["destacada"] = True
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    ejes = [l for l in lectura.splitlines() if l.startswith("- **Dependencia")]
    assert ejes == ["- **Dependencia simétrica (ρ1 = ρ0).**",
                    "- **Dependencia solo entre los casos con neumonía (ρ0 = 0).**",
                    "- **Dependencia solo entre los casos sin neumonía (ρ1 = 0).**"]
    celdas = [l.strip()[2:].split(":")[0] for l in lectura.splitlines() if l.startswith("  - ")]
    assert celdas == ["(0,3; 0,3)", "(0,3; 0)", "(0; 0,3)"]


def test_la_cola_mayor_se_lee_de_las_dos_colas(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    lado = otro["celdas"][3]["horquilla"]["a_favor"]
    lado.update(bajo=0.0, sobre=0.25, contencion=0.75)
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert ("con la imagen a favor queda dentro el 75,0 %; la cola mayor es la de más allá "
            "de la independencia (25,0 %, frente a 0,0 % por el lado conservador)") in lectura
    lado.update(bajo=0.0, sobre=0.0, contencion=1.0)
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert "con la imagen a favor queda dentro el 100,0 %; ninguna cola tiene casos" in lectura


def test_los_enlaces_de_las_figuras_recibidas_y_ninguno_mas(resultados_minimos, validar):
    sin = informe.redactar(resultados_minimos)
    assert "![" not in sin and ".png" not in sin
    assert "sin figuras" in _seccion(sin, "Figuras")
    figuras = {"fiabilidad_r1-030_r0-030": "validacion-semisintetica/fiabilidad_r1-030_r0-030.png",
               "contencion_rejilla": "validacion-semisintetica/contencion_rejilla.png"}
    con = informe.redactar(resultados_minimos, figuras)
    enlaces = re.findall(r"!\[([^\]]*)\]\(([^)]*)\)", con)
    assert [e[1] for e in enlaces] == [
        "validacion-semisintetica/fiabilidad_r1-030_r0-030.png",
        "validacion-semisintetica/contencion_rejilla.png"]
    assert "(0,3; 0,3)" in enlaces[0][0]
    assert all("simulación semisintética" in e[0] for e in enlaces)
    assert con.count(".png") == 2
    assert con.split("\n## Figuras\n")[0] == sin.split("\n## Figuras\n")[0]
    # el nombre de cada figura de fiabilidad es el que le pone el script
    todas = {f"fiabilidad_{validar.slug_de_celda(c)}": f"f/{i}.png"
             for i, c in enumerate(resultados_minimos["celdas"])}
    enlaces = re.findall(r"!\[([^\]]*)\]\(([^)]*)\)", informe.redactar(resultados_minimos, todas))
    assert [e[1] for e in enlaces] == ["f/0.png", "f/1.png", "f/2.png", "f/3.png"]
    assert [c["nombre"] in e[0] for c, e in zip(resultados_minimos["celdas"], enlaces)] == [True] * 4


def test_no_aparecen_nan_none_llaves_ni_puntos_decimales(resultados_minimos):
    figuras = {"horquilla_por_celda": "validacion-semisintetica/horquilla_por_celda.png"}
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][3]["horquilla"]["a_favor"]["lambda"] = {"q1": None, "mediana": None, "q3": None}
    otro["celdas"][3]["discordantes"]["sesgo_mediano"] = float("nan")
    otro["celdas"][3]["intervalos"]["discordantes.sesgo_mediano"] = [float("nan"), float("nan")]
    for documento in (informe.redactar(resultados_minimos, figuras), informe.redactar(otro)):
        assert not re.search(r"\bnan\b", documento, flags=re.IGNORECASE)
        assert "None" not in documento
        assert "{" not in documento and "}" not in documento
        # los «§4.7» son referencias, no cifras
        assert not re.search(r"(?<![§\d.])\d+\.\d", documento)
        assert "-0," not in documento                       # el menos es «−»
    assert "n/d" not in informe.redactar(resultados_minimos)
    assert "n/d (IC 95 %: n/d a n/d)" in informe.redactar(otro)


def test_sin_bootstrap_no_hay_intervalos(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    otro["parametros"]["replicas"] = 0
    for celda in otro["celdas"]:
        celda.pop("intervalos", None)
        celda.pop("replicas", None)
    documento = informe.redactar(otro)
    assert "(IC 95 %:" not in documento
    assert "sin bootstrap" in documento
    assert "(IC 95 %:" in informe.redactar(resultados_minimos)


def test_los_limites_del_spec_estan_escritos(texto):
    limites = _seccion(texto, "Lo que esta simulación puede afirmar y lo que no")
    assert "no mide exactitud clínica" in limites
    assert "las viñetas no son pacientes" in limites
    assert "la exactitud es la publicada y la dependencia es la supuesta" in limites
    assert "**No puede afirmar**" in limites
    assert "reproduce caso a caso la posterior del generador" in limites
    # el alcance no afirma un resultado: lo que dice esta corrida va aparte
    assert "**Puede decir:**" in limites and "**Puede afirmar:**" not in limites
    assert "- si el sistema reproduce caso a caso" in limites
    assert "- si, **cuando** la puntuación tiene la exactitud publicada" in limites
    # cada punto remite a donde se responde
    assert ("(0A: lo comprueban las pruebas de `tests/test_validacion_0a.py`; la fila 0A de "
            "la horquilla lo acompaña, como control más débil y solo para los concordantes)"
            ) in limites
    assert limites.count("caso a caso") == 1
    assert ("Lo demás se lee en «Lectura de los resultados» y, lo del previo, en "
            "«Sensibilidad al previo».") in limites
    assert "Cada placa con su clínica sorteada es una viñeta." in _seccion(
        texto, "Insumos y parámetros")


def test_los_limites_dicen_lo_que_dice_esta_corrida(texto, resultados_minimos):
    limites = _seccion(texto, "Lo que esta simulación puede afirmar y lo que no")
    cero = resultados_minimos["celdas"][0]
    m = cero["modelos"]["independencia"]
    assert m["ece"] <= m["suelo"]["p95"]
    assert ("En esta corrida, la fila 0A de la horquilla se cumple; la pendiente de la "
            "combinación por independencia en 0A es "
            + informe.numero(m["pendiente"], 2)) in limites
    assert (f"y su ECE ({informe.numero(m['ece'], 3)}) no supera el percentil 95 de su "
            f"suelo") in limites
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][0]["horquilla"]["todos"].update(bajo=0.01, contencion=0.99)
    otro["celdas"][0]["modelos"]["independencia"]["ece"] = 0.5
    otro["celdas"][0]["intervalos"]["modelos.independencia.pendiente"] = [1.05, 1.2]
    limites = _seccion(informe.redactar(otro),
                       "Lo que esta simulación puede afirmar y lo que no")
    assert "la fila 0A de la horquilla **no se cumple**" in limites
    assert "su intervalo no contiene el 1" in limites
    assert "y su ECE (0,500) supera el percentil 95 de su suelo" in limites
    del otro["celdas"][0]
    limites = _seccion(informe.redactar(otro),
                       "Lo que esta simulación puede afirmar y lo que no")
    assert ("Esta corrida no incluye la celda 0A: de los dos primeros puntos no dice nada."
            ) in limites
    assert "En esta corrida, la fila 0A" not in limites
    # sin casos con horquilla la comprobacion no se puede hacer: no es un fallo
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][0]["horquilla"]["todos"].update(
        n=0, bajo=None, sobre=None, contencion=None)
    limites = _seccion(informe.redactar(otro),
                       "Lo que esta simulación puede afirmar y lo que no")
    assert "la fila 0A de la horquilla **no se puede comprobar**; la pendiente" in limites


def test_la_escala_legible_rotula_las_puntuaciones_poco_informativas(texto, resultados_minimos):
    escala = _seccion(texto, "Cuánto de su evidencia conserva la puntuación")
    assert "### Celda (0,3; 0,3)" in escala
    assert "### Celda (0; 0,3)" not in escala                 # solo las destacadas
    filas = [l for l in escala.splitlines() if l.startswith("| ")]
    assert len([l for l in filas if "poco informativa" in l]) == 4     # k = 2 y 3, dos lados
    assert all(l.startswith(("| 2 |", "| 3 |")) for l in filas if "poco informativa" in l)
    lado = resultados_minimos["celdas"][3]["escala_legible"]["en_contra"]
    assert informe.numero(lado["fraccion_mediana_extremas"], 2) in escala


def test_como_se_reproduce_cita_la_orden_y_las_replicas(texto):
    reproducir = _seccion(texto, "Cómo se reproduce")
    assert "python scripts/validar_combinacion.py --replicas 2" in reproducir
    assert "--solo-documento" in reproducir
    assert "sin los pesos" in reproducir


def test_el_modulo_es_puro():
    fuente = pathlib.Path(informe.__file__).read_text(encoding="utf-8")
    for prohibido in ("matplotlib", "open(", "pathlib", "import os", "numpy", "pandas"):
        assert prohibido not in fuente, prohibido


def test_los_nombres_de_las_figuras_son_los_del_guion(validar):
    """El documento y el guion nombran las figuras por separado (el paquete
    no puede importar el guion): que no se separen."""
    assert [clave for clave, _ in informe.FIGURAS_GLOBALES] == list(validar.FIGURAS_GLOBALES)
    assert informe.PREFIJO_FIABILIDAD == validar.PREFIJO_FIABILIDAD


def test_las_definiciones_del_diseno_que_la_prosa_da_por_fijas_son_las_del_codigo():
    """La prosa del documento escribe cuatro definiciones del diseño, que no
    son resultados y no están en el JSON: el nivel del intervalo (95 %), los
    cortes de banda (20 y 70 %), el umbral de «poco informativa» (0,5) y las
    puntuaciones extremas (k ≤ 1 y k ≥ 4). Si el código las cambia, esta
    prueba falla y hay que cambiar la prosa de `informe.py`."""
    import inspect

    from copiloto_triaje.validacion import categoria, metricas, simulacion
    assert inspect.signature(metricas.percentiles).parameters["alfa"].default == 0.05
    assert [categoria.banda(p) for p in (19, 20, 70, 71)] == [
        "baja", "intermedia", "intermedia", "alta"]
    assert simulacion.POCO_INFORMATIVA == 0.5
    assert simulacion.EXTREMAS == (0, 1, 4, 5)
    assert simulacion.HIPOTESIS_CONTENCION == 0.90


# --------------------------------------------------------------------------
# Una prueba por rama: cada frase cuya verdad depende de los datos, con
# resultados trucados para que caiga en cada una de sus ramas.
# --------------------------------------------------------------------------
def test_la_ece_se_lee_frente_al_p95_de_su_suelo(texto, resultados_minimos):
    suelo = {"media": 0.010, "p95": 0.020}
    assert informe._frente_al_suelo(0.020, suelo).startswith("no supera el percentil 95")
    # las dos se imprimen «0,020»: el documento no puede decir que una supera a la otra
    assert informe._frente_al_suelo(0.0201, suelo).startswith("no supera el percentil 95")
    assert informe._frente_al_suelo(0.0204, {"media": 0.01, "p95": 0.0196}).startswith(
        "no supera")
    assert informe._frente_al_suelo(0.0206, suelo).startswith("supera el percentil 95")
    assert informe._frente_al_suelo(0.015, suelo).startswith("no supera")   # no es la media
    for ece, p95 in ((None, 0.02), (0.02, None), (float("nan"), 0.02)):
        assert informe._frente_al_suelo(ece, {"media": 0.01, "p95": p95}) == (
            "no se puede comparar con su suelo")
    otro = copy.deepcopy(resultados_minimos)
    otro["imagen_sola"]["ece"] = otro["imagen_sola"]["suelo"]["p95"] + 0.001
    imagen = _seccion(informe.redactar(otro), "La imagen sola")
    assert ") supera el percentil 95 de su suelo: hay descalibración" in imagen
    otro["imagen_sola"]["ece"] = otro["imagen_sola"]["suelo"]["p95"] - 0.001
    imagen = _seccion(informe.redactar(otro), "La imagen sola")
    assert ") no supera el percentil 95 de su suelo: no se distingue" in imagen
    otro["celdas"][0]["modelos"]["independencia"]["ece"] = 0.5
    assert ") supera el percentil 95 de su suelo" in _seccion(
        informe.redactar(otro), "Escenario 0A: la aritmética")
    assert ") no supera el percentil 95 de su suelo" in _seccion(
        texto, "Escenario 0A: la aritmética")


def test_la_fila_0a_dice_si_la_metrica_se_cumple(texto, resultados_minimos):
    cero = _seccion(texto, "Escenario 0A: la aritmética")
    assert "Se cumple: la métrica de la horquilla pasa su comprobación en el caso nulo." in cero
    assert "NO se cumple" not in cero
    n = resultados_minimos["celdas"][0]["horquilla"]["todos"]["n"]
    for cambio, fuera in ((dict(bajo=10 / n, contencion=1 - 10 / n), "quedan fuera de la horquilla 10"),
                          (dict(sobre=3 / n, contencion=1 - 3 / n), "quedan fuera de la horquilla 3"),
                          # un solo caso fuera se imprime «0,0 %» y «100,0 %»
                          (dict(bajo=1 / n, contencion=1 - 1 / n), "queda fuera de la horquilla 1")):
        otro = copy.deepcopy(resultados_minimos)
        otro["celdas"][0]["horquilla"]["todos"].update(cambio)
        cero = _seccion(informe.redactar(otro), "Escenario 0A: la aritmética")
        assert (f"**NO se cumple: {fuera} de los {informe.entero(n)} concordantes. La "
                f"métrica de la horquilla o el generador tienen un defecto") in cero, cambio
        assert "Se cumple: la métrica" not in cero
    # sin casos no se puede comprobar, que no es lo mismo que no cumplirse
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][0]["horquilla"]["todos"].update(
        n=0, bajo=None, sobre=None, contencion=None)
    documento = informe.redactar(otro)
    cero = _seccion(documento, "Escenario 0A: la aritmética")
    assert "**No se puede comprobar: no hay casos concordantes con horquilla" in cero
    assert "NO se cumple" not in cero and "Se cumple: la métrica" not in cero
    assert "tienen un defecto" not in cero
    assert "Horquilla: no hay casos con horquilla." in _seccion(
        documento, "Lectura de los resultados")
    otro = copy.deepcopy(resultados_minimos)
    del otro["celdas"][0]
    documento = informe.redactar(otro)
    assert "Esta corrida no incluye la celda 0A." in _seccion(
        documento, "Escenario 0A: la aritmética")
    assert "Esta corrida no calculó 0C." in _seccion(
        documento, "0C: optimismo de la derivación (cálculo, no experimento)")
    assert "- **0A.**" not in documento


def test_la_pendiente_de_0a_dice_si_su_intervalo_contiene_el_1(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    cero = otro["celdas"][0]
    cero["modelos"]["independencia"]["pendiente"] = 1.03
    for intervalo, esperado in (([0.91, 1.09], "1,03 (IC 95 %: 0,91 a 1,09); su intervalo contiene el 1."),
                                ([1.0, 1.09], "1,03 (IC 95 %: 1,00 a 1,09); su intervalo contiene el 1."),
                                ([1.004, 1.09], "1,03 (IC 95 %: 1,00 a 1,09); su intervalo contiene el 1."),
                                ([1.01, 1.09], "1,03 (IC 95 %: 1,01 a 1,09); su intervalo no contiene el 1."),
                                ([0.8, 0.99], "1,03 (IC 95 %: 0,80 a 0,99); su intervalo no contiene el 1."),
                                ([0.9, 0.996], "1,03 (IC 95 %: 0,90 a 1,00); su intervalo contiene el 1."),
                                ([0.9, 0.994], "1,03 (IC 95 %: 0,90 a 0,99); su intervalo no contiene el 1.")):
        cero["intervalos"]["modelos.independencia.pendiente"] = intervalo
        lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
        assert ("- **0A.** La pendiente de la combinación por independencia es "
                + esperado + " Horquilla: queda dentro el 100,0 %; ninguna cola tiene casos."
                ) in lectura
    del cero["intervalos"]["modelos.independencia.pendiente"]
    lectura = _seccion(informe.redactar(otro), "Lectura de los resultados")
    assert "independencia es 1,03. Horquilla: " in lectura


def _con_pendiente(resultados, clave, pendiente, intervalo):
    otro = copy.deepcopy(resultados)
    celda = otro["celdas"][3]
    celda["modelos"][clave]["pendiente"] = pendiente
    if intervalo is None:
        del celda["intervalos"][f"modelos.{clave}.pendiente"]
    else:
        celda["intervalos"][f"modelos.{clave}.pendiente"] = list(intervalo)
    return _seccion(informe.redactar(otro), "Lectura de los resultados")


def test_la_pendiente_de_la_independencia_se_lee_con_su_intervalo(resultados_minimos):
    lectura = _con_pendiente(resultados_minimos, "independencia", 0.8, (0.7, 0.9))
    assert ("- **La independencia.** Celdas destacadas en las que la estimación de la "
            "pendiente de la combinación por independencia es menor que 1: 1 de 1: "
            "(0,3; 0,3), 0,80 (IC 95 %: 0,70 a 0,90). Una pendiente menor que 1 es la forma "
            "cuantitativa de «exagera».") in lectura
    assert ("- De esas, con el intervalo entero por debajo de 1 (exagera): 1 de 1: "
            "(0,3; 0,3).") in lectura
    assert "En sentido contrario, la estimación de la pendiente de la combinación" not in lectura
    lectura = _con_pendiente(resultados_minimos, "independencia", 0.95, (0.85, 1.0))
    assert "- De esas, con el intervalo entero por debajo de 1 (exagera): 0 de 1." in lectura
    lectura = _con_pendiente(resultados_minimos, "independencia", 0.8, None)
    assert "menor que 1: 1 de 1: (0,3; 0,3), 0,80. Una pendiente" in lectura
    assert "con el intervalo entero por debajo de 1" not in lectura.split(
        "**El extremo conservador.**")[0]
    lectura = _con_pendiente(resultados_minimos, "independencia", 1.25, (1.1, 1.4))
    assert ("- En sentido contrario, la estimación de la pendiente de la combinación por "
            "independencia es mayor que 1: 1 de 1: (0,3; 0,3), 1,25 (IC 95 %: 1,10 a 1,40)."
            ) in lectura
    assert ("- De esas, con el intervalo entero por encima de 1 (se queda corta): 1 de 1: "
            "(0,3; 0,3).") in lectura
    for pendiente in (1.0, 0.996, 1.004):                    # las tres se imprimen «1,00»
        lectura = _con_pendiente(resultados_minimos, "independencia", pendiente, (0.9, 1.1))
        assert "menor que 1: 0 de 1. Una pendiente" in lectura   # ni de un lado ni del otro
        assert "En sentido contrario, la estimación de la pendiente de la comb" not in lectura
    assert ("Las comparaciones con un umbral o con un valor de referencia se hacen con las "
            "cifras tal como se imprimen: «por encima» y «por debajo» son estrictos, y un "
            "umbral «≥» se alcanza también con la igualdad.") in lectura
    # «exagera» y «se queda corta» se dicen del intervalo, nunca de la estimacion sola
    assert not re.search(r"que 1 \((exagera|se queda)", lectura)


def test_la_pendiente_del_extremo_conservador_se_lee_con_su_intervalo(resultados_minimos):
    lectura = _con_pendiente(resultados_minimos, "conservador", 1.12, (1.02, 1.21))
    assert ("- **El extremo conservador.** Celdas destacadas en las que la estimación de su "
            "pendiente es mayor que 1: 1 de 1: (0,3; 0,3), 1,12 (IC 95 %: 1,02 a 1,21)."
            ) in lectura
    assert ("- De esas, con el intervalo entero por encima de 1 (se queda corto): 1 de 1: "
            "(0,3; 0,3).") in lectura
    # la estimacion por encima de 1 no basta si el intervalo contiene el 1
    lectura = _con_pendiente(resultados_minimos, "conservador", 1.03, (0.95, 1.12))
    assert "pendiente es mayor que 1: 1 de 1: (0,3; 0,3), 1,03" in lectura
    assert "- De esas, con el intervalo entero por encima de 1 (se queda corto): 0 de 1." in lectura
    # un extremo 1,004 se imprime «1,00»: no queda por encima de 1
    lectura = _con_pendiente(resultados_minimos, "conservador", 1.13, (1.004, 1.17))
    assert "(0,3; 0,3), 1,13 (IC 95 %: 1,00 a 1,17)." in lectura
    assert "- De esas, con el intervalo entero por encima de 1 (se queda corto): 0 de 1." in lectura
    lectura = _con_pendiente(resultados_minimos, "conservador", 1.13, (1.006, 1.17))
    assert ("- De esas, con el intervalo entero por encima de 1 (se queda corto): 1 de 1: "
            "(0,3; 0,3).") in lectura
    # y si queda entero por debajo, ni el extremo conservador basta: se dice
    lectura = _con_pendiente(resultados_minimos, "conservador", 0.9, (0.84, 0.98))
    assert "pendiente es mayor que 1: 0 de 1." in lectura
    assert ("- En sentido contrario, la estimación de la pendiente del extremo conservador "
            "es menor que 1: 1 de 1: (0,3; 0,3), 0,90 (IC 95 %: 0,84 a 0,98).") in lectura
    assert ("- De esas, con el intervalo entero por debajo de 1 (también el extremo "
            "conservador exagera): 1 de 1: (0,3; 0,3).") in (
        lectura.split("**El extremo conservador.**")[1])
    assert not re.search(r"que 1 \((también|se queda)", lectura)


def test_las_diferencias_pareadas_se_leen_por_su_intervalo(resultados_minimos):
    def lectura(clave, metrica, intervalo):
        otro = copy.deepcopy(resultados_minimos)
        otro["celdas"][3]["intervalos"][f"pareadas.{clave}.{metrica}"] = list(intervalo)
        return _seccion(informe.redactar(otro), "Lectura de los resultados")

    def frase(texto, titulo):
        return next(l for l in texto.splitlines()
                    if l.startswith(f"- **Frente a la imagen sola: {titulo}.**"))

    cabecera = "Celdas destacadas con intervalo: 1. "
    la = frase(lectura("independencia", "auc", (0.01, 0.03)), "ΔAUC, combinación, independencia")
    assert la.endswith(cabecera + "Con el intervalo entero del lado de la mejora (por "
                       "encima de 0): 1, que es (0,3; 0,3). Con el intervalo entero del lado "
                       "contrario: ninguna. Con el 0 dentro del intervalo: ninguna.")
    la = frase(lectura("independencia", "auc", (-0.03, -0.01)), "ΔAUC, combinación, independencia")
    assert la.endswith("(por encima de 0): ninguna. Con el intervalo entero del lado "
                       "contrario: 1, que es (0,3; 0,3). Con el 0 dentro del intervalo: "
                       "ninguna.")
    for intervalo in ((-0.01, 0.0), (-0.01, 0.02), (0.0004, 0.03), (-0.03, -0.0004)):
        la = frase(lectura("independencia", "auc", intervalo),
                   "ΔAUC, combinación, independencia")
        assert la.endswith("(por encima de 0): ninguna. Con el intervalo entero del lado "
                           "contrario: ninguna. Con el 0 dentro del intervalo: 1, que es "
                           "(0,3; 0,3)."), intervalo
    # en el Brier la mejora es bajar
    la = frase(lectura("conservador", "brier", (-0.02, -0.01)),
               "ΔBrier, combinación, extremo conservador")
    assert la.endswith(cabecera + "Con el intervalo entero del lado de la mejora (por "
                       "debajo de 0): 1, que es (0,3; 0,3). Con el intervalo entero del lado "
                       "contrario: ninguna. Con el 0 dentro del intervalo: ninguna.")
    la = frase(lectura("conservador", "brier", (0.001, 0.01)),
               "ΔBrier, combinación, extremo conservador")
    assert la.endswith("Con el intervalo entero del lado contrario: 1, que es (0,3; 0,3). "
                       "Con el 0 dentro del intervalo: ninguna.")
    # sin intervalos no hay frase
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"]:
        celda.pop("intervalos", None)
    assert "Frente a la imagen sola" not in informe.redactar(otro)
    assert len([l for l in informe.redactar(resultados_minimos).splitlines()
                if l.startswith("- **Frente a la imagen sola: ")]) == 4


def test_las_colas_en_todas_sus_ramas():
    def colas(bajo, sobre):
        dentro = None if bajo is None or sobre is None else 1.0 - bajo - sobre
        return informe._colas({"bajo": bajo, "sobre": sobre, "contencion": dentro})

    assert colas(None, 0.1) == colas(0.1, None) == "no hay casos con horquilla"
    assert colas(0.0, 0.0) == "queda dentro el 100,0 %; ninguna cola tiene casos"
    assert colas(0.2, 0.2) == ("queda dentro el 60,0 %; las dos colas pesan lo mismo "
                               "(20,0 % cada una)")
    # las dos se imprimen «20,0 %»: ninguna es «la mayor»
    assert colas(0.2001, 0.2004) == ("queda dentro el 60,0 %; las dos colas pesan lo mismo "
                                     "(20,0 % cada una)")
    # con un solo caso en una cola no se dice que ninguna tiene casos
    assert colas(0.0004, 0.0) == ("queda dentro el 100,0 %; las dos colas pesan lo mismo "
                                  "(0,0 % cada una)")
    assert colas(0.3, 0.1) == ("queda dentro el 60,0 %; la cola mayor es la del lado "
                               "conservador (30,0 %, frente a 10,0 % más allá de la "
                               "independencia)")
    assert colas(0.1, 0.3) == ("queda dentro el 60,0 %; la cola mayor es la de más allá de "
                               "la independencia (30,0 %, frente a 10,0 % por el lado "
                               "conservador)")


def test_el_reparto_de_0c(texto, resultados_minimos):
    titulo = "0C: optimismo de la derivación (cálculo, no experimento)"
    por_puntuacion = resultados_minimos["celdas"][0]["optimismo_de_la_derivacion"][
        "por_puntuacion"]
    assert [(f["k"], f["rv_derivacion"], f["rv_validacion"]) for f in por_puntuacion] == [
        (0, 0.12, 0.19), (1, 0.20, 0.19), (2, 0.70, 1.04),
        (3, 1.64, 1.04), (4, 7.18, 8.33), (5, 17.5, 8.33)]
    assert ("La RV de la derivación es más extrema que la de validación en k = 0, 2, 3 y 5 "
            "y menos extrema en k = 1 y 4 (más extrema: más lejos de 1). El «optimismo» de "
            "la derivación no es uniforme.") in _seccion(texto, titulo)

    def con(validacion):
        otro = copy.deepcopy(resultados_minimos)
        filas = otro["celdas"][0]["optimismo_de_la_derivacion"]["por_puntuacion"]
        for fila, rv in zip(filas, validacion):
            fila["rv_validacion"] = rv
        return _seccion(informe.redactar(otro), titulo)

    todas = con([0.5, 0.5, 0.9, 1.1, 2.0, 2.0])
    assert ("La RV de la derivación es más extrema que la de validación en k = 0, 1, 2, 3, "
            "4 y 5 (más extrema: más lejos de 1).") in todas
    assert "no es uniforme" not in todas
    ninguna = con([0.01, 0.01, 0.1, 9.0, 99.0, 99.0])
    assert "La RV de la derivación es menos extrema en k = 0, 1, 2, 3, 4 y 5 (" in ninguna
    assert "no es uniforme" not in ninguna
    empate = con([0.12, 0.19, 1.04, 1.04, 8.33, 8.33])
    assert ("más extrema que la de validación en k = 2, 3 y 5, menos extrema en k = 1 y 4 "
            "y igual de extrema en k = 0 (") in empate
    assert "no es uniforme" in empate
    # «más» e «igual», sin «menos»: tampoco es uniforme
    sin_menos = con([0.12, 0.5, 0.9, 1.1, 2.0, 2.0])
    assert ("La RV de la derivación es más extrema que la de validación en k = 1, 2, 3, 4 "
            "y 5 y igual de extrema en k = 0 (") in sin_menos
    assert "no es uniforme" in sin_menos
    solo_iguales = con([0.12, 0.20, 0.70, 1.64, 7.18, 17.5])
    assert "La RV de la derivación es igual de extrema en k = 0, 1, 2, 3, 4 y 5 (" in solo_iguales
    assert "no es uniforme" not in solo_iguales
    # «menos» e «igual», sin «más»: nunca es mas extrema, y no hay optimismo
    # que repartir
    sin_mas = con([0.12, 0.01, 0.1, 9.0, 99.0, 99.0])
    assert ("La RV de la derivación es menos extrema en k = 1, 2, 3, 4 y 5 y igual de "
            "extrema en k = 0 (") in sin_mas
    assert "no es uniforme" not in sin_mas


def test_la_nota_del_rho_extremo_sale_de_la_rejilla(texto, resultados_minimos):
    nota = "sobre la puntuación es un caso extremo, no plausible"
    assert max(resultados_minimos["parametros"]["rejilla"]) < informe.RHO_EXTREMO
    assert nota not in texto
    otro = copy.deepcopy(resultados_minimos)
    otro["parametros"]["rejilla"] = [0.0, 0.3, 0.6]
    assert f"Un ρ de 0,6 {nota}" in _seccion(
        informe.redactar(otro), "Dependencia entre clínica e imagen")


def test_sin_destacadas_y_sin_sensibilidad_se_dice(resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"]:
        celda["destacada"] = False
        celda.pop("sensibilidad_al_previo", None)
    documento = informe.redactar(otro)
    assert "esta corrida no tiene celdas destacadas." in _seccion(
        documento, "Insumos y parámetros")
    assert "Esta corrida no tiene celdas destacadas." in _seccion(
        documento, "Cuánto de su evidencia conserva la puntuación")
    assert "- Esta corrida no tiene celdas destacadas." in _seccion(
        documento, "Lectura de los resultados")
    assert "Esta corrida no calculó la sensibilidad al previo." in _seccion(
        documento, "Sensibilidad al previo")
    assert "Hacia qué lado cae el oráculo" not in documento


def test_la_fraccion_de_0a_solo_se_da_por_entera_si_lo_es(texto, resultados_minimos):
    titulo = "Cuánto de su evidencia conserva la puntuación"
    assert ("es 1,00 con la imagen a favor y 1,00 con la imagen en contra: sin dependencia "
            "la puntuación conserva toda su evidencia.") in _seccion(texto, titulo)
    otro = copy.deepcopy(resultados_minimos)
    otro["celdas"][0]["escala_legible"]["en_contra"]["fraccion_mediana_extremas"] = 0.8
    escala = _seccion(informe.redactar(otro), titulo)
    assert ("es 1,00 con la imagen a favor y 0,80 con la imagen en contra: **sin "
            "dependencia tendría que ser 1,00 en los dos lados, y no lo es.**") in escala
    assert "conserva toda su evidencia." not in escala.split("### Celda")[0].split("\n\n")[-2]


def test_la_expectativa_no_se_presenta_como_declarada_a_ciegas(texto):
    horquilla = _seccion(texto, "La horquilla frente al oráculo")
    assert "**Hipótesis declarada de antemano, a refutar celda a celda:**" in horquilla
    assert "medida sobre el conjunto durante el diseño y no declarada a ciegas" in horquilla
    assert "antes de correr nada" not in texto


def test_las_semillas_van_sin_separador_y_la_prevalencia_es_la_del_conjunto(
        texto, resultados_minimos):
    insumos = _seccion(texto, "Insumos y parámetros")
    assert "(semilla 20261009)" in insumos
    assert "clínica de la réplica b, 10000 + b; placas de la réplica b, 20000 + b." in insumos
    assert "20 261 009" not in texto and "10 000" not in texto
    assert "con la semilla 1 sobre todas las placas" in _seccion(
        texto, "Lectura de los resultados")
    assert "que cubre el redondeo de las RV publicadas" in insumos
    assert "redondeo máximo" not in texto
    otro = copy.deepcopy(resultados_minimos)
    otro["insumos"]["positivas"] = 1000
    otro["insumos"]["placas"] = 4000
    insumos = _seccion(informe.redactar(otro), "Insumos y parámetros")
    assert "(una por paciente; 1 000 positivas, prevalencia 0,2500)" in insumos
    # el previo es el del calibrador, y si no es la prevalencia del conjunto se dice
    assert ("Previo del análisis principal: 0,2215, el del calibrador, que **no es la "
            "prevalencia del conjunto** (0,2500). El previo desplegado, 0,1466,") in insumos
    assert ("Previo del análisis principal: 0,2215, el del calibrador, que es la "
            "prevalencia del conjunto. El previo desplegado, 0,1466,") in _seccion(
        texto, "Insumos y parámetros")
    assert "la prevalencia de la población simulada" not in texto
    sensibilidad = _seccion(texto, "Sensibilidad al previo")
    assert "usa como previo 0,2215 (el de «Insumos y parámetros»)" in sensibilidad
    assert "donde el análisis principal usa 0,2215 tiene un efecto analítico" in sensibilidad
    assert "previo correcto" not in texto
    assert "cifras que lo llevan (comparadas sin redondear)." in _seccion(
        texto, "Lectura de los resultados")
    assert "(estimaciones puntuales):" in _seccion(texto, "Lectura de los resultados")


def test_las_columnas_de_texto_van_a_la_izquierda(texto):
    assert informe._tabla(["celda", "n", "veredicto"], [["a", "1", "x"]],
                          texto=("veredicto",)) == [
        "| celda | n | veredicto |", "| :--- | ---: | :--- |", "| a | 1 | x |", ""]
    assert informe._tabla(["a", "b"], [])[1] == "| :--- | ---: |"
    guias = {l: texto.splitlines()[i + 1] for i, l in enumerate(texto.splitlines())
             if l.startswith("| ") and texto.splitlines()[i + 1].startswith("| :---")}
    assert guias["| celda | contención | umbral | veredicto |"].endswith("| :--- |")
    assert all(g.endswith("| :--- |") for c, g in guias.items() if c.endswith("| rótulo |"))
    assert all(g.endswith("| :--- |") for c, g in guias.items()
               if c.endswith("| en qué sentido |"))


def test_las_listas_de_celdas_no_llevan_doble_parentesis(texto, resultados_minimos):
    otro = copy.deepcopy(resultados_minimos)
    for celda in otro["celdas"][1:]:
        celda["destacada"] = True
    for documento in (texto, informe.redactar(otro)):
        assert "((" not in documento and "))" not in documento
    assert "las figuras que ya hubiera" not in texto
    assert "que pueden ser de una corrida anterior" in informe.redactar(
        resultados_minimos, {"contencion_rejilla": "f/contencion_rejilla.png"})
