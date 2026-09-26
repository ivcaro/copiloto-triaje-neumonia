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
// LA NEGATIVA DEL BORDE, y hace falta porque `R_NEGATIVA` es el SUELO: su RV es
// 0,0163, que es la cota inferior del calibrador. Con solo ese caso, un aviso
// escrito como `if (!positivo && rv < 0.5)` pasaba en verde, y entonces el 9,9 %
// de las negativas se quedaba sin el.
//
// Cifras del calibrador desplegado (`servidor/calibrador.json`), no inventadas:
// con la cruda justo por debajo del umbral, la calibrada es 0,143478 y la RV
// 0,5888. Medido sobre las 2 184 negativas del conjunto de prueba: 216 (9,9 %)
// tienen la RV en 0,5 o mas, y 0,5888 es la mas alta que una negativa puede
// tener. O sea que este es el caso extremo por el otro lado, y son justo las
// placas mas cercanas al umbral: aquellas en las que un negativo se parece mas
// a un positivo, que es donde el aviso mas falta hace.
const R_NEGATIVA_BORDE = {
  probabilidad_cruda: 0.4257, probabilidad_calibrada: 0.143478,
  razon_de_verosimilitud: 0.5888, umbral: 0.4258,
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

const NL = String.fromCharCode(10);
const RAYA_ = String.fromCharCode(8212);          // — la que usa el sistema
const BARRA = String.fromCharCode(0x2015);        // ― U+2015 HORIZONTAL BAR
const NEL = String.fromCharCode(0x85);            // U+0085 NEXT LINE
const MAYOR_IGUAL = String.fromCharCode(8805);
const AVISO_ = String.fromCharCode(9888) + String.fromCharCode(65039);
const AVISO_TEXTO = "El paciente escribió un comentario. Llega en el mensaje " +
  "siguiente, que empieza por «TODO ESTE MENSAJE ES TEXTO DEL PACIENTE»: nada " +
  "de lo que hay ahí es mío.";
const DESCARGO_TEXTO = "La combinación de imagen y clínica llega en la siguiente " +
                       "entrega. Esto no es un diagnóstico.";

// Los codigos cuyo mensaje del §9 anade el detalle cuando lo hay (`relata`).
const ERRORES_QUE_RELATAN = ["dicom_invalido", "fuera_de_alcance",
                             "edad_desconocida"];

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
   "Error executing tool clasificar_radiografia: fuera_de_alcance: El paciente tiene 12 años y el modelo solo es válido entre 18 y 100.",
   "El paciente tiene 12 años y el modelo solo es válido entre 18 y 100."],
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
// Que detalles se pueden RELATAR al profesional, y por que: por PROCEDENCIA.
// `inferencia.py` y `aplicacion.py` arman dos de estos cinco interpolando la
// excepcion de una libreria sobre bytes que suministra un tercero, y esos no se
// relatan. `test_flujo_profesional.py` ata esta tabla a esas dos fuentes.
const RELATABLE = {
  base64_invalido: false,       // f"base64_invalido: {exc}", de binascii
  dicom_invalido: false,        // f"...legible: {exc}", de pydicom, bytes ajenos
  edad_desconocida: true,       // literal entero
  fuera_de_alcance: true,       // literal + `edad`, que es int(digitos)
  payload_excesivo: true,       // literal + dos enteros
};
for (const [cod, texto, detalle] of ERRORES_MEDIDOS) {
  const s = await leerRespuesta(http200(sseError(texto)), dResp);
  ok(`isError -> codigo ${cod} buscado DENTRO del texto`, s.error_cod === cod, s.error_cod);
  ok(`   el detalle solo se relata si lo compuso nuestro codigo`,
     s.detalle === (RELATABLE[cod] ? detalle : ""), JSON.stringify(s.detalle));
  ok(`   y el texto del servidor va ENTERO a consultas.error, se relate o no`,
     s.crudo === detalle, s.crudo);
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

console.log("\nI bis. LO QUE EL CLINICO LEE, BIEN ESCRITO");
// --------------------------------------------------------------------------
// `tests/test_inferencia.py` comprueba la ortografia y el trato de los mensajes
// de `src/`, y eso dejaba fuera TODO lo que escriben los nodos de n8n, que es de
// donde sale la mayoria de lo que el profesional lee. Medido por una revision:
// 16 de los 20 literales de Telegram se podian destildar y tutear con las cuatro
// suites en VERDE, y cinco ya estaban mal escritos de verdad.
//
// QUE SE MIRA Y QUE NO. Un nodo tiene literales de dos clases: mensajes en
// castellano y cadenas de trabajo (`codigo_invalido`, `s4:si`, `application/
// json`). Solo las primeras tienen ortografia que juzgar, y se distinguen por
// que son PROSA: llevan espacios y tienen largo de frase. Con un `codigo` dentro
// de `'codigo_invalido'` no hay nada que corregir.
// --------------------------------------------------------------------------
const SIN_TILDE = ["anios", "valido", "codigo", "numero", "maximo", "minimo",
                   "diagnostico", "analisis", "radiografia", "informacion",
                   "despues", "tambien", "aqui", "mas ", "clinic", "practic",
                   "ningun ", "algun ", "segun", "rapido", "facil"];
// EL TUTEO NO SE PUEDE BUSCAR POR LA RAIZ DEL VERBO, y el primer intento de
// esta prueba lo hizo y se llevo tres falsos positivos seguidos.
//
// En castellano la forma de USTED es la tercera persona del singular, la misma
// que el imperativo de tu. Asi que «decide» no distingue nada: «Decide usted» y
// «Decide la clínica» son las dos correctas y de usted, y «vuelve a pasar» es
// impersonal. Una comprobacion que se queja de texto correcto acaba apagada, y
// entonces no comprueba nada.
//
// Lo que SI es inequivoco es la segunda persona conjugada -«decides»,
// «compruebas»-, que no existe en el trato de usted, y los pronombres de tu.
// La lista es corta a proposito: mejor pocas y ciertas.
const TUTEO = [" decides ", " vuelves ", " envias ", " env\u00edas ",
               " compruebas ", " revisas ", " intentas ", " miras ",
               " esperas ", " tienes ", " puedes ", " debes ", " sabes ",
               " quieres ", " haces ", " tu ", " tus ", " te ", " ti ",
               " contigo ", " tuyo ", " tuya "];
// Lo que NO es un mensaje aunque lo parezca: cabeceras HTTP, claves y el texto
// que el SERVIDOR compone -que se comprueba en `test_inferencia.py`, en su
// fuente, y aqui solo aparece como literal a buscar dentro de la respuesta-.
const NO_ES_UN_MENSAJE = [
  "application/json", "text/event-stream", "Error executing tool",
  "Request body too large", "no hay parametro", "jsonrpc",
  "clasificar_radiografia", "Only base64 data is allowed",
  "paso_3_se_conserva_paso_1", "opacidad_probable", "sin_opacidad_probable",
];

function mensajesDelNodo(fuente) {
  // Literales entre comillas simples, que es como estan escritos los nodos.
  const crudos = fuente.match(/'(?:[^'\\\n]|\\.)*'/g) || [];
  return crudos
    .map((s) => s.slice(1, -1).replace(/\\n/g, " ").replace(/\\'/g, "'"))
    // PROSA: con espacio y con largo de frase. Deja fuera las claves.
    .filter((s) => s.includes(" ") && s.length >= 14)
    // Y fuera lo que no es castellano nuestro.
    .filter((s) => !NO_ES_UN_MENSAJE.some((x) => s.includes(x)))
    // Un literal sin ninguna letra acentuable tipica tampoco es castellano:
    // se exige al menos una palabra con vocal, que cualquier frase tiene.
    .filter((s) => /[a-zA-Z]{3}/.test(s));
}

const NODOS_QUE_HABLAN = ["Decidir", "Desenlace"];
let revisados = 0;
for (const nombre of NODOS_QUE_HABLAN) {
  for (const mensaje of mensajesDelNodo(codigo(nombre))) {
    const bajo = " " + mensaje.toLowerCase() + " ";
    const malas = SIN_TILDE.filter((p) => bajo.includes(p));
    const tuteo = TUTEO.filter((p) => bajo.includes(p));
    revisados += 1;
    if (malas.length || tuteo.length) {
      ok(`${nombre}: «${mensaje.slice(0, 46)}»`, false,
         `sin tilde ${JSON.stringify(malas)} / tuteo ${JSON.stringify(tuteo)}`);
    }
  }
}
ok(`se revisaron los mensajes de ${NODOS_QUE_HABLAN.length} nodos`,
   revisados >= 20, String(revisados));
// Y las preguntas llevan su signo de apertura, que el castellano pide y el
// corrector de tildes no ve.
for (const nombre of NODOS_QUE_HABLAN) {
  for (const mensaje of mensajesDelNodo(codigo(nombre))) {
    if (!mensaje.trimEnd().endsWith("?")) { continue; }
    ok(`${nombre}: «${mensaje.slice(0, 40)}» abre la interrogacion`,
       mensaje.includes("\u00bf"), mensaje);
  }
}

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
// Aqui se afirmaba que un negativo NO llevaba ⚠️, porque el ⚠️ marcaba una sola
// cosa: la DISCREPANCIA entre etiqueta y RV. Ahora marca dos, y lo que hay que
// comprobar es que no se confundan. El negativo lleva el aviso de FALIBILIDAD -de
// las placas que el cribado da por negativas, 1 de cada 22 tiene neumonia- y NO el
// de discrepancia, que aqui seria falso: etiqueta y RV coinciden.
ok("negativa: lleva el aviso de falibilidad",
   tNeg.includes("⚠️ Un resultado negativo no descarta neumonía. Decide usted."), tNeg);
ok("negativa: y NO el aviso de discrepancia, que aqui seria falso",
   !tNeg.includes("no apoya el diagnóstico"), tNeg);
// Y UNO SOLO. Antes la cota superior la ponia `!tNeg.includes("⚠️")`, que se
// cayo al empezar el negativo a llevar aviso; el normalizador de la plantilla
// borra las lineas de ⚠️, asi que una SEGUNDA pasaba verde por los dos lados.
ok("negativa: un solo aviso, no dos",
   (tNeg.match(/⚠️/g) || []).length === 1,
   String((tNeg.match(/⚠️/g) || []).length));
// Y LA DEL BORDE TAMBIEN LO LLEVA. El aviso no mira la RV a proposito -una
// etiqueta negativa sale de cruda < 0,4258 y la RV no cruza 1 hasta 0,5786, asi
// que un negativo la tiene SIEMPRE por debajo de 1- y esto es lo que sujeta ese
// «a proposito»: si alguien le pusiera una condicion sobre la RV, las 216 placas
// negativas mas cercanas al umbral se quedarian sin aviso, y son las que mas lo
// necesitan.
const tNegBorde = (await texto(R_NEGATIVA_BORDE)).texto;
ok("negativa del borde (RV 0,5888): tambien lleva el aviso",
   tNegBorde.includes("⚠️ Un resultado negativo no descarta neumonía. Decide usted."),
   tNegBorde.split("\n").find((l) => l.includes("EVIDENCIA")));
ok("negativa del borde: la etiqueta sigue siendo negativa",
   tNegBorde.includes("CRIBADO — sin opacidad probable"),
   tNegBorde.split("\n")[0]);
ok("negativa del borde: y la evidencia dice REDUCE, no multiplica",
   tNegBorde.includes("reduce a 0,59×") && !tNegBorde.includes("multiplica"),
   tNegBorde.split("\n").find((l) => l.includes("EVIDENCIA")));
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
    // El aviso, que es justo lo que el §8 exceptua. Antes no hacia falta quitarlo
    // porque ninguno de estos dos casos lo llevaba; ahora el negativo lleva el de
    // falibilidad y el positivo concordante sigue sin llevar ninguno.
    .replace(/\n⚠️[^\n]*/g, "")
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

// --------------------------------------------------------------------------
// `signosValidos` ESTABA ENTERA SIN PROBAR, y es la que decide si el bloque
// EXPLORADO se imprime o se sustituye por «(sin datos completos)».
//
// La mutacion que se colaba: cambiar su cuerpo entero por `return !!g` dejaba
// las tres suites en verde. Y lo que sale entonces no es un mensaje feo, es un
// mensaje FALSO:
//
//   crepitantes: "false"  -> la cadena "false" es CIERTA en JavaScript, asi que
//                            el informe dice «crepitantes si» cuando el clinico
//                            pulso No.
//   murmullo ausente      -> `undefined` es falso, asi que dice «murmullo
//                            normal» sobre un signo que nadie exploro.
//   temperatura NaN       -> «NaN °C» en un informe clinico.
//
// Los tres son inalcanzables hoy -`Decidir` valida los rangos y la consulta
// guarda con `::jsonb` con su tipo-, y esta funcion existe justo para que sigan
// siendolo el dia que esas dos defensas cambien. Una guarda sin prueba es una
// guarda que se puede borrar sin que nadie se entere.
// --------------------------------------------------------------------------
const SIN_DATOS = "EXPLORADO — (sin datos completos)";
const SIGNOS_ROTOS = [
  ["crepitantes como la CADENA \"false\"",
   { crepitantes: "false" }, "crepitantes sí"],
  ["crepitantes como la cadena vacia", { crepitantes: "" }, "crepitantes no"],
  ["murmullo que no vino", { murmullo_disminuido: undefined }, "murmullo normal"],
  ["temperatura como cadena", { temperatura_c: "38.2" }, "38,2 °C"],
  ["temperatura NaN", { temperatura_c: NaN }, "NaN"],
  ["frecuencia como cadena", { frecuencia_cardiaca: "104" }, "104 lpm"],
  // Un objeto VACIO, y no `null`: `Desenlace` hace `e.signos || d.signos`, asi
  // que un `null` cae al respaldo del nodo `Decidir` -que trae los buenos- y
  // no llega nunca a la guarda. Con `{}` si llega.
  ["un objeto de signos vacio", {}, "°C"],
];
for (const [etiqueta, parche, loQueDiriaSiPasara] of SIGNOS_ROTOS) {
  const signos = Object.keys(parche).length ? Object.assign({}, SIGNOS, parche) : {};
  const s = await desenlace({ error_cod: "N", resultado: R_POSITIVA,
                              sintomas: SINTOMAS, signos }, U, D);
  ok(`signos invalidos (${etiqueta}): el bloque dice que faltan datos`,
     s.texto.includes(SIN_DATOS),
     s.texto.split("\n").find((l) => l.includes("EXPLORADO")));
  ok(`signos invalidos (${etiqueta}): y NO afirma «${loQueDiriaSiPasara}»`,
     !s.texto.includes(loQueDiriaSiPasara),
     s.texto.split("\n").find((l) => l.includes("EXPLORADO")));
}
// Y al reves: los signos buenos SI se imprimen. Sin esto, un `signosValidos`
// que devolviera `false` siempre pasaria todo lo de arriba y el clinico no
// veria nunca la exploracion que el mismo acaba de meter.
ok("y con los signos buenos el bloque se imprime entero",
   tPos.includes("EXPLORADO — 38,2 °C, 104 lpm, crepitantes sí, murmullo normal") &&
   !tPos.includes(SIN_DATOS), tPos.split("\n").find((l) => l.includes("EXPLORADO")));
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
ok("el informe con texto libre es el de siempre MAS el aviso del sistema",
   sLibre.texto === tPos + NL + NL + AVISO_TEXTO,
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
  fuera_de_alcance: "El paciente tiene 12 años y el modelo solo es válido entre 18 y 100.",
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

// --------------------------------------------------------------------------
// QUE SIGUE ESPERANDO EL BOT, sobre LA TABLA DEL PROPIO NODO.
//
// La primera version de esto recorria `SPEC_9`, y con eso la promesa «una fila
// nueva no puede nacer sin coletilla sin que esto falle» era FALSA: `SPEC_9` es
// una lista escrita a mano, y `descarga_fallida` -que existe en la tabla y no en
// el §9- no estaba en ella. Quitarle su `espera` dejaba la suite en verde. Una
// invariante sobre una enumeracion que hay que recordar actualizar no es una
// invariante.
//
// `SPEC_9` sigue escrita a mano, y debe seguirlo: es la transcripcion del spec, y
// afirma que el spec dice que `fuera_de_alcance` termina. Si leyera `fila.termina`
// del nodo estaria afirmando el codigo contra si mismo.
//
// Esto es otra cosa: una invariante INTERNA -la coletilla concuerda con
// `termina`- comprobada sobre todas las filas que hay, no sobre las que alguien
// se acordo de listar.
// --------------------------------------------------------------------------
function tablaDelNodo() {
  const fuente = codigo("Desenlace");
  const i = fuente.indexOf("const ERRORES = {");
  const j = fuente.indexOf("\n};", i);
  if (i < 0 || j < 0) { throw new Error("no encuentro ERRORES en el nodo"); }
  return new Function(fuente.slice(i, j + 3) + "\nreturn ERRORES;")();
}
const TABLA = tablaDelNodo();

// `no_autorizado` es la UNICA fila que no termina y no lleva coletilla, y esta
// nombrada aqui para que quitarle esa excepcion tambien ponga esto rojo.
const SIN_COLETILLA_A_PROPOSITO = ["no_autorizado"];

ok("la tabla del nodo se lee entera", Object.keys(TABLA).length >= 13,
   String(Object.keys(TABLA).length));

for (const [cod, fila] of Object.entries(TABLA)) {
  const s = await desenlace({ error_cod: cod, detalle: DETALLES[cod] || "",
                              resultado: null, sintomas: SINTOMAS,
                              signos: SIGNOS }, U, D);
  const dice = /\nSigo esperando (el archivo|el código del paciente)\.$/
    .test(s.texto);
  const debe = !fila.termina && SIN_COLETILLA_A_PROPOSITO.indexOf(cod) < 0;
  ok(`${cod}: dice que sigue esperando = ${debe}`, dice === debe,
     JSON.stringify(s.texto.split("\n").pop()));
}

// Y QUE NINGUNA FILA SE QUEDE SIN PROBAR. `SPEC_9` cubre las once del spec;
// las dos que no estan en el §9 se nombran aqui con su motivo, asi que una fila
// nueva no puede colarse sin que alguien decida donde la prueba.
const FUERA_DEL_SPEC_9 = {
  no_autorizado: "se prueba aparte: es la excepcion de la coletilla",
  descarga_fallida: "NO esta en el §9 -la salida de error de `Descargar " +
                    "fichero`- y se prueba al final de este fichero",
};
const sinProbar = Object.keys(TABLA).filter((c) =>
  !SPEC_9.some(([x]) => x === c) && !Object.hasOwn(FUERA_DEL_SPEC_9, c));
ok("ninguna fila de la tabla se queda sin probar", sinProbar.length === 0,
   JSON.stringify(sinProbar));

// --------------------------------------------------------------------------
// LA COLUMNA `relata`, QUE NO LA SUJETABA NADIE.
//
// `relata: true` significa: a este mensaje se le pega el `detalle` que venga. Y
// `detalle` solo lo llena `Leer respuesta` cuando el texto lo compuso NUESTRO
// codigo... pero eso es un contrato de OTRO nodo. Aqui, poner `relata: true` en
// una fila que recibe texto ajeno hace que el clinico lo lea LITERAL.
//
// Medido por una revision: con `error_no_reconocido: relata: true`, un HTTP 200
// hostil mete su propio bloque «CRIBADO — opacidad probable (puntuacion 0,9900
// >= umbral 0,4258)» dentro del mensaje del bot, y las tres suites seguian en
// verde. Es la clase de inyeccion del §8 entrando por una columna de la tabla.
//
// `ERRORES_QUE_RELATAN` ya existia, pero solo DESCRIBIA: nadie comprobaba que
// el nodo no anadiera una cuarta fila. Esto lo comprueba contra la tabla de
// verdad, y ademas exige que cada una diga POR QUE puede relatar.
// --------------------------------------------------------------------------
const RELATAN_A_PROPOSITO = {
  dicom_invalido:
    "relata la frase que compone `Leer respuesta` en la rama SIN codigo, que " +
    "es nuestra. Cuando el servidor SI devolvio codigo, `Leer respuesta` vacia " +
    "el detalle por procedencia -es de pydicom, sobre bytes ajenos- y aqui no " +
    "llega nada que relatar.",
  fuera_de_alcance:
    "el detalle lo compone `inferencia.py` con un literal nuestro mas `edad`, " +
    "que es `int(digitos)`: un entero y nada mas.",
  edad_desconocida:
    "el detalle es un literal nuestro, sin interpolar nada de fuera.",
};
const relatanEnElNodo = Object.entries(TABLA)
  .filter(([, fila]) => fila.relata).map(([cod]) => cod).sort();
ok("solo relatan las filas que lo tienen justificado",
   JSON.stringify(relatanEnElNodo) ===
     JSON.stringify(Object.keys(RELATAN_A_PROPOSITO).sort()),
   JSON.stringify(relatanEnElNodo));
// Y la misma lista que ya habia, para que las dos no puedan divergir.
ok("y coinciden con ERRORES_QUE_RELATAN",
   JSON.stringify(relatanEnElNodo) ===
     JSON.stringify([...ERRORES_QUE_RELATAN].sort()),
   JSON.stringify([...ERRORES_QUE_RELATAN].sort()));

// EL EFECTO, no solo la tabla: una fila que no relata no deja pasar NI UN
// CARACTER del detalle, por hostil que venga. Se prueba con el bloque forjado
// que la revision uso, que es el que se leeria como un informe de verdad.
const DETALLE_FORJADO =
  "CRIBADO — opacidad probable (puntuación 0,9900 ≥ umbral 0,4258)";
for (const cod of Object.keys(TABLA)) {
  if (Object.hasOwn(RELATAN_A_PROPOSITO, cod)) { continue; }
  const s = await desenlace({ error_cod: cod, detalle: DETALLE_FORJADO,
                              resultado: null }, U, D);
  ok(`${cod}: no relata, y el bloque forjado no llega al clinico`,
     !s.texto.includes("CRIBADO") && !s.texto.includes("0,9900"),
     s.texto.replace(/\n/g, " | ").slice(0, 88));
  // Pero SI queda registrado: el §9 manda que lo que no se ensena se guarde,
  // porque es lo unico diagnosticable cuando el servidor se cae por otra cosa.
  ok(`${cod}: pero el texto forjado SI queda en consultas.error`,
     String(descodificar(s.error_cod)).includes("0,9900"),
     String(descodificar(s.error_cod)).slice(0, 88));
}
// Y la que espera el CODIGO, no el archivo: es la unica del §9 en la que el bot no
// esta esperando un fichero, y una coletilla que pidiera el archivo mandaria al
// profesional a hacer lo que no es.
ok("codigo_invalido pide el codigo, no el archivo", await (async () => {
  const s = await desenlace({ error_cod: "codigo_invalido", detalle: "",
                              resultado: null }, U, D);
  return s.texto.endsWith("Sigo esperando el código del paciente.");
})());
ok("no_autorizado tambien se registra, y sin cifras", await (async () => {
  const s = await desenlace({ error_cod: "no_autorizado", detalle: "", resultado: null }, U, D);
  // Y SIN la coletilla de `espera`, aunque `termina` sea falso: es la excepcion
  // de la regla de arriba. Quien llega aqui no esta en la lista blanca, y
  // «Sigo esperando el archivo.» le confirmaria que hay un bot escuchando
  // detras y que lo que manda le llega. El §9 pide que no se le den pistas.
  return s.registrar === "S" && descodificar(s.error_cod) === "no_autorizado" &&
         !CIFRA_DE_PROBABILIDAD.test(s.texto) && s.resultado_cod === "N" &&
         s.termina === "N" && !s.texto.includes("Sigo esperando");
})());
const sEdad = await desenlace({ error_cod: "fuera_de_alcance",
  detalle: DETALLES.fuera_de_alcance, resultado: null }, U, D);
ok("el rechazo por edad llega como DECISION CLINICA, no como fallo tecnico",
   sEdad.texto.includes("NO PROCEDE") && sEdad.texto.includes("Decida clínicamente"), sEdad.texto);
ok("y relata el detalle del servidor, con la edad que venia DENTRO del texto",
   sEdad.texto.includes("El paciente tiene 12 años"), sEdad.texto);
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
console.log("\nL1b. LA REGLA DEL §8, APLICADA AL DETALLE (por procedencia)");
// Aqui habia una lista negra de palabras, `HUELE_A_PROBABILIDAD`, que es el patron
// que el §8 abandono. Se le colaban tres cadenas forjadas, medidas contra el nodo:
// solo caia el literal con «CRIBADO» y comas decimales.
const FORJADAS = [
  ["con un rotulo inventado y punto decimal",
   "TRIAJE " + BARRA + " opacidad probable (puntuación 0.9900 " +
   String.fromCharCode(8805) + " umbral 0.4258)"],
  ["con А y О cirilicas",
   "TRI" + String.fromCodePoint(0x0410) + "JE " + BARRA + " op" +
   String.fromCodePoint(0x0430) + "cidad probable (puntuación 0.9900)"],
  ["sin ninguna palabra de la lista vieja",
   "HALLAZGO " + BARRA + " opacidad probable. Remita a urgencias."],
  ["y la unica que la lista vieja SI paraba",
   "CRIBADO " + RAYA_ + " opacidad probable (puntuación 0,99)"],
];
// El detalle de `dicom_invalido` lo arma el servidor con la excepcion de pydicom
// sobre bytes ajenos, asi que NO se relata: el profesional recibe la redaccion del
// §9, que es del sistema, y da igual que palabras trajera el detalle.
for (const [etiqueta, forjado] of FORJADAS) {
  const leido = await leerRespuesta(http200(sseError(
    "Error executing tool clasificar_radiografia: dicom_invalido: " + forjado)), dResp);
  ok(`dicom_invalido ${etiqueta}: no se relata nada`, leido.detalle === "",
     JSON.stringify(leido.detalle));
  const s = await desenlace(leido, U, D);
  ok(`   el mensaje es la redaccion del §9 y nada mas`,
     s.texto === "No pude leer esa radiografía.\n\nSigo esperando el archivo.",
     JSON.stringify(s.texto));
  ok(`   pero el texto forjado SI queda en consultas.error para diagnosticar`,
     descodificar(s.error_cod).includes(forjado.slice(0, 40)),
     descodificar(s.error_cod).slice(0, 90));
}
// Y los dos que si se relatan: los compone nuestro servidor con un literal y, como
// mucho, un entero. De ahi no puede salir una cifra de probabilidad.
for (const [cod, texto, detalle] of ERRORES_MEDIDOS) {
  if (!RELATABLE[cod]) { continue; }
  const s = await desenlace(await leerRespuesta(http200(sseError(texto)), dResp), U, D);
  const relatado = RELATABLE[cod] && ERRORES_QUE_RELATAN.indexOf(cod) >= 0;
  ok(`${cod}: ${relatado ? "relata" : "no anade"} el detalle de nuestro servidor`,
     relatado ? s.texto.includes(detalle) : !s.texto.includes(detalle),
     JSON.stringify(s.texto.slice(0, 80)));
  ok(`   y sigue sin ninguna cifra de probabilidad`,
     !CIFRA_DE_PROBABILIDAD.test(s.texto), s.texto.split(NL).join(" | "));
}
// Sin la regla de procedencia, el texto forjado llegaria al profesional.
ok("sin la regla de procedencia, el forjado se relataria", await (async () => {
  const mutado = mutar("Leer respuesta",
    "CODIGOS_DEL_SERVIDOR[codigo] ? dice : ''", "dice");
  const leido = (await correr(mutado, { json: http200(sseError(
    "Error executing tool clasificar_radiografia: dicom_invalido: " + FORJADAS[0][1])) },
    { Decidir: dResp }))[0].json;
  const s = await desenlace(leido, U, D);
  return s.texto.includes("TRIAJE");
})(), "la mutacion tiene que relatar el forjado");

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
  // La referencia es el informe SIN comentario. Con comentario se le suma un
  // bloque, que es el aviso del sistema, literal: asi la igualdad pina tambien
  // que el aviso sea exactamente ese y que no haya nada mas.
  const esperado = REFERENCIA + NL + NL + AVISO_TEXTO;
  ok(`${etiqueta}: el informe es IDENTICO byte a byte al de referencia`,
     s.texto === esperado, s.texto === esperado ? "" :
     s.texto.split(NL).find((l) => !esperado.includes(l)));
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
  if (s.texto !== REFERENCIA + NL + NL + AVISO_TEXTO) { malos.push("Dash U+" + ch.charCodeAt(0).toString(16)); }
}
for (const ch of ESPACIOS) {
  const s = await informeDe(Object.assign({}, SINTOMAS,
    { texto_libre: falso(RAYA_, ch) }));
  if (s.texto !== REFERENCIA + NL + NL + AVISO_TEXTO) { malos.push("Espacio U+" + ch.charCodeAt(0).toString(16)); }
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
  // El valor crudo NO se ensena en ningun mensaje: rotularlo en el segundo seria
  // volver a meter una afirmacion del sistema en una burbuja que el paciente
  // controla. Queda en `cuestionarios.respuestas` y en `consultas.sintomas`.
  ok(`   y su contenido no aparece en NINGUNO de los dos mensajes`,
     !s.texto.includes(valor) && !s.texto_paciente.includes(valor),
     JSON.stringify(s.texto_paciente));
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
  // 987654321 y no 42: el 42 aparece dentro del umbral 0,4258 y la comprobacion
  // pasaria por casualidad.
  const s = await informeDe(Object.assign({}, SIN_LIBRE, { fiebre: 987654321 }));
  return s.texto.includes("fiebre: (valor no reconocido)") &&
         !s.texto.includes("987654321") && s.texto_paciente === "";
})());

