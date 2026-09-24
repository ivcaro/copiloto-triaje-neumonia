-- bd/esquema.sql
-- Esquema de SP3. Se aplica entero y es idempotente.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Estado efimero del PACIENTE mientras contesta. Existe porque un flujo de
-- n8n no recuerda nada entre mensajes y el callback_data de Telegram esta
-- limitado a 64 bytes: no caben las respuestas.
CREATE TABLE IF NOT EXISTS sesiones_paciente (
  chat_id        bigint PRIMARY KEY,
  paso           smallint    NOT NULL DEFAULT 0,
  consentido_en  timestamptz,
  respuestas     jsonb       NOT NULL DEFAULT '{}',
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

-- Estado efimero del PROFESIONAL. Su conversacion es mas larga (codigo, cuatro
-- signos, DICOM). Sin esta tabla, dos consultas simultaneas pueden cruzar los
-- signos de un paciente con la radiografia de otro, y el mensaje resultante
-- saldria sintacticamente perfecto.
CREATE TABLE IF NOT EXISTS sesiones_profesional (
  chat_id        bigint PRIMARY KEY,
  paso           smallint    NOT NULL DEFAULT 0,
  codigo         text,
  signos         jsonb       NOT NULL DEFAULT '{}',
  actualizado_en timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cuestionarios (
  codigo        text PRIMARY KEY,
  respuestas    jsonb       NOT NULL,
  consentido_en timestamptz NOT NULL,
  creado_en     timestamptz NOT NULL DEFAULT now(),
  expira_en     timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS cuestionarios_expira ON cuestionarios (expira_en);

CREATE TABLE IF NOT EXISTS profesionales (
  chat_id bigint PRIMARY KEY,
  nombre  text        NOT NULL,
  activo  boolean     NOT NULL DEFAULT true,
  alta_en timestamptz NOT NULL DEFAULT now(),
  baja_en timestamptz
);

-- Registro permanente. Fuente del dashboard y de la validacion de H7.
-- `codigo` NO lleva clave foranea a proposito: cuestionarios se borra a los 7
-- dias y la referencia arrastraria o bloquearia este registro.
CREATE TABLE IF NOT EXISTS consultas (
  id         bigserial PRIMARY KEY,
  codigo     text,
  chat_id    bigint,
  -- COPIA (D12): cuestionarios se borra a los 7 dias: sin esta copia, H7 no
  -- tiene nada que validar una vez pasada esa ventana.
  sintomas   jsonb,
  signos     jsonb,
  resultado  jsonb,
  error      text,
  ms_extremo integer,
  creado_en  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS consultas_creado ON consultas (creado_en);
CREATE INDEX IF NOT EXISTS consultas_error  ON consultas (error);

CREATE TABLE IF NOT EXISTS cuestionarios_iniciados (
  dia     date PRIMARY KEY,
  cuantos integer NOT NULL DEFAULT 0
);

-- El codigo seudonimo: 6 caracteres de un alfabeto de 31, sin 0/O ni 1/I/L
-- porque se dicta en voz alta en una consulta.
--
-- El bucle interior es muestreo por RECHAZO y no un modulo a secas: 256 no es
-- multiplo de 31, asi que `byte % 31` haria salir los 8 primeros caracteres un
-- 29% mas que el resto. Descartando los bytes >= 248 (31*8) el reparto queda
-- uniforme. No es una frontera de seguridad, pero un alfabeto sesgado en algo
-- que se usa como identificador es deuda gratuita.
CREATE OR REPLACE FUNCTION generar_codigo() RETURNS text AS $$
DECLARE
  alfabeto constant text := 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';
  resultado text := '';
  b integer;
BEGIN
  FOR _i IN 1..6 LOOP
    LOOP
      b := get_byte(gen_random_bytes(1), 0);
      EXIT WHEN b < 248;
    END LOOP;
    resultado := resultado || substr(alfabeto, 1 + (b % 31), 1);
  END LOOP;
  RETURN resultado;
END;
$$ LANGUAGE plpgsql VOLATILE;
