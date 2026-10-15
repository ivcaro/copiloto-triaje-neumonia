# -*- coding: utf-8 -*-
"""La capa del curso para los datos (SP5-C2): `src/data_processing.py` y `src/utils.py`.

QUÉ VIGILA
- Que `src/data_processing.py` no tiene lógica propia: lo que reexporta es, objeto por
  objeto, lo de `copiloto_triaje.datos`, y lo que define él mismo es un `main` que llama a
  `scripts/preparar_datos.py`.
- Que reexportar no rompe nada: lo que se importa desde la capa del curso hace lo mismo que
  desde el paquete (la partición por paciente y su comprobación de fuga, el filtro de edad).
- Que `python -m src.data_processing` hace de verdad el trabajo: con unos DICOM de juguete
  deja los tres manifiestos, sin ningún paciente en dos de ellos.
- Las utilidades de `src/utils.py`: la raíz y las rutas (todas dentro del repositorio y
  relativas a él), el cargador de guiones y el reparto de `sys.argv`.

Esta prueba importa torch (el `Dataset` está en lo que se reexporta): corre en la imagen Linux
de pruebas (README, «Pruebas»).
"""
import hashlib
import inspect
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:      # `src` es un paquete de la raíz, no de `pythonpath`
    sys.path.insert(0, str(REPO))

from copiloto_triaje.datos import dataset, dicom, particion, preparacion  # noqa: E402

from src import data_processing, utils  # noqa: E402

PIEZAS = {
    "DatasetRadiografias": dataset, "construir_transformaciones": dataset,
    "PlacaNoEvaluable": dicom, "comprobar_que_se_puede_evaluar": dicom,
    "convertir_a_png": dicom, "convertir_lote": dicom, "leer_dicom": dicom,
    "leer_dicom_desde_bytes": dicom,
    "FugaDeDatos": particion, "particionar_por_paciente": particion,
    "verificar_sin_fuga": particion,
    "cargar_etiquetas": preparacion, "construir_registros": preparacion,
    "edad_en_anios": preparacion, "escribir_manifiestos": preparacion,
    "filtrar_por_edad": preparacion,
}


# --------------------------------------------------------------------------
# Sin lógica propia
# --------------------------------------------------------------------------
@pytest.mark.parametrize("nombre,modulo", sorted(PIEZAS.items()))
def test_lo_que_reexporta_es_el_mismo_objeto_que_el_del_paquete(nombre, modulo):
    assert getattr(data_processing, nombre) is getattr(modulo, nombre)
    assert nombre in data_processing.__all__


def test_todo_lo_publico_es_del_paquete_salvo_el_main_que_llama_al_guion():
    propios = [n for n in data_processing.__all__ if n not in PIEZAS]
    assert propios == ["main"]
    for nombre in data_processing.__all__:
        objeto = getattr(data_processing, nombre)
        if nombre != "main":
            assert objeto.__module__.startswith("copiloto_triaje.datos."), nombre
    # y el `main` es una llamada, no una copia: cabe en unas pocas líneas
    fuente = inspect.getsource(data_processing.main).splitlines()
    assert len([linea for linea in fuente if linea.strip()]) < 8


def test_los_modulos_de_la_capa_dicen_donde_esta_la_implementacion():
    for modulo in (data_processing, utils):
        assert "copiloto_triaje" in modulo.__doc__, modulo.__name__
        assert "DÓNDE ESTÁ LA IMPLEMENTACIÓN" in modulo.__doc__, modulo.__name__


# --------------------------------------------------------------------------
# Reexportar no rompe nada
# --------------------------------------------------------------------------
def _registros(n_pacientes=120, por_paciente=2):
    return [{"patientId": f"P{i:04d}", "archivo": f"P{i:04d}_{j}.png",
             "etiqueta": int(i < n_pacientes * 0.225), "edad": 50}
            for i in range(n_pacientes) for j in range(por_paciente)]