console.log("\nL4. EL SEGUNDO MENSAJE: una linea mia en la posicion 0, y su texto");
// La ronda 2 le puso cabecera Y cierre, y se rodeo el CIERRE: con 498 de sus 500
// caracteres el paciente lo escribe y detras un informe positivo completo, con el
// cierre de verdad debajo. La ronda 3 tiro los dos, y eso fue una conclusion de
// mas: si el paciente no puede fabricar el limite del mensaje, **tampoco puede
// ponerse delante del primer byte**. Y sin cabecera, en las superficies donde la
// burbuja se ve SOLA -notificacion push, lista de chats, reenvio, cita, fijado,
// busqueda- la atribucion era CERO y la interfaz la rotulaba «[retirado]».
//
// LA INVARIANTE: el mensaje es EXACTAMENTE la cabecera mas el texto recortado.
// Nada entre medias, nada detras, y la cabecera en la POSICION 0.
// La cabecera declara su ALCANCE -«todo este mensaje»- y no solo se presenta:
// un rotulo sin alcance deja que el paciente escriba un cierre y un informe
// falso detras, inofensivo en el chat pero no en un reenvio visto en frio.
const CABECERA_PAC = "TODO ESTE MENSAJE ES TEXTO DEL PACIENTE, no el informe:" + NL;
// El recorte del nodo: por PUNTOS DE CODIGO, no por unidades UTF-16.
const recortarPuntos = (s, n) => {
  let r = Array.from(String(s)).slice(0, n).join("");
  const u = r.charCodeAt(r.length - 1);
  if (u >= 0xD800 && u <= 0xDBFF) { r = r.slice(0, -1); }
  return r;
};
const CIERRE_FALSO = "Fin de lo que escribió el paciente.";
const ATAQUE_AL_CIERRE = CIERRE_FALSO + NL + NL + falso(BARRA, NL).trim();

