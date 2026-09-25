# SP3 — Bot de Telegram orquestado en n8n

**Hito:** H5, vence el 2-oct-2026.
**Depende de:** SP2, desplegado y verificado en el VPS el 24-sep-2026.
**Entrega a:** SP4 (H6, 9-oct), que añade la regla clínica de Heckerling y la
combinación bayesiana sobre los datos que este sub-proyecto recoge.

---

## 1. Qué construye SP3, y qué no

Construye el flujo conversacional completo de los **dos roles** y lo conecta al
copiloto ya desplegado: un bot para el **paciente**, que consiente, responde un
cuestionario de síntomas y recibe un **código seudónimo**; un bot para el
**profesional**, que presenta ese código, aporta los **signos** de la
exploración y una **radiografía DICOM**, y recibe lo que dice el modelo; la base
de datos que sostiene ambos; y la orquestación, en n8n.

**No construye** la regla de Heckerling, ni la probabilidad previa, ni la
combinación bayesiana. Los síntomas y los signos se **recogen y se guardan**,
pero en SP3 el profesional los ve **al lado** del resultado de la imagen, nunca
mezclados. Unirlos es H6.

**No lleva LLM.** Ninguna pieza de SP3 llama a un modelo de lenguaje (§4.5).

---

## 2. Decisiones

| # | Decisión | Razón |
| :-- | :--- | :--- |
| D1 | **Dos bots de Telegram separados** | Un paciente no puede recibir el resultado aunque falle una condición: su flujo no tiene ese camino. La separación deja de depender de que un `if` esté bien escrito |
| D2 | **PostgreSQL propia** (`copiloto-bd`) | Los datos clínicos quedan en infraestructura que controlamos. Las PostgreSQL del VPS son del cliente y no se tocan |
| D3 | **SP3 sin la matemática** | H5 entrega algo demostrable; H6 añade la fórmula sobre datos ya recogidos, sin volver a tocar los bots |
| D4 | **Cuestionario por botones**, texto libre opcional y fuera del cálculo | Un extractor probabilístico en la ENTRADA de un cálculo clínico no falla con un error: produce una probabilidad previa equivocada que nadie ve |
| D5 | **DICOM como documento de Telegram** | El servidor solo acepta DICOM: la edad sale de la cabecera y el preprocesamiento debe ser el del entrenamiento. Telegram recomprime a JPEG lo enviado como *foto* |
| D6 | **Lista blanca de `chat_id`**, comprobada en **cada** mensaje | Un bot de Telegram es descubrible. Comprobar solo en `/start` deja entrar a quien salte ese paso |
| D7 | **Toda la lógica en n8n** | Decisión del responsable. El coste real y su compensación están en §13, no implícitos |
| D8 | **Se llama a `/mcp`, no a `/inferir`** | Las dos puertas son el mismo servidor y el mismo modelo, pero hablar JSON-RPC con `clasificar_radiografia` es la integración que el proyecto promete y la que SP4 consumirá |
| D9 | **Bots NUEVOS de BotFather** | Un token de Telegram admite UN webhook. Reutilizar una credencial existente le robaría el webhook a un bot del cliente y lo dejaría mudo, sin error visible |
| D10 | **Dashboard después de H5**, con contraseña | No compite con los bots en la semana del hito |
| D11 | **Consentimiento explícito** antes de guardar nada | Es lo que un comité de ética preguntará en H7, y guardar síntomas sin decirlo no es defendible |
| D12 | **Los síntomas se copian a `consultas`** al consultarse | Sin esto, H7 no tiene nada que validar: `cuestionarios` se borra a los 7 días. Solo perduran los casos que un clínico realmente usó |
| D13 | **La etiqueta y la evidencia calibrada se presentan por separado** | Salen de escalas distintas y se contradicen en una banda real. Ver §8 |

---

## 3. Hechos verificados que condicionan el diseño

Medidos, no recordados. Cada fila es una restricción que el diseño obedece.

| Hecho | Consecuencia |
| :--- | :--- |
| La etiqueta `clasificacion` se decide con `probabilidad_cruda >= 0,4258`; `probabilidad_calibrada` y `razon_de_verosimilitud` salen de la curva isotónica | **Son escalas distintas.** En `cruda ∈ [0,4258 ; 0,5786]` la etiqueta es positiva y la RV es menor que 1. Ver §8 |
| La RV cruza 1,0 en `cruda = 0,5786` | Debajo de ahí la imagen **resta** probabilidades a favor de neumonía |
| **379 de las 3 811 radiografías de prueba (9,9 %) caen en esa banda**, y son el **23,3 % de todo lo que el cribado etiqueta como `opacidad_probable`** | El aviso de §8 se dispara **una de cada cuatro veces** que hay un positivo. No es un caso raro: es el comportamiento habitual |
| De esas 379, el **80,5 % no tenía opacidad** de verdad | La RV acierta y la etiqueta es la llamada conservadora del cribado. El aviso dice algo cierto y útil 4 de cada 5 veces |
| La RV viene acotada a `[0,0163 ; 77,32]` | La imagen no puede anular ni volver certeza la clínica |
| El servidor atiende un `tools/call` suelto (`stateless_http=True`) | No hace falta el saludo `initialize`: un solo nodo HTTP Request |
| El base64 envuelto en líneas se acepta (LF y CRLF) | n8n puede codificar como quiera |
| Hay **dos** límites de tamaño distintos | Ver §10.4 |
| Un token de Telegram admite **un** webhook | D9 |
| n8n 2.35.4 soporta el marco de evaluaciones completo | §13 |
| Un Telegram Trigger es un webhook público en `https://n8n.[retirado].com/webhook/...` | §4.2 |
| `callback_data` de Telegram está limitado a 64 bytes | No caben las respuestas: hace falta estado en base de datos (§5.1) |
| Latencia del copiloto en el VPS: mediana 143 ms, peor 225 ms | El presupuesto de 4 s de H4 sigue holgado dentro del bot |

Ejemplos reales, medidos contra el contenedor el 24-sep-2026:

