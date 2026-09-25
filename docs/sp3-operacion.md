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

## 5. Trampas de PowerShell

Las tres nos costaron tiempo:

- **`&&` no existe** en PowerShell 5.1. El separador es `;`.
- **`curl` es un alias de `Invoke-WebRequest`** y no entiende `-d`. Usa
  `curl.exe`, o mejor `Invoke-RestMethod`, que además evita que el token quede
  en el historial: va **dentro** de la URL.
- **Las comillas anidadas se las come.** Por eso el alta de profesionales es un
  script y no una línea de `python -c`: el error que salía hablaba de sintaxis
  de Python y mandaba a mirar donde no era.

---

## 6. Credenciales y workflows

| Rol | Credencial en n8n | Workflow |
| :--- | :--- | :--- |
| Paciente | `[retirado]` | `🩺 Copiloto Triaje: Paciente (Telegram)` |
| Profesional | `[retirado]` | `🩺 Copiloto Triaje: Profesional (Telegram)` |
| Pruebas | `[retirado]` | — |
| Base de datos | `copiloto-bd` | — |

**No se toca ninguna otra credencial de Telegram.** `[retirado]` la usan cinco
workflows del cliente, y un token de Telegram admite **un solo webhook**:
apuntarle un flujo nuestro lo dejaría mudo sin ningún error visible.

Los tres workflows llevan el prefijo `🩺 Copiloto Triaje:`. Cualquier otro de
esa instancia es del cliente y **no se modifica**.

---

## 7. Retirada

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
