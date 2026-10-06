# Licencias de los ejemplos

Las cuatro radiografías de la app de demostración (`ejemplos/`) salen de **tres**
imágenes de Wikimedia Commons, las tres de Mikael Häggström. Su autor las publicó
bajo **CC0 1.0 Universal**, una dedicación al dominio público: se pueden copiar,
modificar y redistribuir sin pedir permiso y sin dar crédito. Se da igualmente, de
cortesía.

**No son de RSNA ni del NIH.** El repositorio no lleva ninguna imagen del conjunto
con el que se entrenó el modelo ni de ningún otro conjunto de datos de radiografías.
El modelo se entrenó y se evaluó con RSNA, así que **no se ha medido con ellos**: son
de otra fuente, de otros equipos y de otras poblaciones, y lo que den no dice nada de
su rendimiento. Sirven para enseñar cómo funciona la app, no para evaluarla.

La edad, el sexo y la vista de cada cabecera DICOM son los de la persona de la imagen
según su página de origen, salvo la edad de `rechazado_menor.dcm`, que es inventada
(más abajo). Las cabeceras no llevan nombre ni fechas: el identificador es
`EJEMPLO-1`, `EJEMPLO-2`, `EJEMPLO-3` y `EJEMPLO-4`.

## Cómo se hicieron

1. Se descargó cada original de su página de origen en Commons (un JPEG de tres
   canales idénticos: gris de hecho, aunque se abra como imagen en color) y se
   comprobó su SHA-1 contra el que da Commons. Las descargas, de hasta 2765 px, no se
   versionan.
2. `python app/empaquetar_ejemplos.py --reducir <carpeta con las descargas>` repite
   esa comprobación, se queda con un canal (los tres son iguales), baja el lado mayor
   a 768 px (interpolación LANCZOS) y guarda cada imagen en escala de grises de 8 bits
   como PNG en `originales/`; no escribe nada si alguna de las tres falla. No se
   recorta ni se retoca nada más.
3. `python app/empaquetar_ejemplos.py` empaqueta esos PNG como DICOM sin compresión
   en `ejemplos/`. Volver a correrlo da los mismos bytes.

El SHA-1 de cada ejemplo, más abajo, es el de la descarga original, no el de los
ficheros de esta carpeta.

## `normal_pa.dcm`

