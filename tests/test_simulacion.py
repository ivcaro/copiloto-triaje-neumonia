"""La simulación celda a celda sobre las 3 811 placas congeladas (spec de
SP5 §4.3-§4.6, §8, §11.2-§11.3). La fila 0A es la comprobación de la
métrica: con dependencia nula el oráculo no puede salirse de la horquilla."""
import numpy as np
import pytest

from copiloto_triaje.servicio.heckerling import (
    PREVALENCIA_COHORTE, RV_POR_PUNTUACION, combinacion, combinar,
)
from copiloto_triaje.validacion import generador, metricas, oraculo, simulacion


@pytest.fixture(scope="module")
def conjunto():
    return simulacion.cargar_conjunto()


def _escenario(conjunto, rho1, rho0):
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, rho1, rho0)
    clinica = generador.generar(modelo, simulacion.SEMILLA_PUNTUAL)
    salidas = simulacion.salidas_del_sistema(conjunto.prevalencia, clinica, conjunto.rv)
    l_or = simulacion.oraculo_de_los_casos(modelo, conjunto.q, clinica)
    return modelo, clinica, salidas, l_or


@pytest.fixture(scope="module")
def escenario_0a(conjunto):
    return _escenario(conjunto, 0.0, 0.0)


def test_el_conjunto_es_el_de_prueba_con_su_previo(conjunto):
    assert conjunto.y.size == 3811 and int(conjunto.y.sum()) == 844
    assert conjunto.prevalencia == pytest.approx(0.2215)
    assert sorted(conjunto.orden) == list(range(3811))
    # el orden es el de patientId: el primero en orden alfabetico lleva el 0
    assert conjunto.ids[int(np.argmin(conjunto.orden))] == min(conjunto.ids)
    assert np.allclose(conjunto.q, metricas.logit(conjunto.p_cal))


def test_los_nombres_de_las_celdas():
    assert simulacion.nombre_de_celda(0.0, 0.0) == "0A"
    assert simulacion.nombre_de_celda(0.3, 0.0) == "(0,3; 0)"
    assert simulacion.nombre_de_celda(0.15, 0.45) == "(0,15; 0,45)"


def test_las_salidas_son_las_del_codigo_del_servidor(conjunto, escenario_0a):
    _, clinica, salidas, _ = escenario_0a
    filas = clinica.to_dict("records")
    conocida = salidas["conocida"]
    assert np.array_equal(conocida, (clinica["asma"] != "no_se").values)
    for i in np.flatnonzero(conocida)[[0, 1, 2, 500, -1]]:
        b = combinacion(conjunto.prevalencia, generador.hallazgos(filas[i]), float(conjunto.rv[i]))
        assert salidas["independencia"][i] == b["independencia"][0]
        assert salidas["concordantes"][i] == b["concordantes"]
        assert salidas["conservador"][i] == (b["dependencia"][0] if b["concordantes"]
                                             else b["independencia"][0])
        assert salidas["puntuacion"][i] == b["puntuacion"][0]
    assert np.array_equal(salidas["puntuacion"][conocida], clinica["k"].values[conocida])
    assert np.array_equal(salidas["puntuacion"][~conocida], clinica["k4"].values[~conocida])
    # la horquilla solo existe con concordancia y con UNA puntuacion
    assert np.array_equal(np.isfinite(salidas["l_dependencia"]),
                          salidas["concordantes"] & conocida)
    assert np.all(salidas["l_minima"] <= salidas["l_maxima"])
    assert set(salidas["primaria"]) <= {"baja", "intermedia", "alta"}


def test_con_el_asma_desconocida_no_hay_un_modelo_puntual_sino_un_rango(conjunto, escenario_0a):
    """Dos puntuaciones, [k4, k4 + 1]: los modelos puntuales quedan sin dato y
    lo que se mide es el rango y su punto medio EN LOG-ODDS."""
    _, clinica, salidas, _ = escenario_0a
    no_se = np.flatnonzero(~salidas["conocida"])
    assert no_se.size == 351
    for nombre in ("independencia", "conservador", "clinica", "l_independencia",
                   "l_dependencia"):
        assert np.all(np.isnan(salidas[nombre][no_se])), nombre
        assert np.all(np.isfinite(salidas[nombre][salidas["conocida"]])
                      | (nombre == "l_dependencia")), nombre
    for i in no_se[[0, 1, 2, 100, -1]]:
        k4, r = int(clinica["k4"].values[i]), float(conjunto.rv[i])
        dos = [metricas.logit([combinar(conjunto.prevalencia, RV_POR_PUNTUACION[k], r)])[0]
               for k in (k4, k4 + 1)]
        assert salidas["l_medio"][i] == pytest.approx(sum(dos) / 2, abs=1e-12)
        assert salidas["l_minima"][i] <= min(dos) and max(dos) <= salidas["l_maxima"][i]
        assert salidas["l_minima"][i] <= salidas["l_medio"][i] <= salidas["l_maxima"][i]