| | cruda | calibrada | RV | clasificación | edad |
| :--- | ---: | ---: | ---: | :--- | ---: |
| placa positiva | 0,9764 | 0,8455 | 19,24 | `opacidad_probable` | 33 |
| placa negativa | 0,0064 | 0,0046 | 0,0163 | `sin_opacidad_probable` | 27 |

---

## 4. Arquitectura

### 4.1. Piezas

| Pieza | Qué es | Nueva |
| :--- | :--- | :--- |
| `copiloto-mcp` | inferencia, ya desplegado | no, **no se toca** |
| `copiloto-bd` | PostgreSQL 16, en `[retirado]_[retirado]_network`, sin puertos | sí |
| `🩺 Copiloto Triaje: Paciente (Telegram)` | workflow | sí |
| `🩺 Copiloto Triaje: Profesional (Telegram)` | workflow | sí |
| `🩺 Copiloto Triaje: Mantenimiento` | workflow, disparador programado diario | sí |
| Dos bots de Telegram | dos tokens nuevos, dos credenciales nuevas | sí |

**`copiloto-bd`** se especifica como se especificó `copiloto-mcp`: imagen
`postgres:16-alpine` con digest fijado, **volumen con nombre** para los datos,
`healthcheck` con `pg_isready`, topes `cpus: "1"` y `memory: 1G`, rotación de
log `max-size: 10m` / `max-file: 3`, `restart: unless-stopped`, y contraseña por
variable de entorno (§12). Va en el **mismo `docker-compose.yml`** que
`copiloto-mcp`, bajo el proyecto `copiloto-mcp`, para que la vuelta atrás siga
siendo un solo `docker compose -p copiloto-mcp down`.

### 4.2. Superficie pública

Esto no estaba en el primer borrador y es lo que más expone el sistema.

Cada Telegram Trigger registra un **webhook público** en
`https://n8n.[retirado].com/webhook/<id>`, alcanzable desde internet a través del
`nginx-proxy-manager` del cliente. Telegram hace POST ahí; **cualquiera que
conozca la URL también puede**.

Eso convierte el `chat_id` en **un dato que aporta quien llama**. Si alguien
forja un `update` con un `chat_id` de la lista blanca, pasa la puerta de D6.

**Obligatorio:** los dos webhooks se registran con **`secret_token`** de
Telegram, y el flujo **rechaza** todo update cuya cabecera
`X-Telegram-Bot-Api-Secret-Token` no coincida, **antes de mirar nada más**. Si
el nodo Telegram Trigger de n8n no expone ese campo, se registra el webhook a
mano con `setWebhook` y se comprueba la cabecera en el primer nodo del flujo.

Sin esa comprobación, la lista blanca no protege de nada y D6 es decorativo.

**Límite de uso del bot del paciente:** máximo **5 cuestionarios completados por
`chat_id` y día**. No es antiabuso serio; evita que un bucle o una broma llenen
la tabla en la máquina del cliente.

El contador vive en una **tabla propia**, `limite_paciente`, y no como una
columna de `cuestionarios`. La diferencia no es de estilo: `cuestionarios` está
identificado por el **código seudónimo**, y meterle el `chat_id` al lado ataría
cada cuestionario a una cuenta de Telegram concreta — que es exactamente lo que
el seudónimo existe para impedir. Con la tabla aparte, el sistema sabe *cuántos*
ha hecho un `chat_id` hoy sin saber *cuáles*.

Y el contador **se borra a los 2 días** con la limpieza diaria (§5.4). Guardar
más tiempo la actividad por cuenta de Telegram no aporta nada al límite y sí
acumula un rastro de quién usó el bot y cuándo.

### 4.3. El recorrido

```
PACIENTE                              PROFESIONAL
  /start                                /start o cualquier mensaje
  consentimiento ─ no acepta ─► fin     │
  7 preguntas de botones                ├─► secret_token válido?  no ─► descarta
     ▼                                  ├─► chat_id en lista blanca? no ─► "no autorizado"
copiloto-bd ◄───────────────────────────┤ código del paciente
     │ código seudónimo                 │ 4 preguntas de signos
     ▼                                  │ DICOM como DOCUMENTO
"dáselo a tu médico"                    ▼
                             copiloto-mcp:8000/mcp
                             tools/call clasificar_radiografia
                                        │
                                        ▼
                             §8: clasificación y evidencia,
                             en bloques separados
```

El flujo del paciente **no contiene ningún nodo que hable con `copiloto-mcp`**.
Esa ausencia es la garantía de D1 y se verifica en la revisión (§13).

### 4.4. Reparto síntomas / signos, y su correspondencia con Heckerling

De los cinco predictores, **tres exigen exploración física** y no los puede
reportar el paciente.

| Predictor de Heckerling | Campo | Quién | Tipo |
| :--- | :--- | :--- | :--- |
| Temperatura > 37,8 °C | `signos.temperatura_c` | profesional | número |
| Frecuencia cardiaca > 100 lpm | `signos.frecuencia_cardiaca` | profesional | entero |
| Crepitantes | `signos.crepitantes` | profesional | booleano |
| Murmullo vesicular disminuido | `signos.murmullo_disminuido` | profesional | booleano |
| **Ausencia** de asma | `sintomas.asma` | paciente | `si` / `no` / `no_se` |

**El asma es el único con tres estados, y eso es deliberado.** Heckerling
necesita un booleano, pero *convertir* `no_se` en uno sería fabricar el dato:
tratarlo como "no tiene asma" sube la probabilidad previa sin fundamento, y
tratarlo como "sí tiene" la baja igual de infundadamente. SP3 **conserva los
tres estados** y muestra al profesional "asma: no sabe" para que lo resuelva
clínicamente. **H6 debe definir explícitamente qué hace con `no_se` y no puede
coaccionarlo en silencio.**

**El paciente aporta** (7 preguntas, botones):

