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
| D2 | **PostgreSQL propia** (`copiloto-bd`) | Los datos clínicos **se guardan** en infraestructura que controlamos. Las PostgreSQL del VPS son del cliente y no se tocan. Dónde *pasan* antes de guardarse es otra cosa, y no es esta: llegan por Telegram (§5.5) |
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

> **Corregido el 26-sep, a raíz de una evaluación externa.** D2 decía que «los
> datos clínicos quedan en infraestructura que controlamos», sin más. Es cierto
> del **almacenamiento** y falso del **recorrido**: los síntomas, los signos, el
> código seudónimo y la radiografía llegan por Telegram, o sea que pasan por
> infraestructura de un tercero antes de tocar `copiloto-bd`. Dicho sin acotar,
> D2 parece una decisión sobre privacidad de extremo a extremo, cuando lo que
> decide es de quién es la base de datos — que también importa, pero es otra
> cosa. El tramo de entrada se declara como riesgo aceptado en el §5.5.

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
| Un Telegram Trigger es un webhook público en `https://n8n.ejemplo.test/webhook/...` | §4.2 |
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
| `copiloto-bd` | PostgreSQL 16, en `<RED_N8N>`, sin puertos | sí |
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
`https://n8n.ejemplo.test/webhook/<id>`, alcanzable desde internet a través del
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

> **Corregido el 26-sep.** Este apartado decia que el bot del paciente arranca
> **solo** con `/start`, y el del profesional con `/start o cualquier mensaje`.
> La asimetria parecia justificada -al paciente hay que pedirle consentimiento,
> al profesional no- y era un defecto: **el boton *Iniciar* de Telegram solo
> aparece en un chat nuevo**. Quien ya uso el bot no lo vuelve a ver, y las dos
> rutas normales acaban sin sesion (`Completar` la borra al entregar el codigo,
> y la limpieza diaria borra las que pasan de 24 h). O sea que **todo paciente
> que repite consulta** llegaba sin sesion, escribia «hola» y no recibia nada.
> Ahora cualquier mensaje abre el consentimiento, que es exactamente lo que
> mandaba `/start`: no se guarda ni un dato sin aceptarlo, asi que el D11 sigue
> intacto.

