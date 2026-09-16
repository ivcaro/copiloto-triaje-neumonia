import copy

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

import copiloto_triaje.modelo.entrenamiento as entrenamiento_mod
from copiloto_triaje.config import Config
from copiloto_triaje.modelo.entrenamiento import entrenar, evaluar_epoca


class ModeloTrivial(torch.nn.Module):
    """Un lineal sobre la media de la imagen: entrena rapido en CPU."""

    def __init__(self):
        super().__init__()
        self.capa = torch.nn.Linear(1, 1)

    def forward(self, x):
        return self.capa(x.mean(dim=(1, 2, 3), keepdim=False).unsqueeze(1))


class ModeloTrivialConFeatures(ModeloTrivial):
    """Variante de ModeloTrivial con un `.features` minimo. Solo la necesitan
    las pruebas que ejercitan la fase de ajuste fino: `descongelar_para_ajuste`
    accede a `modelo.features`, y el ModeloTrivial comun no lo tiene (a
    proposito, para el resto de las pruebas de este archivo)."""

    def __init__(self):
        super().__init__()
        self.features = torch.nn.ModuleList([torch.nn.Identity()])


class ModeloProyeccion(torch.nn.Module):
    """Lineal sobre los 192 pixeles, no sobre su media.

    Un modelo de un solo peso sobre un unico rasgo escalar no sirve para
    probar el criterio de epoca: su curva ROC es INVARIANTE al entrenamiento
    (escalar y desplazar un rasgo no cambia el orden de los puntajes), asi que
    ninguna metrica basada en la ROC se moveria entre epocas. Con 192 entradas
    el modelo tiene que APRENDER en que pixeles esta la senal, de modo que el
    ordenamiento -y por tanto la ROC- si mejora epoca a epoca, que es lo que
    un criterio de seleccion de epoca honesto debe poder ver.

    El sesgo inicial positivo no es un truco para forzar el fallo: con
    `pos_weight = negativos/positivos` la salida constante optima de la
    perdida es exactamente logit 0, es decir probabilidad 0,5, o sea el
    umbral ingenuo. El modelo queda sentado encima del umbral y cae entero a
    un lado o al otro segun el signo del sesgo. Fijarlo positivo elige, de
    forma determinista, el lado que reprodujo la revision (recall 1,0 con
    especificidad 0,0); con el signo contrario el fallo es el simetrico
    (recall 0,0 con especificidad 1,0) y el criterio viejo se rompe igual.
    """

    def __init__(self, sesgo_inicial: float = 0.2, semilla: int = 7):
        super().__init__()
        self.capa = torch.nn.Linear(192, 1)
        # Inicializacion con un generador PROPIO, no el global: `nn.Linear`
        # consume el generador global, asi que unos pesos iniciales heredados
        # del estado que dejo la prueba anterior harian que este escenario
        # dependiera del orden de ejecucion del archivo.
        g = torch.Generator().manual_seed(semilla)
        limite = 1.0 / 192 ** 0.5  # el rango por defecto de nn.Linear
        with torch.no_grad():
            self.capa.weight.copy_(
                (torch.rand(1, 192, generator=g) * 2 - 1) * limite * 0.05)
            self.capa.bias.fill_(sesgo_inicial)
        self.features = torch.nn.ModuleList([torch.nn.Identity()])

    def forward(self, x):
        return self.capa(x.flatten(1))


def cargadores_desbalanceados(n_train=600, n_val=300, tasa_positivos=0.225,
                              senal=2.5, lote=32):
    """Escenario realista: 22,5% de positivos (la proporcion real de RSNA) y
    clases solapadas. La senal vive en 4 pixeles de un solo canal y el resto
    es ruido, asi que las clases se distinguen pero no de forma trivial."""

    def conjunto(n, semilla):
        g = torch.Generator().manual_seed(semilla)
        n_pos = int(n * tasa_positivos)
        y = torch.cat([torch.ones(n_pos), torch.zeros(n - n_pos)])
        x = torch.randn(n, 3, 8, 8, generator=g)
        x[:, 0, :2, :2] += y.view(-1, 1, 1) * senal
        return TensorDataset(x, y)

    return (DataLoader(conjunto(n_train, 0), batch_size=lote),
            DataLoader(conjunto(n_val, 1), batch_size=lote))


