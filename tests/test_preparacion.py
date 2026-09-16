import re

import pandas as pd
import pytest

from copiloto_triaje.datos.preparacion import (
    cargar_etiquetas, construir_registros, escribir_manifiestos, verificar_zip_existe,
)
from copiloto_triaje.datos.particion import particionar_por_paciente


def test_cargar_etiquetas_colapsa_las_filas_por_paciente(tmp_path):
    """Un paciente positivo tiene varias filas (una por caja); debe quedar
    una sola etiqueta y ser positiva."""
    csv = tmp_path / "labels.csv"
    csv.write_text(
        "patientId,x,y,width,height,Target\n"
        "P0001,10,10,50,50,1\n"
        "P0001,80,80,40,40,1\n"
        "P0002,,,,,0\n", encoding="utf-8")
    etiquetas = cargar_etiquetas(csv)
    assert etiquetas == {"P0001": 1, "P0002": 0}


def test_construir_registros_cruza_metadatos_con_etiquetas():
    metadatos = [{"patientId": "P0001", "archivo_png": "P0001.png", "edad": "51"},
                 {"patientId": "P0002", "archivo_png": "P0002.png", "edad": "19"}]
    registros = construir_registros(metadatos, {"P0001": 1, "P0002": 0})
    assert len(registros) == 2
    assert registros[0]["etiqueta"] == 1
    assert registros[1]["etiqueta"] == 0


def test_construir_registros_descarta_los_que_no_tienen_etiqueta():
    metadatos = [{"patientId": "P0001", "archivo_png": "P0001.png"},
                 {"patientId": "FANTASMA", "archivo_png": "X.png"}]
    registros = construir_registros(metadatos, {"P0001": 1})
    assert [r["patientId"] for r in registros] == ["P0001"]


def test_escribir_manifiestos_crea_tres_csv_con_la_semilla(tmp_path):
    registros = [{"patientId": f"P{i:04d}", "archivo_png": f"P{i:04d}.png",
                  "etiqueta": i % 4 == 0} for i in range(100)]
    for r in registros:
        r["etiqueta"] = int(r["etiqueta"])
    particiones = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    rutas = escribir_manifiestos(particiones, tmp_path, semilla=42)
    assert set(rutas) == {"train", "val", "test"}
    for nombre, ruta in rutas.items():
        df = pd.read_csv(ruta)
        assert {"patientId", "archivo_png", "etiqueta", "semilla"} <= set(df.columns)
        assert (df["semilla"] == 42).all()


def test_verificar_zip_existe_falla_de_inmediato_citando_la_ruta_buscada(tmp_path):
    """El spec exige que la configuracion invalida (rutas inexistentes) falle
    de forma inmediata y explicita al inicio, no a mitad del proceso, y que el
    mensaje sea accionable. Config no puede validar esto (otras pruebas la
    construyen a proposito con rutas temporales inexistentes), asi que la
    validacion vive aqui y la usa el script antes de descomprimir nada."""
    zip_inexistente = tmp_path / "no_existe.zip"
    with pytest.raises(FileNotFoundError, match=re.escape(str(zip_inexistente))):
        verificar_zip_existe(zip_inexistente)

    # tmp_path existe pero es un directorio, no un archivo: tambien debe fallar.
    with pytest.raises(FileNotFoundError, match=re.escape(str(tmp_path))):
        verificar_zip_existe(tmp_path)