```
PACIENTE                              PROFESIONAL
  /start o cualquier mensaje            /start o cualquier mensaje
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
  error        text,         -- `codigo: texto crudo del servidor`. NO es solo
                             -- el codigo: agrupar por el exige
                             -- `split_part(error, ':', 1)`. Se guarda el texto
                             -- crudo SIEMPRE porque en las caidas sin codigo es
                             -- lo unico diagnosticable que queda
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
- **Desde SP4**, con la placa viajan al copiloto los cinco datos de la regla de
  Heckerling —temperatura, pulso, crepitantes, murmullo y asma—, y nada más del
  cuestionario. Van dentro del mismo cuerpo JSON-RPC que el base64, por la misma
  red privada, y con la misma retención en `none`.
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

### 5.5. El canal de entrada: Telegram ve los datos antes que nosotros

> **Añadido el 26-sep, a raíz de una evaluación externa.** El evaluador señaló
> que el proyecto afirmaba, en varios sitios, que la radiografía «no sale de la
> red local», y que con Telegram de por medio eso no se sostiene. Tiene razón.
> Las afirmaciones están corregidas donde estaban —D2 de este spec, §1 y §10 del
> diseño de SP2, el §1 de `docs/sp2-despliegue.md` y dos sitios del README— y el
> riesgo se declara aquí, con nombre, en vez de quedar implícito en un compose
> sin `ports`.

**Los dos tramos, y solo el segundo es nuestro.** El error venía de tratarlos
como si fueran uno:

| Tramo | ¿Sale de la red del centro? | Quién lo ve, además de nosotros |
| :--- | :--- | :--- |
| paciente o profesional → **Telegram** → n8n | **Sí** | los servidores de Telegram: el DICOM completo, las respuestas del cuestionario y de los signos, el código seudónimo y la cuenta de quien los manda |
| n8n → `copiloto-mcp` | **No** | nadie: el contenedor no publica puertos y solo se alcanza por nombre de servicio dentro de la red de Docker del VPS (§10 aquí, §1 del diseño de SP2) |

**Qué expone el primer tramo.** Tres cosas, y conviene nombrarlas por separado
porque no pesan lo mismo:

- **El DICOM entero, con su cabecera.** Las placas de RSNA vienen anonimizadas;
  una placa real sacada de un PACS **no tiene por qué venirlo**, y puede traer
  nombre, número de historia y fecha de estudio. Eso es más dato personal del que
  guarda `consultas`, y el bot no lo mira: lo reenvía tal cual al copiloto.
- **Las respuestas clínicas**, que viajan como `callback_data` y texto de
  mensaje: los siete síntomas, los cuatro signos y el código seudónimo.
- **Quién habla con el bot y cuándo.** Es justo el dato que el seudónimo del §5.2
  y la tabla aparte del §4.2 existen para no tener en nuestras tablas. Telegram
  sí lo tiene, atado a una cuenta con número de teléfono.

**Qué protege el cifrado, y qué no.** El tramo va cifrado en tránsito: HTTPS
contra `api.telegram.org` y HTTPS hasta el webhook de n8n. Eso protege de quien
escuche el cable; **no protege de Telegram**. El fichero se queda en su
almacenamiento mientras exista para el bot —es de donde lo descarga `getFile`—,
su borrado no lo controlamos y no lo podemos comprobar. Y los chats con un bot
**no** llevan cifrado de extremo a extremo: en Telegram eso son los «chats
secretos», que un bot no puede usar. Decir «va cifrado» y quedarse ahí sería el
mismo error de antes escrito de otra manera.

**Por qué se aceptó.** Telegram era la vía de entrega elegida del proyecto,
antes de este diseño: es lo que el profesional ya tiene instalado, y lo que
permite un piloto sin pedirle al centro que despliegue nada. La alternativa que
elimina el riesgo es un canal propio, y un canal propio hay que instalarlo,
publicarlo y mantenerlo dentro de la red del centro — en un piloto de una
maestría, con dos integrantes y un VPS prestado, nadie lo va a instalar. Cambiar
el canal ahora costaría el hito y todavía no protegería a nadie: en H5 solo
circulan placas de RSNA y síntomas fabricados.

**Qué lo acota hoy.** Cuatro cosas, y ninguna lo elimina:

1. **Lo que circula en H5 no es de pacientes reales.** Las placas son de RSNA y
   los síntomas de §13.1 son inventados. El riesgo se vuelve real el día que
   entre la primera placa de un paciente, y ese día es H7.
2. **El paciente nunca manda la imagen**, solo botones. El DICOM lo manda el
   profesional, que está en una lista blanca de personas identificadas (§4.2, D6).
3. **Por nuestra parte, lo que va por Telegram no lleva identidad del paciente**:
   el único identificador que se cruza es el código seudónimo del §5.2. Lo que sí
   puede llevarla es la cabecera del DICOM, y eso depende del PACS del centro, no
   de nosotros — es la otra cara de la deuda del §18 sobre revalidar de dónde
   sale la placa.
4. **Nada de ese tramo se queda en nuestras tablas, ni en las ejecuciones de n8n
   si el §5.4 se cumple.** Pero el §5.4 acota *nuestra* retención: no toca la de
   Telegram, que es la que este apartado declara.

**Qué haría falta para eliminarlo.** Sustituir Telegram por un canal que no salga
de la red del centro. Tres formas, de menos a más trabajo:

| Canal local | Qué implica |
| :--- | :--- |
| **Carga web propia**: una página servida por nosotros, autenticada, donde el profesional sube el DICOM contra el mismo `POST /inferir` que ya existe (§10 del diseño de SP2) | la más corta, porque la puerta REST está hecha y probada; faltan sesión, TLS y un sitio donde publicarla. Pierde la conversación por botones: el cuestionario del paciente habría que rehacerlo |
| **App o cliente instalado** en el equipo del centro | quita el navegador de la ecuación y permite leer del PACS sin pasos manuales; es un proyecto aparte, no una variante de este |
| **Servidor de ficheros dentro de la red del centro** —carpeta vigilada o un nodo DICOM— que n8n lea desde dentro | es lo que un hospital querría de verdad, y lo que un piloto no está en posición de pedir |

Con cualquiera de los tres, «la radiografía no sale de la red del centro» pasa a
ser cierta del recorrido completo. **Hasta entonces no se escribe**: ni en este
spec, ni en el README, ni en la presentación del hito.

**Lo que hay que decirle a quien consiente.** El consentimiento de D11 enumera
qué se guarda, cuánto tiempo y quién lo ve (§6), y hoy no nombra a Telegram. Si
el dato pasa por un tercero, el consentimiento tiene que decirlo, o D11 se queda
corto justo en lo que un comité va a preguntar. El texto exacto no se inventa
aquí: queda en la deuda del §18, junto al acuerdo con el cliente del §17, y se
revisa antes de que entre el primer dato real.

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
rotulados**.

**Estos dos ejemplos son literales**, copiados de
`pruebas/corpus/01-positiva_clara/` y `02-negativa_clara/`: es exactamente lo
que `Desenlace` emite. Van en bloque de código y no citados con negritas porque
el mensaje **no lleva formato** —ver «Formato», al final de la sección—: los
rótulos se reconocen por ir en mayúsculas y con raya, y eso es lo único que el
texto del paciente no puede imitar sin que se note.

Positiva clara (placa `0022073f…`, cruda 0,9802):

```
CRIBADO — opacidad probable
(puntuación 0,9802 ≥ umbral 0,4258; punto orientado a detectar, sens. 0,88 / esp. 0,70)

