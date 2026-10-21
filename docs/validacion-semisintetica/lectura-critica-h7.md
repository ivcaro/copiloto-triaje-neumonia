# Lectura crítica de H7, por el equipo

**Rótulo:** análisis del equipo del proyecto sobre la sesión de concordancia H7. **No son palabras
del médico.** Él respondió al cerrar el acta y **no dio su conformidad**; su respuesta está anexada
en el [acta](acta-h7.md), sin editar, y donde su lectura y la del equipo difieren, aquí se dicen las
dos. Las cifras salen del acta y de `sesion.json`; lo que aquí se propone es trabajo futuro, no un
cambio hecho en el sistema.

La sesión no salió como se esperaba, y el acta lo publica tal cual. Este documento es lo que el
equipo lee en esos resultados y lo que cambiaría antes de otra validación. Las implicaciones éticas
están en [`consideraciones_eticas.md`](../consideraciones_eticas.md), §15.

## 1. El sistema aparenta más certeza de la que tiene

En 4 de los 16 desacuerdos el sistema imprimió «< 1 %» y el médico respondió 60 % o 75 %; en el
conjunto, el porcentaje del médico no cae dentro de la horquilla del sistema en ninguno de los 24
casos, y queda por encima en promedio (2,82 en log-odds). Que el médico sea más precavido ante una
placa dudosa y una clínica respiratoria es lo esperable en un primer nivel: no dejar pasar una
neumonía incipiente.

Lo que el equipo concluye es que **las cifras extremas son justo las menos fiables**. La simulación
semisintética muestra que la combinación por independencia exagera cuando la clínica y la imagen
dependen entre sí (pendiente de calibración menor que 1 en las seis celdas destacadas,
[`validacion-semisintetica-sp5.md`](../validacion-semisintetica-sp5.md)): una pendiente menor que 1
quiere decir predicciones demasiado extremas, y el error crece hacia los extremos. Un «< 1 %» impreso
comunica una seguridad que ni la placa ni el cálculo sostienen.

**Qué cambiaríamos:** no imprimir el combinado más allá de unos límites (por ejemplo, por debajo de
5 % o por encima de 95 %), sino decir «muy baja» o «muy alta» con la horquilla conservadora delante,
y medir en la próxima sesión si eso acerca al médico y al sistema.

## 2. ¿El sistema arrastra al médico?

Con el mensaje delante, el médico cambió de banda en 12 de 20 casos y el kappa pasó de 0,25 a 0,81.
Eso no es concordancia: es **influencia**, la forma que toma el sesgo de automatización. Parte del
cambio es por releer —3 de los 4 controles, sin mensaje, también cambiaron de banda, y el intervalo
entre lecturas fue de 5 días y no de 7—, y con 4 controles no se puede separar una cosa de la otra.

Lo que la sesión no puede decir es si esa influencia **ayuda o daña**: depende de si el sistema
acierta en los casos en que arrastra. Un médico cansado que se confía en un caso difícil en que el
modelo falla es exactamente el daño que los avisos del informe intentan evitar.

**El médico lo lee de otra forma**, y lo dijo al cerrar el acta: «a mi parecer se cambió de opinión
al cotejar los síntomas, las imágenes y el análisis de la IA». Es decir, que integró información
nueva, que es justo lo que se espera de un apoyo. Su lectura y la del equipo son compatibles con
los mismos 12 cambios de 20, y esta sesión no permite distinguirlas: por eso el diseño de abajo es
lo primero que haría falta.

**Qué cambiaríamos:** en la próxima validación, un diseño cruzado (cada caso con y sin sistema, en
orden aleatorio), al menos dos semanas entre lecturas, más de un médico, y medir si los cambios de
banda se acercan a la etiqueta de referencia o se alejan de ella.

## 3. Más lento, no más rápido

La razón de tiempos con y sin copiloto fue 2,00 (IC 95 % 1,57 a 2,49); corregida por el efecto de
releer, 1,11 (0,69 a 1,81). No hay evidencia de que ahorre tiempo, y en una guardia con pacientes
esperando un triaje más lento no se adopta. La nota de lenguaje (2,5 sobre 5) apunta en la misma
dirección: un informe correcto (4,7) que obliga a leer de más.

El pre-informe de SP5-D responde al lenguaje, pero **añade un mensaje más que leer**: su efecto en el
tiempo no está medido y puede ir en cualquier sentido.

**Qué cambiaríamos:** una primera línea que diga la conclusión y los avisos en una frase, con el
detalle debajo, y medir el tiempo con el informe, con el pre-informe y con los dos.

## 4. La puerta de entrada: ¿hay un DICOM?

El sistema necesita el **archivo DICOM**: de su cabecera salen la edad (el modelo solo vale de 18 a 100
años) y la proyección, y una foto o un JPEG las pierde, por eso el bot rechaza las fotos. A la pregunta
de SP3 (§18) sobre si en la práctica la placa se obtiene del PACS, el médico respondió al cerrar el
acta que le llega «por Dicon o por link»: como archivo DICOM o como un enlace.

Con el DICOM, el sistema funciona tal cual. Con un enlace, depende de lo que haya detrás: si deja
descargar el DICOM, también; si es un visor que solo muestra la imagen, no. Es la respuesta de un
médico, no un estudio de cómo llegan las placas en Ecuador, y la duda del equipo sigue en pie para
los centros sin PACS: ahí la placa puede llegar como imagen comprimida o impresa.

**Qué cambiaríamos:** antes de cualquier piloto, preguntar a la institución cómo le llega la placa al
médico de triaje. Donde haya PACS o un enlace que dé el DICOM, integrarse con él; donde no, aceptar
una imagen sin cabecera con la edad y la proyección tecleadas por el profesional, lo que exigiría
volver a validar el modelo con imágenes comprimidas.

## 5. Lo que pidió el médico: más variables clínicas

Al cerrar el acta pidió añadir si el paciente es fumador, el tipo de tos, el aspecto y la coloración
de las secreciones, el estado general y los resultados de laboratorio, «para hacer más preciso el
diagnóstico». Es razonable clínicamente, y el bot del paciente ya pregunta el tipo de tos (seca o con
flema), aunque no entra en el cálculo: de las respuestas del paciente, solo el asma entra en la
puntuación de Heckerling.

La salvedad es de método. La combinación es bayesiana y explícita: una variable solo puede mover la
cifra con su razón de verosimilitud, medida en una población comparable. Sumar variables sin ella
sería inventar evidencia, y es justo lo que el diseño quiso evitar al usar una regla publicada.

**Qué cambiaríamos:** buscar razones de verosimilitud publicadas para esas variables (sobre todo las
de laboratorio) o pasar a un modelo multivariable validado que las incluya; mientras tanto, mostrar
las que no tengan evidencia como contexto en el informe, sin que muevan la cifra.

## Lo que esto no cambia

Los resultados publicados no se reinterpretan: el kappa de 0,25 no alcanza el mínimo de 0,4 y se dice.
La conclusión es la misma que dicen el README y la [ficha del modelo](../ficha_modelo.md): **el
copiloto no está listo para usarse con pacientes reales**, y antes harían falta la validación local,
la evaluación de impacto y el comité de bioética.
