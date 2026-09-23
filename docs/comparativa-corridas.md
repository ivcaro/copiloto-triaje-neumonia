# Comparativa de corridas - SP1 núcleo de imagen

Generado el 2026-09-23 08:58 UTC a partir de 2 reporte(s) de métricas.

## Veredicto

**Gana `efficientnet_b0_320px_lote24_4+20ep`.**

- Regla aplicada: `paso_1_mas_criterios_cumplidos`
- Paso 1: satisface más criterios de aceptación que cualquier otra. Ninguna métrica individual entra a discutir esto.
- Sobre el conjunto de prueba: recall 0.882, especificidad 0.702, AUC 0.885.
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
| 1 | `efficientnet_b0_320px_lote24_4+20ep` | efficientnet_b0 | 320 | 4+20 | 5 | 0.4258 | 0.882 | 0.702 | 0.885 | 0.602 | 3/3 |
| 2 | `corrida2_densenet121_320px` | densenet121 | 320 | 4+4 | 7 | 0.2633 | 0.880 | 0.699 | 0.888 | 0.599 | 2/3 |

### Criterios de aceptación (spec §2), sobre el conjunto de PRUEBA

| Corrida | Recall (sensibilidad) >= 0.80 | Especificidad >= 0.70 | AUC-ROC >= 0.85 | Total |
| :--- | :--- | :--- | :--- | ---: |
| `efficientnet_b0_320px_lote24_4+20ep` | cumple | cumple | cumple | 3/3 |
| `corrida2_densenet121_320px` | cumple | **NO CUMPLE** | cumple | 2/3 |

## Lectura de los resultados

Diferencias frente a la corrida mejor clasificada, y a qué se pueden atribuir:

- **`efficientnet_b0_320px_lote24_4+20ep`** frente a **`corrida2_densenet121_320px`**: recall +0.001, especificidad +0.004, AUC -0.003. Cambian 4 cosas a la vez (arquitectura: densenet121 -> efficientnet_b0; épocas: 4+4 -> 4+20; coste de entrenamiento: n/d -> 19025.9; dispositivo: cuda -> cpu), así que la mejora **no se puede atribuir** a ninguna de ellas por separado: haría falta una corrida que cambiase solo una.

Dos reservas que este informe no puede resolver por sí solo:

- Elegir la mejor de varias corridas mirando el conjunto de prueba es, en rigor, usar la prueba para seleccionar, y eso deja la métrica de la ganadora algo optimista. La comparación limpia se hace sobre validación y la prueba se toca una sola vez, al final, con la configuración ya elegida.
- Cada configuración se entrenó una vez y con una sola semilla. Las diferencias pequeñas, del orden de 0,01, caben dentro de lo que una semilla distinta mueve por sí sola.

## Procedencia

| Corrida | Reporte leído |
| :--- | :--- |
| `efficientnet_b0_320px_lote24_4+20ep` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\efficientnet_b0_320px_lote24_4+20ep\reporte_metricas.json` |
| `corrida2_densenet121_320px` | `C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\corridas\colab_densenet121_320px\reporte_metricas.json` |