EVIDENCIA DE LA IMAGEN — multiplica por 30,3 las probabilidades a favor de neumonía (probabilidad calibrada 0,90)

REFERIDO POR EL PACIENTE — fiebre sí, tos con flema, 3 a 7 días, sin falta de aire, dolor torácico al respirar, asma: no sabe
EXPLORADO — 38,2 °C, 104 lpm, crepitantes sí, murmullo normal

La combinación de imagen y clínica llega en la siguiente entrega. Esto no es un diagnóstico.
```

Negativa clara (placa `0022995a…`, cruda 0,0047). Lleva **una línea más** que la
positiva, el aviso del apartado siguiente:

```
CRIBADO — sin opacidad probable
(puntuación 0,0047 < umbral 0,4258; punto orientado a detectar, sens. 0,88 / esp. 0,70)

EVIDENCIA DE LA IMAGEN — reduce a 0,02× las probabilidades a favor de neumonía (probabilidad calibrada < 0,01)
⚠️ Un resultado negativo no descarta neumonía. Decide usted.

REFERIDO POR EL PACIENTE — fiebre sí, tos con flema, 3 a 7 días, sin falta de aire, dolor torácico al respirar, asma: no sabe
EXPLORADO — 38,2 °C, 104 lpm, crepitantes sí, murmullo normal

