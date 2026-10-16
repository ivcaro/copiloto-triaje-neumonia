---
title: Copiloto de triaje para neumonía
emoji: 🫁
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8501
short_description: Demostración académica; no es un producto sanitario
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