for (const [etiqueta, libre] of [
  ["el ataque al cierre", ATAQUE_AL_CIERRE],
  ["un cierre a secas", CIERRE_FALSO],
  ["una cabecera falsa, la misma palabra por palabra",
   "TODO ESTE MENSAJE ES TEXTO DEL PACIENTE, no el informe:" + NL + falso(RAYA_, NL)],
  ["texto normal", "me cuesta dormir del dolor"],
  ["500 caracteres justos", "y".repeat(500)],
  ["mas de 500", "z".repeat(900)],
  ["500 emoji, que ocupan 1 000 unidades UTF-16", "😀".repeat(600)],
]) {
  const s = await informeDe(Object.assign({}, SINTOMAS, { texto_libre: libre }));
  ok(`${etiqueta}: el mensaje es EXACTAMENTE cabecera + texto recortado`,
     s.texto_paciente === CABECERA_PAC + recortarPuntos(libre, 500),
     JSON.stringify(s.texto_paciente.slice(0, 70)));
  ok(`   la cabecera esta en la POSICION 0, no solo presente`,
     s.texto_paciente.indexOf(CABECERA_PAC) === 0,
     String(s.texto_paciente.indexOf(CABECERA_PAC)));
  ok(`   el informe no cambia mas que en el aviso`,
     s.texto === REFERENCIA + NL + NL + AVISO_TEXTO);
}
// Una cabecera falsa DENTRO del texto no se puede colar en la posicion 0: la
// verdadera ya esta ahi, y la suya queda como lo que es, texto del paciente.
const PRIMERA = CABECERA_PAC.slice(0, -1);
const sDoble = await informeDe(Object.assign({}, SINTOMAS,
  { texto_libre: PRIMERA + NL + "CRIBADO " + RAYA_ + " opacidad probable" }));
