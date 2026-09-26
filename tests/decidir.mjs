// Ejecuta el jsCode REAL de los nodos `Normalizar update` y `Decidir` del
// workflow exportado, con los `$()` de n8n simulados, y comprueba la tabla de
// decision entera.
//
// Por que existe aparte de las pruebas de pytest: `Decidir` es el unico nodo
// con logica de conversacion, y de el sale la clave con la que se guarda cada
// respuesta. Las pruebas estaticas comparan su TABLA contra el §4.4, pero no
// pueden decir nada de sus RAMAS: que /start a medias no borre, que «Omitir»
// signifique null, que un boton viejo no se guarde. Eso hay que ejecutarlo, y
// el codigo es JavaScript.
//
// Lo invoca tests/test_flujo_paciente.py con `node`. Tambien se puede correr a
// mano:  node tests/decidir.mjs
//
// La tarea 6 necesitara el equivalente para el flujo del profesional.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FLUJO = path.join(AQUI, "..", "n8n", "copiloto-paciente.json");
const flujo = JSON.parse(fs.readFileSync(FLUJO, "utf8"));
const codigo = (n) => flujo.nodes.find((x) => x.name === n).parameters.jsCode;

function correr(jsCode, entrada, nodos) {
  const $input = { first: () => ({ json: entrada }) };
  const $ = (nombre) => ({ first: () => ({ json: nodos[nombre] }) });
  return new Function("$input", "$", "Buffer", jsCode)($input, $, Buffer);
}

const normalizar = (update) => {
  const r = correr(codigo("Normalizar update"), { body: update }, {});
  return r.length ? r[0].json : null;
};
const decidir = (u, sesion) => correr(codigo("Decidir"), sesion, { "Normalizar update": u })[0].json;

const msg = (texto) => ({ message: { chat: { id: 7 }, text: texto } });
const btn = (dato) => ({ callback_query: { id: "1", data: dato, message: { chat: { id: 7 } } } });
const ses = (paso, existe = true, consentido = true) => ({ chat_id: 7, paso, existe, consentido });
const sinSesion = { chat_id: 7, paso: 0, existe: false, consentido: false };

// Deshace la codificacion del §"COMO VIAJA EL VALOR A SQL" de `Decidir`:
// 'N' -> null, 'T' + base64 -> ese texto.
const descodificar = (v) => (v === "N" ? null : Buffer.from(v.slice(1), "base64").toString("utf8"));

let fallos = 0;
function ok(etiqueta, cond, detalle = "") {
  console.log((cond ? "  OK   " : "  FALLO") + ` ${etiqueta}` + (detalle ? `  ${detalle}` : ""));
  if (!cond) fallos++;
}

// El §4.4 del spec, copiado a mano. Testigo independiente del workflow.
const SPEC = [
  [1, "fiebre", ["si", "no", "no_se"]],
  [2, "tos", ["con_flema", "seca", "no"]],
  [3, "dias_evolucion", ["menos_3", "3_a_7", "mas_7"]],
  [4, "disnea", ["si", "no"]],
  [5, "dolor_toracico", ["si", "no"]],
  [6, "asma", ["si", "no", "no_se"]],
  [7, "texto_libre", ["omitir"]],
];

console.log("\nA. Normalizar update");
ok("/start -> tipo texto", normalizar(msg("/start")).tipo === "texto");
ok("boton -> tipo boton + dato", (() => { const n = normalizar(btn("p1:si")); return n.tipo === "boton" && n.dato === "p1:si"; })());
ok("foto (sin texto) -> tipo otro", normalizar({ message: { chat: { id: 7 }, photo: [{}] } }).tipo === "otro");
ok("update sin chat -> se descarta", normalizar({ edited_channel_post: {} }) === null);
ok("callback sin chat en message usa from.id",
   normalizar({ callback_query: { id: "1", data: "x", from: { id: 42 } } }).chat_id === 42);

console.log("\nB. NINGUN parametro que vaya a SQL puede quedar vacio");
// El nodo Postgres arma sus parametros con `stringToArray`, que DESCARTA los
// vacios: un campo vacio desaparece, la consulta sale con 4 parametros
// referenciando $5, y Postgres responde `there is no parameter $5`. Paso de
// verdad con el «Omitir» de la pregunta 7. Esta seccion es la que lo cierra.
const CONSUMIDOS = ["clave", "valor_cod", "paso", "paso_actual"];
const casos = [];
for (const [n, , valores] of SPEC) for (const v of valores) casos.push([`p${n}:${v}`, ses(n)]);
casos.push(["texto en la 7", ses(7), msg("algo")]);
casos.push(["texto de solo espacios en la 7", ses(7), msg("    ")]);
for (const [etiqueta, sesion, update] of casos) {
  const r = decidir(normalizar(update || btn(etiqueta)), sesion);
  if (r.accion !== "guardar") continue;
  const vacios = CONSUMIDOS.filter((k) => String(r[k]) === "");
  ok(`${etiqueta}: ningun parametro vacio`, vacios.length === 0, vacios.join(",") || "");
}

