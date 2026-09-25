// Ejecuta el `jsCode` REAL de los cuatro nodos de codigo del flujo del
// profesional, con los `$()` de n8n simulados, y comprueba lo que no se puede
// afirmar sin ejecutarlo.
//
// Es el equivalente de `tests/decidir.mjs` para la tarea 6, y cubre dos cosas
// mas que aquel:
//
//  - `Leer respuesta` se prueba contra las respuestas LITERALES del contenedor,
//    copiadas de una medicion del 25-sep-2026 (§10). Incluye el 413 del
//    transporte, que no lleva SSE ni JSON-RPC y que en el primer borrador del
//    spec habria caido en el camino de exito.
//
//  - `Desenlace` se prueba contra los valores REALES de tres placas del conjunto
//    de prueba, una de ellas de la banda contradictoria. Ahi vive el criterio 6:
//    tres bloques rotulados, y el aviso cuando la etiqueta es positiva y la
//    razon de verosimilitud es menor que 1. Y el criterio 7: ninguna rama de
//    error emite una cifra de probabilidad.
//
// Lo invoca tests/test_flujo_profesional.py con `node`. A mano:
//   node tests/profesional.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FLUJO = path.join(AQUI, "..", "n8n", "copiloto-profesional.json");
const flujo = JSON.parse(fs.readFileSync(FLUJO, "utf8"));
const nodo = (n) => {
  const x = flujo.nodes.find((y) => y.name === n);
  if (!x) throw new Error(`el workflow no tiene un nodo '${n}'`);
  return x;
};
const codigo = (n) => nodo(n).parameters.jsCode;

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

// `opciones` existe por H4: el arnés NO puede fabricar el `this` que haría
// funcionar `this.helpers` y luego decir que ha probado el nodo. Con
// `thisArg`/`helpersEnAmbito` se puede correr el mismo código **sin** ningún
// accesor, que es el caso que interesa.
async function correr(jsCode, entrada, nodos, opciones = {}) {
  const $input = {
    first: () => entrada,
    all: () => [entrada],
  };
  const $ = (nombre) => {
    if (!(nombre in nodos)) {
      throw new Error(`No node named '${nombre}' was executed`);
    }
    return { first: () => ({ json: nodos[nombre] }) };
  };
  const nombres = ["$input", "$", "Buffer"];
  const valores = [$input, $, Buffer];
  if ("helpersEnAmbito" in opciones) {
    nombres.push("helpers");
    valores.push(opciones.helpersEnAmbito);
  }
  const fn = new AsyncFunction(...nombres, jsCode);
  return await fn.apply(opciones.thisArg, valores);
}

let fallos = 0;
function ok(etiqueta, cond, detalle = "") {
  console.log((cond ? "  OK   " : "  FALLO") + ` ${etiqueta}` + (detalle ? `  ${detalle}` : ""));
  if (!cond) fallos++;
}

// --------------------------------------------------------------------------
// Ayudas
// --------------------------------------------------------------------------
const normalizar = async (update) => {
  const r = await correr(codigo("Normalizar update"), { json: { body: update } }, {});
  return r.length ? r[0].json : null;
};
const decidir = async (u, sesion) =>
  (await correr(codigo("Decidir"), { json: sesion }, { "Normalizar update": u }))[0].json;
const leerRespuesta = async (http, d) =>
  (await correr(codigo("Leer respuesta"), { json: http }, { Decidir: d }))[0].json;
const desenlace = async (entrada, u, d) =>
  (await correr(codigo("Desenlace"), { json: entrada },
                { "Normalizar update": u, Decidir: d }))[0].json;

const msg = (texto, chat = 7) => ({ message: { chat: { id: chat }, text: texto } });
const btn = (dato, chat = 7) => ({ callback_query: { id: "1", data: dato, message: { chat: { id: chat } } } });
const doc = (file_id, file_size = 131000) => ({
  message: { chat: { id: 7 }, document: { file_id, file_size, file_name: "a.dcm" } },
});
const foto = () => ({ message: { chat: { id: 7 }, photo: [{ file_id: "f", width: 90, height: 90 }] } });

const ses = (paso, extra = {}) => Object.assign(
  { chat_id: 7, autorizado: true, existe: true, paso, codigo: null, signos: {}, sintomas: null },
  extra);
const sinSesion = { chat_id: 7, autorizado: true, existe: false, paso: 0, codigo: null, signos: {}, sintomas: null };

const descodificar = (v) => (v === "N" ? null : Buffer.from(v.slice(1), "base64").toString("utf8"));

// El §4.4 del spec, copiado A MANO. Testigo independiente del workflow.
const SPEC_4_4 = [
  [2, "temperatura_c", 30.0, 45.0],
  [3, "frecuencia_cardiaca", 20, 250],
];
const SPEC_BOOL = [
  [4, "crepitantes", "s4"],
  [5, "murmullo_disminuido", "s5"],
];

// Valores REALES medidos contra `copiloto-mcp:0.1.0` el 25-sep-2026 sobre tres
// placas del conjunto de prueba de RSNA.
const R_POSITIVA = {
  probabilidad_cruda: 0.9802, probabilidad_calibrada: 0.8960419611171628,
  razon_de_verosimilitud: 30.29389781009622, umbral: 0.4258,
  clasificacion: "opacidad_probable", edad_paciente: 31,
  modelo: "efficientnet_b0_320px", auc_validacion: 0.8827, milisegundos: 155.8,
};
// LA PLACA DE LA BANDA. cruda 0,5649 >= umbral 0,4258 -> etiqueta POSITIVA,
// y razon de verosimilitud 0,87 < 1 -> la imagen RESTA probabilidades.
// patientId 03cf9ba9-dfbe-47b9-aa96-3e69432d73c3, etiqueta real 0: sin opacidad.
const R_BANDA = {
  probabilidad_cruda: 0.5649, probabilidad_calibrada: 0.1984732824427481,
  razon_de_verosimilitud: 0.8702999032570139, umbral: 0.4258,
  clasificacion: "opacidad_probable", edad_paciente: 58,
  modelo: "efficientnet_b0_320px", auc_validacion: 0.8827, milisegundos: 42.7,
};
const R_NEGATIVA = {
  probabilidad_cruda: 0.0047, probabilidad_calibrada: 0.004608294930875576,
  razon_de_verosimilitud: 0.016271632806621517, umbral: 0.4258,
  clasificacion: "sin_opacidad_probable", edad_paciente: 54,
  modelo: "efficientnet_b0_320px", auc_validacion: 0.8827, milisegundos: 42.6,
};

const sse = (obj) => `event: message\r\ndata: ${JSON.stringify(obj)}\r\n\r\n`;
const sseExito = (r) => sse({
  jsonrpc: "2.0", id: 1,
  result: { content: [{ text: JSON.stringify(r), type: "text" }],
            isError: false, structuredContent: r },
});
const sseError = (texto) => sse({
  jsonrpc: "2.0", id: 1,
  result: { content: [{ text: texto, type: "text" }], isError: true },
});
const http200 = (cuerpo) => ({ statusCode: 200, statusMessage: "OK", headers: {}, cuerpo });

const SINTOMAS = {
  fiebre: "si", tos: "con_flema", dias_evolucion: "3_a_7", disnea: "no",
  dolor_toracico: "si", asma: "no", texto_libre: null,
};
const SIGNOS = { temperatura_c: 38.2, frecuencia_cardiaca: 104, crepitantes: true, murmullo_disminuido: false };
const U = { chat_id: 7, t0: Date.now() };
const D = { chat_id: 7, t0: U.t0, sintomas: SINTOMAS, signos: SIGNOS, pregunta: "Temperatura..." };

// Todas las palabras y formas que delatan una cifra de probabilidad.
// La puntuacion se ensena con cuatro decimales (ver el nodo). Aqui hace falta
// para comprobar que la desigualdad es cierta sobre lo que se ensena.
const dec4 = (x) => Number(x).toFixed(4).replace(".", ",");

const CIFRA_DE_PROBABILIDAD = /(probabilidad|verosimilitud|calibrad|cribado|evidencia de la imagen|multiplica por|reduce a|\d,\d{2})/i;