def test_las_rv_de_imagen_tienen_que_casar_con_los_casos(conjunto, escenario_0a):
    _, clinica, _, _ = escenario_0a
    with pytest.raises(ValueError, match="tienen que casar"):
        simulacion.salidas_del_sistema(conjunto.prevalencia, clinica.head(5), conjunto.rv[:4])


def test_un_bloque_que_no_es_el_redondeo_de_combinar_se_denuncia(conjunto, escenario_0a,
                                                                 monkeypatch):
    """Los extremos sin redondear se recalculan con `combinar`; si el bloque
    dejara de ser su redondeo, la simulación se detiene en vez de medir otra cosa."""
    _, clinica, _, _ = escenario_0a

    def con(campo):
        def alterada(prevalencia, hallazgos, rv_imagen):
            b = combinacion(prevalencia, hallazgos, rv_imagen)
            if b[campo] is not None:
                b[campo] = [round(x + 0.0001, 4) for x in b[campo]]
            return b
        return alterada

    concordantes = clinica[escenario_0a[2]["concordantes"]].head(5)
    rv = conjunto.rv[concordantes.index.values]
    for campo in ("independencia", "dependencia"):
        monkeypatch.setattr(simulacion, "combinacion", con(campo))
        with pytest.raises(AssertionError, match="no es el redondeo"):
            simulacion.salidas_del_sistema(conjunto.prevalencia, concordantes, rv)


def test_el_oraculo_usa_la_misma_informacion_que_el_sistema(conjunto, escenario_0a):
    modelo, clinica, salidas, l_or = escenario_0a
    s = salidas["conocida"]
    assert np.allclose(l_or[s], oraculo.logit_oraculo(
        modelo, conjunto.q[s], clinica["k"].values[s]))
    assert np.allclose(l_or[~s], oraculo.logit_oraculo_no_se(
        modelo, conjunto.q[~s], clinica["k4"].values[~s]))


# --------------------------------------------------------------------------
# Las metricas de una celda
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def medida_0a(conjunto, escenario_0a):
    _, _, salidas, l_or = escenario_0a
    return simulacion.medir(conjunto, salidas, l_or)


@pytest.fixture(scope="module")
def medida_simetrica(conjunto):
    _, _, salidas, l_or = _escenario(conjunto, 0.3, 0.3)
    return simulacion.medir(conjunto, salidas, l_or)


def test_la_fila_0a_es_la_comprobacion_de_la_metrica(medida_0a):
    """Colas exactamente 0 y contención 100 %, por cada lado de la imagen y
    también con el asma oculta (spec §4.6, §11.2)."""
    for lado in ("todos", "a_favor", "en_contra"):
        h = medida_0a["horquilla"][lado]
        assert h["bajo"] == 0.0 and h["sobre"] == 0.0 and h["contencion"] == 1.0
        assert h["sin_horquilla"] == 0
    assert medida_0a["no_se"]["contencion"] == 1.0
    # sin dependencia la independencia ES el oraculo salvo el redondeo de las RV
    assert medida_0a["horquilla"]["todos"]["lambda"]["mediana"] == pytest.approx(0.9915, abs=1e-3)
    assert medida_0a["discordantes"]["error_abs_mediano"] < metricas.EPSILON


def test_sin_la_tolerancia_la_fila_0a_acusaria_a_la_independencia(conjunto, escenario_0a):
    """Por qué hace falta ε: la RV publicada 1,64 es menos extrema que la
    exacta 1,6408, y sin tolerancia el oráculo queda «más allá de la
    independencia» en los concordantes con k = 3 (spec §4.6)."""
    _, _, salidas, l_or = escenario_0a
    h = salidas["conocida"] & salidas["concordantes"]
    sin = metricas.horquilla(l_or[h], salidas["l_dependencia"][h],
                             salidas["l_independencia"][h], epsilon=0.0)
    assert 0.05 < sin["sobre"] < 0.25


