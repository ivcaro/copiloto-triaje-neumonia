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


def test_el_contrato_nunca_emite_probabilidad_cero_ni_uno(tmp_path):
    """El recorte de `Calibrador.calibrar` existe para que SP4 no reciba 0 ni 1
    exactos: lo primero que hara con la probabilidad es calcular p/(1-p). Un
    `round(x, 4)` sobre un recorte de 1e-6 lo deshace, y el fallo no se ve
    porque la fixture sintetica nunca llega a los extremos de la curva.
    """
    real = Calibrador.desde_json("servidor/calibrador.json")

    class CasiCero(torch.nn.Module):
        def forward(self, x):
            # logit muy negativo: cruda ~ 1e-9, por debajo del minimo de la curva
            return torch.full((x.shape[0], 1), -20.0)

    motor = Motor(modelo=CasiCero(), calibrador=real, umbral=0.4258,
                  tam_imagen=32, nombre_modelo="prueba", auc_validacion=0.883)
    ruta = tmp_path / "a.dcm"
    crear_dicom(ruta, edad="054Y")
    salida = motor.clasificar(ruta.read_bytes())

    assert salida["probabilidad_calibrada"] > 0.0
    assert salida["razon_de_verosimilitud"] > 0.0
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