| # | Pregunta | Clave | Valores |
| :-- | :--- | :--- | :--- |
| 1 | ¿Ha sentido fiebre estos días? | `fiebre` | `si` / `no` / `no_se` |
| 2 | ¿Tiene tos? | `tos` | `con_flema` / `seca` / `no` |
| 3 | ¿Desde hace cuánto? | `dias_evolucion` | `menos_3` / `3_a_7` / `mas_7` |
| 4 | ¿Le falta el aire? | `disnea` | `si` / `no` |
| 5 | ¿Le duele el pecho al respirar? | `dolor_toracico` | `si` / `no` |
| 6 | ¿Tiene asma diagnosticada? | `asma` | `si` / `no` / `no_se` |
| 7 | ¿Algo más? (opcional) | `texto_libre` | texto o `null` |

La 7 **no alimenta ningún cálculo**. Se recorta a 500 caracteres y se muestra al
profesional **como texto plano, nunca con `parse_mode`**: es el único canal por
el que el paciente escribe libremente, y un `*` o un `_` sueltos romperían el
formato del mensaje del profesional o permitirían inyectar formato. Se sale de
ella con el botón **«Omitir»** o escribiendo.

**El profesional aporta** (4 preguntas):

| # | Pregunta | Clave | Entrada |
| :-- | :--- | :--- | :--- |
| 1 | Temperatura (°C) | `temperatura_c` | número, **30,0 a 45,0**, acepta coma o punto |
| 2 | Frecuencia cardiaca (lpm) | `frecuencia_cardiaca` | entero, **20 a 250** |
| 3 | Crepitantes | `crepitantes` | botones Sí / No |
| 4 | Murmullo disminuido | `murmullo_disminuido` | botones Sí / No |

Fuera de rango o no numérico: el bot lo dice, **no avanza de paso** y vuelve a
preguntar. Un `38,2` y un `38.2` son el mismo valor; se normaliza a punto antes
de guardar.

### 4.5. Por qué no hay LLM

Con D4 el paciente contesta con botones y lo que entra al cálculo es exactamente
lo que tocó, así que la "normalización de español coloquial" del documento
maestro deja de hacer falta. La consecuencia buena: **ningún dato de paciente
sale hacia un tercero**.

**Deuda:** anotarlo en el "Registro de cambios" del documento maestro de la
Semana 1 (§18).

---

## 5. Datos

### 5.1. Esquema

```sql
-- Estado efímero del PACIENTE mientras contesta.
CREATE TABLE sesiones_paciente (
  chat_id        bigint PRIMARY KEY,
  paso           smallint    NOT NULL DEFAULT 0,
  consentido_en  timestamptz,                  -- null = aún no aceptó
  respuestas     jsonb       NOT NULL DEFAULT '{}',
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

-- Estado efímero del PROFESIONAL. Su conversación es más larga que la del
-- paciente (código + 4 signos + DICOM) y n8n no recuerda nada entre mensajes.
-- Sin esta tabla, dos consultas simultáneas pueden cruzar los signos de un
-- paciente con la radiografía de otro, y el mensaje resultante sería
-- sintácticamente perfecto.
CREATE TABLE sesiones_profesional (
  chat_id        bigint PRIMARY KEY,
  paso           smallint    NOT NULL DEFAULT 0,
  codigo         text,
  signos         jsonb       NOT NULL DEFAULT '{}',
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE cuestionarios (
  codigo        text PRIMARY KEY,
  respuestas    jsonb       NOT NULL,
  consentido_en timestamptz NOT NULL,
  creado_en     timestamptz NOT NULL DEFAULT now(),
  expira_en     timestamptz NOT NULL
);

CREATE TABLE profesionales (
  chat_id bigint PRIMARY KEY,
  nombre  text        NOT NULL,
  activo  boolean     NOT NULL DEFAULT true,
  alta_en timestamptz NOT NULL DEFAULT now(),
  baja_en timestamptz
);

-- El registro permanente. Fuente del dashboard y de la validación de H7.
CREATE TABLE consultas (
  id           bigserial PRIMARY KEY,
  codigo       text,
  chat_id      bigint,
  sintomas     jsonb,        -- COPIA (D12): cuestionarios se borra a los 7 días
  signos       jsonb,
  resultado    jsonb,        -- el structuredContent completo
  error        text,         -- el código, no el texto
  ms_extremo   integer,      -- latencia de extremo a extremo, para §16
  creado_en    timestamptz NOT NULL DEFAULT now()
);

-- Contador para la métrica "iniciados vs completados" del dashboard, que el
-- esquema anterior hacía imposible de calcular: las sesiones se borran.
CREATE TABLE cuestionarios_iniciados (
  dia     date PRIMARY KEY,
  cuantos integer NOT NULL DEFAULT 0
);

-- Contador del limite de 5/dia (§4.2). Tabla APARTE y no una columna de
-- `cuestionarios`: esa esta identificada por el codigo seudonimo, y meterle el
-- chat_id al lado ataria cada cuestionario a una cuenta de Telegram, que es lo
-- que el seudonimo existe para impedir. Aqui se sabe CUANTOS, no CUALES.
CREATE TABLE limite_paciente (
  chat_id bigint  NOT NULL,
  dia     date    NOT NULL,
  cuantos integer NOT NULL DEFAULT 0,
  PRIMARY KEY (chat_id, dia)
);
```

`consultas` guarda **también los rechazos**, con su código. Un sistema que solo
registra sus éxitos no se puede validar, y la tasa de rechazos es la señal de
salud operativa del §16.

`consultas.codigo` **no lleva clave foránea** a `cuestionarios`: esa tabla se
borra a los 7 días y la referencia rompería el registro permanente.

### 5.2. El código seudónimo

Seis caracteres del alfabeto `ABCDEFGHJKMNPQRSTUVWXYZ23456789` — **31
caracteres**, sin `0`, `O`, `1`, `I` ni `L`, porque se dicta en voz alta.
~887 millones de combinaciones.

Lo genera PostgreSQL con `gen_random_bytes` (extensión `pgcrypto`), no n8n: así
la generación y la comprobación de unicidad ocurren **en la misma transacción**.
Ante colisión, reintenta; a la tercera, falla con un error registrado.

**No es de un solo uso:** un profesional puede consultar dos veces —segunda
opinión, placa repetida— y bloquearlo estorbaría sin ganar seguridad, porque
adivinar un código no sirve si no se está además en la lista blanca. Cada uso
queda en `consultas`.

