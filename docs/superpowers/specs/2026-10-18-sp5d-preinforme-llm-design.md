# SP5-D: el pre-informe redactado por un LLM

Fecha: 18-oct-2026. Rama `sp5d-preinforme-llm` desde `main` (1b06b16). Modo rápido: un paquete
de código y pruebas, otro de documentación, una revisión final y una tanda de arreglos.

## Qué y por qué

El bot del profesional manda hoy un informe determinista: tres bloques rotulados y el
combinado con Heckerling (SP3 §8, SP4 §8). En la sesión con el médico (H7, acta
`docs/validacion-semisintetica/acta-h7.md`) la nota más baja fue la del **lenguaje del
mensaje: 2,5 de 5** (corrección 4,7; utilidad 4,0). SP5-D añade, **detrás** de ese informe y
sin tocarlo, un segundo mensaje: un **pre-informe** en prosa clínica que redacta un LLM a
partir del informe.

El LLM se retiró en SP3 (§4.5) de la **entrada**: un extractor probabilístico delante de un
cálculo clínico produce, cuando se equivoca, una probabilidad previa equivocada que nadie ve.
Vuelve solo a la **salida**, donde lo que escribe se puede comprobar contra el informe que
ya llegó. El cálculo no cambia: ni una cifra del informe depende del LLM.

## Decisiones (del equipo, 18-oct)

- D1. **Proveedor: OpenAI**, por API, con una credencial de n8n **propia del proyecto**
  (`openai-copiloto`, con la clave del equipo; nunca una credencial de un cliente). Modelo
  `gpt-4o-mini`, temperatura 0,2, hasta 350 *tokens* de salida.
- D2. **Solo en el bot del profesional.** Ni la app de demostración ni el bot del paciente
  llaman al LLM. La base de datos no cambia: el pre-informe no se guarda.
- D3. **El LLM recibe el informe determinista y nada más**: el mismo texto de
  `redactarResultado`, sin el aviso del comentario del paciente. Ese texto **no contiene
  ni un carácter escrito por el paciente** (su texto libre va en otra burbuja, SP3 §4.4), así
  que el paciente no puede inyectarle instrucciones. No lleva nombre, cuenta de Telegram,
  código del caso, edad ni la imagen.
- D4. **El informe determinista sale primero y no espera al LLM.** El pre-informe es una
  burbuja más, al final: informe → (texto del paciente, si lo hay) → pre-informe. El
  objetivo de latencia (< 8 s) sigue midiéndose sobre el informe.
- D5. **Se revisa antes de mandarlo, y si no pasa, no se manda.** No hay reintento ni texto de
  reserva: el informe ya llegó, y un silencio es mejor que un texto dudoso. Reglas en el
  apartado «La revisión».
- D6. **Rotulado en la posición 0** (como la cabecera del texto del paciente, SP3 §4.4): quien
  vea la burbuja sola —reenvío, notificación— sabe qué es y qué manda.
- D7. **El consentimiento del bot del paciente nombra a OpenAI.** Una viñeta más, publicada en
  producción con el mismo método del 5-oct.
- D8. **No se valida con el médico antes de la entrega.** H7 midió el informe sin
  pre-informe: el acta no se toca, y la documentación dice que el pre-informe no está validado.

## Lo que se construye

### En `n8n/copiloto-profesional.json`

1. `Desenlace`: un campo nuevo en la salida, `preinforme_fuente`, `''` por defecto. En la
   rama con resultado (`else if (e.resultado)`) vale
   `redactarResultado(e.resultado, sintomas, signos, false)`: el informe sin la línea que
   avisa del segundo mensaje. En las demás ramas, `''`.
2. Conexiones: `Hay texto del paciente?` rama verdadera → `Enviar texto del paciente` →
   `Preparar pre-informe`; rama falsa → `Preparar pre-informe`. Después,
   `Preparar pre-informe` → `Pedir pre-informe` → `Revisar pre-informe` → `Enviar pre-informe`.
3. `Preparar pre-informe` (código): si `preinforme_fuente` está vacío devuelve `[]` y la rama
   se para. Si no, devuelve `{fuente, cuerpo}` con el cuerpo de la petición de chat
   (modelo, temperatura, `max_tokens`, mensaje de sistema y el informe como mensaje de
   usuario).
4. `Pedir pre-informe` (HTTP Request): `POST https://api.openai.com/v1/chat/completions`,
   credencial predefinida `openAiApi` (`id` `CRED_OPENAI`, `name` `openai-copiloto`), cuerpo
   JSON `$json.cuerpo`, tiempo máximo 15 s, sin reintentos y **`onError:
   continueRegularOutput`**: un fallo de OpenAI no pone la ejecución en rojo ni para nada.
5. `Revisar pre-informe` (código): aplica la revisión. Si pasa, devuelve
   `{texto: CABECERA + redactado}`; si no, `[]`.
6. `Enviar pre-informe` (Telegram, la credencial del bot del profesional): `chatId` el de
   `Normalizar update`, texto **solo** la expresión `={{ $json.texto }}`, sin
   `parse_mode` y sin atribución.