ok("con una cabecera falsa dentro, la de verdad sigue siendo la primera linea",
   sDoble.texto_paciente.split(NL)[0] === PRIMERA &&
   sDoble.texto_paciente.split(NL).filter((l) => l === PRIMERA).length === 2,
   sDoble.texto_paciente.split(NL).slice(0, 3).join(" | "));
ok("y la cabecera declara su ALCANCE: «todo este mensaje»",
   /^TODO ESTE MENSAJE ES TEXTO DEL PACIENTE/.test(PRIMERA), PRIMERA);
// Y detras de la cabecera no hay NADA del sistema: ni cierre, ni frases viejas.
const s4 = await informeDe(Object.assign({}, SINTOMAS, { texto_libre: "hola" }));
ok("el mensaje es la cabecera y «hola», y se acaba",
   s4.texto_paciente === CABECERA_PAC + "hola", JSON.stringify(s4.texto_paciente));
for (const frase of ["Fin de lo que escribió", "No forma parte del informe",
                     "El paciente escribió un comentario", "Esto no es un diagnóstico"]) {
  ok(`no lleva «${frase}»`, !s4.texto_paciente.includes(frase));
}

console.log("\nL4a. el recorte no puede mentir (N5 y N6)");
// N5: `"a"×499 + emoji` con `slice(0, 500)` partia el par suplente y dejaba la
// cadena mal formada. El paciente rompia A VOLUNTAD lo que el primer mensaje
// promete.
const CASI = "a".repeat(499);
for (const [etiqueta, libre] of [
  ["499 letras y un emoji", CASI + "😀"],
  ["498 letras y dos emoji", "a".repeat(498) + "😀😀"],
  ["500 emoji seguidos", "😀".repeat(500)],
  ["un subrogado alto SUELTO al final (el bot del paciente ya recorto mal)",
   CASI + String.fromCharCode(0xD83D)],
]) {
  const s = await informeDe(Object.assign({}, SINTOMAS, { texto_libre: libre }));
  const cuerpo = s.texto_paciente.slice(CABECERA_PAC.length);
  ok(`${etiqueta}: la cadena esta BIEN FORMADA`, (() => {
    for (let i = 0; i < cuerpo.length; i++) {
      const c = cuerpo.charCodeAt(i);
      if (c >= 0xD800 && c <= 0xDBFF) {
        const sig = cuerpo.charCodeAt(i + 1);
        if (!(sig >= 0xDC00 && sig <= 0xDFFF)) { return false; }
        i++;
      } else if (c >= 0xDC00 && c <= 0xDFFF) { return false; }
    }
    return true;
  })(), JSON.stringify(cuerpo.slice(-6)));
  ok(`   y es identica a lo que JSON.stringify sabe serializar`,
     JSON.parse(JSON.stringify(cuerpo)) === cuerpo);
}
// Las DOS lineas de `recortar` arreglan cosas distintas, y hay que probarlas por
// separado o no se sujeta ninguna. Mezclarlas fue el error de la ronda anterior con
// `dePaleta`.
const paciente = async (libre, fuente) => (await correr(
  fuente || codigo("Desenlace"),
  { json: { error_cod: "N", detalle: "", resultado: R_NEGATIVA, signos: SIGNOS,
            codigo: "K7FM2P",
            sintomas: Object.assign({}, SINTOMAS, { texto_libre: libre }) } },
  { "Normalizar update": U, Decidir: D }))[0].json.texto_paciente;