Un paciente puede tener **varios códigos vivos** si rellena el cuestionario más
de una vez (hasta el límite de §4.2). El profesional usa el que le dicten.

### 5.3. Esquema de los `jsonb`

Las claves y los valores permitidos son los de las tablas de §4.4. `resultado`
guarda el `structuredContent` completo del servidor, tal cual, sin recortar: sus
campos están en §10.2.

Una fila de `consultas` completa se ve así:

```json
{
  "sintomas": {"fiebre":"si","tos":"con_flema","dias_evolucion":"3_a_7",
               "disnea":"no","dolor_toracico":"si","asma":"no",
               "texto_libre":null},
  "signos":   {"temperatura_c":38.2,"frecuencia_cardiaca":104,
               "crepitantes":true,"murmullo_disminuido":false},
  "resultado":{"probabilidad_cruda":0.9764,"probabilidad_calibrada":0.8455,
               "razon_de_verosimilitud":19.238,"umbral":0.4258,
               "clasificacion":"opacidad_probable","edad_paciente":33,
               "modelo":"efficientnet_b0_320px","auc_validacion":0.8827,
               "milisegundos":143.0}
}
```

### 5.4. Retención, y dónde viven los datos de verdad

El primer borrador razonaba como si todo el dato clínico viviera en
`copiloto-bd`. **No es cierto**, y es el hallazgo más incómodo de la revisión:

> **n8n guarda los datos de ejecución de cada nodo**, incluidos el DICOM
> descargado, su base64 y las respuestas del cuestionario, en la base de datos
> de n8n **del cliente**.

Por eso, además de la retención de nuestras tablas:

- Los dos workflows se configuran con **`Save successful production executions:
  none`** y **`Save failed production executions: none`**, o con la retención
  mínima que n8n permita sin tocar la configuración global del cliente.
- Ningún nodo escribe el base64 en un campo que se persista.
- Si n8n no permitiera desactivarlo por workflow, se declara como deuda (§18) y
  se acuerda con el cliente (§17) antes de meter datos reales.

Retención de nuestras tablas:

| Tabla | Vive | Por qué |
| :--- | :--- | :--- |
| `sesiones_paciente` / `sesiones_profesional` | se borran al completar; las abandonadas, a las **24 h** | estado, no dato |
| `cuestionarios` | **7 días**, borrado real | ventana entre que se llena y se usa |
| `consultas` | mientras dure el proyecto | seudónimas; sin ellas no hay H7 ni dashboard |
| `profesionales` | mientras esté activo; al dar de baja se pone `baja_en` y el `nombre` se sustituye por `"(dado de baja)"` | es la única tabla con un dato personal directo de una persona real |
| `cuestionarios_iniciados` | agregado por día, sin datos personales | indefinido, no hay nada que proteger |
| `limite_paciente` | **2 días** | solo sirve para el límite del día; más tiempo es un rastro de quién usó el bot y cuándo. Dos días y no uno por el borde de la zona horaria |

**Zona horaria:** todo es `timestamptz`. `expira_en` es `creado_en + 7 días`.
Las agrupaciones por día del dashboard y el `cuestionarios_iniciados.dia` usan
**`America/Guayaquil`**, declarado explícitamente en las consultas, para que
"hoy" signifique lo mismo en el informe que en la cabeza de quien lo lee.

**Decisión pendiente, explícita:** qué pasa con `consultas` al cerrar el
proyecto. Se resuelve antes de H8 (§18).

El borrado lo ejecuta `🩺 Copiloto Triaje: Mantenimiento`, diario.

---

## 6. Flujo del paciente

1. `/start` → **consentimiento**: qué se guarda, cuánto tiempo, quién lo ve, y
   que **no es un diagnóstico; si le cuesta respirar, que acuda a urgencias**.
   Botones **Acepto** / **No acepto**.
   - *No acepto* → mensaje de despedida y **no se guarda nada**.
   - *Acepto* → se crea la sesión con `consentido_en`, y se incrementa
     `cuestionarios_iniciados`.
2. Las 7 preguntas de §4.4, una por mensaje.
3. Cada respuesta actualiza `sesiones_paciente`, poniendo `actualizado_en = now()`.
4. Al completar: se genera el código, nace la fila de `cuestionarios` con su
   `consentido_en`, se borra la sesión, y se responde:

   > **Su código es `K7FM2P`.**
   > Enséñeselo a su médico junto con su radiografía. Caduca en 7 días.

5. Fin.

`/reiniciar` borra la sesión y vuelve al paso 1. Un mensaje que no sea un botón
esperado (salvo en la pregunta 7) se contesta repitiendo la pregunta actual.

---

## 7. Flujo del profesional

**En cada mensaje entrante, antes de nada:** se comprueba el `secret_token`
(§4.2) y luego el `chat_id` contra `profesionales` con `activo = true`. **No es
un paso del flujo, es una condición de entrada**: un profesional dado de baja a
mitad de conversación deja de pasar en el mensaje siguiente.

1. Saludo → pide el código.
2. Busca en `cuestionarios` comprobando `expira_en`. Guarda `codigo` en la
   sesión.
3. Muestra los síntomas referidos, con "asma: no sabe" si aplica.
4. Las 4 preguntas de signos de §4.4, guardando cada una en la sesión.
5. Pide la radiografía, advirtiendo que debe ir **como archivo**.
6. Descarga de Telegram, base64, llamada al copiloto (§10).
7. Responde según §8.
8. Escribe la fila de `consultas` —con la **copia** de los síntomas (D12)— y
   borra la sesión.

`/reiniciar` borra la sesión y vuelve al paso 1.

---

## 8. Cómo se presenta el resultado

**Esta sección existe porque el primer borrador ponía la etiqueta y la razón de
verosimilitud en el mismo renglón, y se contradicen.**

La etiqueta sale de `probabilidad_cruda >= 0,4258`, un punto elegido sobre la
ROC de las puntuaciones crudas para conseguir recall 0,88 con especificidad
0,70. La probabilidad calibrada y la RV salen de la curva isotónica, que es otra
escala. En `cruda ∈ [0,4258 ; 0,5786]` **la etiqueta es positiva y la RV es
menor que 1**: el cribado marca la placa, y la evidencia bayesiana *baja* las
probabilidades a favor de neumonía. Las dos cosas son correctas y miden cosas
distintas.

