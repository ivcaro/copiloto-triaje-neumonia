"""Pruebas del nucleo de inferencia.

Se prueba aqui, en el paquete y no contra el servidor, para que corran sin
levantar Docker y en menos de un segundo.
"""
import numpy as np
import pytest
import torch

from copiloto_triaje.servicio.calibracion import Calibrador, ajustar_calibrador
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
                 tam_imagen=32, nombre_modelo="prueba", auc_validacion=0.88)


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
                  tam_imagen=32, nombre_modelo="prueba", auc_validacion=0.883)
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