def test_los_recuentos_cuadran(medida_0a):
    r = medida_0a["recuentos"]
    assert r == {"casos": 3811, "asma_conocida": 3460, "concordantes": 2217,
                 "concordantes_a_favor": 523, "concordantes_en_contra": 1694,
                 "discordantes": 1243, "no_se": 351}
    assert r["asma_conocida"] + r["no_se"] == r["casos"]
    assert r["concordantes"] + r["discordantes"] == r["asma_conocida"]
    assert r["concordantes_a_favor"] + r["concordantes_en_contra"] == r["concordantes"]


def test_los_cuatro_modelos_de_0a(medida_0a):
    m = medida_0a["modelos"]
    assert set(m) == set(simulacion.MODELOS)
    assert m["imagen"]["auc"] == pytest.approx(0.8847, abs=5e-4)
    assert m["clinica"]["auc"] == pytest.approx(0.7897, abs=5e-4)
    assert m["independencia"]["auc"] == pytest.approx(0.9304, abs=5e-4)
    assert m["independencia"]["pendiente"] == pytest.approx(1.025, abs=5e-3)
    # el extremo conservador se queda corto: tira informacion que si era nueva
    assert m["conservador"]["pendiente"] > 1.2
    p = medida_0a["pareadas"]
    assert set(p) == set(simulacion.COMBINADOS)
    assert p["independencia"]["auc"] == pytest.approx(
        m["independencia"]["auc"] - m["imagen"]["auc"])
    assert p["conservador"]["brier"] == pytest.approx(
        m["conservador"]["brier"] - m["imagen"]["brier"])
    assert p["independencia"]["auc"] > 0.04 and p["independencia"]["brier"] < -0.02


def test_con_dependencia_simetrica_la_independencia_exagera(medida_simetrica):
    assert medida_simetrica["modelos"]["independencia"]["pendiente"] == pytest.approx(
        0.788, abs=5e-3)
    h = medida_simetrica["horquilla"]["todos"]
    assert h["n"] == 2430
    assert h["contencion"] == pytest.approx(0.7066, abs=5e-4)
    assert h["bajo"] == pytest.approx(0.2934, abs=5e-4) and h["sobre"] == 0.0


def test_la_direccion_depende_de_donde_vive_la_dependencia(conjunto):
    """Solo entre enfermos: con la imagen a favor el oráculo queda MÁS ALLÁ de
    la independencia. Solo entre sanos: con la imagen a favor queda por el
    lado conservador. La dirección es un resultado de la celda (spec §4.5)."""
    def horquilla(rho1, rho0):
        _, _, salidas, l_or = _escenario(conjunto, rho1, rho0)
        return simulacion.medir(conjunto, salidas, l_or)["horquilla"]

    enfermos, sanos = horquilla(0.6, 0.0), horquilla(0.0, 0.6)
    assert enfermos["a_favor"]["sobre"] > 0.7 and enfermos["a_favor"]["bajo"] < 0.05
    assert enfermos["en_contra"]["bajo"] > 0.7
    assert sanos["a_favor"]["bajo"] > 0.8 and sanos["a_favor"]["sobre"] == 0.0
    assert sanos["en_contra"]["sobre"] > 0.7


def test_medir_sobre_filas_repetidas_es_medir_ese_remuestreo(conjunto, escenario_0a):
    _, _, salidas, l_or = escenario_0a
    filas = np.random.default_rng(3).integers(0, 3811, 3811)
    m = simulacion.medir(conjunto, salidas, l_or, filas)
    assert m["recuentos"]["casos"] == 3811
    s = salidas["conocida"][filas]
    assert m["recuentos"]["asma_conocida"] == int(s.sum())
    assert m["modelos"]["imagen"]["brier"] == pytest.approx(
        metricas.brier(conjunto.y[filas][s], conjunto.p_cal[filas][s]))
    # con dependencia nula, ningun remuestreo saca al oraculo de la horquilla
    assert m["horquilla"]["todos"]["contencion"] == 1.0