**Regla:** nunca van en el mismo renglón. El mensaje tiene **tres bloques
rotulados**:

> **Cribado** — opacidad probable
> *(puntuación 0,98 ≥ umbral 0,4258; punto orientado a detectar, sens. 0,88 /
> esp. 0,70)*
>
> **Evidencia de la imagen** — multiplica por **19,2** las probabilidades a
> favor de neumonía *(probabilidad calibrada 0,85)*
>
> **Referido por el paciente** — fiebre sí, tos con flema, 3 a 7 días, sin asma
> **Explorado** — 38,2 °C, 104 lpm, crepitantes sí, murmullo normal
>
> *La combinación de imagen y clínica llega en la siguiente entrega. Esto no es
> un diagnóstico.*

**Cuando la etiqueta es positiva y la RV es menor que 1**, el bloque de
evidencia lo dice de forma explícita:

> **Evidencia de la imagen** — **reduce** a **0,59×** las probabilidades a favor
> de neumonía *(probabilidad calibrada 0,14)*.
> ⚠️ El cribado marca esta placa por estar orientado a detectar, pero la imagen
> en sí no apoya el diagnóstico. Decide la clínica.

**Cuando la etiqueta es negativa** se usan los mismos tres bloques con
"sin opacidad probable" y la RV correspondiente. La plantilla es una sola; solo
cambian los valores y el aviso.

**Formato:** los números se muestran con la precisión de arriba —probabilidades
con dos decimales, RV con uno o dos—, y el mensaje se manda con `parse_mode:
MarkdownV2` **escapando** todo lo que venga de datos, o con `parse_mode` vacío
si el texto libre del paciente está presente (§4.4).

---

## 9. Errores

| Situación | Código registrado | Qué dice el bot | Estado después |
| :--- | :--- | :--- | :--- |
| Envía **foto** en vez de archivo | `envio_como_foto` | "Telegram recomprime las fotos y destruye el DICOM. Envíela como archivo." | **se queda en el paso 5**, esperando el archivo |
| No es un DICOM legible | `dicom_invalido` | relata el detalle del servidor | se queda en el paso 5 |
| **Edad fuera de 18-100** | `fuera_de_alcance` | el detalle del servidor, **sin ninguna cifra de probabilidad** | **termina**: se registra y se borra la sesión |
| La cabecera no declara edad | `edad_desconocida` | el detalle del servidor, **sin ninguna cifra** | termina |
| Base64 mal formado | `base64_invalido` | "No pude leer el archivo. Vuelva a enviarlo." | se queda en el paso 5 |
| Más de 5 MB (respuesta MCP) | `payload_excesivo` | "El archivo supera los 5 MB." | se queda en el paso 5 |
| **HTTP 413** del transporte (§10.4) | `payload_excesivo_transporte` | mismo mensaje | se queda en el paso 5 |
| Código inexistente o caducado | `codigo_invalido` | "Ese código no existe o caducó. Pida al paciente que repita el cuestionario." | se queda en el paso 2 |
| Fichero de Telegram > 20 MB | `fichero_no_descargable` | "Telegram no me deja descargar archivos de más de 20 MB." | se queda en el paso 5 |
| Timeout o error de red | `copiloto_no_responde` | "El servicio de imagen no está disponible. Inténtelo en unos minutos." | se queda en el paso 5 |
| `isError` con un código desconocido | `error_no_reconocido` | "El servicio devolvió un error que no sé interpretar. Se ha registrado." | termina, y el texto íntegro va a `consultas.error` |

**Ninguna rama de error emite una cifra de probabilidad.** El rechazo por edad
es una **decisión clínica del sistema**, no un fallo técnico, y debe llegar como
tal: si se filtrara un número junto al rechazo, alguien lo usaría.

El mensaje que se muestra sale de **relatar el detalle del servidor** tras
quitarle el prefijo del SDK y el código (§10.3). No se reconstruye la frase ni
se interpola la edad por nuestra cuenta: la edad no viene en ningún campo
estructurado cuando hay error, solo dentro del texto.

---

## 10. Integración con el copiloto

**Verificado contra el contenedor real el 24-sep-2026.**

Un nodo HTTP Request, sin AI Agent y sin nodo MCP Client Tool: ese nodo exige un
AI Agent, y obligaría al modelo a **emitir** ~175 KB de base64 literal.

### 10.1. Petición

```
POST http://copiloto-mcp:8000/mcp
Content-Type: application/json
Accept: application/json, text/event-stream

{"jsonrpc":"2.0","id":1,"method":"tools/call",
 "params":{"name":"clasificar_radiografia",
           "arguments":{"dicom_base64":"<base64 por expresión de n8n>"}}}
```

No hace falta el saludo `initialize`: el servidor es `stateless_http=True`.
Comprobado. El base64 **puede ir envuelto** (LF o CRLF): el servidor quita los
espacios. Comprobado.

En el nodo HTTP Request: **Response Format = `Text`**, no `JSON`, porque la
respuesta es SSE y un parseo automático fallaría. **Timeout 30 000 ms.**
**Un solo reintento** ante error de red, nunca ante una respuesta con `isError`.
La fila de `consultas` se escribe **una sola vez**, con el desenlace final, para
que el dashboard no cuente dos veces la misma consulta.

### 10.2. Respuesta correcta

Llega como evento SSE; el JSON está en la línea `data:`, no suelto:

```
event: message
data: {"jsonrpc":"2.0","id":1,"result":{"content":[{"type":"text","text":"<json>"}],"structuredContent":{...},"isError":false}}
```

Se lee de `result.structuredContent`. Campos: `probabilidad_cruda`,
`probabilidad_calibrada`, `razon_de_verosimilitud`, `umbral`, `clasificacion`,
`edad_paciente`, `modelo`, `auc_validacion`, `milisegundos`.

Si `structuredContent` no viniera, se cae a parsear `result.content[0].text`,
que lleva el mismo JSON como texto.

### 10.3. Errores del servidor

