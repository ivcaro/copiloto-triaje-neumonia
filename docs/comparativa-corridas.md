# Comparativa de corridas - SP1 núcleo de imagen

Generado el 2026-09-24 02:01 UTC a partir de 8 reporte(s) de métricas.

## Veredicto

**Gana `kaggle_efficientnet_b0_320px_c2`.**

- Regla aplicada: `paso_2_mayor_recall`
- Paso 2: empataba con otra en número de criterios satisfechos y ganó por recall. En triaje el falso negativo es el error caro, así que el recall desempata antes que cualquier otra métrica.
- Sobre el conjunto de prueba: recall 0.892, especificidad 0.709, AUC 0.889.
- Cumple el mínimo pero **no el objetivo** en: Especificidad.

## Regla de selección

Quien lea este informe tiene que poder auditar por qué ganó la que ganó, así que la regla se escribe aquí entera y en el mismo orden en que la aplica el código (`scripts/comparar_corridas.py`):

1. **Cuántos criterios del spec §2 satisface** cada corrida sobre el conjunto de prueba: recall >= 0,80, especificidad >= 0,70 y AUC >= 0,85. Gana la que satisface más. Un criterio que el reporte no trae medido no cuenta como satisfecho.
2. **A igualdad de criterios, mayor recall.** El coste clínico de un falso negativo (mandar a casa una neumonía) es mayor que el de un falso positivo (una placa revisada de más), así que el recall desempata antes que cualquier otra métrica.
3. **Si también empatan en recall, mayor AUC**, que mide la calidad del ordenamiento del modelo con independencia del umbral elegido.
4. **Si ninguna satisface los tres mínimos, no se corona ninguna.** El informe dice que ninguna cumple y muestra cuánto le falta a cada una, en vez de presentar como ganadora a una corrida que el proyecto ya declaró inaceptable.

## Tabla comparativa

| # | Corrida | Arquitectura | Resolución (px) | Épocas | Mejor época | Umbral | Recall | Especificidad | AUC | F1 | Criterios |
| ---: | :--- | :--- | ---: | :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- |
| 1 | `kaggle_efficientnet_b0_320px_c2` | efficientnet_b0 | 320 | 4+20 | 6 | 0.2646 | 0.892 | 0.709 | 0.889 | 0.612 | 3/3 |
| 2 | `kaggle_densenet121_320px_c1` | densenet121 | 320 | 4+20 | 10 | n/d | 0.891 | 0.702 | 0.874 | n/d | 3/3 |
| 3 | `kaggle_densenet121_320px_c2` | densenet121 | 320 | 4+20 | 10 | 0.3175 | 0.891 | 0.702 | 0.874 | 0.607 | 3/3 |
| 4 | `kaggle_efficientnet_b0_320px_c1` | efficientnet_b0 | 320 | 4+20 | 6 | n/d | 0.889 | 0.708 | 0.888 | n/d | 3/3 |
| 5 | `kaggle_mobilenet_v3_large_320px_c1` | mobilenet_v3_large | 320 | 4+20 | 6 | n/d | 0.882 | 0.706 | 0.886 | n/d | 3/3 |
| 6 | `efficientnet_b0_320px_lote24_4+20ep` | efficientnet_b0 | 320 | 4+20 | 5 | 0.4258 | 0.882 | 0.702 | 0.885 | 0.602 | 3/3 |
| 7 | `kaggle_mobilenet_v3_large_320px_c2` | mobilenet_v3_large | 320 | 4+20 | 9 | 0.1660 | 0.874 | 0.706 | 0.876 | 0.601 | 3/3 |
| 8 | `corrida2_densenet121_320px` | densenet121 | 320 | 4+4 | 7 | 0.2633 | 0.880 | 0.699 | 0.888 | 0.599 | 2/3 |

### Criterios de aceptación (spec §2), sobre el conjunto de PRUEBA

| Corrida | Recall (sensibilidad) >= 0.80 | Especificidad >= 0.70 | AUC-ROC >= 0.85 | Total |
| :--- | :--- | :--- | :--- | ---: |
| `kaggle_efficientnet_b0_320px_c2` | cumple | cumple | cumple | 3/3 |
| `kaggle_densenet121_320px_c1` | cumple | cumple | cumple | 3/3 |
| `kaggle_densenet121_320px_c2` | cumple | cumple | cumple | 3/3 |
| `kaggle_efficientnet_b0_320px_c1` | cumple | cumple | cumple | 3/3 |
| `kaggle_mobilenet_v3_large_320px_c1` | cumple | cumple | cumple | 3/3 |
| `efficientnet_b0_320px_lote24_4+20ep` | cumple | cumple | cumple | 3/3 |
| `kaggle_mobilenet_v3_large_320px_c2` | cumple | cumple | cumple | 3/3 |
| `corrida2_densenet121_320px` | cumple | **NO CUMPLE** | cumple | 2/3 |

## Lectura de los resultados

Diferencias frente a la corrida mejor clasificada, y a qué se pueden atribuir:

