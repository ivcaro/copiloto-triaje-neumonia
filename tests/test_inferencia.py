"""Pruebas del nucleo de inferencia.

Se prueba aqui, en el paquete y no contra el servidor, para que corran sin
levantar Docker y en menos de un segundo.
"""
import math
import warnings
from types import MappingProxyType

import numpy as np
import pydicom
import pytest
import torch
import torch.nn.functional as F
from PIL import Image

from copiloto_triaje.datos.dataset import construir_transformaciones
from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes
from copiloto_triaje.modelo.arquitectura import construir_modelo, descongelar_todo
from copiloto_triaje.servicio.calibracion import Calibrador, ajustar_calibrador
from copiloto_triaje.servicio.heckerling import combinacion, combinar
from copiloto_triaje.servicio.inferencia import ErrorDeInferencia, Motor

from test_dicom import crear_dicom  # reutiliza el generador de DICOM sinteticos


@pytest.fixture
def motor(tmp_path):
    """Un motor con un modelo lineal diminuto: aqui se prueba la logica del
    nucleo, no la calidad de la red, y cargar EfficientNet real haria que cada
    prueba descargara pesos de ImageNet."""
    rng = np.random.default_rng(0)
    y = (rng.random(500) < 0.2215).astype(int)
    crudo = 1 / (1 + np.exp(-rng.normal(1.7 * y, 1.0)))
    calibrador = ajustar_calibrador(y, crudo, 0.2215, "prueba")

    class Trivial(torch.nn.Module):
        def forward(self, x):
            return x.mean(dim=(1, 2, 3)).view(-1, 1)

    return Motor(modelo=Trivial(), calibrador=calibrador, umbral=0.5,
                 tam_imagen=32, nombre_modelo="prueba", auc_validacion=0.88,
                 prevalencia_local=0.1466)


def test_clasificar_devuelve_el_contrato_completo(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes())

    esperadas = {"probabilidad_cruda", "probabilidad_calibrada",
                 "razon_de_verosimilitud", "umbral", "clasificacion",
                 "edad_paciente", "modelo", "auc_validacion", "milisegundos"}
    assert esperadas <= set(salida)
    assert 0.0 <= salida["probabilidad_cruda"] <= 1.0
    assert salida["edad_paciente"] == 54
    assert salida["razon_de_verosimilitud"] > 0


def test_una_placa_de_menor_se_rechaza(motor, tmp_path):
    """El modelo se entreno solo con adultos. Emitir una probabilidad sobre un
    nino seria dar por valido un numero que no lo es."""
    ruta = tmp_path / "nino.dcm"
    crear_dicom(ruta, edad="012Y")
    with pytest.raises(ErrorDeInferencia) as fallo:
        motor.clasificar(ruta.read_bytes())
    assert fallo.value.codigo == "fuera_de_alcance"
    assert "12" in str(fallo.value)


def test_una_edad_ilegible_no_se_da_por_adulta(motor, tmp_path):
    """Suponer que quien no declara edad es adulto es exactamente el atajo que
    el filtro existe para evitar."""
    ruta = tmp_path / "sin_edad.dcm"
    crear_dicom(ruta, edad="")
    with pytest.raises(ErrorDeInferencia) as fallo:
        motor.clasificar(ruta.read_bytes())
    assert fallo.value.codigo == "edad_desconocida"


def test_lo_que_no_es_un_dicom_se_rechaza_con_su_codigo(motor):
    with pytest.raises(ErrorDeInferencia) as fallo:
        motor.clasificar(b"esto no es un DICOM")
    assert fallo.value.codigo == "dicom_invalido"


def test_la_clasificacion_respeta_el_umbral(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes())
    esperada = ("opacidad_probable"
                if salida["probabilidad_cruda"] >= salida["umbral"]
                else "sin_opacidad_probable")
    assert salida["clasificacion"] == esperada


def test_el_preprocesamiento_es_el_mismo_que_el_de_entrenamiento(motor, tmp_path):
    """Si el servidor preprocesa distinto que el entrenamiento, el modelo se
    degrada en produccion y ninguna metrica lo avisa. Se captura el tensor que
    `clasificar` le pasa AL MODELO, no el que devuelve un metodo auxiliar que
    produccion no llama: si alguien cambia la conversion dentro de `clasificar`,
    esta prueba tiene que enterarse.
    """
    from PIL import Image
    from copiloto_triaje.datos.dataset import construir_transformaciones
    from copiloto_triaje.datos.dicom import leer_dicom_desde_bytes

    visto = {}
    original = motor.modelo.forward

    def espiar(x):
        visto["tensor"] = x
        return original(x)

    motor.modelo.forward = espiar

    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    datos = ruta.read_bytes()
    motor.clasificar(datos)

    arreglo, _ = leer_dicom_desde_bytes(datos)
    esperado = construir_transformaciones(32, entrenamiento=False)(
        Image.fromarray(arreglo).convert("RGB")).unsqueeze(0)
    assert torch.allclose(visto["tensor"], esperado)