La combinación de imagen y clínica llega en la siguiente entrega. Esto no es un diagnóstico.
```

**El ejemplo que había aquí antes no era el mensaje que sale, y cada diferencia
manda a un sitio distinto.** Ponía «puntuación 0,98»: la puntuación cruda va con
**cuatro** decimales, porque no es una probabilidad —es justo lo que esta
sección existe para separar— y con dos al lado de un umbral de cuatro salen
desigualdades visiblemente falsas, «puntuación 0,43 < umbral 0,4258» en 3 de las
3 811 placas de prueba. Enseñaba cuatro síntomas de los seis, y el bloque lleva
**los seis siempre**, en el orden del §4.4: un síntoma que falta se lee como un
síntoma que el paciente no tiene. Y ponía los rótulos en minúscula y negrita,
cuando van en **mayúsculas y sin negrita** — que tampoco es estilo, es lo que
los hace reconocibles en un mensaje sin formato.

La probabilidad calibrada tampoco se imprime con dos decimales a secas: el
calibrador acota su salida a los extremos sostenidos de la curva (0,0046 y
0,9565), y con dos decimales 344 de las 3 811 placas de prueba se presentarían
como «probabilidad calibrada 0,00» — certeza de ausencia, que es exactamente lo
que esa cota existe para no fabricar. Por eso el ejemplo negativo dice
**`< 0,01`** y no `0,00`.

**Cuando la etiqueta es positiva y la RV es menor que 1**, el bloque de
evidencia lo dice de forma explícita:

```
EVIDENCIA DE LA IMAGEN — reduce a 0,87× las probabilidades a favor de neumonía (probabilidad calibrada 0,20)
⚠️ El cribado marca esta placa por estar orientado a detectar, pero la imagen en sí no apoya el diagnóstico. Decide la clínica.
```

(Literal, de `pruebas/corpus/03-banda_contradictoria/`, placa `03cf9ba9…`, cruda
0,5649.)

**Desde SP4 (H6)**, entre `EXPLORADO` y el descargo va un cuarto bloque,
`COMBINADO — …` (o `SIN COMBINAR — …` cuando faltan datos), y el descargo se
queda en «Esto no es un diagnóstico.»: la frase «la combinación llega en la
siguiente entrega» ya no sale. Los ejemplos de arriba son los de SP3 tal como
el corpus los registró; el formato del bloque nuevo está en el §8 del spec de
SP4.

### El aviso es asimétrico a propósito

El resultado **negativo** lleva una línea que el positivo no lleva:

```
⚠️ Un resultado negativo no descarta neumonía. Decide usted.
```

**Lleva ⚠️, igual que el del positivo contradictorio, y eso no es adorno.** Sin
el símbolo los dos avisos quedaban al revés: el del positivo contradictorio
-donde equivocarse manda a alguien sano a una prueba de más- se marcaba, y el
del negativo -donde equivocarse manda a casa a alguien con neumonía- no. El
aviso más importante era el menos visible. O lo llevan los dos o no lo lleva
ninguno.

La asimetría de que el negativo lleve aviso y el positivo concordante no, parece
un descuido y no lo es. **Marcar de más y marcar de menos
no hacen el mismo daño.** Si el cribado marca una placa sana, el profesional la
mira, no ve nada y sigue: cuesta tiempo. Si el cribado **no** marca una
neumonía, puede cerrar el estudio ahí — y ese es el daño de verdad. El aviso va
donde está el daño.

Salió de leer el corpus de §13.1, no de razonar: hay un caso real —mujer de 28
años, RSNA anotó `Lung Opacity`— donde el cribado y la evidencia **coinciden y
los dos se equivocan**. El clínico lee «sin opacidad probable» y «reduce a
0,04× las probabilidades», y leído solo, tranquiliza. Ningún aviso automático
puede existir ahí: el sistema no tiene forma de saber que está fallando. Lo
único honesto es decir que un negativo no descarta.

**Y la línea no lleva cifra, deliberadamente.** Las que se podrían poner son
ciertas y engañosas a la vez:

| La pregunta | La cifra |
| :--- | ---: |
| De los que tienen neumonía, ¿a cuántos se les escapa? | 1 de cada 8,4 |
| El bot dice negativo, ¿qué probabilidad hay de que la tenga? | 1 de cada 22 |
| El bot dice positivo, ¿cuántos la tienen? | menos de la mitad |

Las tres suponen una población con la prevalencia del conjunto de validación
(22,15 %), y en una consulta real es otra. Un número que parece preciso y no lo
es sería el mismo error que el §8 existe para evitar.

**Por eso el positivo no lleva nada.** El «menos de la mitad» describe lo que
pasaría si alguien aplicara la **etiqueta** a ciegas a esa población, y nadie
hace eso: el profesional ya tiene una sospecha antes de mirar la placa. Lo que
el sistema entrega de verdad es la razón de verosimilitud, y con ella los
números son otros — una placa clara (RV 19,2) sobre un paciente que el médico
sospecha al 50 % sale al **95 %**. Leer «más de la mitad se equivocan» junto a
ese resultado le restaría crédito a algo que lo merece.

Eso es justo lo que H6 va a formalizar: la RV multiplica el previo del
**paciente concreto**, no la prevalencia de un dataset.

**Cuando la etiqueta es negativa** se usan los mismos tres bloques con
"sin opacidad probable" y la RV correspondiente. La plantilla es una sola; solo
cambian los valores y el aviso.

### El informe no contiene ni un carácter que haya escrito el paciente

Esta regla nació de un fallo real y de dos intentos de arreglarlo que no
bastaron. Merece la pena contar el camino, porque la conclusión no es
evidente.

El texto libre de la pregunta 7 se mostraba dentro del informe. Con 240
caracteres, un paciente conseguía que sobre una placa de puntuación **0,0047**
el clínico recibiera **dos** bloques `CRIBADO` y **dos** `EVIDENCIA`,
tipográficamente idénticos, y que el falso —«opacidad probable, multiplica por
77,3»— fuera el que quedaba pegado al descargo: el último que se lee.

El primer arreglo quitaba al dato los saltos de línea y la raya `—` que separa
los rótulos, para que `RÓTULO — ` solo lo pudiera producir el sistema. Se
rodeó por tres vías: **`U+2015 HORIZONTAL BAR`**, que se ve idéntica y no
estaba en la lista; **`U+0085 NEXT LINE`**, el único espacio Unicode que el
`\s` de JavaScript no cubre y que UAX #14 clasifica como salto obligatorio; y
—la que zanja el asunto— **447 caracteres sin ningún carácter de control**,
que al envolverse la burbuja hacían que una fila *renderizada* empezara por un
rótulo falso en 3 de 7 anchos de pantalla.

Esa tercera no la arregla ningún filtro: **el salto lo mete el cliente de
Telegram, no el dato.** Una lista de caracteres prohibidos va siempre un punto
de código por detrás.

**La regla, por tanto, se invierte:**

> El mensaje del informe se compone **únicamente** de números validados, de
> valores de una enumeración cerrada, y de literales del sistema. **Ningún
> texto que haya escrito el paciente entra en él.**

El texto libre viaja en un **mensaje aparte**, enviado a continuación, con su
propia cabecera y sin filtrar. El paciente no pierde sus palabras y el clínico
gana algo: deja de haber duda sobre quién escribió qué.

La invariante que lo fija **no nombra ningún carácter**, y por eso sobrevive al
siguiente homoglifo que alguien descubra.

**La pregunta que encuentra esta clase de fallo.** Costó tres intentos, y lo
que falló las dos primeras veces fue la pregunta, no el esfuerzo. Preguntarse
*«qué caracteres son peligrosos»* lleva a una lista negra, y una lista negra va
siempre un punto de código por detrás. La pregunta que sirve es:

> **¿De dónde puede venir cada byte de este mensaje?**

Si la respuesta para algún byte es «de alguien de fuera», ese mensaje no puede
contener afirmaciones del sistema.

**Y hay una segunda pregunta, que costó otras tres rondas descubrir.** De las
cinco que llevó cerrar esta sección, en **cuatro** el fallo no estuvo en la
estructura nueva sino en **una esquina que había quedado fuera del cambio
anterior**: el cierre después del informe, el detalle del servidor después del
cierre, la cabecera después del detalle. Cada arreglo era correcto y cada uno
dejaba un sitio con la misma forma sin tocar.

> **¿Qué otros sitios tienen esta misma forma?**

Se hace **en cuanto se arregla uno**, no cuando el siguiente explota. En este
flujo los sitios que aún mezclan dato ajeno con afirmación propia están
enumerados; fuera de él, los dos que quedan son el **dashboard del §15** y lo
que **H6** escriba en `cuestionarios`. Esa pregunta habría encontrado los tres
fallos —el bloque falso, el cierre falsificable, y el que el filtro no veía— a
la primera, y sirve igual para el dashboard del §15, para H6, y para cualquier
sitio donde este proyecto vuelva a mezclar dato ajeno con afirmación propia.

> **Para quien construya el dashboard del §15:** el texto libre sigue
> guardándose sin neutralizar, que es lo correcto —quien presenta decide cómo—.
> Pero eso significa que **el dashboard hereda el problema entero**, y en HTML
> es peor: un filtro pensado para Telegram no toca `<`, `>`, `&` ni `"`.
> Escapar para HTML es obligatorio ahí, y es otro problema que este.