// ==========================================================================
async function principal() {

console.log("\nA. Normalizar update: documento y foto NO son lo mismo");
ok("documento -> tipo documento, con file_id y file_size", await (async () => {
  const n = await normalizar(doc("BQACxyz", 131072));
  return n.tipo === "documento" && n.file_id === "BQACxyz" && n.file_size === 131072;
})());
ok("foto -> tipo foto (Telegram ya la recomprimio)", (await normalizar(foto())).tipo === "foto");
ok("texto -> tipo texto", (await normalizar(msg("/start"))).tipo === "texto");
ok("boton -> tipo boton + dato", await (async () => {
  const n = await normalizar(btn("s4:si"));
  return n.tipo === "boton" && n.dato === "s4:si";
})());
ok("sticker (sin texto ni fichero) -> tipo otro",
   (await normalizar({ message: { chat: { id: 7 }, sticker: {} } })).tipo === "otro");
ok("update sin chat -> se descarta", (await normalizar({ edited_channel_post: {} })) === null);
ok("t0 viene puesto (el reloj del §16)", typeof (await normalizar(msg("hola"))).t0 === "number");

console.log("\nB. NINGUN parametro que vaya a SQL puede quedar vacio");
// `stringToArray` de n8n parte por comas y DESCARTA LOS VACIOS: un valor vacio
// desaparece, la consulta sale con un parametro menos y Postgres responde
// `there is no parameter $N`. En la T5 eso dejo sin codigo al paciente que
// pulsaba «Omitir». Aqui se cierra para las cinco consultas.
const CONSUMIDOS = {
  "Abrir sesion": ["reinicio"],
  "Buscar cuestionario": ["codigo_cod"],
  "Guardar signo": ["clave", "valor_cod", "paso", "paso_actual"],
};
const CASOS_B = [
  ["/start sin sesion", sinSesion, msg("/start")],
  ["/reiniciar", ses(3), msg("/reiniciar")],
  ["codigo bien formado", ses(1), msg("k7fm2p")],
  ["temperatura con coma", ses(2), msg("38,2")],
  ["temperatura con punto", ses(2), msg("38.2")],
  ["frecuencia", ses(3), msg("104")],
  ["crepitantes si", ses(4), btn("s4:si")],
  ["crepitantes no", ses(4), btn("s4:no")],
  ["murmullo si", ses(5), btn("s5:si")],
  ["murmullo no", ses(5), btn("s5:no")],
  ["documento en el paso 6", ses(6), doc("ABC")],
  ["foto en el paso 6", ses(6), foto()],
  ["no autorizado", ses(3, { autorizado: false }), msg("hola")],
];
for (const [etiqueta, sesion, update] of CASOS_B) {
  const r = await decidir(await normalizar(update), sesion);
  const todos = ["reinicio", "codigo_cod", "valor_cod", "termina"];
  const vacios = todos.filter((k) => k in r && String(r[k]) === "");
  ok(`${etiqueta}: ningun parametro con forma de vacio`, vacios.length === 0, vacios.join(","));
  // Y los que la consulta de esa accion consume de verdad.
  const cons = r.accion === "saludo" ? CONSUMIDOS["Abrir sesion"]
    : r.accion === "buscar_codigo" ? CONSUMIDOS["Buscar cuestionario"]
    : r.accion === "guardar_signo" ? CONSUMIDOS["Guardar signo"] : [];
  const malos = cons.filter((k) => String(r[k]) === "");
  ok(`${etiqueta}: los parametros de su consulta van llenos`, malos.length === 0, malos.join(","));
}
// `Desenlace` alimenta la consulta con seis parametros; ninguno puede ir vacio.
for (const [etiqueta, entrada] of [
  ["exito", { error_cod: "N", detalle: "", resultado: R_POSITIVA, sintomas: SINTOMAS, signos: SIGNOS }],
  ["error", { error_cod: "dicom_invalido", detalle: "no es DICOM", resultado: null }],
  ["caso", { error_cod: "N", detalle: "", codigo: "K7FM2P", sintomas: SINTOMAS, signos: {} }],
]) {
  const r = await desenlace(entrada, U, D);
  const vacios = ["resultado_cod", "error_cod", "ms", "termina", "registrar"]
    .filter((k) => String(r[k]) === "");
  ok(`Desenlace (${etiqueta}): ningun parametro vacio`, vacios.length === 0, vacios.join(","));
}

console.log("\nC. LA PUERTA del §7: la baja corta en el mensaje siguiente");
for (const [etiqueta, sesion, update] of [
  ["un codigo valido", ses(1, { autorizado: false }), msg("K7FM2P")],
  ["una temperatura", ses(2, { autorizado: false }), msg("38.2")],
  ["un boton", ses(4, { autorizado: false }), btn("s4:si")],
  ["una radiografia", ses(6, { autorizado: false }), doc("ABC")],
  ["/reiniciar", ses(3, { autorizado: false }), msg("/reiniciar")],
  ["/start", sinSesion === null ? sinSesion : Object.assign({}, sinSesion, { autorizado: false }), msg("/start")],
]) {
  const r = await decidir(await normalizar(update), sesion);
  ok(`dado de baja, ${etiqueta} -> no_autorizado y nada mas`,
     r.accion === "desenlace" && r.error_cod === "no_autorizado" &&
     r.valor_cod === "N" && r.codigo_cod === "N" && r.reinicio === "N",
     JSON.stringify({ a: r.accion, e: r.error_cod }));
}

console.log("\nD. /start y /reiniciar");
ok("/start sin sesion -> saludo, paso 1", await (async () => {
  const r = await decidir(await normalizar(msg("/start")), sinSesion);
  return r.accion === "saludo" && r.paso === 1 && r.reinicio === "N";
})());
ok("/START y /start@Bot tambien", await (async () => {
  const a = await decidir(await normalizar(msg("/START")), sinSesion);
  const b = await decidir(await normalizar(msg("/start@[retirado]")), sinSesion);
  return a.accion === "saludo" && b.accion === "saludo";
})());
for (const p of [2, 3, 4, 5, 6]) {
  const r = await decidir(await normalizar(msg("/start")), ses(p));
  ok(`/start en el paso ${p} NO es destructivo (repite la pregunta)`,
     r.accion === "preguntar" && r.paso === p && r.reinicio === "N", JSON.stringify(r.accion));
}
for (const p of [1, 3, 6]) {
  const r = await decidir(await normalizar(msg("/reiniciar")), ses(p));
  ok(`/reiniciar en el paso ${p} SI es destructivo`,
     r.accion === "saludo" && r.reinicio === "S" && r.paso === 1, JSON.stringify(r.accion));
}
ok("un mensaje cualquiera sin sesion abre una",
   (await decidir(await normalizar(msg("hola")), sinSesion)).accion === "saludo");

console.log("\nE. el codigo del paciente (§5.2)");
ok("un codigo de 6 del alfabeto se busca", await (async () => {
  const r = await decidir(await normalizar(msg("K7FM2P")), ses(1));
  return r.accion === "buscar_codigo" && descodificar(r.codigo_cod) === "K7FM2P";
})());
ok("minusculas se suben a mayusculas", await (async () => {
  const r = await decidir(await normalizar(msg("  k7fm2p  ")), ses(1));
  return r.accion === "buscar_codigo" && descodificar(r.codigo_cod) === "K7FM2P";
})());
for (const malo of ["K7FM2", "K7FM2PP", "K7FM2O", "K7FM20", "K7FM2I", "K7FM2L", "k7-m2p", ""]) {
  const r = await decidir(await normalizar(msg(malo || "x")), ses(1));
  ok(`«${malo}» no se busca en la base ni se registra`,
     r.accion === "preguntar" && r.paso === 1, JSON.stringify(r.accion));
}
ok("una foto donde se espera el codigo repite la pregunta",
   (await decidir(await normalizar(foto()), ses(1))).accion === "preguntar");

console.log("\nF. los cuatro signos: rangos del §4.4, y fuera de rango NO avanza");
for (const [paso, clave, min, max] of SPEC_4_4) {
  const entero = paso === 3;
  const dentro = entero ? String(Math.round((min + max) / 2)) : ((min + max) / 2).toFixed(1);
  const r = await decidir(await normalizar(msg(dentro)), ses(paso));
  ok(`paso ${paso}: ${dentro} -> guarda en ${clave}, avanza al ${paso + 1}`,
     r.accion === "guardar_signo" && r.clave === clave && r.paso === paso + 1 &&
     r.paso_actual === paso, JSON.stringify(r));
  ok(`paso ${paso}: el valor viaja como literal JSON tipado`,
     JSON.parse(descodificar(r.valor_cod)) === Number(dentro), descodificar(r.valor_cod));
  for (const fuera of [String(min - 0.1), String(max + 0.1), "-5", "abc", ""]) {
    const q = await decidir(await normalizar(msg(fuera || " ")), ses(paso));
    ok(`paso ${paso}: «${fuera}» NO avanza y se queda en el ${paso}`,
       q.accion === "preguntar" && q.paso === paso && q.clave === "",
       JSON.stringify({ a: q.accion, p: q.paso }));
  }
}
ok("38,2 y 38.2 son el mismo valor (§4.4)", await (async () => {
  const a = await decidir(await normalizar(msg("38,2")), ses(2));
  const b = await decidir(await normalizar(msg("38.2")), ses(2));
  return a.valor_cod === b.valor_cod && JSON.parse(descodificar(a.valor_cod)) === 38.2;
})());
ok("la frecuencia cardiaca no acepta decimales (es un entero)",
   (await decidir(await normalizar(msg("104.5")), ses(3))).accion === "preguntar");
ok("30,0 y 45,0 SI se aceptan (los extremos del rango)", await (async () => {
  const a = await decidir(await normalizar(msg("30,0")), ses(2));
  const b = await decidir(await normalizar(msg("45,0")), ses(2));
  return a.accion === "guardar_signo" && b.accion === "guardar_signo";
})());

console.log("\nG. los botones: un teclado VIEJO no contesta la pregunta de ahora");
for (const [paso, clave, prefijo] of SPEC_BOOL) {
  for (const [valor, esperado] of [["si", true], ["no", false]]) {
    const r = await decidir(await normalizar(btn(`${prefijo}:${valor}`)), ses(paso));
    ok(`paso ${paso}: ${prefijo}:${valor} -> ${clave} = ${esperado}`,
       r.accion === "guardar_signo" && r.clave === clave &&
       JSON.parse(descodificar(r.valor_cod)) === esperado && r.paso === paso + 1,
       JSON.stringify(r));
  }
}
// EL fallo silencioso de la tarea: sin el prefijo, el «Si» de crepitantes se
// guardaria en `murmullo_disminuido` y el mensaje final saldria perfecto.
const cruzado = await decidir(await normalizar(btn("s4:si")), ses(5));
ok("el boton de crepitantes pulsado en el paso del murmullo NO se guarda",
   cruzado.accion === "preguntar" && cruzado.paso === 5 && cruzado.clave === "",
   JSON.stringify(cruzado));
const cruzado2 = await decidir(await normalizar(btn("s5:no")), ses(4));
ok("y al contrario tampoco",
   cruzado2.accion === "preguntar" && cruzado2.paso === 4 && cruzado2.clave === "");
ok("un callback ajeno se descarta sin contestar",
   (await decidir(await normalizar(btn("borrar:todo")), ses(4))).accion === "nada");
ok("un valor que no es si/no se descarta",
   (await decidir(await normalizar(btn("s4:quiza")), ses(4))).accion === "nada");
ok("texto donde se esperaba un boton repite la pregunta", await (async () => {
  const r = await decidir(await normalizar(msg("si claro")), ses(4));
  return r.accion === "preguntar" && r.paso === 4 && r.teclado === "crepitantes";
})());

console.log("\nH. la radiografia (§9)");
ok("un documento en el paso 6 -> clasificar, con su file_id", await (async () => {
  const r = await decidir(await normalizar(doc("BQACxyz")), ses(6));
  return r.accion === "clasificar" && r.file_id === "BQACxyz";
})());
const rFoto = await decidir(await normalizar(foto()), ses(6));
ok("una FOTO -> envio_como_foto, y el paso no cambia",
   rFoto.accion === "desenlace" && rFoto.error_cod === "envio_como_foto" &&
   rFoto.paso_actual === 6, JSON.stringify(rFoto.error_cod));
const rGrande = await decidir(await normalizar(doc("BIG", 21 * 1024 * 1024)), ses(6));
ok("mas de 20 MB -> fichero_no_descargable, sin pedirle nada a Telegram",
   rGrande.accion === "desenlace" && rGrande.error_cod === "fichero_no_descargable");
ok("exactamente 20 MiB todavia se intenta",
   (await decidir(await normalizar(doc("B", 20 * 1024 * 1024)), ses(6))).accion === "clasificar");
ok("texto en el paso 6 repite la peticion del archivo", await (async () => {
  const r = await decidir(await normalizar(msg("ya va")), ses(6));
  return r.accion === "preguntar" && r.paso === 6;
})());
ok("un documento en el paso 2 (temperatura) NO se clasifica",
   (await decidir(await normalizar(doc("X")), ses(2))).accion === "preguntar");

console.log("\nH2. A base64: el cuerpo JSON-RPC del §10.1 se arma en JavaScript");
// Se arma AQUI y no en una expresion del nodo HTTP. Medido contra el n8n real el
// 25-sep-2026: `={{ JSON.stringify({jsonrpc:'2.0',...}) }}` falla con
// «invalid syntax» -las llaves anidadas dejan `}}}` y el separador de
// expresiones corta donde no debe- y la peticion no llega a salir. El sintoma
// habria sido que TODAS las radiografias contestaran `copiloto_no_responde`.
//
// Y los TRES accesos al binario, con el `this` que corresponde a cada uno. La
// version anterior de este arnes fabricaba siempre el `this` con `helpers`
// dentro, asi que estructuralmente no podia detectar que en esta instalacion de
// n8n el accesor fuera otro: probaba su propio andamio.
const AYUDANTE_OK = { getBinaryDataBuffer: async () => Buffer.from("hola") };
const AYUDANTE_ROTO = {
  getBinaryDataBuffer: async () => { throw new Error("binario en disco"); } };
const ENTRADA_BIN = { json: {},
  binary: { data: { data: Buffer.from("hola").toString("base64") } } };
const B64_HOLA = Buffer.from("hola").toString("base64");

async function aBase64(opciones) {
  const r = await correr(codigo("A base64"), ENTRADA_BIN,
                         { Decidir: { chat_id: 7, t0: 123 } }, opciones);
  return r[0].json;
}
const CASOS_BIN = [
  ["this.helpers", { thisArg: { helpers: AYUDANTE_OK } }, "ayudante"],
  ["helpers suelto en el ambito", { helpersEnAmbito: AYUDANTE_OK }, "ayudante"],
  ["NINGUN accesor: cae a binary.data.data", {}, "binario"],
  ["el ayudante existe pero lanza", { thisArg: { helpers: AYUDANTE_ROTO } }, "binario"],
];
for (const [etiqueta, opciones, via] of CASOS_BIN) {
  const s = await aBase64(opciones);
  const cuerpo = JSON.parse(s.cuerpo_jsonrpc);
  ok(`${etiqueta}: el cuerpo es el JSON-RPC del §10.1 con el base64 correcto`,
     cuerpo.jsonrpc === "2.0" && cuerpo.method === "tools/call" &&
     cuerpo.params.name === "clasificar_radiografia" &&
     cuerpo.params.arguments.dicom_base64 === B64_HOLA, s.cuerpo_jsonrpc);
  ok(`${etiqueta}: y dice por donde se resolvio («${via}»)`, s.via === via, s.via);
  ok(`${etiqueta}: el base64 no sale por ningun otro campo (§5.4)`,
     !("dicom_base64" in s) &&
     Object.keys(s).sort().join(",") === "chat_id,cuerpo_jsonrpc,t0,via",
     Object.keys(s).join(","));
}
// Lo que esto NO prueba, y hay que decirlo: si en la instalacion del cliente los
// binarios viven en disco Y el accesor del ayudante no esta, `binary.data.data`
// vendria vacio y no hay forma de simularlo desde aqui. El campo `via` es lo que
// permite verlo desde fuera; se midio con una sonda en el n8n real (ver informe).
ok("sin binario por ningun camino, el base64 va vacio y lo dice", await (async () => {
  const r = await correr(codigo("A base64"), { json: {}, binary: {} },
                         { Decidir: { chat_id: 7, t0: 1 } }, {});
  const s = r[0].json;
  return s.via === "nada" &&
         JSON.parse(s.cuerpo_jsonrpc).params.arguments.dicom_base64 === "";
})());
ok("la expresion del nodo HTTP no lleva llaves anidadas", (() => {
  const j = nodo("Llamar al copiloto").parameters.jsonBody;
  return j === "={{ $json.cuerpo_jsonrpc }}";
})(), nodo("Llamar al copiloto").parameters.jsonBody);

console.log("\nI. Leer respuesta, contra las respuestas LITERALES del contenedor");
const dResp = { chat_id: 7, t0: Date.now(), sintomas: SINTOMAS, signos: SIGNOS };
for (const [etiqueta, r] of [["positiva", R_POSITIVA], ["banda", R_BANDA], ["negativa", R_NEGATIVA]]) {
  const s = await leerRespuesta(http200(sseExito(r)), dResp);
  ok(`${etiqueta}: structuredContent leido entero, sin error`,
     s.error_cod === "N" && s.resultado &&
     s.resultado.probabilidad_cruda === r.probabilidad_cruda &&
     s.resultado.razon_de_verosimilitud === r.razon_de_verosimilitud &&
     JSON.stringify(s.resultado) === JSON.stringify(r), JSON.stringify(s.error_cod));
}
ok("sin structuredContent se cae a result.content[0].text (§10.2)", await (async () => {
  const s = await leerRespuesta(http200(sse({
    jsonrpc: "2.0", id: 1,
    result: { content: [{ text: JSON.stringify(R_POSITIVA), type: "text" }], isError: false },
  })), dResp);
  return s.error_cod === "N" && s.resultado.probabilidad_cruda === 0.9802;
})());
// Los textos de error son los que el contenedor devolvio de verdad.
const ERRORES_MEDIDOS = [
  ["fuera_de_alcance",
   "Error executing tool clasificar_radiografia: fuera_de_alcance: El paciente tiene 12 anios y el modelo solo es valido entre 18 y 100.",
   "El paciente tiene 12 anios y el modelo solo es valido entre 18 y 100."],
  ["dicom_invalido",
   "Error executing tool clasificar_radiografia: dicom_invalido: El fichero no es un DICOM legible: File is missing DICOM File Meta Information header or the 'DICM' prefix is missing from the header. Use force=True to force reading.",
   "El fichero no es un DICOM legible: File is missing DICOM File Meta Information header or the 'DICM' prefix is missing from the header. Use force=True to force reading."],
  ["base64_invalido",
   "Error executing tool clasificar_radiografia: base64_invalido: Only base64 data is allowed",
   "Only base64 data is allowed"],
  ["payload_excesivo",
   "Error executing tool clasificar_radiografia: payload_excesivo: 5242881 bytes, maximo 5242880",
   "5242881 bytes, maximo 5242880"],
];
for (const [cod, texto, detalle] of ERRORES_MEDIDOS) {
  const s = await leerRespuesta(http200(sseError(texto)), dResp);
  ok(`isError -> codigo ${cod} buscado DENTRO del texto`, s.error_cod === cod, s.error_cod);
  ok(`   y el detalle es lo que queda tras el segundo ':'`, s.detalle === detalle, s.detalle);
  ok(`   nunca 'Error executing tool ...' como codigo`,
     !s.error_cod.startsWith("Error executing"), s.error_cod);
  ok(`   y no trae resultado`, s.resultado === null);
}
ok("un isError con un codigo que no conocemos -> error_no_reconocido", await (async () => {
  const s = await leerRespuesta(http200(sseError(
    "Error executing tool clasificar_radiografia: gremlins_en_el_gpu: se fue la luz")), dResp);
  return s.error_cod === "error_no_reconocido" && s.detalle.includes("gremlins");
})());
// §10.4: el 413 del TRANSPORTE. Cuerpo medido: "Request body too large", sin SSE.
const s413 = await leerRespuesta(
  { statusCode: 413, statusMessage: "Payload Too Large", headers: {}, cuerpo: "Request body too large" }, dResp);
ok("HTTP 413 -> payload_excesivo_transporte, y no se intenta parsear",
   s413.error_cod === "payload_excesivo_transporte" && s413.resultado === null, s413.error_cod);
ok("HTTP 500 -> copiloto_no_responde", await (async () => {
  const s = await leerRespuesta({ statusCode: 500, headers: {}, cuerpo: "boom" }, dResp);
  return s.error_cod === "copiloto_no_responde";
})());
ok("un item SIN statusCode (timeout, conexion rechazada) -> copiloto_no_responde",
   (await leerRespuesta({ error: { message: "timeout of 30000ms exceeded" } }, dResp)).error_cod
   === "copiloto_no_responde");
ok("200 con algo que no es el SSE del §10.2 -> error_no_reconocido", await (async () => {
  const s = await leerRespuesta(http200("<html>502 Bad Gateway</html>"), dResp);
  return s.error_cod === "error_no_reconocido" && s.detalle.includes("502");
})());
ok("200 con SSE pero structuredContent incompleto -> error_no_reconocido", await (async () => {
  const s = await leerRespuesta(http200(sse({
    jsonrpc: "2.0", id: 1, result: { isError: false, structuredContent: { hola: 1 } },
  })), dResp);
  return s.error_cod === "error_no_reconocido";
})());
ok("el base64 del DICOM NO viaja en la salida de este nodo (§5.4)", await (async () => {
  const s = await leerRespuesta(http200(sseExito(R_POSITIVA)), dResp);
  return !("dicom_base64" in s) && !("cuerpo" in s);
})());

console.log("\nJ. §8: TRES BLOQUES ROTULADOS, y la etiqueta nunca con la RV");
async function texto(r) {
  const s = await desenlace(
    { error_cod: "N", detalle: "", resultado: r, sintomas: SINTOMAS, signos: SIGNOS }, U, D);
  return s;
}
for (const [etiqueta, r] of [["positiva", R_POSITIVA], ["banda", R_BANDA], ["negativa", R_NEGATIVA]]) {
  const s = await texto(r);
  const t = s.texto;
  const bloques = t.split("\n\n");
  ok(`${etiqueta}: los cuatro rotulos del informe estan`,
     t.includes("CRIBADO —") && t.includes("EVIDENCIA DE LA IMAGEN —") &&
     t.includes("REFERIDO POR EL PACIENTE —") && t.includes("EXPLORADO —"),
     JSON.stringify(t.slice(0, 80)));
  ok(`${etiqueta}: bloques separados por linea en blanco`, bloques.length >= 4, String(bloques.length));
  // LA REGLA DEL §8: nunca en el mismo renglon.
  const renglonCribado = t.split("\n").find((l) => l.includes("CRIBADO —"));
  ok(`${etiqueta}: el renglon del cribado no lleva la RV ni la calibrada`,
     !/verosimilitud|calibrad|multiplica|reduce a/i.test(renglonCribado), renglonCribado);
  const renglonEvidencia = t.split("\n").find((l) => l.includes("EVIDENCIA DE LA IMAGEN —"));
  ok(`${etiqueta}: el renglon de la evidencia no lleva la etiqueta del cribado`,
     !/opacidad probable|umbral|puntuación/i.test(renglonEvidencia), renglonEvidencia);
  ok(`${etiqueta}: dice que no es un diagnostico`, t.includes("no es un diagnóstico"));
  ok(`${etiqueta}: el resultado se guarda entero y tal cual (§5.3)`,
     JSON.stringify(JSON.parse(descodificar(s.resultado_cod))) === JSON.stringify(r));
  ok(`${etiqueta}: termina la conversacion y registra`,
     s.termina === "S" && s.registrar === "S");
}
const tPos = (await texto(R_POSITIVA)).texto;
ok("positiva: etiqueta «opacidad probable»", tPos.includes("CRIBADO — opacidad probable"));
ok("positiva: puntuacion con CUATRO decimales y >= umbral",
   tPos.includes("puntuación 0,9802 ≥ umbral 0,4258"), tPos.split("\n")[1]);
ok("positiva: la RV con un decimal por encima de 10",
   tPos.includes("multiplica por 30,3 las probabilidades"), tPos);
ok("positiva: calibrada con dos decimales", tPos.includes("probabilidad calibrada 0,90"));
ok("positiva: SIN aviso de discrepancia", !tPos.includes("⚠️"));
ok("positiva: el punto de operacion se declara",
   tPos.includes("sens. 0,88 / esp. 0,70"));

const tNeg = (await texto(R_NEGATIVA)).texto;
ok("negativa: etiqueta «sin opacidad probable»", tNeg.includes("CRIBADO — sin opacidad probable"));
ok("negativa: la desigualdad va al otro lado",
   tNeg.includes("puntuación 0,0047 < umbral 0,4258"), tNeg.split("\n")[1]);
ok("negativa: la RV reduce, con dos decimales",
   tNeg.includes("reduce a 0,02× las probabilidades"), tNeg);
ok("negativa: SIN aviso (la etiqueta y la RV coinciden)", !tNeg.includes("⚠️"));
// La cota del calibrador no se puede deshacer al presentarla: 344 de las 3 811
// placas de prueba (9,03 %) tienen la calibrada por debajo de 0,005 y con dos
// decimales a secas saldrian como «0,00», que es certeza de ausencia fabricada.
// El recuento se hace calibrando la cruda SIN redondear, que es lo que
// `inferencia.py` calibra; con la cruda de 4 decimales que viaja en la respuesta
// saldrian 345, y esa es la cifra equivocada.
ok("negativa: la calibrada NUNCA se ensena como 0,00",
   tNeg.includes("probabilidad calibrada < 0,01") && !tNeg.includes("calibrada 0,00"),
   tNeg.split("\n").find((l) => l.includes("EVIDENCIA")));
// §8: «La plantilla es una sola; solo cambian los valores y el aviso.» Lo que
// cambia de redaccion es lo que el propio §8 cambia: la etiqueta, el
// comparador, y «multiplica por N» frente a «reduce a N×».
ok("negativa: la plantilla es la MISMA que la positiva", await (async () => {
  const quitar = (x) => x
    .replace(/< 0,01|> 0,99/g, "#")
    .replace(/multiplica por ([0-9,]+)/g, "V #")
    .replace(/reduce a ([0-9,]+)×/g, "V #")
    .replace(/(sin )?opacidad probable/g, "E")
    .replace(/[0-9,]+/g, "#")
    .replace(/≥|</g, "C");
  return quitar(tNeg) === quitar(tPos);
})(), "solo cambian los valores");

// ---- EL CRITERIO 6 ----
const sBanda = await texto(R_BANDA);
const tBanda = sBanda.texto;
ok("BANDA: la etiqueta es positiva", tBanda.includes("CRIBADO — opacidad probable"));
ok("BANDA: la evidencia dice REDUCE, no multiplica",
   tBanda.includes("reduce a 0,87× las probabilidades") && !tBanda.includes("multiplica"), tBanda);
ok("BANDA: el aviso explicito esta", tBanda.includes("⚠️"));
ok("BANDA: el aviso dice que la imagen no apoya el diagnostico",
   /no apoya el diagnóstico/.test(tBanda) && /Decide la clínica/.test(tBanda));
ok("BANDA: el aviso va en el bloque de la EVIDENCIA, no en el del cribado", (() => {
  const bloques = tBanda.split("\n\n");
  const iAviso = bloques.findIndex((b) => b.includes("⚠️"));
  return iAviso >= 0 && bloques[iAviso].includes("EVIDENCIA DE LA IMAGEN");
})());
ok("BANDA: la calibrada (0,20) tambien se ve",
   tBanda.includes("probabilidad calibrada 0,20"), tBanda);

console.log("\nK. §8: los dos bloques de la clinica");
ok("los sintomas salen con las palabras del §4.4",
   tPos.includes("REFERIDO POR EL PACIENTE — fiebre sí, tos con flema, 3 a 7 días, sin falta de aire, dolor torácico al respirar, sin asma"),
   tPos.split("\n").find((l) => l.includes("REFERIDO")));
ok("«asma: no sabe» se ensena tal cual (§4.4: no se coacciona a booleano)",
   (await desenlace({ error_cod: "N", resultado: R_POSITIVA,
                      sintomas: Object.assign({}, SINTOMAS, { asma: "no_se" }), signos: SIGNOS },
                    U, D)).texto.includes("asma: no sabe"));
ok("los signos salen con sus unidades",
   tPos.includes("EXPLORADO — 38,2 °C, 104 lpm, crepitantes sí, murmullo normal"),
   tPos.split("\n").find((l) => l.includes("EXPLORADO")));
ok("murmullo disminuido se dice cuando lo esta",
   (await desenlace({ error_cod: "N", resultado: R_POSITIVA, sintomas: SINTOMAS,
                      signos: Object.assign({}, SIGNOS, { murmullo_disminuido: true }) },
                    U, D)).texto.includes("murmullo disminuido"));
// El texto libre YA NO ESTA en el informe: va en un mensaje aparte. Lo que aqui
// se comprueba es que el bloque de la clinica no cambia por lo que el paciente
// escriba; el mensaje aparte se comprueba entero en la seccion L2.
const veneno = "me duele *mucho* el _pecho_, y `esto` tambien";
const sLibre = await desenlace({ error_cod: "N", resultado: R_POSITIVA,
  sintomas: Object.assign({}, SINTOMAS, { texto_libre: veneno }), signos: SIGNOS }, U, D);
ok("el informe NO lleva el texto libre del paciente", !sLibre.texto.includes(veneno),
   sLibre.texto.split("\n").find((l) => l.includes("EXPLORADO")));
ok("y va entero e intacto en el mensaje aparte",
   sLibre.texto_paciente.includes(veneno), sLibre.texto_paciente);
ok("el informe con texto libre es IDENTICO al informe sin el", sLibre.texto === tPos,
   "esa igualdad es la regla del informe");

console.log("\nL. §9: las once ramas, su estado despues, y NINGUNA CIFRA");
// La tabla del §9 del spec, copiada A MANO. Testigo independiente.
const SPEC_9 = [
  ["envio_como_foto", false],
  ["dicom_invalido", false],
  ["fuera_de_alcance", true],
  ["edad_desconocida", true],
  ["base64_invalido", false],
  ["payload_excesivo", false],
  ["payload_excesivo_transporte", false],
  ["codigo_invalido", false],
  ["fichero_no_descargable", false],
  ["copiloto_no_responde", false],
  ["error_no_reconocido", true],
];
const DETALLES = {
  fuera_de_alcance: "El paciente tiene 12 anios y el modelo solo es valido entre 18 y 100.",
  edad_desconocida: "La cabecera DICOM no declara una edad interpretable. No se asume que el paciente sea adulto: pide la edad al profesional.",
  dicom_invalido: "El fichero no es un DICOM legible: File is missing DICOM File Meta Information header",
  payload_excesivo: "5242881 bytes, maximo 5242880",
  base64_invalido: "Only base64 data is allowed",
};
for (const [cod, termina] of SPEC_9) {
  const s = await desenlace({ error_cod: cod, detalle: DETALLES[cod] || "",
                              resultado: null, sintomas: SINTOMAS, signos: SIGNOS }, U, D);
  ok(`${cod}: hay mensaje`, s.texto.length > 10, s.texto.slice(0, 40));
  ok(`${cod}: termina = ${termina}`, s.termina === (termina ? "S" : "N"), s.termina);
  ok(`${cod}: se registra en consultas`, s.registrar === "S");
  ok(`${cod}: el codigo va a consultas.error`,
     String(descodificar(s.error_cod)).startsWith(cod), descodificar(s.error_cod));
  // EL CRITERIO 7, para las once.
  ok(`${cod}: NINGUNA cifra de probabilidad en el mensaje`,
     !CIFRA_DE_PROBABILIDAD.test(s.texto), s.texto.replace(/\n/g, " | "));
  ok(`${cod}: y NINGUN resultado junto al rechazo`, s.resultado_cod === "N");
}
ok("no_autorizado tambien se registra, y sin cifras", await (async () => {
  const s = await desenlace({ error_cod: "no_autorizado", detalle: "", resultado: null }, U, D);
  return s.registrar === "S" && descodificar(s.error_cod) === "no_autorizado" &&
         !CIFRA_DE_PROBABILIDAD.test(s.texto) && s.resultado_cod === "N" && s.termina === "N";
})());
const sEdad = await desenlace({ error_cod: "fuera_de_alcance",
  detalle: DETALLES.fuera_de_alcance, resultado: null }, U, D);
ok("el rechazo por edad llega como DECISION CLINICA, no como fallo tecnico",
   sEdad.texto.includes("NO PROCEDE") && sEdad.texto.includes("Decida clínicamente"), sEdad.texto);
ok("y relata el detalle del servidor, con la edad que venia DENTRO del texto",
   sEdad.texto.includes("El paciente tiene 12 anios"), sEdad.texto);
ok("error_no_reconocido guarda el texto INTEGRO en consultas.error (§9)", await (async () => {
  const s = await desenlace({ error_cod: "error_no_reconocido",
    detalle: "gremlins_en_el_gpu: se fue la luz", resultado: null }, U, D);
  return descodificar(s.error_cod).includes("gremlins_en_el_gpu: se fue la luz");
})());
ok("un codigo que la tabla no conoce no inventa un mensaje", await (async () => {
  const s = await desenlace({ error_cod: "algo_nuevo", detalle: "", resultado: null }, U, D);
  return s.termina === "S" && descodificar(s.error_cod) === "error_no_reconocido: algo_nuevo" &&
         !CIFRA_DE_PROBABILIDAD.test(s.texto);
})());
// LA RED: si un detalle del servidor trajera una cifra con forma de
// probabilidad, el mensaje se cae al texto fijo en vez de emitirla.
ok("un detalle con una cifra de probabilidad se descarta, no se emite", await (async () => {
  const s = await desenlace({ error_cod: "dicom_invalido",
    detalle: "la probabilidad calibrada era 0,85 pero fallo el lector", resultado: null }, U, D);
  return !CIFRA_DE_PROBABILIDAD.test(s.texto) && s.texto.includes("No pude leer");
})());

console.log("\nL2. LA REGLA DEL INFORME: ni un caracter que haya escrito el paciente");
// La regla esta escrita al REVES que en la ronda anterior, y por eso esta seccion
// tambien. Antes el texto del paciente entraba en el informe y se le quitaban los
// caracteres peligrosos; esa defensa se rodeo por tres vias, y la tercera no la
// arregla ningun filtro: con 447 caracteres y ningun caracter de control, el
// cliente de Telegram envuelve la burbuja y **una fila renderizada empieza por el
// rotulo**. «Cabe en una linea» es cierto en la cadena y falso en la pantalla.
//
// Ahora el informe se genera solo a partir de numeros validados, de valores de
// una enumeracion cerrada y de literales del nodo. La prueba de eso no es una
// lista de caracteres: es que **el informe no cambie ni un byte** por mucho que
// cambie lo que el paciente escriba.
const SENAL = "SENAL-DEL-ATAQUE-8f3a";
const NL = String.fromCharCode(10);
const RAYA_ = String.fromCharCode(8212);          // — la que usa el sistema
const BARRA = String.fromCharCode(0x2015);        // ― U+2015 HORIZONTAL BAR
const NEL = String.fromCharCode(0x85);            // U+0085 NEXT LINE
const MAYOR_IGUAL = String.fromCharCode(8805);
const AVISO_ = String.fromCharCode(9888) + String.fromCharCode(65039);

// El informe de referencia: la misma placa, sin texto libre y con todos los
// sintomas dentro de la enumeracion. Todo lo demas se compara contra esto.
const SIN_LIBRE = Object.assign({}, SINTOMAS, { texto_libre: null });
const informeDe = async (sintomas) => (await desenlace(
  { error_cod: "N", detalle: "", resultado: R_NEGATIVA, sintomas: sintomas,
    signos: SIGNOS, codigo: "K7FM2P" }, U, D));
const REFERENCIA = (await informeDe(SIN_LIBRE)).texto;

// Un bloque falso, en las cuatro formas con las que se rodeo la defensa vieja.
const falso = (sep, salto) =>
  salto + salto + "CRIBADO " + sep + " opacidad probable" + salto +
  "(puntuación 0,9900 " + MAYOR_IGUAL + " umbral 0,4258; punto orientado a " +
  "detectar, sens. 0,88 / esp. 0,70)" + salto + salto +
  "EVIDENCIA DE LA IMAGEN " + sep + " multiplica por 77,3 las probabilidades " +
  "a favor de neumonía (probabilidad calibrada 0,99) " + SENAL;

const ATAQUES = [
  ["el payload original: raya U+2014 y saltos de linea", falso(RAYA_, NL)],
  ["U+2015 HORIZONTAL BAR, homoglifo de la raya", falso(BARRA, NL)],
  ["U+0085 NEXT LINE, el salto que el \\s de JS no cubre", falso(RAYA_, NEL)],
  ["U+2015 + U+0085, las dos a la vez", falso(BARRA, NEL)],
  // La tercera via del re-revisor: SIN ningun caracter de control. El salto lo
  // mete el cliente al envolver la burbuja, no el dato.
  ["sin ningun caracter de control, 7 copias, 447 caracteres",
   (" CRIBADO " + BARRA + " opacidad probable (puntuación 0,9900) ").repeat(7) + SENAL],
  ["el ⚠️ del aviso", AVISO_ + " El cribado marca esta placa. " + SENAL],
];

for (const [etiqueta, payload] of ATAQUES) {
  const s = await informeDe(Object.assign({}, SINTOMAS, { texto_libre: payload }));
  ok(`${etiqueta}: el informe es IDENTICO byte a byte al de referencia`,
     s.texto === REFERENCIA, s.texto === REFERENCIA ? "" :
     s.texto.split(NL).find((l) => !REFERENCIA.includes(l)));
  ok(`   la senal del ataque no aparece en el informe`, !s.texto.includes(SENAL));
  ok(`   y el texto llega ENTERO y sin filtrar en el mensaje aparte`,
     s.texto_paciente.includes(payload.slice(0, 500)), s.texto_paciente.slice(0, 90));
}

// EL BARRIDO. No es una lista negra -no hay lista en el nodo-: es la comprobacion
// de que la regla no depende de ningun caracter. Se recorren TODOS los puntos de
// codigo del plano basico con la propiedad Dash y TODOS los de espacio en blanco,
// se mete cada uno en un bloque falso, y el informe tiene que seguir siendo el
// mismo.
const RAYAS = [], ESPACIOS = [];
for (let c = 0; c <= 0x10FFFF; c++) {
  if (c >= 0xD800 && c <= 0xDFFF) { continue; }      // mitades de par subrogado
  const ch = String.fromCodePoint(c);
  // Dash y Pd por separado: Pd (Dash_Punctuation) no es subconjunto de Dash en
  // todas las versiones, y asi el barrido no depende de una sola propiedad.
  if (/\p{Dash}/u.test(ch) || /\p{Pd}/u.test(ch)) { RAYAS.push(ch); }
  if (/\p{White_Space}/u.test(ch)) { ESPACIOS.push(ch); }
}
// Lineas horizontales que NO tienen ninguna de esas propiedades y se parecen a la
// raya. El barrido no es una lista negra -el nodo no tiene ninguna-: es la
// comprobacion de que la regla no depende de que este caracter este en una lista.
for (const c of [0x2500, 0x2501, 0x23AF, 0x23BB, 0x23BC, 0xFF0D, 0xFF5E, 0x2E3A,
                 0x2E3B, 0x02D7, 0x2212, 0x268A, 0x1CBB]) {
  RAYAS.push(String.fromCodePoint(c));
}
ok(`el barrido cubre ${RAYAS.length} caracteres con forma de raya`,
   RAYAS.length >= 40, String(RAYAS.length));
ok(`y los ${ESPACIOS.length} de espacio en blanco de Unicode`,
   ESPACIOS.length >= 25, String(ESPACIOS.length));
// Medido con node v24 / Unicode 17: de los 25 espacios de Unicode, `\s` de
// JavaScript cubre 24 y se deja U+0085 NEXT LINE. Es el hueco por el que se colo
// la defensa vieja, y se deja fijado por si alguna vez vuelve a importar.
ok("U+0085 es el UNICO espacio de Unicode que el \\s de JS no cubre", (() => {
  const fuera = ESPACIOS.filter((ch) => !/\s/.test(ch))
                        .map((ch) => ch.codePointAt(0));
  return fuera.length === 1 && fuera[0] === 0x85;
})(), ESPACIOS.filter((ch) => !/\s/.test(ch))
              .map((ch) => "U+" + ch.codePointAt(0).toString(16)).join(" "));
let malos = [];
for (const ch of RAYAS) {
  const s = await informeDe(Object.assign({}, SINTOMAS,
    { texto_libre: falso(ch, NL) }));
  if (s.texto !== REFERENCIA) { malos.push("Dash U+" + ch.charCodeAt(0).toString(16)); }
}
for (const ch of ESPACIOS) {
  const s = await informeDe(Object.assign({}, SINTOMAS,
    { texto_libre: falso(RAYA_, ch) }));
  if (s.texto !== REFERENCIA) { malos.push("Espacio U+" + ch.charCodeAt(0).toString(16)); }
}
ok(`ninguno de los ${RAYAS.length + ESPACIOS.length} caracteres cambia el informe`,
   malos.length === 0, malos.slice(0, 8).join(" "));

console.log("\nL3. el otro canal del paciente: los VALORES del cuestionario");
// El bloque REFERIDO POR EL PACIENTE sale de una enumeracion cerrada. Un valor
// que no este en ella se declara como no reconocido y su contenido se va al
// mensaje aparte: el informe no imprime nada que no salga de la tabla del §4.4.
for (const [etiqueta, valor] of [
  ["un bloque falso", falso(BARRA, NEL)],
  ["`constructor`, que llega a Object.prototype", "constructor"],
  ["`__proto__`", "__proto__"],
  ["`toString`", "toString"],
  ["`hasOwnProperty`", "hasOwnProperty"],
  ["`valueOf`", "valueOf"],
  ["`isPrototypeOf`", "isPrototypeOf"],
  ["`propertyIsEnumerable`", "propertyIsEnumerable"],
]) {
  const s = await informeDe(Object.assign({}, SIN_LIBRE, { fiebre: valor }));
  ok(`fiebre = ${etiqueta}: el informe lo declara sin imprimirlo`,
     s.texto.includes("REFERIDO POR EL PACIENTE — fiebre: (valor no reconocido),"),
     s.texto.split(NL).find((l) => l.includes("REFERIDO")));
  ok(`   nada de Object.prototype se cuela en el informe`,
     !/native code|function Object/.test(s.texto), s.texto.slice(0, 60));
  ok(`   y el valor de verdad NO se pierde: va al mensaje aparte`,
     s.texto_paciente.includes(valor) &&
     s.texto_paciente.includes("Respuesta a «fiebre» que no reconozco"),
     s.texto_paciente.slice(0, 120));
  ok(`   los otros cinco sintomas siguen saliendo bien`,
     s.texto.includes("tos con flema, 3 a 7 días"), s.texto.split(NL)[5]);
}
ok("dos valores distintos no reconocidos dan el MISMO informe", await (async () => {
  const a = await informeDe(Object.assign({}, SIN_LIBRE, { fiebre: "constructor" }));
  const b = await informeDe(Object.assign({}, SIN_LIBRE, { fiebre: falso(BARRA, NL) }));
  return a.texto === b.texto;
})(), "el informe no depende del contenido del valor");
ok("un valor que SI esta en la enumeracion sale con su frase",
   (await informeDe(Object.assign({}, SIN_LIBRE, { fiebre: "no_se" })))
     .texto.includes("fiebre: no sabe"));
ok("un valor que no es cadena tampoco se imprime", await (async () => {
  const s = await informeDe(Object.assign({}, SIN_LIBRE, { fiebre: 42 }));
  return s.texto.includes("fiebre: (valor no reconocido)") &&
         s.texto_paciente.includes("42");
})());

console.log("\nL4. el mensaje aparte: cabecera, cierre, y quien escribio que");
const sAp = await informeDe(Object.assign({}, SINTOMAS,
  { texto_libre: falso(BARRA, NEL) }));
ok("empieza por la cabecera del sistema",
   sAp.texto_paciente.startsWith("LO QUE ESCRIBIÓ EL PACIENTE, TAL CUAL"),
   sAp.texto_paciente.split(NL)[0]);
ok("la cabecera lleva el caso", sAp.texto_paciente.includes("(caso K7FM2P)"));
ok("dice que el informe es el mensaje anterior",
   sAp.texto_paciente.includes("No forma parte del informe clínico, que es el " +
                               "mensaje anterior."));
ok("y termina con el cierre del sistema",
   sAp.texto_paciente.endsWith("Fin de lo que escribió el paciente."),
   sAp.texto_paciente.slice(-45));
ok("el texto del paciente queda ENCERRADO entre dos frases del sistema", (() => {
  const i = sAp.texto_paciente.indexOf(SENAL);
  return i > sAp.texto_paciente.indexOf("No forma parte del informe") &&
         i < sAp.texto_paciente.indexOf("Fin de lo que escribió");
})());
ok("sin texto libre y con todo reconocido, NO hay mensaje aparte",
   (await informeDe(SIN_LIBRE)).texto_paciente === "",
   JSON.stringify((await informeDe(SIN_LIBRE)).texto_paciente));
ok("un texto libre de solo espacios tampoco lo genera",
   (await informeDe(Object.assign({}, SINTOMAS, { texto_libre: "   " + NL })))
     .texto_paciente === "");
ok("se recorta a 500 caracteres (§4.4)", await (async () => {
  const s = await informeDe(Object.assign({}, SINTOMAS,
    { texto_libre: "x".repeat(900) }));
  return s.texto_paciente.split("x").length - 1 === 500;
})());
ok("las ramas de error NO mandan mensaje aparte", await (async () => {
  for (const [cod] of SPEC_9) {
    const s = await desenlace({ error_cod: cod, detalle: "", resultado: null,
      sintomas: Object.assign({}, SINTOMAS, { texto_libre: falso(RAYA_, NL) }),
      signos: SIGNOS }, U, D);
    if (s.texto_paciente !== "") { return false; }
  }
  return true;
})());

console.log("\nL5. el punto de operacion solo se afirma si es el que se midio (H6)");
const OTRO_UMBRAL = Object.assign({}, R_POSITIVA, {umbral: 0.5, clasificacion: "opacidad_probable"});
const tOtro = (await desenlace({ error_cod: "N", detalle: "", resultado: OTRO_UMBRAL,
  sintomas: SINTOMAS, signos: SIGNOS }, U, D)).texto;
ok("con umbral 0,4258 se declaran sens. y esp.", tPos.includes("sens. 0,88 / esp. 0,70"));
ok("con OTRO umbral, la frase desaparece en vez de describir otro punto de la ROC",
   !tOtro.includes("sens.") && !tOtro.includes("esp."),
   tOtro.split(NL)[1]);
ok("pero el umbral y la puntuacion se siguen ensenando",
   tOtro.includes("puntuación 0,9802 " + MAYOR_IGUAL + " umbral 0,5000"), tOtro.split(NL)[1]);

console.log("\nL6. el comparador sale de los NUMEROS, no de la etiqueta (H7/H8)");
// Con la etiqueta como fuente, una `clasificacion` que el servidor no deberia
// mandar hacia que el mensaje dijera «sin opacidad probable» y «0,5649 < 0,4258»
// a la vez. Ahora la desigualdad es siempre cierta sobre lo que se ve.
for (const [etiqueta, r, esperado] of [
  ["positiva", R_POSITIVA, MAYOR_IGUAL],
  ["banda", R_BANDA, MAYOR_IGUAL],
  ["negativa", R_NEGATIVA, "<"],
]) {
  const t = (await desenlace({ error_cod: "N", detalle: "", resultado: r,
    sintomas: SINTOMAS, signos: SIGNOS }, U, D)).texto;
  const cierto = r.probabilidad_cruda >= r.umbral;
  ok(`${etiqueta}: la desigualdad es cierta sobre los numeros mostrados`,
     t.includes(dec4(r.probabilidad_cruda) + " " + esperado + " umbral") &&
     (esperado === MAYOR_IGUAL) === cierto,
     t.split(NL)[1]);
}
// Y una clasificacion o un structuredContent incompletos no llegan al redactor.
for (const [etiqueta, r] of [
  ["clasificacion desconocida", Object.assign({}, R_BANDA, {clasificacion: "quiza"})],
  ["sin umbral", (() => { const x = Object.assign({}, R_POSITIVA); delete x.umbral; return x; })()],
  ["umbral como cadena", Object.assign({}, R_POSITIVA, {umbral: "0.4258"})],
  ["sin probabilidad_calibrada", (() => { const x = Object.assign({}, R_POSITIVA); delete x.probabilidad_calibrada; return x; })()],
  ["RV no finita", Object.assign({}, R_POSITIVA, {razon_de_verosimilitud: Infinity})],
]) {
  const s = await leerRespuesta(http200(sseExito(r)), dResp);
  ok(`${etiqueta} -> error_no_reconocido, no llega al redactor`,
     s.error_cod === "error_no_reconocido" && s.resultado === null, s.error_cod);
  const m = await desenlace(s, U, D);
  ok(`   y su mensaje no lleva ningun NaN`, !/NaN/.test(m.texto), m.texto);
}

console.log("\nL7. un DICOM truncado no cierra la conversacion (H2)");
// Medido contra el contenedor el 25-sep-2026 con la misma placa truncada al 1, 5,
// 10, 25, 50, 75 y 99 %: el servidor devuelve isError con el texto EXACTO
// «Error executing tool clasificar_radiografia», sin ningun codigo. Antes eso
// caia en `error_no_reconocido`, que TERMINA, y cerraba la conversacion de un
// profesional cuyo unico problema es que el fichero llego a medias. Es el perfil
// «fichero corrupto» del §13.1, el que la tarea 8 va a generar.
const TRUNCADO = "Error executing tool clasificar_radiografia";
const sTrunc = await leerRespuesta(http200(sseError(TRUNCADO)), dResp);
ok("isError SIN codigo -> dicom_invalido, no error_no_reconocido",
   sTrunc.error_cod === "dicom_invalido", sTrunc.error_cod);
const mTrunc = await desenlace(sTrunc, U, D);
ok("y la conversacion NO termina: se queda esperando el archivo",
   mTrunc.termina === "N", mTrunc.termina);
ok("con un mensaje que no acusa de nada falso", !/20 MB|5 MB/.test(mTrunc.texto),
   mTrunc.texto.replace(/\n/g, " | "));
ok("y sin ninguna cifra de probabilidad", !CIFRA_DE_PROBABILIDAD.test(mTrunc.texto));
ok("un isError con un codigo que SI trae, aunque no lo conozcamos, sigue terminando",
   await (async () => {
     const s = await leerRespuesta(http200(sseError(
       TRUNCADO + ": gremlins_en_el_gpu: se fue la luz")), dResp);
     const m = await desenlace(s, U, D);
     return s.error_cod === "error_no_reconocido" && m.termina === "S";
   })());
ok("un isError con el texto vacio tambien es dicom_invalido",
   (await leerRespuesta(http200(sseError("")), dResp)).error_cod === "dicom_invalido");

console.log("\nL8. la descarga que falla no acusa de un tamano falso (H3)");
const sDesc = await correr(codigo("Descarga fallida"), { json: { error: "socket hang up" } },
  { Decidir: { chat_id: 7, t0: 1, sintomas: SINTOMAS, signos: SIGNOS } }, {});
ok("`Descarga fallida` emite su propio codigo", sDesc[0].json.error_cod === "descarga_fallida",
   sDesc[0].json.error_cod);
const mDesc = await desenlace(sDesc[0].json, U, D);
ok("y su mensaje NO menciona los 20 MB", !mDesc.texto.includes("20 MB"),
   mDesc.texto.replace(/\n/g, " | "));
ok("se registra y NO termina la conversacion",
   mDesc.registrar === "S" && mDesc.termina === "N");
ok("el codigo de los 20 MB sigue existiendo para lo que si lo es", await (async () => {
  const m = await desenlace({ error_cod: "fichero_no_descargable", detalle: "",
                              resultado: null }, U, D);
  return m.texto.includes("20 MB");
})());

console.log("\nM. el mensaje del caso: se ensena, pero NO nace fila en consultas");
const sCaso = await desenlace({ error_cod: "N", detalle: "", codigo: "K7FM2P",
  sintomas: SINTOMAS, signos: {} }, U, D);
ok("lleva el codigo y los sintomas", sCaso.texto.includes("K7FM2P") &&
   sCaso.texto.includes("REFERIDO POR EL PACIENTE —"), sCaso.texto);
ok("y NO lleva el texto libre dentro", !sCaso.texto.includes("DICE EL PACIENTE"));
ok("lleva la pregunta del paso 2, resuelta por `Decidir` y no por una copia",
   sCaso.texto.includes(D.pregunta), sCaso.texto);
ok("NO registra (no es un desenlace clinico)", sCaso.registrar === "N");
ok("NO termina la conversacion", sCaso.termina === "N");
ok("y no lleva resultado", sCaso.resultado_cod === "N");

console.log("\nN. la tabla del nodo coincide con el §4.4, literal");
const fuente = codigo("Decidir");
const tabla = [...fuente.matchAll(
  /\{paso:\s*(\d+),\s*clave:\s*'([a-z_]+)',\s*tipo:\s*'([a-z]+)'/g)]
  .map((m) => [Number(m[1]), m[2], m[3]]);
ok("6 pasos en la tabla", tabla.length === 6, JSON.stringify(tabla));
ok("los cuatro signos, con sus claves del §4.4",
   JSON.stringify(tabla.slice(1, 5).map((x) => [x[0], x[1]])) ===
   JSON.stringify([[2, "temperatura_c"], [3, "frecuencia_cardiaca"],
                   [4, "crepitantes"], [5, "murmullo_disminuido"]]),
   JSON.stringify(tabla));
for (const [, clave, min, max] of SPEC_4_4) {
  // 30,0 puede estar escrito `30.0` o `30` en el codigo: es el mismo numero.
  const num = (x) => String(x).replace(".", "\\.") + (Number.isInteger(x) ? "(\\.0)?" : "");
  ok(`el rango de ${clave} es ${min} a ${max}`,
     new RegExp(`min:\\s*${num(min)}\\s*,\\s*max:\\s*${num(max)}\\b`).test(fuente),
     `min:${min} max:${max}`);
}

console.log("\nO. los teclados repiten los prefijos de la tabla, y solo esos");
const botonesDe = (n) => {
  const salida = [];
  for (const fila of (nodo(n).parameters.inlineKeyboard || {}).rows || []) {
    for (const b of (fila.row || {}).buttons || []) {
      salida.push(b.additionalFields.callback_data);
    }
  }
  return salida;
};
ok("Pedir crepitantes -> s4:si / s4:no",
   JSON.stringify(botonesDe("Pedir crepitantes")) === JSON.stringify(["s4:si", "s4:no"]),
   JSON.stringify(botonesDe("Pedir crepitantes")));
ok("Pedir murmullo -> s5:si / s5:no",
   JSON.stringify(botonesDe("Pedir murmullo")) === JSON.stringify(["s5:si", "s5:no"]),
   JSON.stringify(botonesDe("Pedir murmullo")));
const prefijos = [...fuente.matchAll(/prefijo:\s*'(s\d+)'/g)].map((m) => m[1]);
ok("y los prefijos salen de la tabla de `Decidir`",
   JSON.stringify(prefijos) === JSON.stringify(["s4", "s5"]), JSON.stringify(prefijos));
const todosLosBotones = flujo.nodes.flatMap((n) =>
  n.type === "n8n-nodes-base.telegram" ? botonesDe(n.name) : []);
ok("no hay ningun otro boton en todo el flujo",
   JSON.stringify(todosLosBotones.sort()) === JSON.stringify(["s4:no", "s4:si", "s5:no", "s5:si"]),
   JSON.stringify(todosLosBotones));

console.log(fallos ? `\n${fallos} FALLOS` : "\nTODO VERDE");
process.exit(fallos ? 1 : 0);
}

principal().catch((e) => { console.error(e); process.exit(1); });