@pytest.mark.parametrize("logit,extremo", [(-20.0, "minima"), (20.0, "maxima")])
def test_el_contrato_emite_la_evidencia_ya_acotada_por_la_curva(tmp_path, logit,
                                                                extremo):
    """Lo que sale del contrato tiene que ser el valor SOSTENIDO de la curva.

    La cota vive en `Calibrador.calibrar`, pero el numero que SP4 va a leer
    sale de aqui, y esta rama ya ha visto una decision correcta deshecha una
    capa mas arriba: un `round(x, 4)` que convertia el recorte de 1e-6 en 0,0.
    Comprobar solo `> 0` no lo habria detectado -1e-6 tambien es > 0-, asi que
    se compara con el valor exacto que la cota debe producir. Cualquier
    redondeo, recorte o default que se cuele entre `calibrar` y la respuesta
    hace fallar esta prueba.

    Se usa el calibrador REAL y no la fixture sintetica porque la fixture no
    llega a los tramos saturados de la curva.
    """
    real = Calibrador.desde_json("servidor/calibrador.json")
    esperada = getattr(real, f"probabilidad_{extremo}_sostenida")

    class Saturado(torch.nn.Module):
        def forward(self, x):
            # Logit enorme en valor absoluto: la cruda se sale de la curva por
            # el extremo que toque, que es donde la isotonica satura.
            return torch.full((x.shape[0], 1), logit)

    motor = Motor(modelo=Saturado(), calibrador=real, umbral=0.4258,
                  tam_imagen=32, nombre_modelo="prueba", auc_validacion=0.883,
                  prevalencia_local=0.1466)
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes())

    odds_previo = real.prevalencia / (1 - real.prevalencia)
    assert salida["probabilidad_calibrada"] == pytest.approx(esperada)
    assert salida["razon_de_verosimilitud"] == pytest.approx(
        (esperada / (1 - esperada)) / odds_previo)
    # Y las odds siempre se pueden calcular sobre lo que se reporta.
    p = salida["probabilidad_calibrada"]
    assert 0.0 < p < 1.0


@pytest.mark.parametrize("edad,acepta", [("017Y", False), ("018Y", True),
                                         ("100Y", True), ("101Y", False)])
def test_los_limites_de_edad_son_inclusive(motor, tmp_path, edad, acepta):
    """18 y 100 DEBEN pasar; 17 y 101 no. Sin esto, cambiar <= por < rechaza a
    todos los pacientes de 18 anios y la suite sigue en verde."""
    ruta = tmp_path / f"{edad}.dcm"
    crear_dicom(ruta, edad=edad)
    if acepta:
        assert motor.clasificar(ruta.read_bytes())["edad_paciente"] == int(edad[:3])
    else:
        with pytest.raises(ErrorDeInferencia) as fallo:
            motor.clasificar(ruta.read_bytes())
        assert fallo.value.codigo == "fuera_de_alcance"


def test_el_modelo_queda_en_modo_evaluacion(motor):
    """EfficientNet-B0 lleva Dropout en la cabeza: en modo entrenamiento, la
    misma radiografia daria una probabilidad distinta en cada llamada."""
    assert motor.modelo.training is False


def test_los_mensajes_que_lee_un_clinico_estan_bien_escritos():
    """Los detalles de `ErrorDeInferencia` los lee una persona, no un programa.

    Esta prueba existe porque NADA los fijaba y derivaron: durante semanas el
    servidor dijo «El paciente tiene 12 anios y el modelo solo es valido...»,
    sin tildes, y el bot lo relataba tal cual al profesional -pegado a un
    parrafo que si las llevaba-. Lo encontro una persona leyendo el corpus de
    la tarea 8, no una prueba.

    El codigo de este proyecto va sin tildes a proposito: los identificadores y
    los comentarios son para programadores. Los mensajes NO: son la voz del
    sistema ante un clinico, y un sistema que escribe mal le resta credibilidad
    a lo que dice -y aqui lo que dice es «esto no es un diagnostico, decide
    usted»-.
    """
    import pathlib
    import re

    raiz = pathlib.Path(__file__).resolve().parents[1] / "src" / "copiloto_triaje"
    fuentes = [raiz / "servicio" / "inferencia.py",
               raiz / "servicio" / "aplicacion.py"]

    # Palabras que en espanol llevan tilde y aparecen a menudo sin ella.
    SIN_TILDE = ("anios", "valido", "codigo", "numero", "maximo", "minimo",
                 "diagnostico", "analisis", "radiografia", "informacion",
                 "despues", "tambien", "aqui", "esta.", "mas ")
    # Formas de tuteo: el sistema trata de usted.
    TUTEO = (" pide ", " manda ", " envia ", " comprueba ", " revisa ",
             " vuelve a ", " intenta ")

    # Solo los textos de los errores: `raise ErrorDeInferencia(codigo, detalle)`.
    LLAMADA = re.compile(
        r'ErrorDeInferencia\(\s*\n?\s*"[a-z_]+",\s*\n?((?:\s*f?"[^"]*"\s*\n?)+)\)')

    mensajes = []
    for f in fuentes:
        for bloque in LLAMADA.findall(f.read_text(encoding="utf-8")):
            mensajes.append((f.name, " ".join(re.findall(r'"([^"]*)"', bloque))))

    assert mensajes, "no se encontro ningun ErrorDeInferencia: cambio la forma"

    for fichero, texto in mensajes:
        bajo = " " + texto.lower() + " "
        malas = [p for p in SIN_TILDE if p in bajo]
        assert not malas, f"{fichero}: sin tilde {malas} en «{texto}»"
        tuteo = [p for p in TUTEO if p in bajo]
        assert not tuteo, f"{fichero}: tuteo {tuteo} en «{texto}»"


# Los cinco datos que el bot manda con la placa (SP4 §9.3): con 38,2 > 37,8,
# 104 > 100 y crepitantes, tres puntos; el asma decide el cuarto.
HALLAZGOS = {"temperatura_c": 38.2, "frecuencia_cardiaca": 104,
             "crepitantes": True, "murmullo_disminuido": False, "asma": "si"}
CONTRATO_SP3 = {"probabilidad_cruda", "probabilidad_calibrada",
                "razon_de_verosimilitud", "umbral", "clasificacion",
                "edad_paciente", "modelo", "auc_validacion", "milisegundos"}


def test_sin_hallazgos_la_respuesta_es_la_de_sp3_clave_por_clave(motor, tmp_path):
    """Criterio 2 del spec de SP4, en el nucleo: ni una clave mas ni en otro
    orden."""
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes())
    assert set(salida) == CONTRATO_SP3
    assert list(salida) == [
        "probabilidad_cruda", "probabilidad_calibrada",
        "razon_de_verosimilitud", "umbral", "clasificacion", "edad_paciente",
        "modelo", "auc_validacion", "milisegundos",
    ]