**Formato:** los números se muestran con la precisión de arriba —probabilidad
calibrada con dos decimales, RV con uno o dos, puntuación cruda con cuatro—, y
**ningún mensaje de los tres workflows lleva `parse_mode`**: todos van como
texto plano, que es lo que ya dice el §4.4.

**Por qué, y no es una preferencia de estilo.** `MarkdownV2` obliga a escapar
dieciocho caracteres, y el informe está lleno de tres de ellos: los paréntesis
de la línea de la puntuación y el punto de «Decide usted.». Uno sin escapar y
Telegram contesta 400 — con lo que el profesional **no recibe nada**, que es
mucho peor que recibirlo sin negritas. El segundo mensaje es peor todavía: lleva
el texto que escribió el paciente **sin filtrar**, y un `*` o un `_` suelto
rompería el envío o inyectaría formato. Y con formato disponible, los rótulos en
mayúsculas dejarían de ser la única forma de rotular que el paciente no puede
fabricar, que es la que sostiene la regla del informe.

Los nueve nodos de Telegram del flujo del profesional no llevan `parse_mode`, y
`test_ningun_mensaje_lleva_parse_mode` los recorre uno a uno para que siga
siendo así. **Lo que este párrafo prescribía antes —`MarkdownV2` escapando los
datos— haría que el informe no llegara**, y una revisión que lo tomara por
autoridad «corregiría» el flujo hasta dejar mudo al bot.

---

## 9. Errores