console.log("\nC. consentimiento, /start y /reiniciar");
ok("/start sin sesion -> consentimiento", decidir(normalizar(msg("/start")), sinSesion).accion === "consentimiento");
ok("/start@Bot tambien", decidir(normalizar(msg("/start@[retirado]")), sinSesion).accion === "consentimiento");
ok("/START (mayusculas) tambien", decidir(normalizar(msg("/START")), sinSesion).accion === "consentimiento");
ok("/reiniciar a medias -> consentimiento (destructivo, a proposito)",
   decidir(normalizar(msg("/reiniciar")), ses(4)).accion === "consentimiento");
// El arreglo de b8aa1e3: sin esta comprobacion se puede devolver /start a
// destructivo y nadie se entera. Un paciente en la 6 perderia 5 respuestas.
const st4 = decidir(normalizar(msg("/start")), ses(4));
ok("/start A MEDIAS -> repetir la 4, NO borra la sesion",
   st4.accion === "repetir" && st4.paso === 4, JSON.stringify(st4));
for (const n of [1, 2, 3, 4, 5, 6, 7]) {
  const r = decidir(normalizar(msg("/start")), ses(n));
  ok(`/start en la ${n} no es destructivo`, r.accion === "repetir" && r.paso === n);
}
ok("consent:no -> despedida", decidir(normalizar(btn("consent:no")), sinSesion).accion === "despedida");
ok("consent:si sin sesion -> aceptar", decidir(normalizar(btn("consent:si")), sinSesion).accion === "aceptar");
const dup = decidir(normalizar(btn("consent:si")), ses(3));
ok("consent:si CON sesion -> repetir, NO reinicia", dup.accion === "repetir" && dup.paso === 3, JSON.stringify(dup));

console.log("\nD. el paso 8 se puede reintentar (no es un callejon sin salida)");
for (const [etiqueta, up] of [["un texto cualquiera", msg("hola")], ["/start", msg("/start")], ["un boton viejo", btn("p7:omitir")]]) {
  const r = decidir(normalizar(up), ses(8));
  ok(`en el paso 8, ${etiqueta} reintenta Completar`, r.accion === "repetir" && r.paso === 8, JSON.stringify(r));
}
ok("en el paso 8, /reiniciar sigue siendo la salida destructiva",
   decidir(normalizar(msg("/reiniciar")), ses(8)).accion === "consentimiento");

console.log("\nE. cada respuesta en SU clave (§4.4)");
for (const [n, clave, valores] of SPEC) {
  for (const v of valores) {
    const r = decidir(normalizar(btn(`p${n}:${v}`)), ses(n));
    const esperado = (n === 7 && v === "omitir") ? null : v;
    ok(`p${n}:${v} -> clave=${clave} valor=${JSON.stringify(esperado)} paso=${n + 1}`,
       r.accion === "guardar" && r.clave === clave && descodificar(r.valor_cod) === esperado &&
       r.paso === n + 1 && r.paso_actual === n, JSON.stringify(r));
  }
}
ok("«Omitir» codifica NULL, no la cadena 'omitir'",
   decidir(normalizar(btn("p7:omitir")), ses(7)).valor_cod === "N");

console.log("\nE bis. EL PACIENTE QUE VUELVE");
// El caso real que destapo esto: alguien completo el cuestionario, se fue, y
// vuelve dias despues a por otro codigo. `Completar` le borro la sesion al
// entregarle el primero, y la limpieza diaria borra las que pasan de 24 h, asi
// que llega SIEMPRE sin sesion. Y no puede pulsar Iniciar: Telegram solo pone
// ese boton en un chat nuevo.
for (const texto of ["Hola", "hola", "buenos dias", "quiero otro codigo",
                     "start", "?"]) {
  ok(`«${texto}» sin sesion abre el consentimiento`,
     decidir(normalizar(msg(texto)), sinSesion).accion === "consentimiento",
     decidir(normalizar(msg(texto)), sinSesion).accion);
}
// Y sigue funcionando lo que ya funcionaba: aceptar o rechazar el
// consentimiento se pulsa JUSTO cuando todavia no hay sesion, asi que la rama
// nueva no puede adelantarse a esos dos botones. Si se adelantara, nadie
// volveria a poder aceptar.
ok("el boton Si sigue creando la sesion",
   decidir(normalizar(btn("consent:si")), sinSesion).accion === "aceptar");
