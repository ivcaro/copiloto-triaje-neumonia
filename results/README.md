# Resultados

Lo que mide el modelo desplegado (EfficientNet-B0 a 320 px) en el conjunto de prueba, en
agregados: ni una fila por paciente, ni píxeles de RSNA.

| Carpeta | Qué hay |
| :--- | :--- |
| `metrics/` | `metricas_prueba.json`: AUC, sensibilidad (recall) y especificidad con su intervalo de Wilson del 95 %, globales y en 13 subgrupos; el efecto del umbral por vista; y la calibración (Brier, ECE, pendiente, intercepto y curva de fiabilidad). Sus cifras globales y por subgrupo son las de `app/assets/metricas.json`, que enseña la app en «Acerca de». |
| `figures/` | `roc_prueba.png` (curva ROC: todas las placas, PA y AP), `calibracion.png` (fiabilidad de la puntuación cruda y de la calibrada) y `subgrupos.png` (sensibilidad y especificidad por subgrupo). |
| `reports/` | Enlaces a los informes largos: el acta de la sesión con el médico y la validación semisintética (están en `docs/`). |

## Cómo se regeneran

Desde la raíz del repositorio, con las dependencias de `requirements.txt` instaladas:

```
python -m src.evaluate
```

Lee las puntuaciones congeladas del modelo sobre la prueba
(`docs/validacion-semisintetica/crudas_prueba.csv`, con el SHA-256 de los pesos que las
generaron al lado), llama al guion que calcula las métricas de la app
(`app/generar_metricas.py`) y escribe `metrics/` y `figures/`. `--sin-figuras` escribe solo
el JSON; `--help` lista las opciones. El JSON lleva la fecha de generación, y las figuras se
dibujan de él.

Las puntuaciones congeladas se generan infiriendo con los pesos desplegados
(`models/README.md`) sobre las placas de prueba de RSNA (`data/README.md`); sin ellas, el
guion lo dice y no toca estos ficheros.