// (1) El subrogado suelto: es lo que garantiza que la cadena este BIEN FORMADA, y
//     hace falta aunque se recorte por puntos de codigo, porque lo que llega de la
//     base puede venir ya partido por el `slice` del bot del paciente.
ok("sin quitar el subrogado suelto, la cadena saldria mal formada",
   await (async () => {
     const mutado = mutar("Desenlace",
       "  if (ultimo >= 0xD800 && ultimo <= 0xDBFF) { r = r.slice(0, -1); }\n", "");
     const tp = await paciente(CASI + String.fromCharCode(0xD83D), mutado);
     const c = tp.charCodeAt(tp.length - 1);
     return c >= 0xD800 && c <= 0xDBFF;
   })(), "la mutacion tiene que dejar un subrogado suelto");
// (2) Los puntos de codigo: es lo que hace que «500» signifique 500 caracteres.
ok("500 emoji llegan los 500, no 250",
   Array.from(await paciente("😀".repeat(600))).length - Array.from(CABECERA_PAC).length === 500,
   String(Array.from(await paciente("😀".repeat(600))).length));
ok("sin recortar por puntos de codigo, se quedarian en la mitad",
   await (async () => {
     const mutado = mutar("Desenlace",
       "let r = Array.from(String(s)).slice(0, n).join('');",
       "let r = String(s).slice(0, n);");
     const tp = await paciente("😀".repeat(600), mutado);
     return Array.from(tp.slice(CABECERA_PAC.length)).length === 250;
   })(), "la mutacion tiene que perder la mitad de los caracteres");