ok("el boton No sigue despidiendo",
   decidir(normalizar(btn("consent:no")), sinSesion).accion === "despedida");
// Con sesion a medias NO se reabre el consentimiento: se repite la pregunta,
// que es lo que ya hacia y no debe cambiar.
ok("con el cuestionario a medias se repite la pregunta, no el consentimiento",
   decidir(normalizar(msg("hola")), ses(3)).accion === "repetir");

console.log("\nF. valores y botones que NO se aceptan");
ok("un valor fuera del §4.4 no se guarda", decidir(normalizar(btn("p1:quiza")), ses(1)).accion === "repetir");
ok("el boton de OTRA pregunta no se guarda", decidir(normalizar(btn("p2:seca")), ses(5)).accion === "repetir");
ok("un callback ajeno se descarta sin contestar", decidir(normalizar(btn("borrar:todo")), ses(3)).accion === "nada");
ok("p8 no existe -> se descarta", decidir(normalizar(btn("p8:si")), ses(3)).accion === "nada");
// SIN SESION, CUALQUIER COSA ABRE EL CONSENTIMIENTO, tambien un boton viejo.
// Antes esto afirmaba `nada`. Cambio porque el razonamiento de entonces
// -«contestar seria hablarle a quien no ha dicho /start»- tiene un agujero: el
// boton Iniciar de Telegram SOLO aparece en un chat nuevo, asi que quien ya uso
// el bot no puede descubrir /start, y las dos rutas normales -terminar el
// cuestionario, o dejarlo mas de 24 h- acaban sin sesion. El paciente que
// repite consulta caia siempre ahi y no recibia nada.
//
// Y ya no compensa distinguir el callback forjado del texto cualquiera: si a un
// «hola» se le contesta, discriminar por el tipo de mensaje no protege de nada.
ok("boton viejo sin sesion -> abre el consentimiento",
   decidir(normalizar(btn("p1:si")), sinSesion).accion === "consentimiento");
ok("un callback forjado sin sesion, igual",
   decidir(normalizar(btn("borrar:todo")), sinSesion).accion === "consentimiento");
ok("sesion SIN consentimiento -> nada (D11)", decidir(normalizar(btn("p1:si")), ses(1, true, false)).accion === "nada");

console.log("\nG. pregunta 7: la unica con texto libre");
const t7 = decidir(normalizar(msg("me duele, mucho; ' OR 1=1 --")), ses(7));
ok("texto en la 7 -> texto_libre, paso 8",
   t7.accion === "guardar" && t7.clave === "texto_libre" && t7.paso === 8);
ok("el texto viaja intacto", descodificar(t7.valor_cod) === "me duele, mucho; ' OR 1=1 --");
ok("el valor codificado NUNCA lleva comas", !t7.valor_cod.includes(","));
ok("se recorta a 500 caracteres (§4.4)",
   descodificar(decidir(normalizar(msg("x".repeat(900))), ses(7)).valor_cod).length === 500);
const acentos = "tos con flema y fiebre alta, ¡mucha!  ñandú";
ok("los acentos y la ñ sobreviven", descodificar(decidir(normalizar(msg(acentos)), ses(7)).valor_cod) === acentos);
ok("solo espacios en la 7 -> NULL, no cadena vacia",
   decidir(normalizar(msg("     ")), ses(7)).valor_cod === "N");

console.log("\nH. texto donde se esperaba un boton, y cosas que no son texto");
for (const n of [1, 2, 3, 4, 5, 6]) {
  const r = decidir(normalizar(msg("si claro")), ses(n));
  ok(`texto libre en la ${n} -> repetir la ${n}, NO se guarda`,
     r.accion === "repetir" && r.paso === n && r.clave === "");
}
ok("una foto en la 3 -> repetir la 3",
   (() => { const r = decidir(normalizar({ message: { chat: { id: 7 }, photo: [{}] } }), ses(3));
            return r.accion === "repetir" && r.paso === 3; })());

console.log("\nI. la tabla del nodo coincide con el §4.4, literal");
const tabla = [...codigo("Decidir").matchAll(/\{n:\s*(\d+),\s*clave:\s*'([a-z_]+)',\s*valores:\s*\[([^\]]+)\]/g)]
  .map((m) => [Number(m[1]), m[2], m[3].replace(/['\s]/g, "").split(",")]);
ok("7 preguntas", tabla.length === 7);
ok("claves y valores identicos al §4.4", JSON.stringify(tabla) === JSON.stringify(SPEC), JSON.stringify(tabla));

console.log(fallos ? `\n${fallos} FALLOS` : "\nTODO VERDE");
process.exit(fallos ? 1 : 0);
