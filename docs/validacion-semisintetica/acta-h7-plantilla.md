# Acta de H7 — sesión de concordancia con un médico sobre viñetas semisintéticas

**Rótulo:** {{rotulo}}. La placa de cada caso es real (conjunto de prueba de
RSNA); la clínica es generada. El kappa mide acuerdo con un evaluador, no
exactitud clínica.

**Participante:** médico general colaborador, de forma voluntaria; sin datos
personales en ningún fichero del proyecto.

**Fechas:** {{fechas}}.

**Casos:** {{n}}, elegidos con semilla por estratos (tabla al final). Los
mensajes del sistema se generaron {{origen_mensajes}}, con la prevalencia
desplegada ({{prevalencia_sesion}}); la categoría del sistema sale del bloque
`combinacion` del mensaje.

## Método

{{metodo}} Pregunta al médico: probabilidad de que la placa muestre una
opacidad o infiltrado compatible con neumonía, en tres bandas (< 20 %,
20-70 %, > 70 %; convención del equipo) y como porcentaje entero. Instrumento:
el formulario local, un caso por pantalla, sin volver atrás; el tiempo va de
abrir el caso a enviar la banda. Los síntomas referidos son un fondo constante
en todos los casos (salvo el asma y la fiebre, que siguen a la clínica
generada) y así se le dijo al médico.

## Resultados

- **Kappa ponderado lineal (primario):** {{kappa_ponderado}}.
- **Kappa de Cohen sin ponderar:** {{kappa_cohen}}.
- **Kappa binario en «alta»:** {{kappa_binario}}.
- **Frente a 0,4 y 0,6:** {{criterio_kappa}}
- **Sensibilidad a la regla de categoría del sistema (kappa ponderado):**
  {{sensibilidad}}; casos cuya horquilla cruza un límite: {{n_cruzan_un_limite}} de {{n}}.
- **Acuerdo continuo:** Spearman {{spearman}}; diferencia media en log-odds
  (médico − sistema) {{bland_altman}}; el porcentaje del médico cae dentro de
  la horquilla en el {{dentro_horquilla}} % de los casos
  ({{horquillas_anchura_cero}} de {{n}} horquillas son un solo porcentaje: en
  ellas solo cuenta el valor exacto); porcentajes de 0 o 100 acotados:
  {{acotados}}.
- **Influencia del sistema (no es concordancia independiente):** {{influencia}}.
- **Utilidad del pre-informe (1-5):** {{utilidad}}.
- **Tiempo de triaje:** {{tiempo}}. Razones individuales de los controles
  (lectura 2 / lectura 1): {{razones_controles}}.

{{texto_fijado}}

## Desacuerdos, caso por caso

| Caso | Estrato | Sistema | Médico | Horquilla del sistema | Comentario |
| :--- | :--- | :--- | :--- | :--- | :--- |
{{tabla_desacuerdos}}

## Pregunta sobre el PACS

¿En su práctica, la radiografía en DICOM se obtiene del PACS? Es la pregunta
que el diseño de SP3 (§18) dejó para antes de H7.

(Respuesta del médico en la reunión de preparación; se anota a mano.)

## Observaciones del médico

(Se anexan sin editar. Si no las envió, se hace constar.)

## Conformidad

El acta se cierra con la conformidad del médico, o con la constancia de que
no la envió.

## Anexo: los casos

| Caso | Estrato | Clínica frente a imagen |
| :--- | :--- | :--- |
{{tabla_casos}}

**Congelado verificable:** {{huellas}}.