| Situación | Código registrado | Qué dice el bot | Estado después |
| :--- | :--- | :--- | :--- |
| Envía **foto** en vez de archivo | `envio_como_foto` | "Telegram recomprime las fotos y destruye el DICOM. Envíela como archivo." | **se queda en el paso 6**, esperando el archivo |
| No es un DICOM legible | `dicom_invalido` | «No pude leer esa radiografía.» y **nada del detalle del servidor cuando lo hay**; lo que sí se relata es la frase propia de la rama en la que el servidor no devolvió código (ver abajo) | se queda en el paso 6 |
| **Edad fuera de 18-100** | `fuera_de_alcance` | el detalle del servidor, **sin ninguna cifra de probabilidad** | **termina**: se registra y se borra la sesión |
| La cabecera no declara edad | `edad_desconocida` | el detalle del servidor, **sin ninguna cifra** | termina |
| Base64 mal formado | `base64_invalido` | "No pude leer el archivo." | se queda en el paso 6 |
| Más de 5 MB (respuesta MCP) | `payload_excesivo` | "El archivo supera los 5 MB." | se queda en el paso 6 |
| **HTTP 413** del transporte (§10.4) | `payload_excesivo_transporte` | mismo mensaje | se queda en el paso 6 |
| Código inexistente o caducado | `codigo_invalido` | "Ese código no existe o caducó. Pida al paciente que repita el cuestionario." | se queda en el paso 1 |
| Fichero de Telegram > 20 MB | `fichero_no_descargable` | "Telegram no me deja descargar archivos de más de 20 MB." | se queda en el paso 6 |
| Timeout o error de red | `copiloto_no_responde` | "El servicio de imagen no está disponible. Inténtelo en unos minutos." | se queda en el paso 6 |
| `isError` con un código desconocido | `error_no_reconocido` | "El servicio devolvió un error que no sé interpretar. Se ha registrado." | termina, y el texto íntegro va a `consultas.error` |
| **`chat_id` no autorizado** | `no_autorizado` | "No autorizado." y nada mas: sin pistas de que hay detras | **no se toca la sesion**. Se registra el intento con su `chat_id`, que es de donde se leen los de alta (§11) |
| No se pudo descargar el fichero de Telegram | `descarga_fallida` | mensaje propio y honesto; **no** el de los 20 MB, que solo vale cuando de verdad los supera | se queda en el paso 6 |

### El número de la última columna es el de la base, no el del §7

**Son dos numeraciones distintas, y mezclarlas sale caro.** El §7 cuenta pasos
del recorrido, y ahí el 5 es «pide la radiografía». La tabla `PASOS` del nodo
`Decidir` cuenta los seis huecos que la sesión puede tener guardados: **1**
código, **2** temperatura, **3** frecuencia, **4** crepitantes, **5** murmullo,
**6** placa. Esta columna dice en qué estado queda la fila de
`sesiones_profesional`, así que usa el número de la base.

Antes decía «paso 5» en las ocho filas que esperan el archivo —donde el 5 es el
murmullo— y «paso 2» en `codigo_invalido`. Las dos eran falsas, y de la forma
que más daño hace: quien revisara iría a comprobar el paso del murmullo contra
una fila que espera una placa, o «arreglaría» la consulta para que dejase la
sesión donde decía el spec. En `codigo_invalido` la sesión se queda en el **1**
porque `Buscar cuestionario` hace su `UPDATE ... SET paso = 2` con
`WHERE s.paso = 1` y solo cuando el código existe y no ha caducado: si no vale,
no se actualiza nada y el bot vuelve a pedir el código.

### Qué se relata del servidor, y por qué `dicom_invalido` es al revés de lo que parece

La columna «qué dice el bot» dice «el detalle del servidor» en tres filas, y en
`dicom_invalido` **no** lo dice. La decisión es por **procedencia** y la toma
`Leer respuesta` (§10.4 bis): se relata lo que compuso nuestro código, nunca lo
que el servidor armó interpolando la excepción de una librería sobre bytes
ajenos.

- Cuando el servidor **sí** devuelve `dicom_invalido: <detalle>`, ese detalle lo
  compone `inferencia.py` con el texto de la excepción de `pydicom` sobre el
  fichero que mandó quien sea: `detalle` se vacía y el clínico recibe solo «No
  pude leer esa radiografía.» y la coletilla.
- Cuando el servidor se cae sobre esos bytes **sin** devolver código, la frase
  la compone `Leer respuesta` —«No pude interpretar el contenido del fichero. Si
  lo recortó al enviarlo, vuelva a exportarlo completo.»— y esa **sí** se
  relata, porque es nuestra.

En los dos casos el texto crudo del servidor va entero a `consultas.error`, que
es donde se diagnostica. Escrito al revés, este §9 invitaba a devolverle al
profesional un texto que controla quien suministra el DICOM, que es justo el
agujero que el §8 existe para cerrar.

### Toda fila que no termina dice que el bot sigue esperando

La última columna dice si la conversación sigue viva. **El mensaje también tiene
que decirlo**, y antes no lo decía: de las diez filas que no terminan, una sola
-`envio_como_foto`- lo decía explícitamente, dos lo insinuaban con "Vuelva a
enviarlo.", y las seis demás dejaban al profesional sin saber si reenviar la
placa o empezar de cero. "El archivo supera los 5 MB." y punto, con el bot
esperando en silencio al otro lado.