def test_con_hallazgos_la_respuesta_trae_el_bloque_combinacion(motor, tmp_path):
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes(), HALLAZGOS)
    assert set(salida) == CONTRATO_SP3 | {"combinacion"}
    # La combinacion se calcula y se asigna ANTES que los milisegundos: si
    # `milisegundos` se asignara antes que `combinacion` dejaria de ser la
    # ultima clave y no contaria la combinacion.
    assert list(salida)[-1] == "milisegundos"
    c = salida["combinacion"]
    assert c["rv_imagen"] == salida["razon_de_verosimilitud"]
    assert c["prevalencia"] == motor.prevalencia_local == 0.1466
    assert c["puntuacion"] == [3]
    assert 0.0 < c["minima"] <= c["maxima"] < 1.0


def test_la_combinacion_usa_la_prevalencia_del_motor_y_no_una_fija(motor, tmp_path):
    """Spec §5: la prevalencia es un parametro, no una constante escondida.
    Con 0,1466 en todos los motores de prueba, un `combinacion(0.1466, ...)`
    fijo en `inferencia.py` pasaba en verde: aqui el motor lleva otra."""
    otro = Motor(modelo=motor.modelo, calibrador=motor.calibrador,
                 umbral=motor.umbral, tam_imagen=motor.tam_imagen,
                 nombre_modelo=motor.nombre_modelo,
                 auc_validacion=motor.auc_validacion, prevalencia_local=0.3)
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = otro.clasificar(ruta.read_bytes(), HALLAZGOS)
    c = salida["combinacion"]
    assert c["prevalencia"] == 0.3
    assert c["independencia"][0] == pytest.approx(
        combinar(0.3, 1.64, salida["razon_de_verosimilitud"]), abs=5e-4)


def test_unos_hallazgos_invalidos_se_rechazan_antes_de_leer_el_dicom(motor):
    """D4: es barato, y si vienen mal el fallo es de quien llama, no de la
    placa. Por eso gana incluso a un DICOM que no lo es."""
    with pytest.raises(ErrorDeInferencia) as exc:
        motor.clasificar(b"esto no es un dicom",
                         {**HALLAZGOS, "crepitantes": "false"})
    assert exc.value.codigo == "hallazgos_invalidos"
    assert "crepitantes" in str(exc.value)


def test_el_rechazo_por_edad_gana_a_la_combinacion(motor, tmp_path):
    """Con hallazgos perfectos y un menor, la respuesta es el rechazo de
    siempre y nada mas: ninguna rama de error emite una cifra."""
    ruta = tmp_path / "n.dcm"
    crear_dicom(ruta, edad="012Y")
    with pytest.raises(ErrorDeInferencia) as exc:
        motor.clasificar(ruta.read_bytes(), HALLAZGOS)
    assert exc.value.codigo == "fuera_de_alcance"