def test_la_particion_por_paciente_desde_la_capa_del_curso_no_tiene_fuga():
    registros = _registros()
    partes = data_processing.particionar_por_paciente(registros, (0.7, 0.15, 0.15), 42)
    data_processing.verificar_sin_fuga(partes)          # no lanza
    assert sum(len(v) for v in partes.values()) == len(registros)
    assert partes == particion.particionar_por_paciente(registros, (0.7, 0.15, 0.15), 42)


def test_la_comprobacion_de_fuga_desde_la_capa_del_curso_la_detecta():
    partes = {"train": [{"patientId": "P1"}], "val": [{"patientId": "P1"}], "test": []}
    with pytest.raises(data_processing.FugaDeDatos):
        data_processing.verificar_sin_fuga(partes)


def test_el_filtro_de_adultos_desde_la_capa_del_curso():
    registros = [{"patientId": "a", "edad": "051Y"}, {"patientId": "b", "edad": "007Y"},
                 {"patientId": "c", "edad": "150Y"}]
    quedan, resumen = data_processing.filtrar_por_edad(registros, 18, 100)
    assert [r["patientId"] for r in quedan] == ["a"]
    assert resumen["descartados"] == 2


# --------------------------------------------------------------------------
# `python -m src.data_processing`, de punta a punta
# --------------------------------------------------------------------------
N_PACIENTES = 30
POR_PACIENTE = 2


def _escribir_dicom(ruta: Path, patient_id: str, lado: int = 32) -> None:
    ds = Dataset()
    ds.PatientID, ds.PatientAge, ds.PatientSex = patient_id, "051Y", "F"
    ds.ViewPosition, ds.Modality = "PA", "CR"
    ds.Rows, ds.Columns = lado, lado
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 8, 8, 7, 0
    ds.PixelData = (np.arange(lado * lado) % 256).astype(np.uint8).tobytes()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.2"
    ds.file_meta.MediaStorageSOPInstanceUID = generate_uid()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.save_as(str(ruta), enforce_file_format=True)


@pytest.fixture(scope="module")
def preparado(tmp_path_factory):
    """Un RSNA de juguete (30 pacientes con dos placas cada uno), preparado por la capa del
    curso. Devuelve (raíz de salida, código de salida)."""
    base = tmp_path_factory.mktemp("rsna_juguete")
    crudo = base / "crudo"
    imagenes = crudo / "stage_2_train_images"
    imagenes.mkdir(parents=True)
    filas = ["patientId,x,y,width,height,Target"]
    for i in range(N_PACIENTES):
        pid = f"P{i:04d}"
        for j in range(POR_PACIENTE):
            _escribir_dicom(imagenes / f"{pid}_{j}.dcm", pid)
        filas.append(f"{pid},10,10,50,50,1" if i < 7 else f"{pid},,,,,0")
    (crudo / "stage_2_train_labels.csv").write_text("\n".join(filas) + "\n", encoding="utf-8")
    raiz = base / "trabajo"
    antes = list(sys.argv)
    codigo = data_processing.main(["--crudo", str(crudo), "--raiz", str(raiz), "--semilla", "42"])
    assert sys.argv == antes, "el main no restauró sys.argv"
    return raiz, codigo


def test_el_main_de_la_capa_del_curso_prepara_los_datos(preparado):
    raiz, codigo = preparado
    assert codigo == 0
    for nombre in ("train", "val", "test"):
        assert (raiz / "manifiestos" / f"{nombre}.csv").is_file(), nombre
    assert len(list((raiz / "png").glob("*.png"))) == N_PACIENTES * POR_PACIENTE


def test_los_manifiestos_que_deja_la_capa_del_curso_no_tienen_fuga(preparado):
    raiz, _ = preparado
    ids = {n: set(pd.read_csv(raiz / "manifiestos" / f"{n}.csv")["patientId"].astype(str))
           for n in ("train", "val", "test")}
    assert ids["train"] | ids["val"] | ids["test"] == {f"P{i:04d}" for i in range(N_PACIENTES)}
    assert ids["train"].isdisjoint(ids["val"])
    assert ids["train"].isdisjoint(ids["test"])
    assert ids["val"].isdisjoint(ids["test"])


