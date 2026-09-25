# SP3 — Manual de operación

Todo lo que hay que saber para poner en marcha los dos bots, dar de alta a un
clínico, probar el circuito entero y retirarlo. Escrito el 25-sep-2026, con los
dos bots ya funcionando.

**Tres sitios distintos, y confundirlos es el 80 % de los problemas:**

| Dónde | Qué va ahí |
| :--- | :--- |
| **El VPS** (donde el prompt dice `root@ubuntu-…`) | todo lo de `docker` |
| **Tu Windows, PowerShell** | el túnel, las pruebas, los scripts |
| **n8n en el navegador** | credenciales y workflows |

---

## 1. Dar de alta a un profesional

Es lo que más se va a repetir. Tres pasos.

**1. Que la persona le escriba `/start` al bot del profesional.** Le dirá
«No autorizado.» y nada más — sin pistas de qué hay detrás. **Eso es lo
correcto**, y el intento queda registrado con su `chat_id`, que es justo de
donde se lee el identificador.

**2. Averiguar su `chat_id`.** Con el túnel abierto (§3) y el DSN puesto:

```powershell
cd "C:\Users\[retirado]\OneDrive\Desktop\Claude\Proyecto Integrador\copiloto-triaje"; C:\venv-copiloto\Scripts\python.exe pruebas/profesionales.py
```

Lista los intentos no autorizados más recientes **y te imprime el comando de
alta ya montado** para cada uno.

**3. Darla de alta**, con el `chat_id` que te dio el paso anterior:

```powershell
C:\venv-copiloto\Scripts\python.exe pruebas/profesionales.py --alta 123456789 "Dr./Dra. Apellido"
```

Surte efecto **en el mensaje siguiente**: no hace falta reiniciar nada.

**Comprobar y dar de baja:**

```powershell
C:\venv-copiloto\Scripts\python.exe pruebas/profesionales.py --listar
```

```powershell
C:\venv-copiloto\Scripts\python.exe pruebas/profesionales.py --baja 123456789
```

La baja sustituye el nombre por «(dado de baja)»: es el único dato personal
directo del esquema y deja de hacer falta. **También surte efecto en el
mensaje siguiente**, incluso a mitad de una conversación — pero *no* le borra
los signos que ya había recogido, que sería peor.

### Si el script no arranca: las dos sentencias, literales

El script es una comodidad; el alta y la baja son las dos sentencias del §11 del
spec, y con el túnel abierto valen desde cualquier cliente de PostgreSQL. Están
aquí porque el día que el script falle —psycopg sin instalar, el intérprete
movido— hay que poder dar de alta a un clínico igualmente:

```sql
INSERT INTO profesionales (chat_id, nombre) VALUES (123456789, 'Dra. Apellido');
```

```sql
UPDATE profesionales SET activo = false, baja_en = now(),
       nombre = '(dado de baja)'
 WHERE chat_id = 123456789;
```

La única diferencia con el script es que este, en el alta, añade
`ON CONFLICT (chat_id) DO UPDATE` para que volver a dar de alta a quien ya
estuvo —y se dio de baja— funcione en vez de chocar con la clave primaria. Con
el `INSERT` de arriba, a alguien que ya tiene fila hay que reactivarlo con un
`UPDATE ... SET activo = true, baja_en = NULL, nombre = ...`.

---

## 2. Probar el circuito entero

El orden importa: el profesional necesita un código que solo el paciente puede
crear.

1. Escríbele al **bot del paciente**. Acepta el consentimiento y contesta las
   siete preguntas. Al final te da un código de **6 caracteres** — letras y
   números, de un alfabeto sin `0`/`O` ni `1`/`I`/`L` porque se dicta en voz
   alta. Caduca a los 7 días.
2. Escríbele al **bot del profesional**. Te pedirá ese código, te enseñará los
   síntomas que refirió el paciente, y te pedirá los cuatro signos:
   temperatura (30,0–45,0), frecuencia cardiaca (20–250), crepitantes y
   murmullo.
3. Por último la radiografía, **como archivo, no como foto**. Si la mandas
   como foto te lo dirá y seguirá esperando el archivo: Telegram recomprime las
   fotos y destruye el DICOM.

DICOM de prueba, cualquiera de aquí:

```
C:\Users\[retirado]\datasets\rsna-pneumonia\trabajo\crudo\stage_2_train_images\
```

**Casos que merece la pena probar a propósito:**

| Qué probar | Cómo |
| :--- | :--- |
| El aviso de discrepancia del §8 | una placa de la banda `cruda ∈ [0,4258 ; 0,5786]` — pasa en el 23 % de los positivos |
| El rechazo clínico | una placa de un **menor de edad**; hay 1 276 reales en RSNA |
| El rechazo por formato | manda la placa como foto |
| El código caducado | inventa un código de 6 caracteres |

`pruebas/seleccionar_casos.py` saca un ejemplo de cada perfil.

### Lo visual: el guion que ninguna aserción cubre

Las pruebas afirman sobre la base de datos, y por eso hay cosas que **solo se
ven mirando**. Este guion son las ocho, en el orden en que salen al conducir la
conversación una vez. Se hace **en el teléfono**, no en el escritorio: es donde
lo va a usar un clínico y es donde las burbujas se parten.

| # | Qué se mira | Qué está bien |
| :-- | :--- | :--- |
| 1 | El consentimiento del paciente | Se lee entero sin desplegar nada, y dice **«si le cuesta respirar, acuda a urgencias»** antes de los botones |
| 2 | Los botones **Acepto / No acepto** | Dos botones, en su fila, sin cortar el texto |
| 3 | Las 7 preguntas | Los botones caben en el ancho del móvil; ninguna etiqueta se parte a media palabra |
| 4 | El código que entrega | Se lee **dictándolo en voz alta** sin dudar: sin `0`/`O`, sin `1`/`I`/`L` |
| 5 | Los tres bloques del §8 | **Cribado**, **Evidencia de la imagen** y lo referido/explorado quedan en renglones separados. La etiqueta y la razón de verosimilitud **nunca** en el mismo renglón |
| 6 | El aviso de discrepancia | El ⚠️ se ve como un aviso y no como parte de la frase anterior |
| 7 | Las tildes y los grados | `38,2 °C`, `neumonía`, `razón` — si sale `neumonia` o `38,2 C`, algo se comió el UTF-8 por el camino |
| 8 | El mensaje aparte del paciente | Cuando el paciente escribió algo, llega **detrás** del informe, empezando por «TODO ESTE MENSAJE ES TEXTO DEL PACIENTE» |

El 5, el 6 y el 8 son los que importan de verdad: son los que hacen que el
clínico no confunda lo que dice el sistema con lo que dice el paciente.

### El arnés: el circuito entero, 49 veces y sin teclear

Lo de arriba a mano vale para una vez. Para reproducir de golpe los casos
límite reales —y dejarlos escritos para leerlos con calma— está
`pruebas/reproducir_casos.py`. Lo que hace y por qué está en la cabecera del
propio fichero; aquí va cómo se corre.

**Necesita el copiloto alcanzable.** Por defecto busca el contenedor de prueba
en el 18000, el mismo que usan las pruebas de contrato. En el VPS:

```bash
docker run -d --rm --name copiloto-prueba -p 18000:8000 -e UMBRAL=0.4258 -e AUC_VALIDACION=0.8827 -e OMP_NUM_THREADS=2 copiloto-mcp:0.1.0
```

y en tu Windows, si el contenedor está en el VPS, un túnel más:
`ssh -N -L 18000:127.0.0.1:18000 usuario@vps`. O se apunta a otro sitio con
`COPILOTO_URL`.

**Sin bots** — no toca n8n, ni Telegram, ni la base. Llama al copiloto y
redacta el mensaje con el código del propio workflow. Es lo que se puede correr
sin el túnel ni los secretos, y tarda un minuto:

```powershell
cd "C:\Users\[retirado]\OneDrive\Desktop\Claude\Proyecto Integrador\copiloto-triaje"; C:\venv-copiloto\Scripts\python.exe pruebas/reproducir_casos.py --sin-bots
```

**Con los dos bots** — conduce las 49 conversaciones de verdad. Hacen falta el
túnel de la base (§3) y cuatro variables; **son secretos y no se escriben en
ningún fichero del repositorio**:

```powershell
$env:COPILOTO_BD_DSN = "host=127.0.0.1 port=15433 dbname=copiloto user=copiloto password=..."
$env:TELEGRAM_SECRET_PRUEBA = "..."
$env:TELEGRAM_TOKEN_PROFESIONAL = "..."
$env:N8N_URL = "https://n8n.[retirado].com"
C:\venv-copiloto\Scripts\python.exe pruebas/reproducir_casos.py
```

Tarda unos **20 minutos**: son 17 mensajes por caso —16 updates y la subida de
la placa— y una pausa de 1,2 s entre cada uno, porque Telegram limita a ~1 por
segundo y chat, y un 429 no tira un mensaje: corta el chat un rato.

Antes de empezar conviene una pasada corta: `--por-perfil 1` son **9 casos y
tres minutos**, y si algo del entorno está mal se ve ahí en vez de a la
media hora.

**Lo que deja en la base, y hay que saberlo:** el arnés da de alta un `chat_id`
de pruebas en `profesionales` y lo borra al terminar —si lo matas a mitad, se
queda: bórralo con `pruebas/profesionales.py --baja`—, borra el contador de
`limite_paciente` de su propio chat antes de cada caso (si no, el sexto
cuestionario del día chocaría con el límite del §4.2), deja un cuestionario por
caso en `cuestionarios` —que se borran solos a los 7 días— y **deja una fila
por caso en `consultas`**, con síntomas inventados. Esas filas son
indistinguibles de las reales salvo por su `chat_id`, y el resumen lo imprime
al terminar junto con el `DELETE` para quitarlas.

### Leer el corpus

Sale en `pruebas/corpus/`, un fichero por caso, en carpetas numeradas **en
orden de lectura**:

```
pruebas/corpus/
  RESUMEN.txt                        <- empieza aquí
  01-positiva_clara/
  02-negativa_clara/
  03-banda_contradictoria/           <- y sigue por aquí
  04-con_comentario_del_paciente/
  05-menor_edad/
  06-edad_imposible/
  07-edad_desconocida_FABRICADO/
  08-fichero_corrupto_FABRICADO/
  09-fichero_enorme_FABRICADO/
  _fabricados/                       <- los tres DICOM modificados a propósito
```

`RESUMEN.txt` cabe en dos pantallas: los 49 casos a línea por caso, los
rechazos por código, cuántos llevaron el aviso del §8, y las latencias. Cada
fichero de caso lleva **arriba lo que sabemos de esa placa** —la edad de la
cabecera, lo que RSNA anotó, lo que puntuó el modelo— y **debajo el mensaje
literal** que recibió el profesional. No hay que abrir nada más, y no hay
ningún JSON que mirar.

**Las tres carpetas con `FABRICADO` en el nombre no son placas de RSNA.** Son
una placa real modificada a propósito para llegar a tres ramas de error que
ningún caso real alcanza: una sin la etiqueta de la edad, una truncada y una
rellenada por encima de los 5 MiB. Lo dice el nombre de la carpeta, el nombre
del fichero y el propio fichero dentro.

**El corpus no se versiona** (está en `.gitignore`). Se regenera cuando haga
falta, y guardar en el historial de git algo con la forma de un dato clínico
—un código seudónimo, unos síntomas, unos signos y un resultado— es lo
contrario de la retención del §5.4: de git no se borra nada.

---

## 3. El túnel a la base de datos

`copiloto-bd` **no publica puertos**, que es lo correcto en un VPS compartido
con 24 contenedores ajenos. n8n la alcanza porque comparte su red de Docker;
tu máquina, por un túnel SSH temporal.

**Ventana 1** — el túnel. Se queda abierta y aparentemente colgada; eso es lo
normal. La IP del contenedor sale de:

```bash
docker inspect copiloto-bd --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```

```bash
ssh -N -L 15433:<IP-del-contenedor>:5432 usuario@vps
```

Funciona porque el **host** del VPS sí alcanza las IPs de su red de Docker,
aunque nadie de fuera pueda. Al cerrar la ventana desaparece.

**Ventana 2** — el DSN, en **formato clave-valor**:

```powershell
$env:COPILOTO_BD_DSN = "host=127.0.0.1 port=15433 dbname=copiloto user=copiloto password=$(Read-Host 'contraseña')"
```