- **Qué muestra:** radiografía de tórax normal, en proyección posteroanterior (PA), de una mujer de 21 años (según la página de origen). Lleva quemadas las letras de lateralidad «Dx» (derecha) y «Sin» (izquierda), y nada más.
- **Imagen original:** «Normal posteroanterior (PA) chest radiograph (X-ray).jpg», 1929 × 2207 px, 906 335 bytes
- **Página de origen:** https://commons.wikimedia.org/wiki/File:Normal_posteroanterior_(PA)_chest_radiograph_(X-ray).jpg
- **Autor:** Mikael Häggström (obra propia, subida por él mismo a Wikimedia Commons)
- **Licencia:** CC0 1.0 Universal, dedicación al dominio público (https://creativecommons.org/publicdomain/zero/1.0/). Dice la página de origen: «This file is made available under the Creative Commons CC0 1.0 Universal Public Domain Dedication.»
- **Atribución:** Mikael Häggström, vía Wikimedia Commons, CC0 1.0 (de cortesía: la licencia no la exige)
- **Consentimiento:** No consta: la página de origen (consultada el 5-oct-2026) no menciona ningún consentimiento de la persona. El repositorio no ha comprobado nada más.
- **SHA-1 del original:** `3124c4cf4c55eb3d2defa9b909f08f94e941ec43`
- **Qué se cambió:** reducida a 768 px de lado mayor y en escala de grises de 8 bits (`originales/normal_pa.png`), y empaquetada como DICOM sin compresión (`ejemplos/normal_pa.dcm`) con una edad, un sexo y una vista de ejemplo, los de la persona de la imagen según la página de origen. Sin nombre ni fechas.
- **Edad en el DICOM:** `021Y`
- **Sexo en el DICOM:** `F`
- **Vista en el DICOM:** `PA`

## `neumonia_pa.dcm`

- **Qué muestra:** radiografía de tórax en proyección posteroanterior (PA) de un varón de 88 años (según la página de origen), con neumonía: consolidación en parches, sobre todo en el lóbulo superior derecho. Lleva quemada la letra de lateralidad «Sin», boca abajo (volteada en vertical: el orden de las letras se conserva), y un pequeño marcador redondo sobre el borde del tórax, a la derecha de la imagen.
- **Imagen original:** «Chest radiograph in influensa and H influenzae, posteroanterior.jpg», 1163 × 1010 px, 454 394 bytes
- **Página de origen:** https://commons.wikimedia.org/wiki/File:Chest_radiograph_in_influensa_and_H_influenzae,_posteroanterior.jpg
- **Autor:** Mikael Häggström (obra propia, subida por él mismo a Wikimedia Commons)
- **Licencia:** CC0 1.0 Universal, dedicación al dominio público (https://creativecommons.org/publicdomain/zero/1.0/). Dice la página de origen: «This file is made available under the Creative Commons CC0 1.0 Universal Public Domain Dedication.»
- **Atribución:** Mikael Häggström, vía Wikimedia Commons, CC0 1.0 (de cortesía: la licencia no la exige)
- **Consentimiento:** según la página de origen (consultada el 5-oct-2026), la persona dio su consentimiento informado por escrito, incluida la publicación en línea. Es lo que dice esa página: el repositorio no lo ha comprobado.
- **SHA-1 del original:** `dcb6d1627f722498e203ba547afcab17d49efa0a`
- **Qué se cambió:** reducida a 768 px de lado mayor y en escala de grises de 8 bits (`originales/neumonia_pa.png`), y empaquetada como DICOM sin compresión (`ejemplos/neumonia_pa.dcm`) con una edad, un sexo y una vista de ejemplo, los de la persona de la imagen según la página de origen. Sin nombre ni fechas.
- **Edad en el DICOM:** `088Y`
- **Sexo en el DICOM:** `M`
- **Vista en el DICOM:** `PA`

## `neumonia_ap.dcm`

- **Qué muestra:** radiografía de tórax en proyección anteroposterior (AP) de una mujer de 76 años (según la página de origen), con infiltrados neumónicos. Lleva quemada la letra de lateralidad «Sin», boca abajo (volteada en vertical: el orden de las letras se conserva), y nada más.
- **Imagen original:** «Chest X-ray in influenza and Haemophilus influenzae.jpg», 2765 × 2505 px, 2 899 432 bytes
- **Página de origen:** https://commons.wikimedia.org/wiki/File:Chest_X-ray_in_influenza_and_Haemophilus_influenzae.jpg
- **Autor:** Mikael Häggström (obra propia, subida por él mismo a Wikimedia Commons)
- **Licencia:** CC0 1.0 Universal, dedicación al dominio público (https://creativecommons.org/publicdomain/zero/1.0/). Dice la página de origen: «This file is made available under the Creative Commons CC0 1.0 Universal Public Domain Dedication.»
- **Atribución:** Mikael Häggström, vía Wikimedia Commons, CC0 1.0 (de cortesía: la licencia no la exige)
- **Consentimiento:** según la página de origen (consultada el 5-oct-2026), la persona dio su consentimiento informado por escrito, incluida la publicación en línea. Es lo que dice esa página: el repositorio no lo ha comprobado.
- **SHA-1 del original:** `1520e41ffc60375b20d946908cdfc1b1fd8cd61a`
- **Qué se cambió:** reducida a 768 px de lado mayor y en escala de grises de 8 bits (`originales/neumonia_ap.png`), y empaquetada como DICOM sin compresión (`ejemplos/neumonia_ap.dcm`) con una edad, un sexo y una vista de ejemplo, los de la persona de la imagen según la página de origen. Sin nombre ni fechas.
- **Edad en el DICOM:** `076Y`
- **Sexo en el DICOM:** `F`
- **Vista en el DICOM:** `AP`

## `rechazado_menor.dcm`

- **Qué muestra:** la misma radiografía normal de `normal_pa.dcm`, con una edad de 15 años en la cabecera. Sirve para enseñar cómo rechaza el sistema lo que no puede evaluar: el modelo solo es válido entre los 18 y los 100 años.
- **Imagen original:** «Normal posteroanterior (PA) chest radiograph (X-ray).jpg», 1929 × 2207 px, 906 335 bytes
- **Página de origen:** https://commons.wikimedia.org/wiki/File:Normal_posteroanterior_(PA)_chest_radiograph_(X-ray).jpg
- **Autor:** Mikael Häggström (obra propia, subida por él mismo a Wikimedia Commons)
- **Licencia:** CC0 1.0 Universal, dedicación al dominio público (https://creativecommons.org/publicdomain/zero/1.0/). Dice la página de origen: «This file is made available under the Creative Commons CC0 1.0 Universal Public Domain Dedication.»
- **Atribución:** Mikael Häggström, vía Wikimedia Commons, CC0 1.0 (de cortesía: la licencia no la exige)
- **Consentimiento:** No consta, igual que en `normal_pa.dcm`, de donde salen sus píxeles: la página de origen de esa imagen (consultada el 5-oct-2026) no menciona ningún consentimiento de la persona. El repositorio no ha comprobado nada más.
- **SHA-1 del original:** `3124c4cf4c55eb3d2defa9b909f08f94e941ec43`
- **Qué se cambió:** lo mismo que `normal_pa.dcm`, con los mismos píxeles (`originales/normal_pa.png`, reducida a 768 px de lado mayor y en escala de grises de 8 bits) empaquetados como DICOM sin compresión (`ejemplos/rechazado_menor.dcm`), y otra edad en la cabecera: 15 años, inventada. La persona de la imagen tenía 21; la edad se cambió para que el motor rechace la placa con `fuera_de_alcance`. No es un dato clínico de nadie.
- **Edad en el DICOM:** `015Y`
- **Sexo en el DICOM:** `F`
- **Vista en el DICOM:** `PA`