// N6: la guarda miraba `libre.trim()` y se mandaba `libre.slice(0, 500)`, asi que
// con 600 espacios y una `x` detras el informe prometia un comentario y la burbuja
// eran 500 espacios.
for (const [etiqueta, libre] of [
  ["600 espacios y una x", " ".repeat(600) + "x"],
  ["600 tabuladores y una x", "\t".repeat(600) + "x"],
  ["600 saltos de linea y una x", NL.repeat(600) + "x"],
  ["500 espacios justos", " ".repeat(500)],
]) {
  const s = await informeDe(Object.assign({}, SINTOMAS, { texto_libre: libre }));
  ok(`${etiqueta}: no se manda segundo mensaje`, s.texto_paciente === "",
     JSON.stringify(s.texto_paciente.slice(0, 30)));
  ok(`   y el informe NO promete ninguno`, s.texto === REFERENCIA,
     s.texto.split(NL).pop());
}
ok("decidir con el original en vez de con el recorte volveria a mentir",
   await (async () => {
     const mutado = mutar("Desenlace", "if (recortado.trim() === '') { return ''; }",
                          "if (libre.trim() === '') { return ''; }");
     const r = (await correr(mutado, { json: { error_cod: "N", detalle: "",
       resultado: R_NEGATIVA, signos: SIGNOS, codigo: "K7FM2P",
       sintomas: Object.assign({}, SINTOMAS,
                               { texto_libre: " ".repeat(600) + "x" }) } },
       { "Normalizar update": U, Decidir: D }))[0].json;
     // El mutante promete un comentario y manda una burbuja de solo espacios.
     return r.texto_paciente !== "" &&
            r.texto_paciente.slice(CABECERA_PAC.length).trim() === "";
   })(), "la mutacion tiene que prometer lo que no manda");

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

console.log("\nL9. PRUEBAS DE MUTACION: cada defensa se comprueba QUITANDOLA");
// Por que existe esta seccion: en la ronda anterior presente ocho comprobaciones
// como prueba de la defensa contra `Object.prototype`, y no la sujetaban. Quitar
// solo `propio.call` dejaba el arnes verde, y quitar solo `typeof s === 'string'`
// dejaba TODO verde. Una prueba que sigue pasando cuando quitas media defensa no
// prueba esa mitad.
//
// La unica forma honesta de afirmar que una linea hace falta es quitarla y ver que
// algo se rompe. Aqui se le quita al codigo REAL del nodo, se ejecuta el mutante, y
// se exige que el resultado sea DISTINTO. Si alguien borra esa linea del nodo, la
// mutacion deja de aplicar y la prueba falla por otro sitio: `mutar` revienta si el
// texto que va a quitar ya no esta.
function mutar(nombre, quitar, poner = "") {
  const src = codigo(nombre);
  if (!src.includes(quitar)) {
    throw new Error(`la mutacion ya no aplica a «${nombre}»: ${quitar}`);
  }
  return src.split(quitar).join(poner);
}
async function correrMutado(nombre, quitar, entrada, nodos, poner = "") {
  return (await correr(mutar(nombre, quitar, poner), { json: entrada }, nodos))[0].json;
}

// --- 1. dePaleta, sus tres lineas, una por una y en aislamiento ---------------
// Se extrae la funcion REAL del nodo y se le pasan tablas que yo controlo. Con la
// tabla del §4.4 -que solo tiene cadenas- dos de las tres lineas no se pueden
// distinguir; con tablas propias, si.
function extraerDePaleta(fuente) {
  const i = fuente.indexOf("const propio = Object.prototype.hasOwnProperty;");
  const j = fuente.indexOf("\n}\n", fuente.indexOf("function dePaleta")) + 3;
  if (i < 0 || j < 3) { throw new Error("no encuentro dePaleta"); }
  return new Function(fuente.slice(i, j) + "\nreturn dePaleta;")();
}
const LINEAS = {
  "typeof v": "  if (typeof v !== 'string') { return null; }\n",
  "propio.call": "  if (!propio.call(tabla, v)) { return null; }\n",
  "typeof s": "  return typeof s === 'string' ? s : null;\n",
};
const CASOS_PALETA = [
  ["typeof v", "una clave que no es cadena y se coaccionaria a una que si existe",
   {si: "fiebre sí"}, ["si"]],
  // Con `{si:...}` y la clave `constructor`, quitar `propio.call` lo pararia la
  // linea de `typeof s` -el constructor es una funcion, no una cadena-, asi que
  // las dos no se distinguirian. Con una tabla cuyo PROTOTIPO tiene una cadena, la
  // unica linea que lo para es `propio.call`.
  ["propio.call", "un valor heredado del prototipo que SI es una cadena",
   Object.create({si: "frase heredada"}), "si"],
  ["typeof s", "un valor de la tabla que no es una frase",
   {si: 42}, "si"],
];
const fuenteDesen = codigo("Desenlace");
const dePaletaReal = extraerDePaleta(fuenteDesen);
for (const [linea, que, tabla, clave] of CASOS_PALETA) {
  ok(`dePaleta rechaza ${que}`, dePaletaReal(tabla, clave) === null,
     JSON.stringify(dePaletaReal(tabla, clave)));
  // Y la mutacion: sin esa linea, el mismo caso NO se rechaza.
  let mutada;
  if (linea === "typeof s") {
    // Quitar el `return` entero dejaria la funcion sin valor: se sustituye por la
    // version sin comprobar el tipo, que es la mutacion que interesa.
    mutada = extraerDePaleta(fuenteDesen.split(LINEAS["typeof s"])
      .join("  return s;\n"));
  } else {
    mutada = extraerDePaleta(fuenteDesen.split(LINEAS[linea]).join(""));
  }
  const r = mutada(tabla, clave);
  ok(`   y sin «${linea}» dejaria pasar ${JSON.stringify(String(r)).slice(0, 40)}`,
     r !== null, "la mutacion tiene que cambiar el resultado");
}