> **No uses el formato de URL.** `postgresql://usuario:clave@host/base` se
> rompe si la contraseña lleva `/`, `+`, `:` o `@`, que es lo que
> `openssl rand -base64` produce casi siempre. Y el síntoma no es un error de
> autenticación: es **`getaddrinfo failed`**, porque el parser trocea el DSN
> por los sitios equivocados y acaba buscando un servidor que no existe.

El `Read-Host` es a propósito: así la contraseña no queda en el historial de
PowerShell.

---

## 4. Registrar un bot en Telegram

Solo hace falta al crear un bot o si el webhook se desregistra. Los flujos usan
un nodo **Webhook** y no un **Telegram Trigger** —por lo que explica el §16 del
spec— y eso implica registrarlo a mano.

**1. Generar el secreto:**

```powershell
-join ((48..57) + (65..90) + (97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
```

**2. Ponerlo en n8n**, en la credencial `copiloto-paciente: secret_token…` o
`copiloto-profesional: secret_token…`, campo **Value**. El nombre de la
cabecera (`X-Telegram-Bot-Api-Secret-Token`) no se toca.

**3. Registrarlo.** No hay nada que sustituir: pregunta las dos cosas.

```powershell
$t = Read-Host 'token del bot'; $s = Read-Host 'secret_token'; Invoke-RestMethod -Uri "https://api.telegram.org/bot$t/setWebhook" -Method Post -Body @{url='https://n8n.[retirado].com/webhook/copiloto-paciente'; secret_token=$s}
```

La ruta es `copiloto-paciente` o `copiloto-profesional` según el bot. **Si
pegas la del otro, Telegram dirá `Webhook was set` igualmente y el bot quedará
mudo sin decir por qué.**

### Cuando no responde

Lo mismo que hay debajo, pero ya interpretado —los dos bots de una vez, y con
qué hacer en cada caso— lo da:

```powershell
C:\venv-copiloto\Scripts\python.exe pruebas/verificar_webhooks.py
```

A mano, un bot a la vez:

```powershell
$t = Read-Host 'token'; (Invoke-RestMethod -Uri "https://api.telegram.org/bot$t/getWebhookInfo").result | Format-List
```

| Síntoma | Qué pasa |
| :--- | :--- |
| `404 Not Found` al llamar a la API | **el token no existe**, no es la URL. Compruébalo con `getMe` |
| `403` en `last_error_message` | el secreto de n8n y el del `setWebhook` no coinciden |
| `url` vacía o distinta | el webhook no está registrado, o apunta al otro bot |
| todo bien y `pending_update_count` en 0 | Telegram entrega: el problema está dentro del flujo |

**El token sale siempre de BotFather** (`/token`). El que está guardado en una
credencial de n8n **no se puede volver a leer** desde la interfaz.

---

## 5. El mantenimiento diario y los avisos

`🩺 Copiloto Triaje: Mantenimiento` corre **todos los días a las 06:45** (hora
de Guayaquil) y hace dos cosas: ejecuta `bd/limpieza.sql` —el borrado que
promete el consentimiento— y comprueba ocho cosas. Si algo falla, manda un
mensaje por Telegram con **qué pasa, qué efecto tiene y qué hacer**.

### Puesta en marcha, en este orden

**Paso 1, y hasta que no se haga NO LLEGA NINGÚN AVISO:** rellenar el nodo
**`Configuracion`**, campo `chat_equipo`, con el chat_id de quien los recibe.
Va vacío en el repositorio a propósito —un chat_id identifica a una persona
real, y así un `git pull` tampoco puede redirigir los avisos de nadie—, así que
recién importado el workflow **limpia y comprueba, pero no habla**. Mientras esté
vacío, cada corrida que tenga algo que avisar **sale en rojo** en la lista de
ejecuciones de n8n, con el motivo escrito, en vez de callarse; y ojo, la primera
corrida en verde reinicia el «todo bien» semanal, así que puede pasar una semana
sin ninguna señal si además no falla nada.

- El chat_id lo da `pruebas/profesionales.py` (§1), y es **el mismo para todos
  los bots**: es el id del usuario de Telegram.
- Los avisos salen por **`[retirado]`** y no por los dos bots de producción:
  así quedan en su propio hilo, y el canal del aviso no depende de un token que
  quizá haya que revocar. **Hay que haberle escrito a ese bot alguna vez**: un
  bot no puede iniciar una conversación.

