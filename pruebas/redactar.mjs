// Redacta el mensaje del profesional ejecutando el `jsCode` REAL de los nodos
// `Leer respuesta` y `Desenlace` del workflow exportado.
//
// POR QUE ESTE FICHERO EXISTE, Y POR QUE NO ES PYTHON
// ---------------------------------------------------
// `pruebas/reproducir_casos.py` necesita el texto EXACTO que el bot le manda al
// profesional. Ese texto no se puede leer de Telegram: la API de bots no
// devuelve los mensajes que el propio bot envio, y un bot no recibe los mensajes
// de otro bot, asi que no hay ningun espia posible. Tampoco esta en el historial
// de n8n: los dos flujos llevan las dos retenciones en `none` (§5.4 del spec),
// justamente para que el DICOM y las respuestas del paciente no queden en la
// base de datos del cliente.
//
// Queda una sola via honesta: **componerlo con el codigo del propio flujo**. El
// nodo `Responder` manda literalmente `{{ $('Desenlace').first().json.texto }}`,
// asi que ejecutar `Desenlace` con las mismas entradas da el mismo texto, byte a
// byte, por construccion y no por parecido.
//
// Reescribir el §8 en Python habria sido la alternativa, y es peor: seria una
// segunda copia de la redaccion clinica, y se desincronizaria del workflow en
// silencio la primera vez que alguien tocara un rotulo. El spec insiste en esto
// en el propio nodo: «una tabla en un nodo no puede divergir de si misma».
//
// USO
// ---
//   node pruebas/redactar.mjs < entrada.json
//
// Entrada: un array de objetos
//   { http: {statusCode, cuerpo}, decidir: {chat_id,t0,codigo,sintomas,signos},
//     normalizar: {chat_id, t0} }
// Salida: un array del mismo largo con
//   { texto, texto_paciente, error, resultado, termina, registrar, ms }
// `error` ya viene descodificado: el flujo lo guarda como 'T'+base64 porque un
// parametro de Postgres no puede llevar saltos de linea, y aqui no hace falta.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FLUJO = path.join(AQUI, "..", "n8n", "copiloto-profesional.json");

const flujo = JSON.parse(fs.readFileSync(FLUJO, "utf8"));
const codigo = (nombre) => {
  const n = flujo.nodes.find((x) => x.name === nombre);
  if (!n) throw new Error(`el workflow exportado no tiene un nodo '${nombre}'`);
  const js = n.parameters && n.parameters.jsCode;
  if (!js) throw new Error(`el nodo '${nombre}' no es un nodo de codigo`);
  return js;
};

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

// El minimo de n8n que estos dos nodos usan: `$input.first()`, `$('nodo')` y
// `Buffer`. Ni uno mas: un simulador mas generoso dejaria pasar codigo que en
// n8n no funcionaria.
async function correr(jsCode, entrada, nodos) {
  const $input = { first: () => entrada, all: () => [entrada] };
  const $ = (nombre) => {
    if (!(nombre in nodos)) {
      throw new Error(`No node named '${nombre}' was executed`);
    }
    return { first: () => ({ json: nodos[nombre] }) };
  };
  const fn = new AsyncFunction("$input", "$", "Buffer", jsCode);
  return await fn($input, $, Buffer);
}

const descodificar = (v) => {
  const s = String(v == null ? "" : v);
  if (s === "N" || s === "") return null;
  if (s[0] !== "T") return s;
  return Buffer.from(s.slice(1), "base64").toString("utf8");
};

const leerEntrada = () =>
  new Promise((resolve, reject) => {
    let datos = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (t) => { datos += t; });
    process.stdin.on("end", () => {
      try { resolve(JSON.parse(datos)); } catch (e) { reject(e); }
    });
    process.stdin.on("error", reject);
  });

const JS_LEER = codigo("Leer respuesta");
const JS_DESENLACE = codigo("Desenlace");

const casos = await leerEntrada();
const salida = [];
for (const c of casos) {
  const leido = (await correr(JS_LEER, { json: c.http }, { Decidir: c.decidir }))[0].json;
  const d = (await correr(JS_DESENLACE, { json: leido },
                          { "Normalizar update": c.normalizar, Decidir: c.decidir }))[0].json;
  salida.push({
    texto: d.texto,
    texto_paciente: d.texto_paciente,
    error: descodificar(d.error_cod),
    resultado: leido.resultado,
    termina: d.termina === "S",
    registrar: d.registrar === "S",
    ms: d.ms,
  });
}
process.stdout.write(JSON.stringify(salida));