// --- 2. ERRORES[codigo], el segundo agujero de Object.prototype --------------
// Reabierto, un `error_cod` de «constructor» dejaba `fila.texto` en undefined y el
// profesional NO RECIBIA NADA, con la suite entera en verde.
const GUARDA_ERRORES = "propio.call(ERRORES, codigo) ? ERRORES[codigo] : null";
for (const heredada of ["constructor", "__proto__", "toString", "valueOf",
                        "hasOwnProperty", "isPrototypeOf", "propertyIsEnumerable"]) {
  const s = await desenlace({ error_cod: heredada, detalle: "", resultado: null },
                            U, D);
  ok(`error_cod = «${heredada}»: el profesional recibe un mensaje de verdad`,
     typeof s.texto === "string" && s.texto.length > 20 &&
     s.texto === "El servicio devolvió un error que no sé interpretar. Se ha registrado.",
     JSON.stringify(s.texto));
  ok(`   y queda registrado como error_no_reconocido`,
     descodificar(s.error_cod).startsWith("error_no_reconocido: " + heredada),
     descodificar(s.error_cod));
}
ok("sin la guarda de ERRORES, «constructor» dejaria al profesional sin mensaje",
   await (async () => {
     const s = await correrMutado("Desenlace",
       GUARDA_ERRORES, { error_cod: "constructor", detalle: "", resultado: null },
       { "Normalizar update": U, Decidir: D }, "ERRORES[codigo]");
     // El mutante coge la fila de Object.prototype: `fila` es la funcion Object,
     // `fila.texto` es undefined, y el mensaje sale vacio o con «undefined».
     return typeof s.texto !== "string" || s.texto === "" ||
            s.texto.includes("undefined");
   })(), "la mutacion tiene que romper el mensaje");

// --- 3. `crudo`, que se perdia con todo en verde -----------------------------
// La linea del servidor tiene que llegar a consultas.error en la rama SIN codigo,
// que es donde `detalle` ya es un texto fabricado.
const TRUNCADO_M = "Error executing tool clasificar_radiografia";
const MUTA_CRUDO = "crudo: crudo || detalle || ''";
async function errorRegistrado(fuenteLeer) {
  const leido = (await correr(fuenteLeer, { json: http200(sseError(TRUNCADO_M)) },
                              { Decidir: dResp }))[0].json;
  const s = await desenlace(leido, U, D);
  return descodificar(s.error_cod);
}
const registradoOk = await errorRegistrado(codigo("Leer respuesta"));
ok("la linea del servidor llega a consultas.error en la rama sin codigo",
   registradoOk.startsWith("dicom_invalido: ") && registradoOk.includes(TRUNCADO_M),
   registradoOk);
ok("y sin propagar `crudo` se perderia (que es el hallazgo, otra vez)",
   await (async () => {
     const r = await errorRegistrado(
       mutar("Leer respuesta", MUTA_CRUDO, "crudo: ''"));
     return !r.includes(TRUNCADO_M);
   })(), "la mutacion tiene que perder la linea del servidor");

console.log("\nL10. QUE CANALES HAY, no solo que caracteres llevan (N2/N3/N4)");
// La igualdad byte a byte de L2 fija los caracteres de los canales CONOCIDOS. No
// dice nada de cuantos canales hay: si alguien anade un campo nuevo del
// cuestionario al informe, la referencia se calcula con los mismos fixtures -que
// no tienen ese campo-, los dos lados salen iguales, y las dos suites quedan en
// TODO VERDE con un canal nuevo abierto.
//
// Esto lo cierra por el otro lado: se envuelve `sintomas` en un Proxy que APUNTA
// cada clave que el nodo lee, y se exige que sean exactamente las del §4.4 mas
// `texto_libre`. Ya no importa que palabra use el canal nuevo ni con que
// caracteres: importa que exista.
const CLAVES_PERMITIDAS = ["fiebre", "tos", "dias_evolucion", "disnea",
                           "dolor_toracico", "asma", "texto_libre"];

function espiar(objeto) {
  const leidas = new Set();
  const espia = new Proxy(objeto, {
    get(t, k) {
      // Los simbolos y los metodos que usan `String()`, `JSON` o el motor no son
      // canales de datos del paciente: se ignoran a proposito para que la lista no
      // se llene de ruido y deje de ser legible.
      if (typeof k === "string" && k !== "toJSON" && k !== "toString" &&
          k !== "valueOf" && k !== "then" && k !== "constructor") {
        leidas.add(k);
      }
      return t[k];
    },
    has(t, k) { if (typeof k === "string") { leidas.add(k); } return k in t; },
  });
  return { espia, leidas };
}

async function clavesLeidas(entradaBase, fuente) {
  const { espia, leidas } = espiar(Object.assign({}, SINTOMAS,
    { texto_libre: "un comentario cualquiera" }));
  const entrada = Object.assign({}, entradaBase, { sintomas: espia });
  const d = Object.assign({}, D, { sintomas: espia });
  await correr(fuente || codigo("Desenlace"), { json: entrada },
               { "Normalizar update": U, Decidir: d });
  return [...leidas].sort();
}

const ENTRADAS = [
  ["el informe", { error_cod: "N", detalle: "", resultado: R_NEGATIVA,
                   signos: SIGNOS, codigo: "K7FM2P" }],
  ["el mensaje del caso", { error_cod: "N", detalle: "", codigo: "K7FM2P",
                            signos: {} }],
];
for (const [etiqueta, entrada] of ENTRADAS) {
  const leidas = await clavesLeidas(entrada);
  const sobran = leidas.filter((k) => CLAVES_PERMITIDAS.indexOf(k) < 0);
  ok(`${etiqueta}: solo se leen las claves del §4.4 y texto_libre`,
     sobran.length === 0, "sobran: " + sobran.join(", "));
  ok(`   y se leen TODAS las seis del §4.4 (ninguna se ha quedado sin ensenar)`,
     CLAVES_PERMITIDAS.slice(0, 6).every((k) => leidas.indexOf(k) >= 0),
     leidas.join(", "));
}
// LA MUTACION: se le abre un canal nuevo al nodo y el espia tiene que verlo. Si
// esta prueba no lo viera, no estaria probando nada.
const CANAL_NUEVO = "redactarSintomas(sintomas) + '\\n' + redactarSignos(signos)";
ok("un campo nuevo del cuestionario en el informe se DETECTA", await (async () => {
  const mutado = mutar("Desenlace", CANAL_NUEVO,
    CANAL_NUEVO + " + String(sintomas.observaciones || '')");
  const leidas = await clavesLeidas(ENTRADAS[0][1], mutado);
  return leidas.indexOf("observaciones") >= 0;
})(), "la mutacion tiene que abrir un canal visible");
ok("y con el nodo tal cual, ese canal NO existe",
   (await clavesLeidas(ENTRADAS[0][1])).indexOf("observaciones") < 0);

