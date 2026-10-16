---
title: Copiloto de triaje para neumonía
emoji: 🫁
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8501
short_description: Demostración académica; no es un producto sanitario
license: cc-by-nc-4.0
pinned: false
---

# Copiloto de triaje para neumonía en adultos — demostración

Esta es la página de demostración de un proyecto académico (Proyecto Integrador, Maestría en
Inteligencia Artificial): una red que mira una radiografía de tórax y dice si ve una opacidad
compatible con neumonía, y que puede combinar esa evidencia con cinco hallazgos clínicos
(regla de Heckerling). La página tiene tres pestañas: **Probar el modelo**, **Historial de la
sesión** y **Acerca de** (el modelo, las métricas por subgrupo con sus intervalos y las
limitaciones).

**Es una demostración académica. No es un producto sanitario, no diagnostica y no sirve para
decidir sobre un paciente**: en el proyecto el profesional decide siempre.

## Cómo probarla

Deje elegido «Usar un ejemplo», elija uno de los cuatro y pulse «Prueba con ejemplo». Los
ejemplos son radiografías de Wikimedia Commons con licencia CC0 (de fuera del conjunto con el
que se entrenó el modelo); sirven para ver cómo funciona la página, no para evaluarla. También
puede subir un DICOM propio de hasta 5 MB.

**No suba radiografías de pacientes reales ni nada que identifique a una persona.** Esta
página corre en los servidores de Hugging Face: lo que se sube se procesa allí, en el
proceso de la propia página; la aplicación no lo guarda en disco ni lo envía a ningún otro
sitio, pero este Space no es un entorno clínico.

La primera visita puede tardar: un Space gratuito se duerme tras un tiempo sin uso y
arranca de nuevo, y la página carga el modelo la primera vez (unos segundos).

## Dónde está el resto

El código, la documentación completa, los pesos del modelo y el procedimiento para ejecutar
esta misma página en local están en el repositorio del proyecto:
<!-- PENDIENTE: poner aquí el enlace al repositorio cuando sea público -->
(enlace pendiente: se añade cuando el repositorio sea público).

Los ficheros de este Space los arma el guion `despliegue/huggingface/preparar_space.py` del
repositorio: la aplicación (`app/`), el paquete `copiloto_triaje` (`src/`), el calibrador y los
pesos. Nada más.

## Licencia y atribución

- **Licencia.** El código de la aplicación es MIT. Los **pesos del modelo**
  (`pesos_modelo_cpu.pt`, que van dentro de este Space) se publican con
  [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/): se pueden usar, compartir y
  adaptar citando la procedencia y **sin fines comerciales**. La cabecera de este fichero
  declara `cc-by-nc-4.0`, la más restrictiva de las dos, porque el Space lleva ambas cosas.
- **Datos.** El modelo se entrenó con el RSNA Pneumonia Detection Challenge (Kaggle, 2018), que
  deriva del conjunto NIH ChestX-ray14; el **NIH Clinical Center es el proveedor de los datos**.
  Este Space **no contiene ni redistribuye ninguna imagen ni ninguna etiqueta** de esos datos
  (los ejemplos son radiografías de Wikimedia Commons, CC0), y no se intentó identificar ni contactar a
  ninguno de los sujetos de los datos.
- **Uso: solo investigación y educación.** Es un prototipo académico y no es un producto
  sanitario.
- **Referencias.**
  - Imágenes: NIH ChestX-ray14, [sitio de descarga del NIH](https://nihcc.app.box.com/v/ChestXray-NIHCC).
    X. Wang, Y. Peng, L. Lu, Z. Lu, M. Bagheri y R. M. Summers, «ChestX-ray8: hospital-scale chest X-ray database and benchmarks on weakly-supervised classification and localization of common thorax diseases», en *Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR)*, 2017, pp. 3462–3471, doi: 10.1109/CVPR.2017.369.
  - Anotaciones: RSNA Pneumonia Detection Challenge, [sitio de la RSNA](https://www.rsna.org/education/ai-resources-and-training/ai-image-challenge/RSNA-Pneumonia-Detection-Challenge-2018).
    G. Shih *et al.*, «Augmenting the National Institutes of Health chest radiograph dataset with expert annotations of possible pneumonia», *Radiol. Artif. Intell.*, vol. 1, n.º 1, art. e180041, ene. 2019, doi: 10.1148/ryai.2019180041.