`result.isError` es `true` y el texto está en `result.content[0].text` con el
prefijo que antepone el SDK:

```
Error executing tool clasificar_radiografia: fuera_de_alcance: El paciente tiene 12 anios y el modelo solo es valido entre 18 y 100.
```

El código es el **segundo** campo. Se busca **dentro** del texto; **NO** se
parte por el primer `:`, que devolvería `Error executing tool
clasificar_radiografia`. El detalle que se muestra al profesional es lo que
queda tras el segundo `:`.

### 10.4. Los dos límites de tamaño, que no son el mismo

| Tamaño del DICOM | Qué pasa |
| ---: | :--- |
| hasta 5 MiB | funciona |
| 5 MiB a ~5,3 MiB | el **tool** responde `payload_excesivo` dentro de un SSE normal |
| más de ~5,3 MiB | el **transporte** corta antes: **HTTP 413**, sin SSE y sin JSON-RPC |
| más de 20 MB | Telegram no deja ni descargarlo |

El flujo debe tratar **las tres** ramas. El primer borrador solo contemplaba la
primera, y una respuesta 413 habría caído en el camino de éxito y reventado al
buscar `data:`.

**Cualquier respuesta HTTP que no sea 200 con un cuerpo SSE** se trata como
error, se registra con su código de §9 y no se intenta parsear.

En la práctica los DICOM de RSNA tienen 131 KB de mediana, así que nada de esto
debería activarse: está aquí para que, si se activa, el bot diga algo cierto.

### 10.5. La razón de verosimilitud viene acotada

A `[0,0163 ; 77,32]` por diseño de SP2. La imagen puede mover la probabilidad
previa pero no anularla ni volverla certeza. **Esas cotas dependen del
calibrador desplegado**: si se reentrena el modelo, cambian, y §8 y §16 hay que
revisarlos. No son constantes universales.

---

## 11. Alta y baja de profesionales

El primer borrador definía la tabla y la comprobación pero **no cómo entra una
fila**, que es lo único que hace que D6 exista.

**Alta:** manual, por el responsable del proyecto, con una sentencia SQL
ejecutada contra `copiloto-bd`. Para un piloto con un grupo conocido es lo más
simple que de verdad protege: no hay flujo de registro que atacar.

```sql
INSERT INTO profesionales (chat_id, nombre) VALUES (123456789, 'Dra. Apellido');
```

El `chat_id` se obtiene pidiéndole al clínico que escriba `/start` al bot: aunque
no esté autorizado, el flujo **registra el intento** (`consultas.error =
'no_autorizado'` con su `chat_id`) y de ahí se lee.

**Baja:** `UPDATE profesionales SET activo = false, baja_en = now(), nombre =
'(dado de baja)' WHERE chat_id = ...`. Surte efecto en el mensaje siguiente,
porque la comprobación es por mensaje (§7).

---

## 12. Secretos

Las credenciales existen ya en n8n, creadas el 24-sep-2026, y **ninguna la usa
ningún workflow** — comprobado con `usageCount: 0`, que es lo que garantiza que
no le robamos el webhook a un bot del cliente (D9):

| Rol | Credencial en n8n | id |
| :--- | :--- | :--- |
| Paciente | `[retirado]` | `[retirado]` |
| Profesional | `[retirado]` | `[retirado]` |
| Pruebas | `[retirado]` | `[retirado]` |

Las del cliente que **no se tocan**: `[retirado]` (5 workflows) y
`Telegram account` (2). Existe además una credencial `[retirado]` sin uso,
anterior a `[retirado]` y hoy redundante.

| Secreto | Dónde vive | Si se filtra |
| :--- | :--- | :--- |
| Token del bot del paciente | credencial `[retirado]` | revocar en BotFather, crear otro, actualizar la credencial |
| Token del bot del profesional | credencial `[retirado]` | igual |
| `secret_token` del webhook (§4.2) | credencial de n8n | rotarlo y volver a llamar a `setWebhook` |
| Contraseña de `copiloto-bd` | variable de entorno del compose, en un `.env` del VPS | rotar y recrear el contenedor |
| Contraseña del dashboard | credencial de n8n | rotar |

**Ninguno va al repositorio.** El `.env` del VPS está en `.gitignore`. El
`docker-compose.yml` versionado referencia variables, nunca valores.

---

## 13. Pruebas

D7 pone la lógica en workflows, no en código con pytest. Esto es lo que lo
compensa: n8n 2.35.4 soporta el marco de evaluaciones completo, y **un Telegram
Trigger es un webhook** al que se le puede hacer POST de un `update` fabricado
para ejecutar el flujo de verdad y **afirmar sobre la base de datos**.

### 13.1. Los casos salen del conjunto de prueba real, no de la imaginación

Los casos límite **no se fabrican: están en los datos**. El conjunto de prueba
de RSNA trae 3 811 radiografías reales con su edad y su etiqueta, y entre ellas
hay 1 276 menores de edad, 5 pacientes con edades imposibles (148-155 años) y
379 placas en la banda contradictoria de §8. Probar con eso encuentra lo que
un caso sintético no: las 379 aparecieron **midiendo**, no razonando.

**Nivel 1 — el conjunto entero contra `copiloto-mcp`.** Sin pasar por los bots.
Caracteriza las distribuciones que condicionan el diseño: cuántas caen en la
banda contradictoria, cuántas se rechazan por edad, qué latencias salen. Es lo
que produjo las tres filas nuevas de §3. Barato, repetible y se vuelve a correr
entero cada vez que se reentrena el modelo.

**Nivel 2 — un subconjunto estratificado, por los bots de verdad.** Telegram
limita a ~1 mensaje por segundo y chat, así que replicar 3 811 conversaciones
llevaría horas: se eligen unos **60 casos**, a propósito, uno o varios por rama:

| Perfil | De dónde sale del conjunto de prueba |
| :--- | :--- |
| Positiva clara | `cruda > 0,9` |
| Negativa clara | `cruda < 0,1` |
| **Banda contradictoria** | de las 379 medidas |
| **Menor de edad** | de los 1 276 menores reales |
| Edad imposible o ausente | los 5 de 148-155 años |
| Fichero corrupto | truncando un DICOM real |
| Fichero enorme | rellenando un DICOM real por encima de 5 MiB |