### El mensaje de sistema (literal)

```
Redactas el pre-informe de un sistema de apoyo al triaje de neumonía en adultos. Recibes el informe automático que el sistema acaba de mandar a un médico: el resultado de una red que lee la radiografía de tórax, los síntomas que refirió el paciente, los signos que exploró el médico y, si hay datos, la combinación con la regla clínica de Heckerling.
Escribe para ese médico un resumen en español, en registro clínico, en un solo párrafo de 3 a 5 frases.
Reglas:
1. Usa solo lo que dice el informe. Cada número que escribas tiene que estar en el informe exactamente igual: no calcules, no redondees y no añadas ninguno.
2. Lo que mide la imagen es «opacidad compatible», no neumonía.
3. No des un diagnóstico ni recomiendes pruebas, tratamientos, ingreso ni derivación.
4. Si el informe trae avisos (⚠️), di lo que advierten.
5. Termina recordando que la decisión es del médico.
6. Sin saludo, sin títulos, sin listas y sin formato.
```

### La cabecera (literal, posición 0, seguida de una línea en blanco)

```
PRE-INFORME — redactado por IA (OpenAI) a partir del informe de arriba. Si algo no coincide, vale el informe de arriba. No es un diagnóstico.
```

### La revisión (`Revisar pre-informe`)

Sobre `choices[0].message.content` de la respuesta, recortado de blancos. Se rechaza
(devuelve `[]`) si:

1. No hay texto (error de la petición, respuesta sin `choices`, contenido que no es cadena).
2. Mide menos de 80 o más de 1 200 caracteres.
3. **Alguna cifra no está en el informe.** Las cifras son las coincidencias de
   `/\d+(?:[.,]\d+)?/g`; se comparan por valor (coma decimal → punto, `parseFloat`) con el
   conjunto de valores de las cifras del informe fuente.
4. Contiene, sin distinguir mayúsculas ni tildes, alguna de estas formas: `antibiot`,
   `tratamient`, `tratar`, `prescrib`, `dosis`, `medicament`, `farmac`, `hospitaliz`,
   `ingres(ar|o|e)`, `deriv(ar|e|acion)`, `urgencia`, `confirm`, `padece`, `tiene neumonia`,
   `diagnostico de`, o `descart` **salvo** precedido de «no », «no la » o «no lo » (el aviso
   del negativo dice «no la descarta», y decirlo es correcto).

Rechazar de más cuesta un pre-informe que no llega; dejar pasar de menos, una frase que nadie
revisó. Por eso las reglas son estrictas y se prueban con ejemplos en los dos sentidos.

### En el bot del paciente (`n8n/copiloto-paciente.json`, nodo `Pedir consentimiento`)

Una viñeta nueva, detrás de la de la inteligencia artificial:

```
• Para su médico, otro programa de inteligencia artificial de OpenAI, una empresa extranjera, resume el informe del sistema. Ese resumen no lleva su nombre, su cuenta ni lo que usted escriba.
```

### Marcadores (`scripts/marcadores_n8n.py`)

Un marcador nuevo, `CRED_OPENAI` (el `id` de la credencial), en `MARCADORES`,
`n8n/valores.ejemplo.json` y sus pruebas. El nombre `openai-copiloto` es genérico y no
necesita marcador (como `copiloto-bd`).

## Cómo se comprueba

- `tests/profesional.mjs` ejecuta el `jsCode` real de `Desenlace`, `Preparar pre-informe` y
  `Revisar pre-informe`: la fuente solo en la rama con resultado; la fuente nunca contiene el
  texto libre del paciente, aunque traiga una instrucción; un redactado correcto pasa con la
  cabecera en la posición 0; una cifra de más, un tratamiento, «se descarta», un texto vacío,
  corto o largo y una respuesta de error se rechazan; «no la descarta» pasa.
- `tests/test_flujo_profesional.py`: las conexiones, la configuración de los dos nodos nuevos
  de red (URL, tipo y marcador de credencial, tiempo máximo ≤ 15 s, `onError`) y que el texto
  del envío sea solo la expresión.
- `tests/test_flujo_paciente.py`: el consentimiento nombra a OpenAI y cabe en un mensaje.
- `tests/test_marcadores_n8n.py` con el marcador nuevo; `scripts/verificar_anonimato.py` en 0.
- Suite completa en Linux; prueba real en producción después de publicar (el equipo, por el bot,
  grabando la pantalla para el vídeo).

## Despliegue

Publicación por la API de n8n con el método de SP4 T11 y del 5-oct: se parte de lo
**publicado** (`activeVersion`), se cambian solo `Desenlace`, las conexiones y los cuatro
nodos nuevos (y en el paciente, solo el texto del consentimiento), y se comprueba después
que el resto quedó idéntico. Antes, el equipo crea la credencial `openai-copiloto` en n8n.

## Fuera de alcance

El pre-informe en la app; guardarlo en `consultas`; reintentos o un texto de reserva;
validarlo con el médico; cambiar el informe determinista.
