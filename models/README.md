# Modelos

Esta carpeta describe el modelo del proyecto y recibe sus pesos. **Los pesos no están en git**
(pesan unos 16 MB y `.gitignore` los deja fuera): se publicarán como descarga del release v1.0
del repositorio público, que todavía no existe. Aquí se dice cuál es el modelo, cómo comprobar
que el fichero que bajaste es el bueno y dónde vive el calibrador, que sí está versionado.

## El modelo desplegado

| | |
| :--- | :--- |
| Qué es | Una red de clasificación binaria sobre radiografía de tórax: «opacidad compatible con neumonía» frente a «sin opacidad». Da un logit; su sigmoide es la **puntuación cruda**. |
| Arquitectura | EfficientNet-B0 (preentrenada en ImageNet y ajustada), una sola salida |
| Entrada | Radiografía en escala de grises (replicada a tres canales), a **320 px** |
| Corrida | 6: `efficientnet_b0_320px_lote24_4+20ep` (lote 24; 4 épocas con la cabeza sola y 20 de ajuste fino; parada por recall; entrenada en CPU) |
| Entrenamiento | RSNA Pneumonia Detection Challenge, solo adultos, partición por paciente (`data/README.md`) |
| Fichero | `pesos_modelo_cpu.pt` |
| SHA-256 | `bb985e1f792e1cfee150ec57bdc6d706f7484499fa999da3406a5798260e8d47` |
| Umbral de cribado | 0,4258, sobre la puntuación cruda (elegido en validación) |
| AUC en validación | 0,8827 |
| Prevalencia local declarada | 0,1466 (la probabilidad previa de la combinación con la clínica) |
| Umbral por vista | PA 0,1798 y AP 0,5815; **apagado por defecto**, lo enciende la institución |

Cómo rinde en prueba (3 811 placas, 844 con opacidad), de `app/assets/metricas.json` (mismo
resultado en `results/metrics/metricas_prueba.json`): AUC 0,885; sensibilidad 88,2 % (IC de
Wilson del 95 %: 85,8 a 90,2) y especificidad 70,2 % (68,6 a 71,9) con el umbral de cribado.
Rinde distinto según la proyección (en `results/figures/subgrupos.png`), y se midió en RSNA,
no en pacientes de ninguna consulta. El modelo no diagnostica: el profesional decide siempre.
La ficha completa, con sus límites, está en [`docs/ficha_modelo.md`](../docs/ficha_modelo.md);
por qué esta red y no otra, en [`docs/comparativa-corridas.md`](../docs/comparativa-corridas.md).

## Descargar los pesos y comprobarlos

1. Cuando exista el release v1.0 del repositorio público, baja de él `pesos_modelo_cpu.pt` y
   déjalo en esta carpeta: `models/pesos_modelo_cpu.pt`.
2. Comprueba su huella; tiene que ser la de la tabla de arriba:

   ```
   sha256sum models/pesos_modelo_cpu.pt              # Linux y macOS
   Get-FileHash -Algorithm SHA256 models\pesos_modelo_cpu.pt   # PowerShell
   ```

3. O deja que el repositorio la compruebe contra la de `app/assets/metricas.json`, que es la
   de los pesos con los que se midió todo:

   ```
   python -m src.model
   ```

   Imprime un resumen del modelo y, si los pesos están, si coinciden. Con otros pesos
   (reentrenados, por ejemplo) lanza un error: las métricas del repositorio no serían las suyas.

Los guiones del curso (`src/model.py`) usan `models/pesos_modelo_cpu.pt` si existe. Las imágenes
de Docker del servidor y de la app (`servidor/Dockerfile`, `app/Dockerfile`) copian los pesos
de `servidor/pesos_modelo_cpu.pt`: para construirlas, copia el fichero también ahí (esa ruta
tampoco se versiona).

## Por qué `.pt` y no `.pkl`

La estructura del curso muestra `best_model.pkl`, pensando en modelos de scikit-learn. Este es
una red de PyTorch y se guarda como PyTorch manda: el `state_dict` (los tensores con los pesos),
no el objeto entero. Tres razones:

- **Seguridad.** `pickle` ejecuta código al cargar, y estos pesos se descargan de internet. El
  `state_dict` se carga con `torch.load(..., weights_only=True)`, que solo admite tensores y
  rechaza todo lo demás: es lo que hacen el servidor y la app (`Motor.cargar`).
- **Independencia del código.** Un `state_dict` no arrastra la definición de la clase: se
  reconstruye la arquitectura con `construir_modelo` (`src/model.py`) y se cargan los pesos. El
  fichero no se rompe si el código se reorganiza.
- **CPU.** `pesos_modelo_cpu.pt` es el `state_dict` limpio y en CPU (`exportar_pesos_cpu`): no
  necesita GPU para cargarse.

Por eso `pesos_modelo_cpu.pt` hace aquí el papel de `best_model.pkl`; el nombre dice qué
contiene. Las versiones anteriores (las otras corridas de la comparativa) no se guardan como
ficheros del repositorio: sus métricas están en `docs/comparativa-corridas.md`.

## El calibrador

La puntuación cruda **no es una probabilidad**: el modelo se entrenó con las positivas
ponderadas, lo que la desplaza hacia arriba (`results/figures/calibracion.png` lo muestra). El
calibrador la convierte en probabilidad y en razón de verosimilitud, que es lo que se combina
con la regla clínica de Heckerling.

- Vive en [`servidor/calibrador.json`](../servidor/calibrador.json), **sí versionado**: son unos
  kilobytes de texto.
- Es una regresión isotónica ajustada **en validación** (nunca en prueba), guardada como los 200
  puntos (x, y) de su curva, con la prevalencia del conjunto de ajuste (0,2215) y la corrida de
  la que sale. No es un objeto de scikit-learn serializado: el despliegue no queda atado a una
  versión de la librería.
- La razón de verosimilitud se acota a lo que la curva sostiene (`Calibrador` en
  `src/copiloto_triaje/servicio/calibracion.py`): ninguna radiografía justifica más certeza que
  la que los datos de validación permiten.

Si se reentrena el modelo, el calibrador se reajusta con los pesos nuevos
(`scripts/ajustar_calibrador.py`) y cambian el umbral, el AUC de validación y todas las métricas
de arriba.
