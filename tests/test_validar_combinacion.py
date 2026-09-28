"""scripts/validar_combinacion.py: la rejilla, el JSON y sus huellas."""
import json

import pytest

from copiloto_triaje.servicio.heckerling import PREVALENCIA_COHORTE
from copiloto_triaje.validacion import datos, oraculo, simulacion


def test_las_tareas_de_la_rejilla(validar):
    tareas = validar.tareas_de_la_rejilla(1000)
    assert len(tareas) == 25
    assert tareas[0] == (0.0, 0.0, 1000, True)            # 0A
    completas = [(a, b) for a, b, replicas, todo in tareas if todo]
    assert set(completas) == {(0.0, 0.0)} | set(oraculo.CELDAS_DESTACADAS)
    assert all(replicas == (1000 if todo else 0) for _, _, replicas, todo in tareas)
    assert [(a, b) for a, b, _, _ in tareas[:6]] == [
        (0.0, 0.0), (0.0, 0.15), (0.0, 0.3), (0.0, 0.45), (0.0, 0.6), (0.15, 0.0)]


def test_los_resultados_llevan_rotulo_insumos_y_parametros(resultados_minimos):
    r = resultados_minimos
    assert r["rotulo"] == "simulación semisintética"
    assert "simulación semisintética" in r["titulo"]
    assert "exactitud clínica" in r["advertencia"]
    i = r["insumos"]
    assert (i["placas"], i["positivas"], i["prevalencia"]) == (3811, 844, 0.2215)
    assert i["crudas_sha256"] == datos.huella_de_texto(datos.CRUDAS_CONGELADAS)
    assert i["calibrador_sha256"] == datos.huella_de_texto(datos.CALIBRADOR)
    assert i["pesos_sha256"] == datos.HASH_CONGELADO.read_text(encoding="utf-8").split()[0]
    assert len(i["pesos_sha256"]) == 64
    p = r["parametros"]
    assert p["replicas"] == 2 and p["epsilon"] == 0.015 and p["bins"] == 10
    assert p["previo_desplegado"] == pytest.approx(PREVALENCIA_COHORTE)
    assert p["semilla_puntual"] == simulacion.SEMILLA_PUNTUAL
    assert p["rejilla"] == [0.0, 0.3] and p["destacadas"] == [[0.3, 0.3]]


def test_las_celdas_van_en_el_orden_de_la_rejilla(resultados_minimos):
    celdas = resultados_minimos["celdas"]
    assert [c["nombre"] for c in celdas] == ["0A", "(0; 0,3)", "(0,3; 0)", "(0,3; 0,3)"]
    assert [c["destacada"] for c in celdas] == [False, False, False, True]
    con_intervalos = [c["nombre"] for c in celdas if "intervalos" in c]
    assert con_intervalos == ["0A", "(0,3; 0,3)"]
    assert [c["nombre"] for c in celdas if "sensibilidad_al_previo" in c] == con_intervalos
    assert [c["nombre"] for c in celdas if "optimismo_de_la_derivacion" in c] == ["0A"]
    cero = celdas[0]
    assert cero["horquilla"]["todos"]["contencion"] == 1.0
    assert cero["intervalos"]["horquilla.todos.contencion"] == [1.0, 1.0]
    assert resultados_minimos["imagen_sola"]["casos"] == 3811


def test_el_json_se_escribe_en_utf8_con_lf_y_se_lee_igual(validar, resultados_minimos, tmp_path):
    ruta = validar.escribir_resultados(resultados_minimos, tmp_path / "sub" / "r.json")
    crudo = ruta.read_bytes()
    assert b"\r\n" not in crudo and crudo.endswith(b"\n")
    assert "simulación semisintética".encode("utf-8") in crudo
    assert "intermedia→baja".encode("utf-8") in crudo
    assert validar.leer_resultados(ruta) == resultados_minimos
    assert json.loads(crudo.decode("utf-8")) == resultados_minimos


def test_la_huella_de_texto_no_depende_del_fin_de_linea(tmp_path):
    lf, crlf = tmp_path / "lf.csv", tmp_path / "crlf.csv"
    lf.write_bytes(b"a,b\n1,2\n")
    crlf.write_bytes(b"a,b\r\n1,2\r\n")
    assert datos.huella_de_texto(lf) == datos.huella_de_texto(crlf) == datos.sha256_de(lf)
    assert datos.sha256_de(crlf) != datos.sha256_de(lf)


def test_en_paralelo_sale_lo_mismo_que_en_serie(validar, resultados_minimos):
    r = validar.calcular(replicas=2, procesos=2, rejilla=(0.0, 0.3),
                         destacadas=((0.3, 0.3),))
    assert json.loads(json.dumps(r, ensure_ascii=False)) == resultados_minimos


def test_main_escribe_los_resultados_donde_se_le_dice(validar, tmp_path, monkeypatch, capsys):
    llamadas = []

    def calcular_falso(replicas, procesos):
        llamadas.append((replicas, procesos))
        return {"rotulo": validar.ROTULO, "celdas": []}

    monkeypatch.setattr(validar, "calcular", calcular_falso)
    assert validar.main(["--replicas", "3", "--procesos", "1", "--salida", str(tmp_path)]) == 0
    assert llamadas == [(3, 1)]
    assert validar.leer_resultados(tmp_path / "resultados_simulacion.json")["celdas"] == []
    assert "resultados_simulacion.json" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        validar.main(["--procesos", "0", "--salida", str(tmp_path)])
