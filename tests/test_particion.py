import pytest
from copiloto_triaje.datos.particion import (
    FugaDeDatos, particionar_por_paciente, verificar_sin_fuga,
)


def registros_sinteticos(n_pacientes=200, imagenes_por_paciente=2, tasa_positivos=0.225):
    """Pacientes con VARIAS imagenes cada uno, para que la fuga sea posible."""
    registros = []
    for i in range(n_pacientes):
        etiqueta = 1 if i < int(n_pacientes * tasa_positivos) else 0
        for j in range(imagenes_por_paciente):
            registros.append({"patientId": f"P{i:04d}", "archivo": f"P{i:04d}_{j}.png",
                              "etiqueta": etiqueta})
    return registros


def test_ningun_paciente_aparece_en_dos_particiones():
    p = particionar_por_paciente(registros_sinteticos(), (0.7, 0.15, 0.15), semilla=42)
    verificar_sin_fuga(p)  # no debe lanzar
    ids = {k: {r["patientId"] for r in v} for k, v in p.items()}
    assert ids["train"].isdisjoint(ids["val"])
    assert ids["train"].isdisjoint(ids["test"])
    assert ids["val"].isdisjoint(ids["test"])


def test_todas_las_imagenes_de_un_paciente_caen_juntas():
    p = particionar_por_paciente(registros_sinteticos(), (0.7, 0.15, 0.15), semilla=42)
    ubicacion = {}
    for nombre, regs in p.items():
        for r in regs:
            ubicacion.setdefault(r["patientId"], set()).add(nombre)
    assert all(len(v) == 1 for v in ubicacion.values())


def test_no_se_pierde_ni_se_duplica_ningun_registro():
    registros = registros_sinteticos()
    p = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    total = sum(len(v) for v in p.values())
    assert total == len(registros)
    archivos = [r["archivo"] for v in p.values() for r in v]
    assert len(archivos) == len(set(archivos))


def test_proporciones_aproximadas():
    registros = registros_sinteticos(n_pacientes=1000)
    p = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    n = len(registros)
    assert 0.66 <= len(p["train"]) / n <= 0.74
    assert 0.12 <= len(p["val"]) / n <= 0.18
    assert 0.12 <= len(p["test"]) / n <= 0.18


def test_estratificacion_conserva_la_tasa_de_positivos():
    registros = registros_sinteticos(n_pacientes=1000, tasa_positivos=0.225)
    p = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    for nombre, regs in p.items():
        tasa = sum(r["etiqueta"] for r in regs) / len(regs)
        assert 0.17 <= tasa <= 0.28, f"{nombre} tiene tasa {tasa}"


def test_la_misma_semilla_reproduce_la_misma_particion():
    registros = registros_sinteticos()
    a = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    b = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    assert [r["archivo"] for r in a["test"]] == [r["archivo"] for r in b["test"]]


def test_semillas_distintas_dan_particiones_distintas():
    registros = registros_sinteticos()
    a = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=42)
    b = particionar_por_paciente(registros, (0.7, 0.15, 0.15), semilla=7)
    assert [r["archivo"] for r in a["test"]] != [r["archivo"] for r in b["test"]]


def test_verificar_sin_fuga_detecta_una_fuga_inyectada():
    p = particionar_por_paciente(registros_sinteticos(), (0.7, 0.15, 0.15), semilla=42)
    intruso = dict(p["train"][0])
    p["test"].append(intruso)
    with pytest.raises(FugaDeDatos, match="train"):
        verificar_sin_fuga(p)


def test_proporciones_invalidas_fallan_de_inmediato():
    with pytest.raises(ValueError, match="deben sumar 1"):
        particionar_por_paciente(registros_sinteticos(), (0.7, 0.2, 0.2), semilla=42)