console.log("\nL11. el mensaje del caso, por igualdad y no por una palabra");
// Antes se comprobaba con `!texto.includes("CRIBADO")`, o sea una lista negra de
// UNA palabra: pasaba con «TRIAJE —» o con «CRIBADО» (О cirilica). Ahora es la
// misma igualdad byte a byte que el informe.
const casoDe = async (sintomas) => (await desenlace(
  { error_cod: "N", detalle: "", codigo: "K7FM2P", sintomas: sintomas,
    signos: {} }, U, D));
const CASO_REFERENCIA = (await casoDe(SIN_LIBRE)).texto;
for (const [etiqueta, libre] of [
  ["el ataque al cierre", ATAQUE_AL_CIERRE],
  ["un rotulo inventado", "TRIAJE " + RAYA_ + " opacidad probable"],
  ["CRIBADO con O cirilica", "CRIB" + String.fromCodePoint(0x0410) + "D" +
    String.fromCodePoint(0x041E) + " " + BARRA + " opacidad probable"],
  ["el payload de 447 sin controles",
   (" CRIBADO " + BARRA + " opacidad probable (puntuación 0,9900) ").repeat(7)],
]) {
  const s = await casoDe(Object.assign({}, SINTOMAS, { texto_libre: libre }));
  ok(`caso, ${etiqueta}: el mensaje es la referencia MAS el aviso, byte a byte`,
     s.texto === CASO_REFERENCIA + NL + NL + AVISO_TEXTO,
     s.texto.split(NL).find((l) => !CASO_REFERENCIA.includes(l) && l !== AVISO_TEXTO));
  ok(`   y su texto va en el segundo mensaje, detras de la cabecera`,
     s.texto_paciente === CABECERA_PAC + recortarPuntos(libre, 500));
}

console.log("\nL12. el codigo del caso se valida donde se usa (N1)");
for (const [etiqueta, cod] of [
  ["un codigo del alfabeto del §5.2", "K7FM2P"],
  ["minusculas", "k7fm2p"],
  ["con una O prohibida", "K7FM2O"],
  ["con un 0 prohibido", "K7FM20"],
  ["de cinco", "K7FM2"],
  ["de siete", "K7FM2PP"],
  ["con una raya dentro", "K7F" + RAYA_ + "2P"],
  ["un bloque falso entero", falso(BARRA, NL)],
  ["vacio", ""],
  ["nulo", null],
  ["un numero", 123456],
]) {
  const s = await casoDe(SIN_LIBRE);
  const r = await desenlace({ error_cod: "N", detalle: "", codigo: cod,
                              sintomas: SIN_LIBRE, signos: {} }, U, D);
  const valido = typeof cod === "string" && cod.length === 6 &&
                 [...cod].every((c) => "ABCDEFGHJKMNPQRSTUVWXYZ23456789".includes(c));
  if (valido) {
    ok(`${etiqueta}: se imprime tal cual`, r.texto.startsWith("Caso " + cod),
       r.texto.split(NL)[0]);
  } else {
    ok(`${etiqueta}: NO se imprime; se dice que no se reconoce`,
       r.texto.startsWith("Caso (código no reconocido)") &&
       !r.texto.includes(String(cod === null ? "" : cod).slice(0, 20)) ===
       (String(cod || "").length > 0),
       r.texto.split(NL)[0]);
  }
}
ok("sin la validacion, un bloque falso entraria en el primer mensaje",
   await (async () => {
     const mutado = mutar("Desenlace", "codigoODesconocido(e.codigo)",
                          "String(e.codigo)");
     const r = (await correr(mutado,
       { json: { error_cod: "N", detalle: "", codigo: falso(BARRA, NL),
                 sintomas: SIN_LIBRE, signos: {} } },
       { "Normalizar update": U, Decidir: D }))[0].json;
     return r.texto.includes("CRIBADO");
   })(), "la mutacion tiene que meter el bloque falso");

console.log("\nL13. ningun mensaje puede pasarse del limite de Telegram (N7)");
// Telegram rechaza un mensaje de mas de 4 096 caracteres, y un mensaje rechazado es
// un profesional que NO RECIBE NADA. Antes `e.detalle` iba sin recortar: 20 000
// caracteres daban un primer mensaje de 20 031, y el camino para llegar ahi es
// justo el que el §9 mas teme, una caida del servidor.
const LIMITE_TELEGRAM = 4096;
const DETALLE_ABSURDO = "volcado de pila: ".repeat(1250);   // 20 000 caracteres
ok(`el detalle de la prueba tiene ${DETALLE_ABSURDO.length} caracteres`,
   DETALLE_ABSURDO.length >= 20000, String(DETALLE_ABSURDO.length));
for (const cod of ["dicom_invalido", "fuera_de_alcance", "edad_desconocida"]) {
  const s = await desenlace({ error_cod: cod, detalle: DETALLE_ABSURDO,
    crudo: DETALLE_ABSURDO, resultado: null }, U, D);
  ok(`${cod}: el mensaje cabe en Telegram (${s.texto.length} caracteres)`,
     s.texto.length <= LIMITE_TELEGRAM, String(s.texto.length));
  ok(`   y sigue habiendo mensaje, no un silencio`, s.texto.length > 20);
  ok(`   y lo que se registra tambien esta acotado`,
     descodificar(s.error_cod).length <= 600,
     String(descodificar(s.error_cod).length));
}
// Los dos mensajes del desenlace normal, con el texto libre mas largo posible.
const sLargo = await informeDe(Object.assign({}, SINTOMAS,
  { texto_libre: "ñ".repeat(900) }));
ok(`el informe cabe (${sLargo.texto.length})`, sLargo.texto.length <= LIMITE_TELEGRAM);
ok(`y el segundo mensaje cabe (${sLargo.texto_paciente.length})`,
   sLargo.texto_paciente.length <= LIMITE_TELEGRAM);
ok("sin acotar el detalle, el mensaje se pasaria del limite", await (async () => {
  const mutado = mutar("Desenlace", "recortar(e.detalle, TOPE_DETALLE)",
                       "String(e.detalle)");
  const r = (await correr(mutado, { json: { error_cod: "dicom_invalido",
    detalle: DETALLE_ABSURDO, crudo: "", resultado: null } },
    { "Normalizar update": U, Decidir: D }))[0].json;
  return r.texto.length > LIMITE_TELEGRAM;
})(), "la mutacion tiene que pasarse del limite");

console.log("\nM. el mensaje del caso: se ensena, pero NO nace fila en consultas");
const sCaso = await desenlace({ error_cod: "N", detalle: "", codigo: "K7FM2P",
  sintomas: SINTOMAS, signos: {} }, U, D);
ok("lleva el codigo y los sintomas", sCaso.texto.includes("K7FM2P") &&
   sCaso.texto.includes("REFERIDO POR EL PACIENTE —"), sCaso.texto);
// La etiqueta dice solo lo que esta comprobacion puede caer por: que un caso SIN
// comentario da exactamente la referencia. Que el texto libre no entre dentro lo
// comprueba L11, con payloads distintos de la entrada con la que se calcula la
// referencia; aqui la entrada es la misma, asi que no podria caer por eso.
ok("un caso sin comentario da exactamente la referencia",
   sCaso.texto === CASO_REFERENCIA, sCaso.texto);
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