def test_la_prevalencia_local_es_obligatoria_y_una_probabilidad():
    class Nada(torch.nn.Module):
        def forward(self, x):
            return x.mean(dim=(1, 2, 3)).view(-1, 1)
    rng = np.random.default_rng(1)
    y = (rng.random(200) < 0.2).astype(int)
    cal = ajustar_calibrador(y, rng.random(200), 0.2, "prueba")
    comunes = dict(modelo=Nada(), calibrador=cal, umbral=0.5, tam_imagen=32,
                   nombre_modelo="prueba", auc_validacion=0.88)
    with pytest.raises(TypeError):
        Motor(**comunes)                                  # falta
    # `nan` no cumple ninguna comparacion e `inf` no esta por debajo de 1: las
    # dos tienen que caer en la misma guarda que un 1,5.
    for mala in (0.0, 1.0, 1.5, -0.2, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            Motor(**comunes, prevalencia_local=mala)
    assert Motor(**comunes, prevalencia_local=0.1466).prevalencia_local == 0.1466


# --- El umbral por vista (SP5-C1 §4) -----------------------------------------
#
# Una mitigacion de equidad: la etiqueta del cribado usa un umbral para las
# placas PA y otro para las AP. Es un parametro de despliegue OPCIONAL y esta
# APAGADO por defecto: sin el, la respuesta es la de SP3 y SP4 clave por clave.
# El umbral solo decide la etiqueta; la evidencia y la combinacion no cambian.

# El umbral global del `motor` es 0,5, asi que cada puntuacion de las pruebas
# cae en un sitio distinto: 0,30 queda por debajo del global y de AP y por
# encima de PA; 0,54 queda por encima del global y por debajo de AP.
UMBRALES_POR_VISTA = {"PA": 0.18, "AP": 0.58}


def _logit(p):
    return math.log(p / (1.0 - p))


class _PuntuacionFija(torch.nn.Module):
    """Un modelo que da SIEMPRE la misma puntuacion, sea cual sea la placa: lo
    unico que importa aqui es en que lado de cada umbral cae."""

    def __init__(self, puntuacion):
        super().__init__()
        self.logit = _logit(puntuacion)

    def forward(self, x):
        return torch.full((x.shape[0], 1), self.logit)


def _con_puntuacion(base, puntuacion, **extra):
    """Un motor como `base` pero con un modelo de puntuacion fija. `extra` son
    los parametros que cada prueba quiere probar (`umbrales_por_vista`)."""
    return Motor(modelo=_PuntuacionFija(puntuacion), calibrador=base.calibrador,
                 umbral=base.umbral, tam_imagen=base.tam_imagen,
                 nombre_modelo=base.nombre_modelo,
                 auc_validacion=base.auc_validacion,
                 prevalencia_local=base.prevalencia_local, **extra)


def _dicom_de_vista(tmp_path, vista):
    """Los bytes de un DICOM sintetico de 54 anios con esa `ViewPosition`.

    Con `vista=None` la cabecera NO lleva la etiqueta (un equipo que no la
    escribe), que no es lo mismo que llevarla vacia.
    """
    ruta = tmp_path / "vista.dcm"
    with warnings.catch_warnings():
        # pydicom avisa de que " pa " o "ll" no son valores validos de CS: es
        # justo lo que hay que escribir para ver que el motor lo lee igual.
        warnings.simplefilter("ignore", UserWarning)
        crear_dicom(ruta, edad="054Y", vista="" if vista is None else vista)
    if vista is None:
        ds = pydicom.dcmread(str(ruta))
        del ds.ViewPosition
        ds.save_as(str(ruta), enforce_file_format=True)
        assert "ViewPosition" not in pydicom.dcmread(str(ruta))
    return ruta.read_bytes()


def _claves(por_vista=False, con_hallazgos=False):
    """Las claves de la respuesta, en su orden: `umbral_por_vista` va justo
    detras de `umbral`, y `milisegundos` sigue siendo la ultima."""
    claves = ["probabilidad_cruda", "probabilidad_calibrada",
              "razon_de_verosimilitud", "umbral"]
    if por_vista:
        claves.append("umbral_por_vista")
    claves += ["clasificacion", "edad_paciente", "modelo", "auc_validacion"]
    if con_hallazgos:
        claves.append("combinacion")
    return claves + ["milisegundos"]


CON_Y_SIN_HALLAZGOS = pytest.mark.parametrize(
    "hallazgos", [None, HALLAZGOS], ids=["sin_hallazgos", "con_hallazgos"])


@pytest.mark.parametrize("vista", ["PA", "AP", "LL"])
@CON_Y_SIN_HALLAZGOS
def test_sin_umbrales_por_vista_la_respuesta_no_cambia(motor, tmp_path, hallazgos,
                                                       vista):
    """La regla de oro del parametro: apagado, la respuesta es la de hoy, clave
    por clave, con y sin `hallazgos` y sea cual sea la vista de la placa. Se
    mira de las dos formas de no pedirlo -sin el parametro y con `None`-, y los
    valores se calculan aqui aparte, no con lo que devuelve el motor."""
    datos = _dicom_de_vista(tmp_path, vista)
    # 0,30: por debajo del umbral global (0,5) y por encima del que tendria PA
    # (0,18). Si la vista se mirara aunque el parametro no este, saldria otra
    # etiqueta.
    cruda = float(torch.sigmoid(torch.tensor([_logit(0.30)]))[0])
    rv = motor.calibrador.razon_de_verosimilitud(cruda)
    esperada = {
        "probabilidad_cruda": round(cruda, 4),
        "probabilidad_calibrada": motor.calibrador.calibrar(cruda),
        "razon_de_verosimilitud": rv,
        "umbral": 0.5,
        "clasificacion": "sin_opacidad_probable",
        "edad_paciente": 54,
        "modelo": "prueba",
        "auc_validacion": 0.88,
    }
    if hallazgos is not None:
        esperada["combinacion"] = combinacion(motor.prevalencia_local,
                                              hallazgos, rv)

    for sin_parametro in (_con_puntuacion(motor, 0.30),
                          _con_puntuacion(motor, 0.30, umbrales_por_vista=None)):
        assert sin_parametro.umbrales_por_vista is None
        salida = sin_parametro.clasificar(datos, hallazgos)
        assert list(salida) == _claves(con_hallazgos=hallazgos is not None)
        assert "umbral_por_vista" not in salida
        assert {k: v for k, v in salida.items() if k != "milisegundos"} == esperada


@pytest.mark.parametrize("puntuacion, vista, umbral, clasificacion", [
    (0.30, "PA", 0.18, "opacidad_probable"),        # el global la dejaria en sin_
    (0.30, "AP", 0.58, "sin_opacidad_probable"),
    (0.54, "PA", 0.18, "opacidad_probable"),
    (0.54, "AP", 0.58, "sin_opacidad_probable"),    # el global la dejaria en opacidad_
])
@CON_Y_SIN_HALLAZGOS
def test_con_umbrales_por_vista_cada_vista_usa_el_suyo(motor, tmp_path, hallazgos,
                                                       puntuacion, vista, umbral,
                                                       clasificacion):
    con = _con_puntuacion(motor, puntuacion, umbrales_por_vista=UMBRALES_POR_VISTA)
    salida = con.clasificar(_dicom_de_vista(tmp_path, vista), hallazgos)

    # `umbral` es el APLICADO, no el global: quien lee la respuesta ve contra
    # que se comparo la puntuacion.
    assert salida["umbral"] == umbral
    assert salida["clasificacion"] == clasificacion
    assert salida["umbral_por_vista"] == {"vista": vista, "aplicado": True}
    assert list(salida) == _claves(por_vista=True,
                                   con_hallazgos=hallazgos is not None)


@pytest.mark.parametrize("vista", ["LL", "", None],
                         ids=["lateral", "etiqueta_vacia", "sin_etiqueta"])
def test_una_vista_desconocida_usa_el_umbral_global(motor, tmp_path, vista):
    """Ni PA ni AP: no hay umbral de vista que aplicar. Se usa el global y la
    respuesta lo dice, en vez de adivinar la vista."""
    con = _con_puntuacion(motor, 0.30, umbrales_por_vista=UMBRALES_POR_VISTA)
    salida = con.clasificar(_dicom_de_vista(tmp_path, vista))

    assert salida["umbral"] == 0.5
    # Con el de PA (0,18) esta misma placa saldria opacidad_probable.
    assert salida["clasificacion"] == "sin_opacidad_probable"
    assert salida["umbral_por_vista"] == {"vista": None, "aplicado": False}


@pytest.mark.parametrize("escrita, leida", [(" pa ", "PA"), ("ap", "AP"),
                                            (" Ap", "AP")])
def test_la_vista_se_lee_sin_espacios_ni_minusculas(motor, tmp_path, escrita, leida):
    con = _con_puntuacion(motor, 0.30, umbrales_por_vista=UMBRALES_POR_VISTA)
    salida = con.clasificar(_dicom_de_vista(tmp_path, escrita))

    assert salida["umbral_por_vista"] == {"vista": leida, "aplicado": True}
    assert salida["umbral"] == UMBRALES_POR_VISTA[leida]


@pytest.mark.parametrize("vista, cambia_la_etiqueta", [("PA", True), ("AP", False)])
def test_el_umbral_por_vista_no_toca_la_evidencia_ni_la_combinacion(
        motor, tmp_path, vista, cambia_la_etiqueta):
    """El umbral solo decide la etiqueta del cribado. Calibrar la razon de
    verosimilitud por vista queda fuera: la evidencia que SP4 combina con la
    clinica es la misma con el parametro encendido y apagado."""
    datos = _dicom_de_vista(tmp_path, vista)
    encendido = _con_puntuacion(motor, 0.30,
                                umbrales_por_vista=UMBRALES_POR_VISTA)
    sin = _con_puntuacion(motor, 0.30).clasificar(datos, HALLAZGOS)
    con = encendido.clasificar(datos, HALLAZGOS)

    for clave in ("probabilidad_cruda", "probabilidad_calibrada",
                  "razon_de_verosimilitud", "combinacion"):
        assert con[clave] == sin[clave], clave
    # Y nada mas cambia que lo que depende del umbral.
    del_umbral = {"umbral", "umbral_por_vista", "clasificacion", "milisegundos"}
    assert ({k: v for k, v in con.items() if k not in del_umbral}
            == {k: v for k, v in sin.items() if k not in del_umbral})
    # Que el parametro SI actuaba: la prueba no pasa por estar apagado.
    assert con["umbral"] != sin["umbral"]
    assert (con["clasificacion"] != sin["clasificacion"]) is cambia_la_etiqueta


MAL_FORMADOS = [
    ("falta_AP", {"PA": 0.18}, ("falta 'AP'",)),
    ("falta_PA", {"AP": 0.58}, ("falta 'PA'",)),
    ("faltan_las_dos", {}, ("falta 'PA', 'AP'",)),
    ("sobra_una", {"PA": 0.18, "AP": 0.58, "LL": 0.3}, ("sobra 'LL'",)),
    ("claves_en_minuscula", {"pa": 0.18, "ap": 0.58},
     ("falta 'PA', 'AP'", "sobra 'pa', 'ap'")),
    ("cero", {"PA": 0.0, "AP": 0.58}, ("'PA'", "0.0")),
    ("uno", {"PA": 0.18, "AP": 1.0}, ("'AP'", "1.0")),
    ("negativo", {"PA": -0.2, "AP": 0.58}, ("'PA'", "-0.2")),
    ("mayor_que_uno", {"PA": 0.18, "AP": 1.5}, ("'AP'", "1.5")),
    ("nan", {"PA": float("nan"), "AP": 0.58}, ("'PA'", "nan")),
    ("infinito", {"PA": 0.18, "AP": float("inf")}, ("'AP'", "inf")),
    ("texto", {"PA": 0.18, "AP": "alto"}, ("'AP'", "'alto'")),
    ("nada", {"PA": None, "AP": 0.58}, ("'PA'", "None")),
    ("booleano", {"PA": True, "AP": 0.58}, ("'PA'", "True")),
    ("no_es_un_mapa", [0.18, 0.58], ("mapa",)),
]


@pytest.mark.parametrize("malos, dice", [m[1:] for m in MAL_FORMADOS],
                         ids=[m[0] for m in MAL_FORMADOS])
def test_unos_umbrales_por_vista_mal_formados_se_rechazan_al_construir(
        motor, malos, dice):
    """Exactamente PA y AP, cada una un numero finito estrictamente entre 0 y
    1 -la misma guarda que la prevalencia-. Y el `ValueError` dice QUE esta
    mal: quien despliega lo lee en el arranque, no en una placa."""
    with pytest.raises(ValueError) as fallo:
        _con_puntuacion(motor, 0.30, umbrales_por_vista=malos)
    for trozo in dice:
        assert trozo in str(fallo.value), str(fallo.value)


def test_unos_umbrales_por_vista_bien_formados_se_aceptan_y_se_copian(motor):
    """Vale cualquier mapa, no solo un `dict`, y el motor guarda SU copia: si
    guardara el mapa de quien lo construyo, cambiarlo despues se saltaria la
    validacion de arriba."""
    originales = {"AP": 0.5815, "PA": 0.1798}
    con = _con_puntuacion(motor, 0.30,
                          umbrales_por_vista=MappingProxyType(originales))
    assert con.umbrales_por_vista == {"PA": 0.1798, "AP": 0.5815}

    originales["PA"] = 7.0
    assert con.umbrales_por_vista == {"PA": 0.1798, "AP": 0.5815}


def test_cargar_pasa_los_umbrales_por_vista_al_motor(motor, tmp_path):
    """`Motor.cargar` es la puerta del servidor: tiene que llevar el parametro
    hasta el constructor tal cual -y sus errores con el-. Se carga una red real
    sin entrenar, guardada aqui, para no depender de los pesos desplegados."""
    from copiloto_triaje.modelo.arquitectura import construir_modelo

    pesos = tmp_path / "pesos.pt"
    torch.save(construir_modelo("efficientnet_b0", congelar_backbone=False,
                                preentrenado=False).state_dict(), pesos)
    calibrador = motor.calibrador.a_json(tmp_path / "calibrador.json")
    comunes = dict(ruta_pesos=pesos, ruta_calibrador=calibrador, umbral=0.4258,
                   auc_validacion=0.8827, prevalencia_local=0.1466)

    assert Motor.cargar(**comunes).umbrales_por_vista is None
    con = Motor.cargar(**comunes, umbrales_por_vista=UMBRALES_POR_VISTA)
    assert con.umbrales_por_vista == UMBRALES_POR_VISTA
    with pytest.raises(ValueError, match="falta 'AP'"):
        Motor.cargar(**comunes, umbrales_por_vista={"PA": 0.18})


# --- El mapa de calor (SP5-C1 §5) ---------------------------------------------
#
# Grad-CAM sobre el ultimo bloque de EfficientNet-B0, respecto del logit de
# opacidad. El modelo de la fixture `motor` es trivial -no tiene `features` ni
# `classifier`-, asi que aqui se arma la red de verdad con pesos aleatorios y
# semilla fija: se prueba el algoritmo y el contrato del metodo, no que el mapa
# senale algo clinico.
#
# Una red sin entrenar trae las estadisticas de BatchNorm de fabrica y apaga sus
# activaciones capa tras capa: las del ultimo bloque apenas llegan a 1e-12, y el
# logit es el sesgo de la cabeza sea cual sea la placa. De ahi dos cosas. El mapa
# SIN normalizar vale ~1e-15 y no ~1, asi que quitar la normalizacion se nota de
# lejos. Y una prueba que compare LOGITS tiene que quitar el sesgo y comparar en
# relativo, o pasaria en vacio: lo que la imagen aporta al logit no llega a la
# resolucion de un float32 puesta al lado del sesgo.

# 128 px son 4 x 4 celdas en el ultimo bloque; con 32 seria una sola y no habria
# nada que interpolar.
TAM_MAPA = 128


@pytest.fixture
def motor_con_red(motor):
    """Un `Motor` con la EfficientNet-B0 de verdad y pesos aleatorios.

    La semilla se fija sin tocar el estado global de torch (`fork_rng`): las
    demas pruebas no tienen por que enterarse. El backbone queda congelado, que
    es lo que da `construir_modelo` por defecto, y eso obliga a `mapa_de_calor`
    a marcar la IMAGEN como derivable: sin eso no hay grafo que atraviese
    `features`. `Motor.cargar` lo carga sin congelar: las pruebas a las que esa
    diferencia les importa descongelan con `descongelar_todo`.
    """
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        modelo = construir_modelo("efficientnet_b0", preentrenado=False)
    return Motor(modelo=modelo, calibrador=motor.calibrador, umbral=motor.umbral,
                 tam_imagen=TAM_MAPA, nombre_modelo="prueba",
                 auc_validacion=motor.auc_validacion,
                 prevalencia_local=motor.prevalencia_local)


def _dicom_con_pixeles(tmp_path, pixeles):
    """Los bytes de un DICOM sintetico de 54 anios con ESOS pixeles (un arreglo
    cuadrado de uint8). `crear_dicom` escribe siempre el mismo patron, y aqui
    hacen falta una imagen con forma y otras uniformes."""
    ruta = tmp_path / "pixeles.dcm"
    crear_dicom(ruta, edad="054Y", lado=pixeles.shape[0])
    ds = pydicom.dcmread(str(ruta))
    ds.PixelData = pixeles.astype(np.uint8).tobytes()
    ds.save_as(str(ruta), enforce_file_format=True)
    return ruta.read_bytes()


def _placa_asimetrica(lado=64):
    """Una rampa vertical con un bloque brillante arriba a la izquierda: ni
    uniforme ni simetrica, para que un mapa traspuesto o volteado no pase por
    bueno."""
    pixeles = np.tile(np.linspace(0, 200, lado).astype(np.uint8)[:, None],
                      (1, lado))
    pixeles[4:20, 6:30] = 255
    return pixeles


@pytest.fixture
def placa(tmp_path):
    """Los bytes de un DICOM de 54 anios con la placa asimetrica."""
    return _dicom_con_pixeles(tmp_path, _placa_asimetrica())


_TIPOS_DE_GANCHO = ("_forward_hooks", "_forward_pre_hooks", "_backward_hooks",
                    "_backward_pre_hooks")


def _ganchos(modelo):
    """Los ganchos que lleva registrados CUALQUIER modulo del modelo, como
    {nombre del modulo: [tipos de gancho]}. Vacio si no hay ninguno."""
    return {nombre: [t for t in _TIPOS_DE_GANCHO if getattr(modulo, t)]
            for nombre, modulo in modelo.named_modules()
            if any(getattr(modulo, t) for t in _TIPOS_DE_GANCHO)}


def _espiar_entradas(modulo, modelo):
    """Envuelve el `forward` de `modulo` y devuelve la lista donde cada llamada
    anota lo que recibe y los ganchos que `modelo` lleva EN ESE MOMENTO."""
    llamadas = []
    original = modulo.forward

    def espiar(x, *resto, **kwargs):
        llamadas.append({"entrada": x, "ganchos": _ganchos(modelo)})
        return original(x, *resto, **kwargs)

    modulo.forward = espiar
    return llamadas


def test_el_mapa_de_calor_tiene_la_forma_y_el_tipo_del_contrato(motor_con_red, placa):
    """`(tam_imagen, tam_imagen)` y float32, sea cual sea el tamano de la placa
    -la de la prueba es de 64 x 64 y el modelo la ve a 128-: es el tamano de
    entrada del modelo, y la app lo reescala a la imagen original."""
    mapa = motor_con_red.mapa_de_calor(placa)
    assert isinstance(mapa, np.ndarray)
    assert mapa.dtype == np.float32
    assert mapa.shape == (TAM_MAPA, TAM_MAPA)


def test_el_mapa_de_calor_esta_entre_cero_y_uno_y_llega_a_uno(motor_con_red, placa):
    """Normalizado por su maximo: el punto mas caliente vale 1. Con estos pesos
    el mapa sin normalizar no pasa de ~1e-14 (ver arriba), asi que sin la
    division esta prueba falla de lejos."""
    mapa = motor_con_red.mapa_de_calor(placa)
    # Que no pase en vacio: con la semilla 0 y esta placa el mapa no es de ceros
    # (con otras semillas puede serlo) y entonces su maximo seria 0, no 1.
    assert mapa.any(), "el mapa de la prueba es de ceros: no prueba la normalizacion"
    assert mapa.min() >= 0.0
    assert mapa.max() <= 1.0
    assert mapa.max() == pytest.approx(1.0)


def test_dos_llamadas_dan_el_mismo_mapa(motor_con_red, placa):
    """El mapa es una funcion de la placa. Con el modelo en modo entrenamiento
    el Dropout de la cabeza lo haria distinto en cada llamada. Se compara con
    1e-6 de margen y no a la igualdad exacta de los bits: lo que esta prueba
    persigue es un mapa que cambia de verdad, no el orden de una suma."""
    primero = motor_con_red.mapa_de_calor(placa)
    segundo = motor_con_red.mapa_de_calor(placa)
    np.testing.assert_allclose(segundo, primero, rtol=0, atol=1e-6)


@pytest.mark.parametrize("valor", [0, 128, 255], ids=["negra", "gris", "blanca"])
def test_una_imagen_uniforme_no_da_nan(motor_con_red, tmp_path, valor):
    """Una placa sin ningun detalle -negra, gris o blanca- da un mapa finito y
    entre 0 y 1. La rama del mapa de ceros, la que dividiria 0 entre 0, la fija
    la prueba de abajo."""
    mapa = motor_con_red.mapa_de_calor(
        _dicom_con_pixeles(tmp_path, np.full((64, 64), valor, np.uint8)))
    assert np.isfinite(mapa).all()
    assert mapa.min() >= 0.0 and mapa.max() <= 1.0


@pytest.mark.parametrize("imagen", ["con_forma", "uniforme"])
def test_con_el_gradiente_nulo_el_mapa_es_de_ceros(motor_con_red, tmp_path, imagen):
    """Sin gradiente no hay a quien atribuirle nada: con los pesos de la cabeza
    a cero el logit no depende de la imagen, y el mapa tiene que ser una matriz
    de ceros, no `nan`. Dividir por el maximo sin mirar si es 0 da 0/0 en todos
    los puntos -y normalizar entre el minimo y el maximo, tambien-. Es la rama a
    la que llega una placa uniforme en cuanto su mapa sin normalizar queda
    entero por debajo de 0."""
    torch.nn.init.zeros_(motor_con_red.modelo.classifier[-1].weight)
    pixeles = (_placa_asimetrica() if imagen == "con_forma"
               else np.full((64, 64), 128, np.uint8))
    mapa = motor_con_red.mapa_de_calor(_dicom_con_pixeles(tmp_path, pixeles))
    assert mapa.dtype == np.float32 and mapa.shape == (TAM_MAPA, TAM_MAPA)
    assert not np.isnan(mapa).any()
    assert not mapa.any()


def test_el_mapa_es_el_grad_cam_de_la_red(motor_con_red, placa):
    """Contra una referencia que no usa autograd, para que la prueba no sea solo
    de forma: un mapa sin gradientes, con otra capa, sin ReLU, traspuesto o
    interpolado a lo bruto cumpliria el contrato de arriba y no seria Grad-CAM.

    Con un promedio global y una capa lineal por cabeza, el gradiente del logit
    respecto de cada activacion es w_c / (h * w), el mismo en todo el mapa:
    Grad-CAM se reduce a CAM, ReLU(suma_c w_c * A_c), salvo un factor positivo
    que la normalizacion se lleva. Se calcula asi, sobre las activaciones del
    ultimo bloque, y el mapa del motor -que si pasa por autograd- tiene que
    salir igual."""
    modelo = motor_con_red.modelo
    arreglo, _ = leer_dicom_desde_bytes(placa)
    x = motor_con_red._tensor_desde_arreglo(arreglo)    # que usa el mapa, lo vigila otra
    with torch.no_grad():
        activaciones = modelo.features(x)[0]                    # (1280, 4, 4)
        pesos = modelo.classifier[-1].weight[0]                 # (1280,)
        cam = torch.relu(torch.einsum("c,chw->hw", pesos, activaciones))
        assert cam.max() > 0, "la referencia de la prueba es de ceros"
        cam = F.interpolate(cam[None, None], size=(TAM_MAPA, TAM_MAPA),
                            mode="bilinear", align_corners=False)[0, 0]
    esperado = (cam / cam.max()).numpy()

    np.testing.assert_allclose(motor_con_red.mapa_de_calor(placa), esperado,
                               rtol=0, atol=1e-4)


def test_el_mapa_usa_el_tensor_que_construye_el_entrenamiento(motor_con_red, placa):
    """Lo mismo que la prueba del preprocesamiento de arriba, para el mapa: se
    captura lo que `mapa_de_calor` le pasa AL MODELO -a `features`, que es lo
    primero que ve- y se compara con la conversion armada aparte, no con lo que
    devuelva `_tensor_desde_arreglo`. Un mapa calculado sobre una imagen
    distinta de la que clasifica seria el mapa de otra placa."""
    modelo = motor_con_red.modelo
    llamadas = _espiar_entradas(modelo.features, modelo)

    motor_con_red.mapa_de_calor(placa)

    arreglo, _ = leer_dicom_desde_bytes(placa)
    esperado = construir_transformaciones(TAM_MAPA, entrenamiento=False)(
        Image.fromarray(arreglo).convert("RGB")).unsqueeze(0)
    assert llamadas, "el mapa no paso por `features`"
    assert torch.allclose(llamadas[0]["entrada"], esperado)


def test_el_mapa_no_registra_ganchos_ni_durante_el_calculo(motor_con_red, placa):
    """El `Motor` es uno solo y la app lo comparte entre sesiones, que corren en
    hilos distintos. Un gancho de `forward` registrado para capturar las
    activaciones estaria vivo mientras OTRA sesion llama a `clasificar`, y se
    dispararia dentro de ella mezclando sus activaciones con las de este mapa.
    Quitarlo en un `finally` no lo evita: la ventana esta ENTRE registrarlo y
    quitarlo. Por eso se mira el modelo durante el calculo -al entrar en
    `features` y en `classifier`- y no solo despues."""
    modelo = motor_con_red.modelo
    en_features = _espiar_entradas(modelo.features, modelo)
    en_cabeza = _espiar_entradas(modelo.classifier, modelo)

    motor_con_red.mapa_de_calor(placa)

    assert en_features and en_cabeza, "el mapa no paso por `features` y `classifier`"
    for llamada in en_features + en_cabeza:
        assert llamada["ganchos"] == {}
    assert _ganchos(modelo) == {}


@pytest.mark.parametrize("congelado", [True, False],
                         ids=["backbone_congelado", "backbone_descongelado"])
def test_el_mapa_deja_el_modelo_como_lo_encontro(motor_con_red, placa, congelado):
    """Lo que el mapa deje cambiado en el modelo compartido lo ve la siguiente
    peticion de cualquier sesion: ni modo entrenamiento (el Dropout de la cabeza
    y las estadisticas de BatchNorm), ni pesos o estadisticas distintos, ni
    banderas `requires_grad` cambiadas, ni gradientes acumulados en los
    parametros (lo que dejaria un `backward()` en vez de `autograd.grad`).

    Se mira con el backbone congelado y descongelado: `Motor.cargar` lo despliega
    descongelado, donde un `backward()` si dejaria `.grad` en todos los pesos."""
    modelo = motor_con_red.modelo
    if not congelado:
        descongelar_todo(modelo)
    estado = {k: v.clone() for k, v in modelo.state_dict().items()}
    banderas = {n: p.requires_grad for n, p in modelo.named_parameters()}

    motor_con_red.mapa_de_calor(placa)

    assert not any(m.training for m in modelo.modules())     # sigue en eval()
    despues = modelo.state_dict()
    assert despues.keys() == estado.keys()
    assert all(torch.equal(despues[k], estado[k]) for k in estado)
    assert {n: p.requires_grad for n, p in modelo.named_parameters()} == banderas
    assert all(p.grad is None for p in modelo.parameters())


def test_despues_del_mapa_la_clasificacion_es_la_misma(motor_con_red, placa):
    """La misma placa, la misma respuesta, antes y despues de pedir su mapa. Es
    la formulacion de punta a punta: en una red sin entrenar la respuesta es casi
    solo el sesgo (ver arriba) y ve poco por si sola, asi que lo que sostiene
    esta garantia son las comprobaciones sobre el estado del modelo, las de la
    prueba anterior y la de los ganchos."""
    antes = motor_con_red.clasificar(placa, HALLAZGOS)
    motor_con_red.mapa_de_calor(placa)
    despues = motor_con_red.clasificar(placa, HALLAZGOS)

    def sin_tiempo(respuesta):
        return {k: v for k, v in respuesta.items() if k != "milisegundos"}

    assert sin_tiempo(despues) == sin_tiempo(antes)


def test_el_mapa_se_calcula_aunque_quien_llama_tenga_los_gradientes_apagados(
        motor_con_red, placa):
    """`clasificar` trabaja bajo `torch.no_grad()` y la app puede envolver todo
    lo suyo igual: el mapa enciende los gradientes para si mismo y deja el modo
    como lo encontro -ni apagado para quien lo tenia encendido ni encendido
    para quien lo tenia apagado."""
    esperado = motor_con_red.mapa_de_calor(placa)
    assert torch.is_grad_enabled()
    with torch.no_grad():
        mapa = motor_con_red.mapa_de_calor(placa)
        assert not torch.is_grad_enabled()
    assert torch.is_grad_enabled()
    np.testing.assert_allclose(mapa, esperado, rtol=0, atol=1e-6)


@pytest.mark.parametrize("cual, codigo", [("menor", "fuera_de_alcance"),
                                          ("sin_edad", "edad_desconocida"),
                                          ("no_es_dicom", "dicom_invalido")])
def test_el_mapa_rechaza_lo_mismo_que_clasificar(motor_con_red, tmp_path, cual, codigo):
    """Un menor, una edad que no se lee y lo que no es un DICOM se rechazan con
    el mismo codigo y el MISMO mensaje que en `clasificar`: las dos comparten la
    lectura y las comprobaciones de edad, y esta prueba hace fallar a quien las
    copie en vez de compartirlas y las deje divergir. Un mapa de un paciente
    que el modelo no admite seria dar por valido lo que no lo es."""
    if cual == "no_es_dicom":
        datos = b"esto no es un DICOM"
    else:
        ruta = tmp_path / "a.dcm"
        crear_dicom(ruta, edad="012Y" if cual == "menor" else "")
        datos = ruta.read_bytes()

    def rechazo(llamar):
        with pytest.raises(ErrorDeInferencia) as fallo:
            llamar(datos)
        return fallo.value.codigo, str(fallo.value)

    por_el_mapa = rechazo(motor_con_red.mapa_de_calor)
    assert por_el_mapa[0] == codigo
    assert por_el_mapa == rechazo(motor_con_red.clasificar)


def test_la_composicion_a_mano_del_forward_es_la_del_modelo(motor_con_red):
    """`mapa_de_calor` no llama a `modelo(x)`: compone el forward a mano
    -`features`, `avgpool`, `flatten`, `classifier`- para tener en la mano las
    activaciones del ultimo bloque sin registrar ningun gancho. Eso solo vale
    mientras esa composicion SEA el forward del modelo: si torchvision metiera
    un paso mas entre el pooling y la cabeza, el mapa seria el de una red que no
    es la que clasifica y nada mas lo avisaria.

    Sin sesgo y solo en relativo (`atol=0`): con el sesgo puesto, `modelo(x)`
    seria el sesgo (ver arriba) y cualquier composicion lo igualaria, tambien
    con la tolerancia por defecto, que es absoluta."""
    modelo = motor_con_red.modelo
    torch.nn.init.zeros_(modelo.classifier[-1].bias)
    x = torch.randn(2, 3, TAM_MAPA, TAM_MAPA,
                    generator=torch.Generator().manual_seed(1))
    with torch.no_grad():
        del_modelo = modelo(x)
        a_mano = modelo.classifier(
            torch.flatten(modelo.avgpool(modelo.features(x)), 1))

    # Que la comparacion pueda fallar: dos entradas distintas dan logits distintos.
    assert not torch.allclose(del_modelo[0], del_modelo[1], rtol=1e-3, atol=0)
    assert torch.allclose(a_mano, del_modelo, rtol=1e-5, atol=0)
