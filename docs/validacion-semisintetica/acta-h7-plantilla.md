# Acta de H7 — sesión de concordancia con un médico sobre viñetas semisintéticas

**Rótulo:** {{rotulo}}. La placa de cada caso es real (conjunto de prueba de
RSNA); la clínica es generada. El kappa mide acuerdo con un evaluador, no
exactitud clínica.

**Participante:** médico general colaborador, de forma voluntaria; sin datos
personales en ningún fichero del proyecto.

**Fechas:** lectura 1 el {{fecha_lectura1}}; lectura 2 el {{fecha_lectura2}}.

**Casos:** {{n}}, elegidos con semilla por estratos (tabla al final). Los
mensajes del sistema se generaron con la prevalencia desplegada
({{prevalencia_sesion}}); la categoría del sistema sale del bloque
`combinacion` del {{categoria_de}}.

## Método

Dos lecturas del mismo conjunto: la primera sin copiloto (placa y viñeta;
banda y porcentaje); la segunda, al menos siete días después, con el mensaje
real del sistema en 20 casos y 4 controles sin mensaje. El kappa sale solo de
la primera. Pregunta al médico: probabilidad de que la placa muestre una
opacidad o infiltrado compatible con neumonía, en tres bandas (< 20 %,
20-70 %, > 70 %; convención del equipo) y como porcentaje entero. Instrumento:
el formulario local, un caso por pantalla, sin volver atrás; el tiempo va de
abrir el caso a enviar la banda.

## Resultados

- **Kappa ponderado lineal (primario):** {{kappa_ponderado}}.
- **Kappa de Cohen sin ponderar:** {{kappa_cohen}}.
- **Kappa binario en «alta»:** {{kappa_binario}}.
- **Sensibilidad a la regla de categoría del sistema (kappa ponderado):** {{sensibilidad}}.
- **Acuerdo continuo:** Spearman {{spearman}}; diferencia media en log-odds
  (médico − sistema) {{bland_altman}}; el porcentaje del médico cae dentro de
  la horquilla en el {{dentro_horquilla}} % de los casos; porcentajes de 0 o
  100 acotados: {{acotados}}.
- **Influencia del sistema (no es concordancia independiente):** {{influencia}}.
- **Utilidad del pre-informe (1-5):** {{utilidad}}.
- **Tiempo de triaje:** {{tiempo}}.

{{texto_fijado}}

## Desacuerdos, caso por caso

| Caso | Estrato | Sistema | Médico | Horquilla del sistema | Comentario |
| :--- | :--- | :--- | :--- | :--- | :--- |
{{tabla_desacuerdos}}

## Observaciones del médico

(Se anexan sin editar. Si no las envió, se hace constar.)

## Conformidad

El acta se cierra con la conformidad del médico, o con la constancia de que
no la envió.

## Anexo: los casos

| Caso | Estrato | Clínica frente a imagen |
| :--- | :--- | :--- |
{{tabla_casos}}
