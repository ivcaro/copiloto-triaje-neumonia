# Informes de la validación

Los informes largos viven en `docs/`, donde los enlazan el resto de la documentación; aquí
se listan junto al resto de los resultados.

- [`acta-h7.md`](../../docs/validacion-semisintetica/acta-h7.md): el acta de la sesión de
  concordancia con un médico general colaborador, que lee 24 viñetas semisintéticas (placa
  real de RSNA, clínica generada) en dos lecturas, con su kappa y lo que opinó del lenguaje
  del pre-informe; se cuenta tal cual, incluidas las cifras por debajo de lo previsto.
- [`validacion-semisintetica-sp5.md`](../../docs/validacion-semisintetica-sp5.md): el análisis
  de la simulación semisintética, generado por `scripts/validar_combinacion.py` sin teclear
  ninguna cifra; mide si el sistema calcula lo que dice calcular y cuánto se desvía bajo cada
  supuesto de dependencia entre clínica e imagen, y no mide exactitud clínica en pacientes.

Las métricas del modelo en el conjunto de prueba están en
[`../metrics/metricas_prueba.json`](../metrics/metricas_prueba.json) y sus figuras en
[`../figures/`](../figures/); ver [`../README.md`](../README.md).