El arnés (`pruebas/reproducir_casos.py`) crea la conversación del paciente,
obtiene el código, conduce la del profesional con los signos y la placa real, y
**guarda cada mensaje final**. La salida es un corpus revisable: se lee y se ve
si lo que el bot dijo tiene sentido clínico, que es algo que ninguna aserción
automática puede juzgar.

**Los síntomas de esos casos son inventados, y pasa nada — aquí.** Lo que se
está midiendo es la fontanería: que el estado no se cruce, que los errores digan
lo correcto, que §8 se presente bien. Los síntomas no intervienen en eso.
**Para validar la combinación clínica de H6 y H7, en cambio, no sirven** (§19).

| Superficie | Cómo se prueba |
| :--- | :--- |
| Máquina de estados del paciente | updates sintéticos → aserción sobre `sesiones_paciente` y `cuestionarios` |
| Consentimiento | *No acepto* → **cero filas** en cualquier tabla |
| Máquina de estados del profesional | igual, sobre `sesiones_profesional` |
| **Dos profesionales a la vez** | dos conversaciones solapadas → los signos **no se cruzan** |
| `secret_token` | update sin la cabecera → se descarta sin tocar nada |
| Lista blanca | `chat_id` no autorizado → no llega al copiloto; y dar de baja a mitad de conversación corta en el mensaje siguiente |
| Las 11 ramas de §9 | una por rama → aserción sobre `consultas.error` **y sobre la ausencia de cifras en el mensaje** |
| §8, banda contradictoria | un DICOM con `cruda ∈ [0,4258 ; 0,5786]` → el mensaje lleva el aviso y no pega etiqueta y RV |
| Contrato con el copiloto (§10) | pytest contra el contenedor: SSE, claves, prefijo del error, los tres límites |
| SQL de borrado, código y contadores | pytest contra una PostgreSQL efímera |
| Que el flujo del paciente no toque el copiloto | **revisión del JSON exportado**: ninguna URL del copiloto |
| Que los botones se vean bien | manual, con guion escrito |

Las pruebas son **de integración contra un n8n vivo**: más lentas, con un bot y
un `chat_id` de prueba, y mandan mensajes de Telegram de verdad.

**Contra qué instancia.** Las pruebas corren contra los **mismos workflows** del
n8n del cliente pero con el **bot de prueba** y una base de datos de prueba
(`copiloto-bd`, esquema `pruebas`). No se crea una segunda instancia de n8n. Las
ejecuciones de prueba quedan en el historial del cliente: se acuerda con él
(§17) y se limita el volumen.

**Exportación:** los dos workflows y el de mantenimiento se exportan a `n8n/` de
este repo con `n8n_get_workflow` por su ID, **uno a uno y solo los nuestros**,
en cada cambio. Nunca un volcado completo de la instancia.

---

## 14. Reglas duras

1. **No se modifica ningún workflow existente** del cliente. Los nuestros son
   nuevos y llevan el prefijo `🩺 Copiloto Triaje:`, **los tres**.
2. **No se reutiliza ninguna credencial de Telegram existente** (D9).
3. **No se crea ni se borra** `[retirado]_[retirado]_network`, ni se tocan sus otros
   contenedores.
4. **No se toca `copiloto-mcp`.** Si SP3 necesitara algo del servidor, se para y
   se decide: es otro sub-proyecto con su propia revisión.
5. `copiloto-bd` **no publica puertos**, y su contraseña no es la de ninguna otra
   base de datos de la máquina. *No publicar puertos no es aislamiento*: los
   otros 24 contenedores comparten la red y podrían alcanzarla por nombre. La
   contraseña es lo que protege.
6. **Ningún dato de paciente sale del VPS** hacia un tercero. Matiz honesto: los
   datos **sí pasan por n8n**, que es del cliente y vive en la misma máquina
   (§5.4); y el paciente los escribe **en Telegram**, que es un servicio externo
   fuera de nuestro control. La regla es sobre lo que *nosotros* enviamos.
7. **No se cambia la configuración global de n8n**, solo la de nuestros
   workflows.

---

## 15. Dashboard (después de H5)

Un workflow: **Webhook con autenticación básica** → consultas SQL → HTML.

| Bloque | De dónde sale |
| :--- | :--- |
| Consultas por día, últimos 30 | `consultas`, agrupado en `America/Guayaquil` |
| Iniciados vs completados | `cuestionarios_iniciados` contra `consultas` |
| Distribución de clasificaciones | `resultado->>'clasificacion'` |
| **Casos en la banda contradictoria** | `resultado` con `cruda` en `[0,4258 ; 0,5786]` — cuántas veces el cribado y la evidencia discreparon |
| Rechazos por código | `consultas.error` |
| Latencia p50/p95 | `ms_extremo` (extremo a extremo) y `resultado->>'milisegundos'` (solo el modelo) |
| Consultas por profesional | `consultas.chat_id` contra `profesionales` |

Solo lo ven las dos personas del equipo, con contraseña. **Ningún código
seudónimo, ninguna respuesta individual y ningún texto libre aparece**: si la
contraseña se aflojara, lo que se filtra son recuentos.

---

## 16. Observabilidad

Un sistema que se cae en silencio no sirve. El workflow de mantenimiento, además
de limpiar, comprueba a diario y **avisa por Telegram al equipo** si:

- `copiloto-mcp` no responde a `/salud`;
- `copiloto-bd` no acepta conexiones;
- alguno de los tres workflows quedó **desactivado**;
- la tasa de `dicom_invalido` de los últimos 7 días supera el 20 % (algo pasa
  con cómo mandan las placas);
- hay cuestionarios caducados sin borrar (la limpieza falló);
- **el webhook de alguno de los dos bots dejó de apuntar a donde debe.**