Cada fila declara ahora **qué** espera, y el mensaje acaba con la frase
correspondiente:

| Lo que espera | La frase, literal |
| :--- | :--- |
| el archivo | *Sigo esperando el archivo.* |
| el código del paciente | *Sigo esperando el código del paciente.* |

Va **al final**, detrás del detalle del servidor y de la coletilla de edad: es
lo que el profesional tiene que hacer a continuación, y lo último que se lee es
lo que se hace. Ocho de las nueve filas la esperan para el archivo; solo
`codigo_invalido` espera el código, y una coletilla que pidiera el archivo ahí
mandaría al clínico a hacer lo que no es.

`no_autorizado` es la **única excepción**: no termina la conversación y aun así
no lleva coletilla. Quien llega ahí no está en la lista blanca, y "Sigo esperando
el archivo." le confirmaría que hay un bot escuchando detrás y que lo que manda
le llega.

Las tres filas que **terminan** no la llevan: no hay nada que esperar cuando se
borra la sesión.

La frase vive en un solo sitio del nodo (`SIGO_ESPERANDO`), y eso no basta por sí
solo -escrita a mano era justo una frase que ocho filas se habían olvidado de
poner-. Lo que lo sostiene es una invariante de `tests/profesional.mjs` que
recorre **la tabla del propio nodo**, no una lista escrita a mano, y exige que la
coletilla concuerde con la última columna. La primera versión de esa prueba
recorría una lista a mano, y `descarga_fallida` -que está en la tabla y no en
este §9- se le colaba entera.

**Son trece, y la cuenta importa:** un spec con once filas y un flujo con
trece hace que la siguiente revision marque dos falsos positivos, o que alguien
los quite del flujo para que cuadre. La distincion entre `dicom_invalido` y
`error_no_reconocido` es la mas delicada de todas: cuando el servidor devuelve
`isError` **sin ningun codigo**, se trata como fichero ilegible y la
conversacion espera otro archivo. Eso acierta con un DICOM truncado -medido en
siete cortes- pero **no distingue un fichero roto de una caida nuestra**: si el
servidor se cayera por memoria o por un modelo que no carga, el profesional
oiria "no pude leer esa radiografia" y reenviaria la placa para siempre. Lo que
lo haria honesto es que el servidor no perdiera el mensaje, y eso es SP2. Por
eso el texto crudo del servidor se registra **siempre** en `consultas.error`,
sea cual sea la rama: es lo unico diagnosticable que queda.

> **Cuidado con la columna de estado:** `termina` significa **borrar la
> sesion**. Por eso `no_autorizado` NO la lleva: a un profesional dado de baja
> a mitad de conversacion le borraria los cuatro signos que ya habia recogido,
> y el §7 dice que deja de pasar en el mensaje siguiente, no que se le tire el
> estado.

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
Error executing tool clasificar_radiografia: fuera_de_alcance: El paciente tiene 12 años y el modelo solo es válido entre 18 y 100.
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

### 10.4 bis. Los códigos de error son parte del contrato

El bot clasifica cada código del servidor en **relatable** o **no relatable**
según quién compuso su texto (§9): se le enseña al clínico lo que compuso
nuestro propio código a partir de datos validados, y no lo que compuso una
librería de terceros sobre bytes ajenos.

Esa tabla vive en el bot y **se ata a las fuentes de Python con una prueba**,
pero hay algo que la prueba no puede cubrir: **si SP2 añadiera un sexto
código, el bot no lo tendría** y caería en `error_no_reconocido`, que termina
la conversación. Es el fallo cerrado y no el abierto, pero es una sorpresa
esperando.

Los cinco de hoy: `dicom_invalido` y `base64_invalido` **no relatables** —los
dos interpolan el texto de una excepción ajena—; `edad_desconocida`,
`fuera_de_alcance` y `payload_excesivo` **relatables**, porque son literales
más enteros ya validados.

**Quien toque los errores de SP2 tiene que venir aquí.**

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
| Paciente | `bot-paciente` | `CRED_TELEGRAM_PACIENTE` |
| Profesional | `bot-profesional` | `CRED_TELEGRAM_PROFESIONAL` |
| Pruebas | `bot-avisos` | `CRED_TELEGRAM_AVISOS` |

Las del cliente que **no se tocan**: la credencial de Telegram del cliente (5 workflows) y
`Telegram account` (2). Existe además una credencial de pruebas sin uso,
anterior a `bot-avisos` y hoy redundante.