def cargadores_sinteticos(n=32):
    g = torch.Generator().manual_seed(0)
    y = torch.cat([torch.ones(n // 2), torch.zeros(n // 2)])
    x = torch.randn(n, 3, 8, 8, generator=g) + y.view(-1, 1, 1, 1) * 2.0
    ds = TensorDataset(x, y)
    return DataLoader(ds, batch_size=8), DataLoader(ds, batch_size=8)


def test_evaluar_epoca_devuelve_etiquetas_y_puntajes_alineados():
    _, val = cargadores_sinteticos()
    y_true, y_score = evaluar_epoca(ModeloTrivial(), val, torch.device("cpu"))
    assert len(y_true) == len(y_score) == 32
    assert set(np.unique(y_true)).issubset({0.0, 1.0})


def test_entrenar_devuelve_historial_y_guarda_checkpoint(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=2, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    assert len(res["historial"]) == 2
    assert "recall" in res["historial"][0]
    assert res["ruta_mejor_checkpoint"].exists()


def test_el_checkpoint_guardado_se_puede_recargar(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=1, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    estado = torch.load(res["ruta_mejor_checkpoint"], weights_only=False)
    assert "modelo" in estado and "epoca" in estado
    ModeloTrivial().load_state_dict(estado["modelo"])


def test_early_stopping_corta_antes_del_maximo_de_epocas(tmp_path):
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=20, epocas_ajuste=0, paciencia=1)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    assert len(res["historial"]) < 20


def cargadores_sinteticos_barajados(n=32):
    """Igual que `cargadores_sinteticos`, pero el de entrenamiento se baraja
    (shuffle=True) sin pasarle un `generator` propio. El `RandomSampler` de
    torch, en ese caso, saca una semilla interna del generador GLOBAL en cada
    epoca (ver `torch/utils/data/sampler.py::RandomSampler.__iter__`): es el
    mismo mecanismo por el que RandomAffine/ColorJitter dependen del global,
    asi que sirve para ejercitar la siembra de `entrenar` sin necesitar el
    dataset real ni sus transformaciones."""
    g = torch.Generator().manual_seed(0)
    y = torch.cat([torch.ones(n // 2), torch.zeros(n // 2)])
    x = torch.randn(n, 3, 8, 8, generator=g) + y.view(-1, 1, 1, 1) * 2.0
    ds = TensorDataset(x, y)
    return DataLoader(ds, batch_size=8, shuffle=True), DataLoader(ds, batch_size=8)


def test_entrenar_con_la_misma_semilla_y_modelo_inicial_es_reproducible(tmp_path):
    """`entrenar` debe sembrar el generador global de torch con `cfg.semilla`
    al inicio. Sin esa siembra, esta prueba queda en rojo: el barajado del
    DataLoader de entrenamiento (que consume el generador global, igual que
    RandomAffine/ColorJitter en el dataset real) heredaria el estado que dejo
    la primera llamada a `entrenar` en vez de arrancar siempre desde la misma
    semilla, y las dos corridas divergirian."""
    train1, val1 = cargadores_sinteticos_barajados()
    train2, val2 = cargadores_sinteticos_barajados()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=3, epocas_ajuste=0)

    # Mismo modelo inicial en las dos corridas: se copian los pesos, no se
    # reconstruye con la misma semilla, para no depender de otro mecanismo
    # de reproducibilidad distinto al que se quiere probar.
    estado_inicial = copy.deepcopy(ModeloTrivial().state_dict())

    modelo1 = ModeloTrivial()
    modelo1.load_state_dict(estado_inicial)
    res1 = entrenar(modelo1, train1, val1, cfg, torch.device("cpu"), tmp_path / "ck1")

    modelo2 = ModeloTrivial()
    modelo2.load_state_dict(estado_inicial)
    res2 = entrenar(modelo2, train2, val2, cfg, torch.device("cpu"), tmp_path / "ck2")

    assert res1["historial"] == res2["historial"]


def test_paciencia_agotada_en_cabeza_no_impide_la_fase_de_ajuste(tmp_path):
    """Hallazgo 1 (Critical) de la ronda de arreglo 1/5: agotar la paciencia
    en la fase 'cabeza' debe cortar SOLO esa fase -la cabeza convergio, que es
    justo el momento de empezar el ajuste fino-, no el entrenamiento completo.
    Antes del fix, el `return` dentro del bucle de epocas salia de toda
    `entrenar` y la fase 'ajuste' nunca se ejecutaba pese a pedirse 3 epocas."""
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=20, epocas_ajuste=3, paciencia=1)
    res = entrenar(ModeloTrivialConFeatures(), train, val, cfg,
                    torch.device("cpu"), tmp_path / "ck")
    epocas_cabeza = [r for r in res["historial"] if r["fase"] == "cabeza"]
    epocas_ajuste = [r for r in res["historial"] if r["fase"] == "ajuste"]
    assert len(epocas_cabeza) < 20, "la fase 'cabeza' deberia haber cortado por paciencia"
    assert len(epocas_ajuste) >= 1, \
        "la fase 'ajuste' nunca se ejecuto tras agotar la paciencia en 'cabeza'"


def test_el_criterio_de_epoca_no_se_satura_con_el_desbalance_real(tmp_path):
    """Hallazgo C1 (Critical) de la oleada final: el criterio de epoca tiene
    que ser coherente con el criterio final de seleccion de umbral.

    Escenario degenerado, reproducido con entrenamiento REAL (sin monkeypatch
    de metricas: inyectar recalls no monotonos a mano es justo el caso que no
    ocurre): 22,5% de positivos como en RSNA, `pos_weight` ~3,44 calculado por
    `entrenar`, y clases solapadas. Con ese peso la salida constante optima de
    la perdida es exactamente probabilidad 0,5, asi que el modelo se sienta
    encima del umbral ingenuo y en la epoca 0 predice casi todo positivo:
    recall 1,000 con especificidad 0,004.

    Con el criterio VIEJO -recall medido en 0,5 fijo y comparacion estricta-
    eso hace tres destrozos a la vez y esta prueba se pone en rojo por los
    tres:
      1. la epoca 0, la MENOS entrenada, se selecciona como mejor y ninguna
         epoca posterior puede superarla jamas (1,0 no es > 1,0);
      2. el modelo se restaura a esa epoca, con especificidad practicamente
         cero, y de ahi salen las metricas del informe;
      3. la paciencia se agota con tres empates y la fase de ajuste fino
         muere a las 3 epocas de 7.
    """
    train, val = cargadores_desbalanceados()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=3, epocas_ajuste=7, paciencia=3)
    res = entrenar(ModeloProyeccion(), train, val, cfg,
                   torch.device("cpu"), tmp_path / "ck")
    historial = res["historial"]

    # Sanity de la propia prueba: si el escenario no es el degenerate, el
    # resto no prueba lo que dice probar. Esto se cumple con los dos criterios.
    assert historial[0]["recall_umbral_fijo"] == 1.0, (
        "el escenario ya no reproduce el modelo casi-todo-positivo de la "
        "epoca 0; sin eso esta prueba no vigila nada")
    assert historial[0]["especificidad_umbral_fijo"] <= 0.05

    # (1) La mejor epoca no puede ser la primera, que es la menos entrenada.
    assert res["mejor_epoca"] > 0, (
        "se selecciono la epoca 0: el criterio saturo en el umbral fijo y "
        "ninguna epoca posterior pudo superarlo")

    # (2) El modelo que se restaura -y del que saldran las metricas del
    # informe- tiene que respetar el piso de especificidad del spec.
    mejor = historial[res["mejor_epoca"]]
    assert mejor["especificidad"] >= cfg.especificidad_minima, (
        f"la epoca elegida tiene especificidad {mejor['especificidad']:.3f}, "
        f"por debajo del minimo {cfg.especificidad_minima} del spec")

    # (3) El ajuste fino no puede morir por paciencia falsa.
    epocas_ajuste = [r for r in historial if r["fase"] == "ajuste"]
    assert len(epocas_ajuste) == cfg.epocas_ajuste, (
        f"la fase de ajuste corrio {len(epocas_ajuste)} de "
        f"{cfg.epocas_ajuste} epocas: la paciencia se agoto con empates")


def test_el_auc_desempata_cuando_el_recall_se_queda_clavado(tmp_path, monkeypatch):
    """El recall en el umbral elegido se queda clavado varias epocas seguidas
    mientras el AUC sigue subiendo; sin desempate por AUC esas epocas cuentan
    como 'sin mejora' y la paciencia corta el entrenamiento antes de tiempo.

    Se controlan los puntajes de validacion por epoca para que el recall sea
    identico en las cuatro y solo el AUC mejore.
    """
    contador = {"epoca": -1}
    # Numero de negativos que en cada epoca ya cayeron POR DEBAJO de los
    # positivos no detectados. El umbral elegido no se mueve (ninguno de esos
    # negativos llega a dar especificidad >= 0,75 en el punto de recall 1,0),
    # asi que el recall queda clavado en 0,6 mientras el AUC sube de 0,60 a
    # 0,84 epoca a epoca: exactamente el empate que la paciencia malinterpreta.
    negativos_ordenados = [0, 2, 4, 6]

    def _pasada_falsa(modelo, cargador, criterio, optimizador, dispositivo):
        contador["epoca"] += 1
        return 0.5

    def _evaluar_falso(modelo, cargador, dispositivo):
        k = negativos_ordenados[contador["epoca"]]
        y_true = np.array([1.0] * 10 + [0.0] * 10)
        y_score = np.concatenate([
            np.full(6, 0.90),        # positivos detectados
            np.full(4, 0.10),        # positivos perdidos
            np.full(k, 0.05),        # negativos ya bien ordenados
            np.full(10 - k, 0.50),   # negativos aun por encima de esos positivos
        ])
        return y_true, y_score

    monkeypatch.setattr(entrenamiento_mod, "_pasada_de_entrenamiento", _pasada_falsa)
    monkeypatch.setattr(entrenamiento_mod, "evaluar_epoca", _evaluar_falso)

    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=4, epocas_ajuste=0, paciencia=2)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")

    recalls = {r["recall"] for r in res["historial"]}
    assert len(recalls) == 1, "el escenario deberia tener el recall clavado"
    assert len(res["historial"]) == 4, (
        "la paciencia corto el entrenamiento pese a que el AUC seguia subiendo")
    assert res["mejor_epoca"] == 3


def _y_true_y_score_con(detectados: int, n: int = 10):
    """(y_true, y_score) sinteticos de n positivos y n negativos: `detectados`
    positivos con score alto (bien clasificados al umbral 0.5) y el resto con
    score bajo; los negativos siempre se clasifican bien. El recall resultante
    es exactamente `detectados / n`."""
    y_true = np.array([1.0] * n + [0.0] * n)
    y_score = np.array([0.9] * detectados + [0.1] * (n - detectados) + [0.1] * n)
    return y_true, y_score


def test_el_mejor_checkpoint_sigue_al_recall_no_a_la_perdida(tmp_path, monkeypatch):
    """Hallazgo 2 (Important) de la ronda de arreglo 1/5: fija el criterio de
    'mejor' epoca al Recall, no a la perdida. Se controlan perdida y recall
    por epoca -con monkeypatch de `_pasada_de_entrenamiento` y `evaluar_epoca`,
    para no depender de que converjan igual bajo entrenamiento real- de modo
    que diverjan a proposito: la perdida es minima en la ultima epoca, pero
    el Recall es maximo en la epoca 1. Si el criterio de seleccion cambiara
    de `m["recall"]` a una funcion de la perdida, esta prueba debe fallar
    (verificacion de mutacion documentada en el reporte)."""
    perdidas = [0.9, 0.9, 0.1]  # minima -"mejor" si el criterio fuera la perdida- en la epoca 2
    recalls = [0.3, 1.0, 0.3]  # maxima en la epoca 1
    contador = {"epoca": -1}

    def _pasada_falsa(modelo, cargador, criterio, optimizador, dispositivo):
        contador["epoca"] += 1
        return perdidas[contador["epoca"]]

    def _evaluar_falso(modelo, cargador, dispositivo):
        detectados = round(recalls[contador["epoca"]] * 10)
        return _y_true_y_score_con(detectados)

    monkeypatch.setattr(entrenamiento_mod, "_pasada_de_entrenamiento", _pasada_falsa)
    monkeypatch.setattr(entrenamiento_mod, "evaluar_epoca", _evaluar_falso)

    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=3, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")

    assert res["mejor_epoca"] == 1
    assert res["mejor_recall"] == 1.0
    estado_mejor = torch.load(res["ruta_mejor_checkpoint"], weights_only=False)
    assert estado_mejor["epoca"] == 1


def test_el_checkpoint_guarda_lo_necesario_para_reanudar(tmp_path):
    """Hallazgo 4 (Important) de la ronda de arreglo 1/5: el spec exige poder
    reanudar el entrenamiento tras una caida de sesion (p.ej. en Colab). Sin
    el estado del optimizador, reanudar reiniciaria el momento de Adam en vez
    de continuar; sin la fase y el historial acumulado no se sabe en que
    punto del plan de dos fases se quedo el entrenamiento."""
    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=2, epocas_ajuste=0)
    res = entrenar(ModeloTrivial(), train, val, cfg, torch.device("cpu"), tmp_path / "ck")
    estado = torch.load(res["ruta_mejor_checkpoint"], weights_only=False)

    for clave in ("modelo", "optimizador", "epoca", "fase", "metricas", "historial"):
        assert clave in estado, f"falta '{clave}' en el checkpoint"
    assert estado["fase"] == "cabeza"
    assert len(estado["historial"]) >= 1

    # El estado del optimizador debe ser recargable de verdad, no solo estar
    # presente como clave.
    optimizador_nuevo = torch.optim.Adam(ModeloTrivial().parameters(), lr=cfg.lr_cabeza)
    optimizador_nuevo.load_state_dict(estado["optimizador"])


def test_entrenar_restaura_los_pesos_de_la_mejor_epoca_no_los_de_la_ultima(tmp_path, monkeypatch):
    """Hallazgo 1 (Critical) de la ronda de arreglo 1/5 (Tarea 10): `entrenar`
    guardaba 'mejor.pt' cada vez que el recall mejoraba, pero nunca lo volvia
    a cargar antes de retornar. El `modelo` que el llamador recibia quedaba en
    el estado de la ULTIMA epoca ejecutada, no en el de la mejor -casi
    siempre peor, porque el early stopping corta precisamente cuando el
    recall dejo de mejorar-. El notebook de la Tarea 10 elige el umbral y
    evalua la prueba sobre ese `modelo`, asi que el bug se traducia en
    metricas reportadas para un modelo distinto del que se dice haber
    entrenado, sin ningun error visible.

    Se fuerza el mejor recall en una epoca intermedia (1), no en la ultima
    (2), y se hace que cada epoca deje un valor CONOCIDO y distinguible en la
    capa lineal (en vez de depender de que el descenso de gradiente real
    produzca pesos distintos por epoca: seria correcto, pero no deterministico
    de verificar). Debe fallar si se quita la restauracion: sin ella, el
    modelo quedaria con el valor de la epoca 2 (3.0) en vez del de la epoca 1
    (2.0)."""
    recalls = [0.3, 1.0, 0.3]  # mejor en la epoca 1 (intermedia), no en la 2 (ultima)
    contador = {"epoca": -1}

    def _pasada_falsa(modelo, cargador, criterio, optimizador, dispositivo):
        contador["epoca"] += 1
        with torch.no_grad():
            modelo.capa.weight.fill_(float(contador["epoca"] + 1))
        return 0.5

    def _evaluar_falso(modelo, cargador, dispositivo):
        detectados = round(recalls[contador["epoca"]] * 10)
        return _y_true_y_score_con(detectados)

    monkeypatch.setattr(entrenamiento_mod, "_pasada_de_entrenamiento", _pasada_falsa)
    monkeypatch.setattr(entrenamiento_mod, "evaluar_epoca", _evaluar_falso)

    train, val = cargadores_sinteticos()
    cfg = Config(raiz_datos=tmp_path, zip_rsna=tmp_path / "r.zip",
                 epocas_cabeza=3, epocas_ajuste=0)
    dir_checkpoints = tmp_path / "ck"
    modelo = ModeloTrivial()
    res = entrenar(modelo, train, val, cfg, torch.device("cpu"), dir_checkpoints)

    assert res["mejor_epoca"] == 1, "la epoca 1 debia ser la mejor, no la ultima (2)"

    peso_checkpoint_mejor = torch.load(
        res["ruta_mejor_checkpoint"], weights_only=False
    )["modelo"]["capa.weight"].item()
    peso_checkpoint_ultimo = torch.load(
        dir_checkpoints / "ultimo.pt", weights_only=False
    )["modelo"]["capa.weight"].item()

    # Sanity de la propia prueba: si esto no se cumple, el resto no prueba
    # lo que dice probar.
    assert peso_checkpoint_mejor == 2.0
    assert peso_checkpoint_ultimo == 3.0

    assert modelo.capa.weight.item() == peso_checkpoint_mejor, (
        "el modelo devuelto por entrenar() debe quedar en los pesos del "
        "MEJOR checkpoint (epoca 1), no en los de la ultima epoca ejecutada"
    )
    assert modelo.capa.weight.item() != peso_checkpoint_ultimo