def test_aplanar_se_queda_con_las_cifras():
    plano = simulacion.aplanar({"a": {"b": 1.5, "n": 3, "c": None, "d": {"e": 0.25}},
                                "f": 2.0, "g": "texto", "h": True})
    assert plano == {"a.b": 1.5, "a.d.e": 0.25, "f": 2.0}


# --------------------------------------------------------------------------
# El bootstrap
# --------------------------------------------------------------------------
def test_el_bootstrap_es_pareado_reproducible_y_por_percentiles(conjunto):
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, 0.3, 0.3)
    a = simulacion.bootstrap(conjunto, modelo, replicas=4)
    assert a == simulacion.bootstrap(conjunto, modelo, replicas=4)
    for ruta in ("modelos.independencia.auc", "pareadas.independencia.auc",
                 "pareadas.conservador.pendiente", "horquilla.todos.contencion",
                 "horquilla.a_favor.lambda.mediana", "discordantes.sesgo_mediano",
                 "no_se.contencion", "no_se.punto_medio.error_abs_mediano"):
        lo, hi = a[ruta]
        assert lo <= hi, ruta
    assert not any(ruta.startswith("recuentos") for ruta in a)
    # cada replica sortea su clinica y sus placas
    r0, r1 = (simulacion.replica(conjunto, modelo, b) for b in (0, 1))
    assert r0 != r1 and r0 == simulacion.replica(conjunto, modelo, 0)
    # y el intervalo son los percentiles 2,5 y 97,5 de las replicas
    corridas = [simulacion.replica(conjunto, modelo, b) for b in range(4)]
    ruta = "pareadas.independencia.auc"
    assert a[ruta] == pytest.approx(list(np.percentile([c[ruta] for c in corridas],
                                                       [2.5, 97.5])))


def test_cada_replica_remuestrea_placas_y_vuelve_a_sortear_la_clinica(conjunto, monkeypatch):
    """Las dos mitades del bootstrap, fijadas: si una réplica dejara de
    remuestrear las placas, o midiera siempre la clínica de la estimación
    puntual, los intervalos se estrecharían sin que nada más lo notara."""
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, 0.3, 0.3)
    semillas, filas = [], []
    generar, medir = generador.generar, simulacion.medir

    def generar_espia(m, semilla):
        semillas.append(semilla)
        return generar(m, semilla)

    def medir_espia(c, salidas, l_oraculo, f=None):
        filas.append(f)
        return medir(c, salidas, l_oraculo, f)

    monkeypatch.setattr(generador, "generar", generar_espia)
    monkeypatch.setattr(simulacion, "medir", medir_espia)
    corridas = [simulacion.replica(conjunto, modelo, b) for b in (0, 1, 2)]
    assert semillas == [simulacion.SEMILLA_CLINICA + b for b in (0, 1, 2)]
    assert simulacion.SEMILLA_PUNTUAL not in semillas
    n = conjunto.y.size
    for b, f in enumerate(filas):
        assert f is not None and f.shape == (n,)
        assert 0 <= f.min() and f.max() < n
        assert np.unique(f).size < n                    # con reemplazo: hay repetidas
        assert np.array_equal(f, np.random.default_rng(
            simulacion.SEMILLA_INDICES + b).integers(0, n, n))
    assert not np.array_equal(filas[0], filas[1])
    # pareado: la diferencia entre modelos es la de ESA réplica
    for c in corridas:
        for combinado in simulacion.COMBINADOS:
            for cifra in ("auc", "brier", "pendiente"):
                assert c[f"pareadas.{combinado}.{cifra}"] == pytest.approx(
                    c[f"modelos.{combinado}.{cifra}"] - c[f"modelos.imagen.{cifra}"], abs=1e-15)


def test_un_intervalo_no_se_calcula_sobre_menos_replicas_de_las_que_dice(conjunto, monkeypatch):
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, 0.3, 0.3)
    monkeypatch.setattr(simulacion, "replica", lambda c, m, b: (
        {"a.auc": 0.9, "a.ece": 0.01} if b != 2 else {"a.auc": 0.9}))
    assert simulacion.bootstrap(conjunto, modelo, replicas=2) == {
        "a.auc": [0.9, 0.9], "a.ece": [0.01, 0.01]}
    with pytest.raises(ArithmeticError, match="a.ece"):
        simulacion.bootstrap(conjunto, modelo, replicas=3)


