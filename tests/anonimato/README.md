# Anonimato del repositorio

Este repositorio no lleva ninguna cadena que identifique a un cliente, a una
empresa, a una máquina ni a personas, ni ningún secreto. Lo vigilan dos
comprobaciones y una revisión a mano. Aquí se dice qué hace cada una y, al
final, **qué no puede ver ninguna de las tres**.

## `tests/test_anonimato.py` (en la suite, en cada corrida)

Tokeniza cada fichero de texto —minúsculas, sin tildes, partición por
cualquier carácter que no sea `[a-z0-9]`— y falla si el SHA-256 de algún
token está en `huellas.txt`. Tokeniza también el texto «desescapado» (un `\n`
escrito con barra invertida, `%20`, `&#99;`), para que un escape no pegue
letras a un token y lo esconda. Antes quita las tiradas de 120 o más
caracteres de base64 (las imágenes incrustadas en los notebooks), que
producirían tokens al azar. El texto que no es UTF-8 también se recorre.

Otra prueba busca en el mismo recorrido los secretos y lo que no se ha podido
mirar, también en los nombres de los ficheros y de las carpetas: lo que más
abajo se describe con el script. Esa no necesita la lista y corre siempre.

Recorre lo que se publicaría: los ficheros con seguimiento, los que no lo
tienen ni están ignorados, y lo que está preparado en el índice de git y no
es lo que hay en disco. Un recorrido vacío no cuenta como limpio.

`huellas.txt` lleva una huella por línea. **La lista de lo prohibido no está
en el repositorio**: solo sus huellas. Una de ellas es la del centinela
público `centinelaanonimato7f3a`, con el que la prueba se comprueba a sí
misma: lo escribe en un fichero temporal y exige detectarlo. Es la única
huella que no cuenta en el árbol: el centinela está escrito en claro en este
documento y en la propia prueba.

No hay lista blanca de huellas. Lo que se conserva —un huso horario,
identificadores opacos de los webhooks, números de chat inventados, una IP
del rango de documentación— se conserva porque no está en la lista, no porque
se exceptúe. El buscador de secretos sí deja pasar lo que es de ejemplo: unas
pocas palabras (`prueba`, `clave`, `token`, `cambiar-esto`), los marcadores
entre `<` y `>`, las variables (`$NOMBRE`, `${NOMBRE}`) y el fichero
`.env.ejemplo`.

## `scripts/verificar_anonimato.py` (antes de publicar)

Repite la búsqueda de huellas sobre cualquier árbol y añade:

- los **secretos**, por patrón (token de bot, claves de API, JWT, claves
  privadas, cabeceras `Authorization`, contraseñas y tokens asignados a una
  clave, contraseña dentro de una URL) y los ficheros que no deben viajar
  (`.env`, claves);
- lo que **no ha podido mirar** —un enlace simbólico, un submódulo, un
  fichero que no se deja abrir—, que sale como hallazgo y no como limpio
  (una carpeta que no se deja recorrer, no: más abajo);
- el **commit**: el contenido de su árbol, el autor, quien confirma y el
  mensaje (con sus pies), contra las huellas y contra los patrones de
  secretos;
- los **nombres** de los ficheros, de las carpetas, de las ramas y de las
  etiquetas;
- que el repositorio tenga **un solo commit, una sola rama y ninguna
  etiqueta**, y que ese commit no lleve más cabeceras que su árbol, su autor
  y quien lo confirma: una firma lleva el identificador de la clave de quien
  firma, así que el commit único se hace con `git commit --no-gpg-sign`;
- que lo que se publica **no lleve ninguna huella de la lista**, ni en el
  árbol —su `huellas.txt` lleva solo la del centinela—, ni en el commit (el
  mensaje, el autor, quien confirma), ni en los nombres de las ramas y de
  las etiquetas. La huella se busca entera y
  suelta, como cualquier token: pegada a otras letras o cifras, o escrita
  de otra forma, no se ve.

      python scripts/verificar_anonimato.py --raiz <árbol> --huellas <huellas> --un-solo-commit