- **`kaggle_efficientnet_b0_320px_c2`** frente a **`kaggle_densenet121_320px_c1`**: recall +0.001, especificidad +0.007, AUC +0.015. Cambian 3 cosas a la vez (arquitectura: densenet121 -> efficientnet_b0; coste de entrenamiento: 5832.0 -> 1723.9; dispositivo: cuda -> n/d), así que la mejora **no se puede atribuir** a ninguna de ellas por separado: haría falta una corrida que cambiase solo una.
- **`kaggle_efficientnet_b0_320px_c2`** frente a **`kaggle_densenet121_320px_c2`**: recall +0.001, especificidad +0.006, AUC +0.015. Cambian 2 cosas a la vez (arquitectura: densenet121 -> efficientnet_b0; coste de entrenamiento: 5647.4 -> 1723.9), así que la mejora **no se puede atribuir** a ninguna de ellas por separado: haría falta una corrida que cambiase solo una.
- **`kaggle_efficientnet_b0_320px_c2`** frente a **`kaggle_efficientnet_b0_320px_c1`**: recall +0.003, especificidad +0.001, AUC +0.001. Cambian 2 cosas a la vez (coste de entrenamiento: 1800.0 -> 1723.9; dispositivo: cuda -> n/d), así que la mejora **no se puede atribuir** a ninguna de ellas por separado: haría falta una corrida que cambiase solo una.
- **`kaggle_efficientnet_b0_320px_c2`** frente a **`kaggle_mobilenet_v3_large_320px_c1`**: recall +0.010, especificidad +0.003, AUC +0.003. Cambian 3 cosas a la vez (arquitectura: mobilenet_v3_large -> efficientnet_b0; coste de entrenamiento: 1188.0 -> 1723.9; dispositivo: cuda -> n/d), así que la mejora **no se puede atribuir** a ninguna de ellas por separado: haría falta una corrida que cambiase solo una.
- **`kaggle_efficientnet_b0_320px_c2`** frente a **`efficientnet_b0_320px_lote24_4+20ep`**: recall +0.011, especificidad +0.006, AUC +0.004. Cambian 2 cosas a la vez (coste de entrenamiento: 19025.9 -> 1723.9; dispositivo: cpu -> n/d), así que la mejora **no se puede atribuir** a ninguna de ellas por separado: haría falta una corrida que cambiase solo una.
- **`kaggle_efficientnet_b0_320px_c2`** frente a **`kaggle_mobilenet_v3_large_320px_c2`**: recall +0.018, especificidad +0.003, AUC +0.014. Cambian 2 cosas a la vez (arquitectura: mobilenet_v3_large -> efficientnet_b0; coste de entrenamiento: 1486.3 -> 1723.9), así que la mejora **no se puede atribuir** a ninguna de ellas por separado: haría falta una corrida que cambiase solo una.
- **`kaggle_efficientnet_b0_320px_c2`** frente a **`corrida2_densenet121_320px`**: recall +0.012, especificidad +0.010, AUC +0.002. Cambian 4 cosas a la vez (arquitectura: densenet121 -> efficientnet_b0; épocas: 4+4 -> 4+20; coste de entrenamiento: n/d -> 1723.9; dispositivo: cuda -> n/d), así que la mejora **no se puede atribuir** a ninguna de ellas por separado: haría falta una corrida que cambiase solo una.

Dos reservas que este informe no puede resolver por sí solo:

- Elegir la mejor de varias corridas mirando el conjunto de prueba es, en rigor, usar la prueba para seleccionar, y eso deja la métrica de la ganadora algo optimista. La comparación limpia se hace sobre validación y la prueba se toca una sola vez, al final, con la configuración ya elegida.
- Cada configuración se entrenó una vez y con una sola semilla. Las diferencias pequeñas, del orden de 0,01, caben dentro de lo que una semilla distinta mueve por sí sola.

## Procedencia

| Corrida | Reporte leído |
| :--- | :--- |
| `kaggle_efficientnet_b0_320px_c2` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\kaggle_efficientnet_b0_320px_c2\reporte_metricas.json` |
| `kaggle_densenet121_320px_c1` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\kaggle_densenet121_320px_c1\reporte_metricas.json` |
| `kaggle_densenet121_320px_c2` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\kaggle_densenet121_320px_c2\reporte_metricas.json` |
| `kaggle_efficientnet_b0_320px_c1` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\kaggle_efficientnet_b0_320px_c1\reporte_metricas.json` |
| `kaggle_mobilenet_v3_large_320px_c1` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\kaggle_mobilenet_v3_large_320px_c1\reporte_metricas.json` |
| `efficientnet_b0_320px_lote24_4+20ep` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\efficientnet_b0_320px_lote24_4+20ep\reporte_metricas.json` |
| `kaggle_mobilenet_v3_large_320px_c2` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\kaggle_mobilenet_v3_large_320px_c2\reporte_metricas.json` |
| `corrida2_densenet121_320px` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\colab_densenet121_320px\reporte_metricas.json` |