def test_las_replicas_no_reajustan_el_generador(conjunto, monkeypatch):
    """z_y, los umbrales y el calibrador quedan fijos: una réplica no vuelve
    a llamar a `oraculo.ajustar` (spec §4.6)."""
    modelo = oraculo.ajustar(conjunto.q, conjunto.y, 0.3, 0.3)

    def prohibido(*a, **k):
        raise AssertionError("una réplica no reajusta el modelo")

    monkeypatch.setattr(oraculo, "ajustar", prohibido)
    assert simulacion.bootstrap(conjunto, modelo, replicas=1)


# --------------------------------------------------------------------------
# La celda completa: escala legible, previo, 0C e intervalos
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def celda_0a(conjunto):
    return simulacion.evaluar_celda(conjunto, 0.0, 0.0, con_sensibilidad=True)


@pytest.fixture(scope="module")
def celda_simetrica(conjunto):
    return simulacion.evaluar_celda(conjunto, 0.3, 0.3, con_sensibilidad=True)


def test_la_celda_lleva_lo_medido_y_lo_que_solo_se_calcula_una_vez(celda_0a, medida_0a):
    assert celda_0a["nombre"] == "0A" and (celda_0a["rho1"], celda_0a["rho0"]) == (0.0, 0.0)
    for clave in ("recuentos", "pareadas", "horquilla", "discordantes", "no_se"):
        assert celda_0a[clave] == medida_0a[clave]
    assert celda_0a["hipotesis"] == {"umbral": 0.9, "contencion": 1.0, "se_sostiene": True}
    for nombre in simulacion.MODELOS:
        m = celda_0a["modelos"][nombre]
        assert m["auc"] == medida_0a["modelos"][nombre]["auc"]
        assert 0.0 < m["suelo"]["media"] < m["suelo"]["p95"]
        assert len(m["fiabilidad"]) == metricas.BINS
        assert sum(b["n"] for b in m["fiabilidad"]) == 3460
    # con independencia de verdad, la ECE de la combinacion no supera su suelo
    independencia = celda_0a["modelos"]["independencia"]
    assert independencia["ece"] < independencia["suelo"]["p95"]


def test_la_hipotesis_del_90_no_se_sostiene_con_dependencia_simetrica(celda_simetrica):
    c = celda_simetrica
    assert c["correlacion_teorica"]["con_neumonia"] == pytest.approx(0.2860, abs=5e-4)
    assert c["correlacion_teorica"]["sin_neumonia"] == pytest.approx(0.2751, abs=5e-4)
    assert c["hipotesis"]["contencion"] == c["horquilla"]["todos"]["contencion"]
    assert c["hipotesis"]["se_sostiene"] is False
    independencia = c["modelos"]["independencia"]
    assert independencia["ece"] > independencia["suelo"]["p95"]


def test_evaluar_celda_lleva_intervalos_solo_si_se_piden(conjunto, celda_0a):
    assert "intervalos" not in celda_0a and "replicas" not in celda_0a
    c = simulacion.evaluar_celda(conjunto, 0.3, 0.0, replicas=2)
    assert c["replicas"] == 2
    medido = {k: c[k] for k in ("modelos", "pareadas", "horquilla", "discordantes", "no_se")}
    solo_puntuales = {f"modelos.{m}.suelo.{x}" for m in simulacion.MODELOS
                      for x in ("media", "p95")}
    assert set(c["intervalos"]) == set(simulacion.aplanar(medido)) - solo_puntuales
    assert "sensibilidad_al_previo" not in c and "optimismo_de_la_derivacion" not in c


def test_una_tarea_es_una_celda_desde_cero(celda_simetrica):
    c = simulacion.evaluar_tarea((0.3, 0.3, 0, True))
    assert c == celda_simetrica


def test_sin_dependencia_la_puntuacion_conserva_todo_su_log_rv(celda_0a):
    for lado in ("a_favor", "en_contra"):
        e = celda_0a["escala_legible"][lado]
        assert e["fraccion_mediana_extremas"] == pytest.approx(1.0, abs=1e-9)
        for fila in e["por_puntuacion"]:
            assert fila["log_rv"]["mediana"] == pytest.approx(fila["ln_rv_recuentos"], abs=1e-9)
            assert fila["fraccion"]["q1"] == pytest.approx(1.0, abs=1e-9)
            assert fila["fraccion"]["q3"] == pytest.approx(1.0, abs=1e-9)
            assert fila["signo_invertido"] == 0.0
            assert fila["poco_informativa"] == (fila["k"] in (2, 3))
    placas = [celda_0a["escala_legible"][lado]["placas"] for lado in ("a_favor", "en_contra")]
    assert placas == [1248, 2563]


