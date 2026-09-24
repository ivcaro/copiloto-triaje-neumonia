-- bd/limpieza.sql
-- Lo ejecuta el workflow de mantenimiento, a diario.
--
-- NO toca `consultas`: es el registro permanente y sin el no hay validacion
-- clinica en H7 ni dashboard.
BEGIN;
DELETE FROM cuestionarios        WHERE expira_en < now();
DELETE FROM sesiones_paciente    WHERE actualizado_en < now() - interval '24 hours';
DELETE FROM sesiones_profesional WHERE actualizado_en < now() - interval '24 hours';
-- El contador del limite por chat_id: 2 dias, no 1, por el borde de la
-- zona horaria (agrupa en America/Guayaquil, esto corre en UTC).
DELETE FROM limite_paciente      WHERE dia < (now() AT TIME ZONE 'America/Guayaquil')::date - 2;
COMMIT;