La última merece su explicación, porque es el precio de una decisión y no un
descuido. Los flujos usan un nodo **Webhook** y no un **Telegram Trigger**, y
esa elección está medida: el Telegram Trigger (v1.5) **no expone el
`secret_token` ni la cabecera de la petición**, así que con él la comprobación
del §4.2 es imposible, y su URL —el `webhookId`, un UUID— **se commitea al
repositorio dentro del JSON exportado**, con lo que el único secreto del
sistema acabaría versionado. Con Webhook + Header Auth el secreto vive en una
credencial y no sale de n8n.

El coste de esa elección es que el registro en Telegram se hace **a mano una
vez**, y por tanto puede desincronizarse en silencio: si alguien reactiva el
flujo o cambia la ruta, Telegram sigue apuntando al sitio viejo y el bot deja
de responder sin que salte nada. El Telegram Trigger da esa garantía gratis;
aquí se compra con un nodo.

Por eso el mantenimiento llama a diario a `getWebhookInfo` de los dos bots y
avisa si la `url` no es la esperada o si `last_error_message` trae algo.

---

## 17. Acuerdo con el cliente

SP3 instala en la máquina de un tercero un contenedor con estado, una base de
datos, tres workflows y **dos webhooks públicos**, y le mete tráfico de internet.
Antes de meter datos reales hay que acordar con el cliente, como mínimo: que se
añade un contenedor y cuánto consume; que entrarán ejecuciones nuevas en su
historial de n8n; que los webhooks pasan por su nginx; y la retención de
ejecuciones de §5.4.

**Retirada:** `docker compose -p copiloto-mcp down`, borrar el volumen de
`copiloto-bd`, desactivar y archivar los tres workflows, borrar sus credenciales
y revocar los dos bots en BotFather. Escrito aquí para que exista antes de
necesitarlo.

---

## 18. Deuda declarada

| Deuda | Cuándo se salda |
| :--- | :--- |
| Anotar en el "Registro de cambios" de la Semana 1 que no hay LLM (§4.5) | al cerrar H5 |
| Decidir qué pasa con `consultas` al cerrar el proyecto | antes de H8 |
| H6 debe definir el tratamiento de `asma = no_se` (§4.4) | H6 |
| Si n8n no deja desactivar el guardado de ejecuciones por workflow (§5.4) | antes de datos reales |
| Las cotas de la RV de §10.5 son literales; cambian si se reentrena | al reentrenar |
| Revalidar con el clínico que el DICOM se obtiene del PACS | antes de H7 |

---

## 19. Riesgos abiertos

| Riesgo | Mitigación |
| :--- | :--- |
| Un update forjado se hace pasar por Telegram | `secret_token` obligatorio (§4.2) |
| Dos profesionales a la vez cruzan datos de pacientes | `sesiones_profesional` con `chat_id` como clave, y prueba dedicada (§13) |
| El cribado y la evidencia se contradicen y confunden | §8 lo hace explícito en el propio mensaje, y el dashboard lo cuenta |
| Las pruebas mandan mensajes reales de Telegram | bot y `chat_id` dedicados, nunca los de producción |
| Un despliegue del cliente reinicia n8n a mitad de conversación | el estado vive en PostgreSQL: se reanuda |
| El cuestionario resulta largo y los pacientes abandonan | `cuestionarios_iniciados` lo mide; acortar es barato |
| El paciente no llega nunca al bot | **no resuelto**: no hay plan de difusión. Es de producto, no técnico, y bloquea la validación de H7 |
| **No existen datos reales que emparejen imagen y clínica** | **No resuelto, y es el riesgo mayor del proyecto.** RSNA trae imagen, etiqueta, edad y sexo; **no trae síntomas ni hallazgos de exploración**. Los casos de §13.2 llevan síntomas inventados, y eso vale para probar el sistema pero **no para validar la combinación bayesiana**: si se inventan síntomas correlacionados con la etiqueta y luego se "valida" que Bayes funciona, se ha validado la invención, no el método. H6 puede implementarse y probarse; **H7 necesita datos clínicos reales emparejados o un piloto prospectivo**. Decidir cuál antes de H6, porque cambia lo que H7 puede afirmar |

---

## 20. Entregables

| Artefacto | Dónde |
| :--- | :--- |
| `n8n/copiloto-paciente.json` | este repo |
| `n8n/copiloto-profesional.json` | este repo |
| `n8n/copiloto-mantenimiento.json` | este repo |
| `servidor/docker-compose.yml` actualizado con `copiloto-bd` | este repo |
| `bd/esquema.sql` | este repo |
| `tests/test_contrato_mcp.py` y `tests/test_bd_sp3.py` | este repo |
| `pruebas/caracterizar_conjunto.py` — nivel 1 de §13.1 | este repo |
| `pruebas/reproducir_casos.py` — el arnés de nivel 2, y su corpus de salida | este repo |
| `docs/sp3-operacion.md` — alta de profesionales, guion manual, retirada | este repo |
| Registro del cambio en el documento maestro de la Semana 1 | `Proyecto Integrador/Semana 1/` |

---

## 21. Criterios de aceptación de H5

1. Un paciente que **no acepta** el consentimiento no deja **ninguna fila** en
   ninguna tabla.
2. Un paciente que acepta completa el cuestionario y recibe un código.
3. Un update **sin `secret_token` válido** se descarta sin tocar nada.
4. Un `chat_id` **no autorizado** recibe "no autorizado", **no** llega al
   copiloto, y queda registrado el intento.
5. Un profesional autorizado presenta el código, aporta los signos, envía un
   DICOM real de adulto y recibe los **tres bloques** de §8.
6. Un DICOM con `cruda` en la **banda contradictoria** produce el aviso explícito
   de §8.
7. Una placa de un paciente **menor de 18** produce el rechazo clínico
   explicado, **sin ninguna cifra**, y queda en `consultas.error`.
8. Una imagen enviada **como foto** produce la explicación, y la conversación
   **sigue esperando el archivo**.
9. **Dos profesionales conversando a la vez** no cruzan sus signos.
10. Los cuestionarios caducados desaparecen; `consultas` conserva la copia de
    los síntomas de los casos consultados.
11. Ningún workflow ni contenedor existente del cliente cambió de estado —
    comprobado con la foto de `docker ps` y la lista de workflows de antes y
    después, como se hizo en SP2.
12. Los tres workflows están exportados en `n8n/` de este repo.