**Paso 2:** montar la tarea programada del lado de Telegram (más abajo, «Lo que
el workflow no puede ver»). Hasta que exista, **un webhook desregistrado en
Telegram deja un bot mudo y nada avisa**.

### Qué comprueba, y cuándo avisa

| Comprobación | Avisa cuando |
| :--- | :--- |
| `bd/limpieza.sql` corrió | el nodo devuelve un error de la base |
| `copiloto-bd` responde | un `SELECT 1` no vuelve |
| `copiloto-mcp` está sano | `/salud` no contesta, no da 200, o no dice `listo`. Tres intentos separados 5 s, porque el contenedor tarda ~19 s en quedar sano |
| Placas rechazadas por formato | hay **3 rechazos o más** *y* pasan del **20 %** de las placas de los últimos 7 días |
| Cuestionarios caducados sin borrar | queda alguno que caducó hace más de una hora |
| El webhook de cada bot sigue en pie | n8n no contesta **403** a un POST sin secreto. 404 = el flujo está desactivado o le cambiaron la ruta; 200 = la comprobación del secreto desapareció |
| Que esto mismo haya corrido | la corrida anterior quedó registrada hace más de 36 h |

**No repite.** Cada fallo se avisa cuando **aparece**, se recuerda **cada 72 h**
mientras dure, y se avisa cuando se **resuelve**. Lo que sigue igual que ayer no
dice nada. Y si no hay nada que decir, llega un **«todo bien» una vez por
semana**: si un lunes no llega, no es que todo vaya bien, es que el
mantenimiento no está corriendo.

### Lo que el workflow no puede ver: el lado de Telegram

Las sondas comprueban el lado de **n8n**. Si el que se desincronizó es
**Telegram** —apunta a otra URL, o su `secret_token` ya no coincide con el de la
credencial— desde fuera todo se ve igual y el bot está mudo. Eso lo dice:

```powershell
C:\venv-copiloto\Scripts\python.exe pruebas/verificar_webhooks.py
```

Pide los dos tokens por teclado (de BotFather: el de la credencial de n8n no se
puede volver a leer) y traduce `getWebhookInfo` a qué hacer. **No está dentro
del workflow porque el token de Telegram va en la ruta de la URL, y una
credencial de n8n solo sabe poner cabeceras o parámetros**: escribirlo en el
nodo lo metería en el JSON que se versiona, que es justo lo que el §16 del spec
evita al no usar el Telegram Trigger.

**Qué queda sin vigilar mientras esto se corra solo a mano:** que Telegram deje
de apuntar a nuestra URL —porque alguien registró la ruta del otro bot, o revocó
el token y registró de nuevo— y que su `secret_token` deje de coincidir con el de
la credencial de n8n. En los dos casos **el bot queda mudo y las sondas del
workflow siguen viendo su 403 tan contentas**: desde fuera de Telegram todo está
bien. Es el único agujero que queda del §16, y se tapa con el paso 2.

### Paso 2: la tarea programada diaria (Windows de [retirado])

Se decidió esto y no dos variables de entorno en el n8n del cliente: reiniciar
**su** n8n por una comprobación nuestra no compensa mientras H5 esté abierto.

**Una vez**, en una consola de PowerShell del usuario que vaya a correrla —las
tres variables quedan en su perfil, no en el repositorio—:

```powershell
setx TELEGRAM_TOKEN_PACIENTE (Read-Host 'token del bot del paciente')
setx TELEGRAM_TOKEN_PROFESIONAL (Read-Host 'token del bot del profesional')
setx TELEGRAM_TOKEN_AVISOS (Read-Host 'token de [retirado]')
setx COPILOTO_CHAT_EQUIPO (Read-Host 'chat_id del equipo')
```

`TELEGRAM_TOKEN_AVISOS` es el del mismo bot que usa el workflow, para que este
aviso caiga **en el mismo hilo** que los otros. Con esas cuatro puestas, el
script manda por Telegram lo que encuentre; sin ellas solo lo imprime.

**La tarea**, a las 07:15 (media hora después del workflow, para no mezclar dos
avisos en el mismo minuto):