def test_con_dependencia_simetrica_conserva_menos_en_los_dos_lados(celda_simetrica):
    e = celda_simetrica["escala_legible"]
    assert e["a_favor"]["fraccion_mediana_extremas"] == pytest.approx(0.639, abs=5e-3)
    assert e["en_contra"]["fraccion_mediana_extremas"] == pytest.approx(0.484, abs=5e-3)
    # los casos esperados de cada lado suman sus placas
    for lado in ("a_favor", "en_contra"):
        assert sum(f["casos_esperados"] for f in e[lado]["por_puntuacion"]) == pytest.approx(
            e[lado]["placas"])


def test_cambios_de_banda():
    c = simulacion.cambios_de_banda(["baja", "intermedia", "alta", "alta"],
                                    ["baja", "baja", "intermedia", "alta"])
    assert c == {"casos": 4, "cambian": 2,
                 "transiciones": {"intermedia→baja": 1, "alta→intermedia": 1}}


def test_declarar_el_previo_de_la_cohorte_desplaza_medio_logit(celda_0a, celda_simetrica):
    for celda in (celda_0a, celda_simetrica):
        s = celda["sensibilidad_al_previo"]
        assert s["previo"] == pytest.approx(PREVALENCIA_COHORTE)
        assert s["previo_principal"] == pytest.approx(0.2215)
        assert s["desplazamiento_log_odds"] == pytest.approx(-0.5045, abs=5e-4)
        for nombre in simulacion.COMBINADOS:
            m = s["modelos"][nombre]
            # el intercepto sube lo que el previo bajo: ≈ +0,50 (spec §4.3)
            assert m["intercepto"] - m["intercepto_principal"] == pytest.approx(
                -s["desplazamiento_log_odds"], abs=2e-3)
            assert m["ece"] > m["suelo"]["p95"]
            # con un previo mas bajo, los casos solo pueden bajar de banda
            assert set(m["bandas"]["transiciones"]) <= {"intermedia→baja", "alta→intermedia"}
            assert m["bandas"]["cambian"] == sum(m["bandas"]["transiciones"].values())
        assert s["categoria_del_sistema"]["casos"] == 3811
    assert celda_0a["sensibilidad_al_previo"]["modelos"]["independencia"]["bandas"] == {
        "casos": 3460, "cambian": 338,
        "transiciones": {"intermedia→baja": 224, "alta→intermedia": 114}}
    assert celda_0a["sensibilidad_al_previo"]["categoria_del_sistema"]["cambian"] == 408


def test_0c_es_un_calculo_sobre_las_rv_publicadas(celda_0a, celda_simetrica):
    c = celda_0a["optimismo_de_la_derivacion"]
    assert [round(f["diferencia_log"], 2) for f in c["por_puntuacion"]] == [
        -0.46, 0.05, -0.40, 0.46, -0.15, 0.74]
    assert [f["rv_validacion"] for f in c["por_puntuacion"]] == [
        0.19, 0.19, 1.04, 1.04, 8.33, 8.33]
    assert [f["rv_derivacion"] for f in c["por_puntuacion"]] == [
        0.12, 0.20, 0.70, 1.64, 7.18, 17.5]
    assert c["bandas"] == {"casos": 3460, "cambian": 225,
                           "transiciones": {"baja→intermedia": 73, "intermedia→baja": 90,
                                            "intermedia→alta": 23, "alta→intermedia": 39}}
    assert "optimismo_de_la_derivacion" not in celda_simetrica


def test_la_imagen_sola_es_el_suelo_de_calibracion(conjunto):
    r = simulacion.imagen_sola(conjunto)
    assert r["casos"] == 3811
    assert r["auc"] == pytest.approx(0.8844, abs=5e-4)
    assert r["pendiente"] == pytest.approx(0.983, abs=5e-3)
    assert r["ece"] == pytest.approx(0.0163, abs=5e-4)
    assert r["ece"] < r["suelo"]["p95"]
    assert sum(b["n"] for b in r["fiabilidad"]) == 3811