Sus hallazgos dicen fichero, línea y huella o clase: nunca el token ni el
secreto, y el nombre de un fichero que lleve un token sale tapado. Sale con 1
si hay hallazgos, si no ha recorrido ningún fichero de texto o si las huellas
que recibe son solo la del centinela.

## Cómo se regeneran las huellas

Quien mantiene la lista en claro, fuera del repositorio:

    python scripts/verificar_anonimato.py --regenerar --lista <lista en claro>

(o con la ruta de la lista en la variable de entorno `ANONIMATO_LISTA`, sin
`--lista`). Las entradas van en la sección `[huellas]` de la lista, una por
línea, y cada una es un token ya tokenizado: una entrada que no dé
exactamente un token es un error, y no se escribe nada.

El `huellas.txt` del repositorio que se publica, con solo la huella del
centinela, se escribe sin lista, y lleva su propia cabecera, que dice qué
fichero es y dónde se hace la comprobación de verdad:

    python scripts/verificar_anonimato.py --regenerar --solo-centinela --huellas <árbol que se publica>/tests/anonimato/huellas.txt

## Lo que no es texto: revisión manual

La prueba de huellas no puede leer imágenes. Se revisaron a mano, una a una:

| Qué | Cuándo | Qué se comprobó |
| :--- | :--- | :--- |
| los 6 PNG de `docs/eda/` | 28-sep-2026 | contenido (gráficos de datos agregados del dataset público, sin nombres, rutas, marcas de agua ni pies) y metadatos (solo `Software` y `dpi`) |
| las 6 imágenes incrustadas en `notebooks/eda_rsna.ipynb` | 28-sep-2026 | son las mismas seis figuras; mismos metadatos |
| los metadatos de los tres notebooks | 29-sep-2026 | del notebook: `kernelspec` y `language_info` y, en el de Colab, `accelerator` y `colab` (con el nombre del propio notebook); de las celdas: en `eda_rsna.ipynb`, las horas de ejecución. Los otros dos notebooks no tienen salidas |
| las 10 figuras de `docs/validacion-semisintetica/` | 29-sep-2026 | contenido (gráficos de la simulación, sin nombres, rutas, marcas de agua ni pies; el título lleva el rótulo «simulación semisintética») y metadatos (`Software`, `dpi`, `Title` y `Description`, que es la huella del JSON de resultados con el que `scripts/validar_combinacion.py` dibujó cada una) |
| los 3 PNG de `app/assets/originales/` | 5-oct-2026 | contenido (radiografías de tórax de adultos de Wikimedia Commons, CC0, de fuera de RSNA y del NIH, reducidas a 768 px y en gris; solo llevan las letras de lateralidad «Dx» y «Sin» —la «Sin» de dos de ellas, `neumonia_pa` y `neumonia_ap`, está boca abajo: volteada en vertical, con el orden de las letras— y, en `neumonia_pa`, un pequeño marcador redondo en el borde del tórax; sin nombres, fechas, números ni marcas de agua) y metadatos (ninguno: el fichero solo tiene los trozos `IHDR`, `IDAT` e `IEND`, y su SHA-256 lo hace cumplir) |
| los 4 DICOM de `app/assets/ejemplos/` | 5-oct-2026 | contenido (los píxeles de esos PNG; `rechazado_menor.dcm` repite los de `normal_pa.dcm`) y cabecera, elemento por elemento: `PatientName` vacío, `PatientID` `EJEMPLO-n`, edad, sexo y vista de ejemplo, UID de la raíz `2.25` sacados del nombre de cada ejemplo y lo mínimo de una imagen de 8 bits sin comprimir; ninguna fecha, hora, centro ni equipo; el preámbulo a ceros y nada detrás de los píxeles |
| las 4 capturas de `docs/interfaz/` | 6-oct-2026 | contenido (la página de la app, solo la página, sin barra del navegador, sin ruta ni nada de la máquina: «Probar el modelo» con «Usar un ejemplo» y el ejemplo «Neumonía, PA», sus cinco hallazgos inventados, el resultado y el mapa de calor sobre la placa —la misma radiografía que `app/assets/originales/neumonia_pa.png`, con las mismas marcas que su fila de arriba y nada más—; el ejemplo «rechazado»; y dos recortes de «Acerca de», el modelo y las métricas con su tabla por subgrupo. Todo el texto es el de la propia app y la literatura que cita: ningún nombre de persona ni de institución, ninguna dirección, ningún identificador) y metadatos (ninguno: el fichero solo tiene los trozos `IHDR`, `IDAT` e `IEND`, y su SHA-256 lo hace cumplir). Se hicieron con la imagen Docker construida y los pesos de verdad, con el navegador de Playwright, y se recortó el blanco sobrante y se volvieron a escribir solo con sus píxeles |