```powershell
$acc = New-ScheduledTaskAction -Execute 'C:\venv-copiloto\Scripts\python.exe' -Argument 'pruebas\verificar_webhooks.py' -WorkingDirectory 'C:\Users\[retirado]\OneDrive\Desktop\Claude\Proyecto Integrador\copiloto-triaje'
$dis = New-ScheduledTaskTrigger -Daily -At 07:15
Register-ScheduledTask -TaskName 'Copiloto Triaje: webhooks de Telegram' -Action $acc -Trigger $dis -Description 'La mitad del §16 que no cabe en n8n: getWebhookInfo de los dos bots.'
```

Comprobar que quedó bien montada, sin esperar a mañana:

```powershell
Start-ScheduledTask -TaskName 'Copiloto Triaje: webhooks de Telegram'; Get-ScheduledTaskInfo -TaskName 'Copiloto Triaje: webhooks de Telegram'
```

`LastTaskResult` en **0** = los dos webhooks están como deben; **1** = hay algo
que arreglar, y el mensaje ya salió por Telegram.

### Probarlo sin esperar a mañana

Abre el workflow en n8n y pulsa **Execute workflow**: corre lo mismo que el
disparador. Las ejecuciones manuales se guardan, las de producción con éxito no,
y las que fallan sí —por ahí se mira qué pasó cuando no llegó ningún aviso—.

### Por qué este workflow sí guarda las ejecuciones que fallan

Los dos bots llevan las dos retenciones en `none` porque sus ejecuciones
arrastran el DICOM, su base64 y las respuestas del paciente a la base de n8n del
cliente (§5.4 del spec). El mantenimiento lleva **los éxitos en `none` y los
errores en `all`**, y es una excepción deliberada, escrita también en el §16 del
spec:

- por él **no pasa ningún dato de paciente**: sus consultas devuelven recuentos y
  códigos de error del §9, nada más, y eso lo ata una prueba de
  `tests/test_mantenimiento.py`;
- y cuando una corrida del mantenimiento falla, **su ejecución es el único rastro
  que queda**, porque el aviso es justamente lo que no pudo salir. Con los
  errores en `none`, el vigilante se cae en silencio.

---

## 6. Trampas de PowerShell

Las tres nos costaron tiempo:

- **`&&` no existe** en PowerShell 5.1. El separador es `;`.
- **`curl` es un alias de `Invoke-WebRequest`** y no entiende `-d`. Usa
  `curl.exe`, o mejor `Invoke-RestMethod`, que además evita que el token quede
  en el historial: va **dentro** de la URL.
- **Las comillas anidadas se las come.** Por eso el alta de profesionales es un
  script y no una línea de `python -c`: el error que salía hablaba de sintaxis
  de Python y mandaba a mirar donde no era.

---

## 7. Credenciales y workflows

| Rol | Credencial en n8n | Workflow |
| :--- | :--- | :--- |
| Paciente | `[retirado]` | `🩺 Copiloto Triaje: Paciente (Telegram)` |
| Profesional | `[retirado]` | `🩺 Copiloto Triaje: Profesional (Telegram)` |
| Pruebas y avisos | `[retirado]` | `🩺 Copiloto Triaje: Mantenimiento` (solo para mandar los avisos) |
| Base de datos | `copiloto-bd` | el del paciente, el del profesional y el de mantenimiento |

**No se toca ninguna otra credencial de Telegram.** `[retirado]` la usan cinco
workflows del cliente, y un token de Telegram admite **un solo webhook**:
apuntarle un flujo nuestro lo dejaría mudo sin ningún error visible.

Los tres workflows llevan el prefijo `🩺 Copiloto Triaje:`. Cualquier otro de
esa instancia es del cliente y **no se modifica**.

---

## 8. Retirada

```bash
docker compose -p copiloto-mcp down
```

Con `-p` no se lee ningún fichero de compose, así que el directorio en el que
estés deja de ser un riesgo. Después: borrar el volumen `copiloto_bd_datos`,
desactivar y archivar los tres workflows, borrar sus credenciales, y revocar
los bots en BotFather.

**Lo que no hay que teclear nunca en ese VPS:** `docker compose down` a secas
(baja el proyecto del directorio donde estés, que puede ser el del cliente),
`docker network rm [retirado]_[retirado]_network`, `docker network prune`, y
`git clean -xfd` en `/opt/copiloto`.
