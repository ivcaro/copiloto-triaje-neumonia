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


# ---------------------------------------------------------------- filtro de edad

def test_edad_en_anios_interpreta_las_formas_del_estandar_dicom():
    from copiloto_triaje.datos.preparacion import edad_en_anios
    assert edad_en_anios("51") == 51        # forma de RSNA: numero suelto
    assert edad_en_anios("051Y") == 51      # forma del estandar, con unidad
    assert edad_en_anios("018M") == 1       # 18 MESES es un bebe, no 18 anios
    assert edad_en_anios("003D") == 0       # dias
    assert edad_en_anios("") is None        # ilegible: no se da por bueno
    assert edad_en_anios(None) is None
    assert edad_en_anios("ABC") is None


def test_filtrar_por_edad_deja_solo_adultos():
    """El alcance entregado declara ADULTOS, pero el analisis exploratorio
    encontro un 4,78% de menores de 18 (desde 1 ano) y cinco pacientes con
    edades imposibles de 148 a 155."""
    from copiloto_triaje.datos.preparacion import filtrar_por_edad
    registros = [
        {"patientId": "adulto_joven", "edad": "18", "etiqueta": 1},
        {"patientId": "adulto", "edad": "51", "etiqueta": 0},
        {"patientId": "mayor", "edad": "100", "etiqueta": 1},
        {"patientId": "nino", "edad": "7", "etiqueta": 1},
        {"patientId": "bebe_en_meses", "edad": "018M", "etiqueta": 0},
        {"patientId": "imposible", "edad": "155", "etiqueta": 0},
        {"patientId": "ilegible", "edad": "", "etiqueta": 1},
    ]
    aceptados, resumen = filtrar_por_edad(registros, 18, 100)

    ids = [r["patientId"] for r in aceptados]
    assert ids == ["adulto_joven", "adulto", "mayor"], \
        "los limites 18 y 100 son inclusivos y todo lo demas se descarta"
    assert resumen["aceptados"] == 3
    assert resumen["descartados"] == 4


def test_filtrar_por_edad_no_pierde_datos_en_silencio():
    """El spec §8 exige que una perdida de datos nunca sea silenciosa: el
    resumen tiene que decir cuantos se fueron y por que motivo."""
    from copiloto_triaje.datos.preparacion import filtrar_por_edad
    registros = [
        {"patientId": "a", "edad": "40", "etiqueta": 0},
        {"patientId": "b", "edad": "5", "etiqueta": 1},
        {"patientId": "c", "edad": "9", "etiqueta": 0},
        {"patientId": "d", "edad": "150", "etiqueta": 0},
        {"patientId": "e", "edad": "xx", "etiqueta": 1},
    ]
    _, resumen = filtrar_por_edad(registros, 18, 100)

    assert resumen["entraron"] == 5
    assert resumen["aceptados"] + resumen["descartados"] == resumen["entraron"], \
        "las cuentas no cuadran: hay registros que no se explican"
    assert resumen["por_motivo"] == {"menor de 18": 2,
                                     "mayor de 100 (implausible)": 1,
                                     "edad ilegible": 1}
    assert {d["patientId"] for d in resumen["detalle"]} == {"b", "c", "d", "e"}


def test_filtrar_por_edad_anade_la_edad_numerica_y_no_muta_la_entrada():
    from copiloto_triaje.datos.preparacion import filtrar_por_edad
    originales = [{"patientId": "a", "edad": "051Y", "etiqueta": 0}]
    aceptados, _ = filtrar_por_edad(originales, 18, 100)
    assert aceptados[0]["edad_anios"] == 51
    assert "edad_anios" not in originales[0], "el filtro no debe mutar su entrada"