def test_el_main_lista_las_opciones_del_guion_con_help(capsys):
    with pytest.raises(SystemExit) as salida:
        data_processing.main(["--help"])
    assert salida.value.code == 0
    texto = capsys.readouterr().out
    assert "python -m src.data_processing" in texto
    for opcion in ("--zip", "--crudo", "--raiz", "--limite", "--semilla"):
        assert opcion in texto


def test_sin_argumentos_el_main_se_para_con_el_uso_del_guion(capsys):
    with pytest.raises(SystemExit) as salida:
        data_processing.main([])
    assert salida.value.code == 2
    assert "--zip" in capsys.readouterr().err


# --------------------------------------------------------------------------
# `src/utils.py`
# --------------------------------------------------------------------------
def test_la_raiz_es_la_del_repositorio_y_las_rutas_son_relativas_a_ella():
    assert utils.RAIZ == REPO
    assert (utils.RAIZ / "pyproject.toml").is_file()
    for ruta in (utils.CALIBRADOR_DESPLEGADO, utils.PUNTUACIONES_DE_PRUEBA,
                 utils.METRICAS_PUBLICADAS, utils.DIR_RESULTADOS, utils.PESOS_DESPLEGADOS):
        assert utils.RAIZ in ruta.parents, ruta
    assert utils.CALIBRADOR_DESPLEGADO.is_file()
    assert utils.METRICAS_PUBLICADAS.is_file()
    # los pesos son `models/` o `servidor/`, según dónde se hayan puesto
    assert utils.PESOS_DESPLEGADOS.parent.name in ("models", "servidor")


def test_el_cargador_de_guiones_devuelve_el_modulo_y_lo_reutiliza():
    guion = utils.cargar_guion("app/generar_metricas.py")
    assert callable(guion.generar) and guion.UMBRAL == 0.4258
    assert utils.cargar_guion("app/generar_metricas.py") is guion


def test_un_guion_que_no_esta_se_dice_con_su_ruta():
    with pytest.raises(FileNotFoundError, match=r"scripts/no_existe\.py"):
        utils.cargar_guion("scripts/no_existe.py")


def test_ejecutar_guion_reparte_los_argumentos_y_restaura_sys_argv(monkeypatch):
    guion = utils.cargar_guion("scripts/preparar_datos.py")
    vistos = {}

    def falso_main():
        vistos["argv"] = list(sys.argv)
        return 7

    monkeypatch.setattr(guion, "main", falso_main)
    antes = list(sys.argv)
    assert utils.ejecutar_guion("scripts/preparar_datos.py", ["--a", "1"], prog="mi-orden") == 7
    assert vistos["argv"] == ["mi-orden", "--a", "1"]
    assert sys.argv == antes
    # un guion que no devuelve nada sale con 0, y sys.argv se restaura aunque falle
    monkeypatch.setattr(guion, "main", lambda: None)
    assert utils.ejecutar_guion("scripts/preparar_datos.py", []) == 0

    def roto():
        raise RuntimeError("falla")

    monkeypatch.setattr(guion, "main", roto)
    with pytest.raises(RuntimeError):
        utils.ejecutar_guion("scripts/preparar_datos.py", ["--x"])
    assert sys.argv == antes


def test_sha256_de_es_el_de_hashlib(tmp_path):
    fichero = tmp_path / "pesos.bin"
    contenido = bytes(range(256)) * 9000          # más de un bloque de lectura
    fichero.write_bytes(contenido)
    assert utils.sha256_de(fichero) == hashlib.sha256(contenido).hexdigest()


def test_configurar_registro_es_idempotente():
    import logging
    utils.configurar_registro()
    manejadores = len(logging.getLogger().handlers)
    registro = utils.configurar_registro(detallado=True)
    assert registro is utils.registro and registro.name == "copiloto"
    assert len(logging.getLogger().handlers) == manejadores