| Secreto | Dónde vive | Si se filtra |
| :--- | :--- | :--- |
| Token del bot del paciente | credencial `bot-paciente` | revocar en BotFather, crear otro, actualizar la credencial |
| Token del bot del profesional | credencial `bot-profesional` | igual |
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
3. **No se crea ni se borra** `<RED_N8N>`, ni se tocan sus otros
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
| Rechazos por código | `split_part(consultas.error, ':', 1)` — la columna guarda `codigo: texto`, no solo el codigo |
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
- hay **3 rechazos por `dicom_invalido` o más** en los últimos 7 días **y**
  además pasan del 20 % de las placas de esa ventana (algo pasa con cómo mandan
  las placas) — contando con `split_part(error, ':', 1)`, porque la columna
  guarda `codigo: texto`. **Las dos condiciones, no solo la tasa:** con el 20 %
  a secas, una placa rechazada de tres dispara el aviso, y eso ocurre el 27 % de
  las semanas flojas aunque la tasa real sea del 10 %. Un aviso que salta cada
  semana deja de leerse, y entonces ya no avisa de nada;
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

Por eso hay que llamar a diario a `getWebhookInfo` de los dos bots y avisar si la
`url` no es la esperada o si `last_error_message` trae algo.

**Esa llamada NO cabe dentro del workflow, y la comprobación va partida en dos
(medido en la tarea 7).** El token de Telegram viaja **en la ruta de la URL**, y
una credencial de n8n solo sabe inyectar cabeceras, parámetros de consulta, cuerpo
o autenticación básica: no puede escribir en la ruta. El nodo Telegram v1.2
tampoco tiene ninguna operación de webhook (`chat`, `callback`, `file`,
`message`). Escribir el token en un parámetro del nodo lo versionaría en el JSON
exportado, que es exactamente el pecado por el que este mismo §16 rechaza el
Telegram Trigger. Así que:

- **La mitad de n8n, dentro del workflow, a diario y sin ningún secreto:** un
  `POST` sin `secret_token` a cada webhook. Medido contra el n8n real: **403** si
  está registrado y activo, **404** si el flujo está desactivado o le cambiaron
  la ruta, y un **200** significaría que la comprobación del §4.2 desapareció.
  Cubre flujo desactivado, ruta cambiada y proxy roto.
- **La mitad de Telegram, fuera:** `pruebas/verificar_webhooks.py`, con los
  tokens del entorno o por teclado, en una **tarea programada diaria en la
  máquina del equipo** (§5 del manual de operación). Se eligió eso, y no dos
  variables de entorno en el n8n del cliente, para no reiniciar su n8n mientras
  H5 esté abierto. **Hasta que esa tarea esté montada, un webhook desregistrado
  en Telegram deja un bot mudo y nada avisa.**

**Excepción declarada a la retención de ejecuciones del §5.4.** Los dos bots
llevan las dos retenciones en `none` porque sus ejecuciones arrastran el DICOM,
su base64 y las respuestas del paciente a la base de n8n del cliente. El
workflow de mantenimiento lleva **los éxitos en `none` y los errores en `all`**,
y no es un descuido:

- por él no pasa ningún dato de paciente: sus consultas devuelven recuentos y
  códigos de error del §9 y nada más, y eso lo ata una prueba de
  `tests/test_mantenimiento.py` que fija las columnas que salen de la base;
- y cuando una corrida del mantenimiento falla, **su ejecución es el único
  rastro que queda**, porque el aviso es justamente lo que no pudo salir. Con
  los errores en `none`, el vigilante se cae en silencio — que es lo que este
  §16 existe para impedir.

Las ejecuciones manuales se guardan por la misma razón: el «Execute workflow» es
como se diagnostica a mano.

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
| Que el consentimiento de D11 nombre a Telegram como tercero por el que pasan la imagen y las respuestas (§5.5) | antes de datos reales, con el comité de H7 |
| Decidir si el piloto con datos reales va por Telegram o por un canal local (§5.5) | antes de H7 |

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
| **La radiografía y las respuestas clínicas pasan por los servidores de Telegram** | **Aceptado y declarado, no mitigado (§5.5).** Telegram era la vía de entrega elegida, y un canal propio no lo va a instalar nadie en un piloto. Hoy lo acota que solo circulan placas de RSNA y síntomas fabricados; deja de acotarlo la primera placa real, que es H7. Eliminarlo exige un canal local: carga web propia sobre el `POST /inferir` que ya existe, una app, o un servidor de ficheros en la red del centro |
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