Varias pruebas de `tests/test_anonimato.py` atan esa revisión:

- `BINARIOS_REVISADOS` es la lista de los binarios revisados: un binario
  nuevo hace fallar la suite hasta que se revisa y se declara aquí. Fuera de
  un repositorio de git —una descarga en ZIP— no se sabe qué está
  versionado, y la prueba se salta diciéndolo. Solo caben PNG y DICOM: son
  los que miran las pruebas de metadatos.
- Los DICOM de los ejemplos de la app no pueden ir a la lista de lo ignorado
  (`*.dcm`, que es el conjunto de datos): el `.gitignore` los exceptúa por su
  carpeta, `app/assets/ejemplos/`, y solo a ellos. Si no, un `git add -A` los
  dejaría fuera sin avisar y esta prueba no los vería.
- `HUELLAS_DE_LOS_BINARIOS` fija, por su SHA-256, los siete binarios de
  `app/assets/` (los tres PNG de `originales/` y los cuatro DICOM de
  `ejemplos/`) y las cuatro capturas de `docs/interfaz/`, como
  `IMAGENES_DE_LOS_NOTEBOOKS` fija las imágenes de los notebooks. Declararlos
  solo por su nombre no vería que otra imagen ocupase su sitio, que un PNG
  ganase un trozo auxiliar (una fecha, un texto) ni que un DICOM se regenerase
  con otra cabecera; con la huella, un binario que cambia, o que falta, hace
  fallar la suite, que dice el fichero y no vuelca bytes. Otra prueba exige que
  todo binario declarado bajo `app/assets/` o `docs/interfaz/` tenga su huella
  (y que no sobre ninguna), para que el próximo no se declare solo por su
  nombre. **Las huellas se rehacen a la vez que los binarios** (otra imagen, un
  cambio de `app/empaquetar_ejemplos.py`, otra versión de pydicom, otra captura
  porque la pantalla cambió) **y solo después de volver a mirarlos**: la huella
  dice «es el que se miró», no «está bien».
- `IMAGENES_DE_LOS_NOTEBOOKS` fija, por su SHA-256, las imágenes incrustadas
  en cada notebook: una imagen nueva, o una que cambie al volver a ejecutar
  el notebook, hace fallar la suite hasta que se revisa. Y como una imagen se
  puede pegar de más maneras (dentro del texto de una celda, en una salida
  HTML, en cualquier otro fichero), otra prueba exige que toda tirada de 120
  o más caracteres de base64 de un fichero de texto que se publica sea una
  de esas imágenes declaradas. Si el base64 va partido en líneas de menos de
  120 caracteres, esa prueba no lo ve (más abajo, en lo que esto no
  protege).
- Las claves de los metadatos de los PNG y de las imágenes incrustadas
  tienen que estar en `METADATOS_PERMITIDOS`, y las de cada notebook y de sus
  celdas, en las de la tabla (con `colab.provenance` vacío): un notebook
  guardado de nuevo desde Colab o Kaggle hace fallar la suite hasta que se
  revisa. Con la lista entera, los valores de los metadatos de las imágenes
  se miran también contra las huellas; con solo la del centinela, esa parte
  se salta diciéndolo.
