# Anonimato del repositorio

Este repositorio no lleva ninguna cadena que identifique a un cliente, a una
empresa, a una máquina ni a personas, ni ningún secreto. Lo vigilan dos
comprobaciones y una revisión a mano. Aquí se dice qué hace cada una y, al
final, **qué no puede ver ninguna de las tres**.

## `tests/test_anonimato.py` (en la suite, siempre)

Tokeniza cada fichero de texto —minúsculas, sin tildes, partición por
cualquier carácter que no sea `[a-z0-9]`— y falla si el SHA-256 de algún
token está en `huellas.txt`. Tokeniza también el texto «desescapado» (un `\n`
escrito con barra invertida, `%20`, `&#99;`), para que un escape no pegue
letras a un token y lo esconda. Antes quita las tiradas de 120 o más
caracteres de base64 (las imágenes incrustadas en los notebooks), que
producirían tokens al azar. El texto que no es UTF-8 también se recorre.

Recorre lo que se publicaría: los ficheros con seguimiento, los que no lo
tienen ni están ignorados, y lo que está preparado en el índice de git y no
es lo que hay en disco. Un recorrido vacío no cuenta como limpio.

`huellas.txt` lleva una huella por línea. **La lista de lo prohibido no está
en el repositorio**: solo sus huellas. Una de ellas es la del centinela
público `centinelaanonimato7f3a`, con el que la prueba se comprueba a sí
misma: lo escribe en un fichero temporal y exige detectarlo.

No hay lista blanca. Lo que se conserva —un huso horario, identificadores
opacos de los webhooks, números de chat inventados, una IP del rango de
documentación— se conserva porque no está en la lista, no porque se exceptúe.

## `scripts/verificar_anonimato.py` (antes de publicar)

Repite la búsqueda de huellas sobre cualquier árbol y añade:

- los **secretos**, por patrón (token de bot, claves de API, JWT, claves
  privadas, cabeceras `Authorization`, contraseñas y tokens asignados a una
  clave, contraseña dentro de una URL) y los ficheros que no deben viajar
  (`.env`, claves);
- lo que **no ha podido mirar** —un enlace simbólico, un submódulo, un
  fichero que no se deja leer—, que sale como hallazgo y no como limpio;
- el **commit**: el contenido de su árbol, el autor, quien confirma y el
  mensaje (con sus pies), contra las huellas y contra los patrones de
  secretos;
- los **nombres** de los ficheros, de las carpetas, de las ramas y de las
  etiquetas;
- que el repositorio tenga **un solo commit, una sola rama y ninguna
  etiqueta**.

      python scripts/verificar_anonimato.py --raiz <árbol> --huellas <huellas> --un-solo-commit

Sus hallazgos dicen fichero, línea y huella o clase: nunca el token ni el
secreto, y el nombre de un fichero que lleve un token sale tapado. Sale con 1
si hay hallazgos, si no ha recorrido ningún fichero o si las huellas que
recibe son solo la del centinela.

## Cómo se regeneran las huellas

Quien mantiene la lista en claro, fuera del repositorio:

    ANONIMATO_LISTA=<lista en claro> python scripts/verificar_anonimato.py --regenerar

Cada entrada de la lista es un token ya tokenizado; una entrada que no dé
exactamente un token es un error, y no se escribe nada.

## Lo que no es texto: revisión manual

La prueba de huellas no puede leer imágenes. Se revisaron a mano, una a una:

| Qué | Cuándo | Qué se comprobó |
| :--- | :--- | :--- |
| los 6 PNG de `docs/eda/` | 28-sep-2026 | contenido (gráficos de datos agregados del dataset público, sin nombres, rutas, marcas de agua ni pies) y metadatos (solo `Software` y `dpi`) |
| las 6 imágenes incrustadas en `notebooks/eda_rsna.ipynb` | 28-sep-2026 | son las mismas seis figuras; mismos metadatos |
| los metadatos de los tres notebooks | 28-sep-2026 | solo `kernelspec`, `language_info` y, en uno, el nombre del propio notebook; los otros dos notebooks no tienen salidas |
| las 10 figuras de `docs/validacion-semisintetica/` | al generarlas | las dibuja `scripts/validar_combinacion.py` desde `resultados_simulacion.json`; su título lleva el rótulo «simulación semisintética»; metadatos `Software`, `dpi`, `Title` y `Description` (la huella del JSON de resultados con el que se dibujó cada una) |

La lista de binarios revisados está en `tests/test_anonimato.py`
(`BINARIOS_REVISADOS`): un binario nuevo hace fallar la suite hasta que se
revisa y se declara aquí. Cuando no hay hallazgos pero sí binarios, el
script no dice «limpio» a secas: dice cuántos binarios quedan sin recorrer.

## Lo que esto no protege

**Compara tokens con una lista cerrada.** Dice «limpio» de lo que la lista
conoce. Un identificador que nadie puso en la lista —el `id` de un workflow
nuevo, un nombre que aparece por primera vez— no lo ve. Antes de publicar
hace falta, además, que una persona recorra el árbol buscando lo que
identifica: correos, dominios, direcciones, rutas con un usuario, nombres
propios, identificadores de una instancia.

**Un token solo se detecta entero y suelto.** No se detecta pegado a otras
letras o cifras (`prefijoTOKENsufijo`, `token2026`), partido por un salto de
línea o por un guion de fin de línea, escrito con letras de otro alfabeto que
se parecen, ni en un base64 corto. Una tirada de 120 o más caracteres del
alfabeto de base64 se quita sin mirarla.

**Los secretos se buscan por su forma.** Detrás de una clave, una contraseña
de menos de ocho caracteres, o escrita solo con letras, o solo con cifras, no
tiene forma de secreto y no salta. Lo que lleva paréntesis, corchetes o
llaves se toma por una expresión, no por un literal.

**No mira la carpeta `.git`.** La dirección del remoto, el historial de
referencias y los commits que ya no alcanza ninguna rama viven ahí. El
repositorio se publica con `git push` de su único commit, nunca comprimiendo
la carpeta.

**Quita cadenas; no oculta la autoría** a quien llegue al repositorio por
otro camino. Y no revisa el historial: por eso el repositorio que se publica
es nuevo y de un solo commit, hecho con una identidad de git que no sea la de
una persona.

**Una huella no es un secreto.** El SHA-256 de un token corto —un nombre, una
palabra, un dominio de pocas letras— se adivina probando candidatos: quien
tenga `huellas.txt` y un diccionario recupera buena parte de la lista. Por
eso la lista completa de huellas vive **solo en el repositorio de
desarrollo**, que es privado. En el repositorio que se publica,
`huellas.txt` lleva únicamente la huella del centinela: allí la prueba del
árbol se salta diciéndolo, las demás siguen comprobando que el mecanismo
funciona, y la comprobación de verdad se hace antes de publicar, con
`scripts/verificar_anonimato.py` y las huellas del repositorio de
desarrollo. Por lo mismo, la salida de la prueba y la del script —que
enseñan el principio de cada huella— tampoco se publican cuando hay
hallazgos.