- Las etiquetas de la cabecera de cada DICOM, la de su `file_meta` y la de su
  conjunto de datos, tienen que estar en `ETIQUETAS_DICOM_PERMITIDAS`, y sus
  nombres de persona, fechas y horas, vacíos: un DICOM guardado de nuevo con
  el nombre de un centro o de un equipo, o con una fecha, hace fallar la suite
  hasta que se revisa. Con la lista entera, los valores de la cabecera se
  miran también contra las huellas; con solo la del centinela, esa parte se
  salta diciéndolo. Los píxeles no son una etiqueta: solo los ve la revisión
  a mano.

Cuando no hay hallazgos pero sí binarios, el script no dice «limpio» a secas:
dice cuántos binarios quedan sin recorrer. Las imágenes incrustadas no las
cuenta: para el script un notebook es texto.

Fuera de un repositorio de git, las pruebas que recorren el árbol miran la
carpeta entera, también lo que git ignoraría: un `.env` que alguien haya
creado en su copia hace fallar la de los secretos (y la de las huellas, si
lleva un token de la lista), y el base64 de una dependencia instalada dentro
de la carpeta, la de las tiradas largas. Cuando fallan así, su mensaje lo
dice. Un fichero que no se deja abrir (sin permiso, bloqueado) no se da por
limpio: la prueba de las tiradas largas lo da como hallazgo, con su nombre.

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
alfabeto de base64 se quita sin mirarla: el contenido de una imagen
incrustada solo lo ve la revisión a mano, y sus metadatos, la prueba que la
fija (más arriba). Y una imagen pegada como `data:` en el texto de una celda
o en una salida HTML, con su base64 partido en líneas cortas, no la ve
ninguna prueba.

**Los secretos se buscan por su forma.** Una asignación solo se mira si el
NOMBRE de la clave lleva `password`, `passwd`, `secret`, `token` o `api_key`,
o acaba en `_KEY` en mayúsculas (o, en minúsculas, en una de unas pocas:
`private_key`, `access_key`, `signing_key`…): una clave que se llame `clave`,
`contrasena`, `pwd` o `auth` no se mira. Y solo salta si el valor tiene forma
de secreto: ocho o más caracteres, con letras y cifras. Una contraseña corta,
o sin cifras, o sin letras, no salta. Un valor escrito sin comillas que lleva
paréntesis, corchetes o llaves se toma por una expresión, no por un literal; y
entre comillas, el que lleva `{{`, `${` o `$(`, o empieza por `=`: un secreto
de verdad con esa forma no salta. Detrás de un subíndice o de una coma
(`entorno["CLAVE"] = valor`, `poner("CLAVE", valor)`), un valor sin comillas
se toma por una variable y no se mira.

**Una carpeta que no se deja recorrer.** Fuera de un repositorio de git, el
recorrido se la salta sin decirlo, con todo lo que tenga dentro; dentro de un
repositorio, el recorrido se detiene con un error.

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
`huellas.txt` lleva únicamente la huella del centinela: allí las pruebas que
necesitan la lista entera se saltan diciéndolo, la búsqueda de secretos y las
pruebas del mecanismo corren igual, y la comprobación de verdad se hace antes
de publicar, con `scripts/verificar_anonimato.py` y las huellas del
repositorio de desarrollo. Por lo mismo, la salida de la prueba y la del
script —que enseñan el principio de cada huella— tampoco se publican cuando
hay hallazgos.

**No decide qué se cuenta.** Las fechas de las sesiones y de las tutorías, o
la institución que nombra el `README.md`, no son cadenas de la lista: si se
publican o no se decide al construir el repositorio que se publica.

**Un salto se ve verde.** Si el `huellas.txt` del repositorio de desarrollo
se quedara solo con la huella del centinela —porque alguien copió encima el
del repositorio publicado—, la prueba de huellas del árbol se saltaría y la
suite seguiría en verde. Se ve corriendo la suite con `-rs`, que lista lo que se
salta y por qué; y el script, que no se salta nada, sale con 1.
