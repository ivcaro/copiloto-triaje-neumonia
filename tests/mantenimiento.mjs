// Ejecuta el `jsCode` REAL del nodo `Evaluar` del workflow de mantenimiento con
// los `$()` y el reloj de n8n simulados. Es el equivalente de `tests/decidir.mjs`
// y `tests/profesional.mjs` para la tarea 7.
//
// Por que hace falta ejecutarlo y no basta leer el JSON: lo que se entrega en
// esta tarea NO es «un workflow que comprueba seis cosas», es **el texto que
// alguien va a leer con sueno cuando algo se rompa**, y la regla de cuando se
// calla. Ninguna de las dos se puede afirmar leyendo. Y la mitad de los estados
// que hay que probar -la base caida, el webhook desregistrado, el copiloto
// mudo- no se pueden provocar contra el VPS sin romper el sistema de verdad.
//
// Lo invoca tests/test_mantenimiento.py con `node`. A mano:
//   node tests/mantenimiento.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FLUJO = path.join(AQUI, "..", "n8n", "copiloto-mantenimiento.json");
const flujo = JSON.parse(fs.readFileSync(FLUJO, "utf8"));
const nodo = (n) => {
  const x = flujo.nodes.find((y) => y.name === n);
  if (!x) throw new Error(`el workflow no tiene un nodo '${n}'`);
  return x;
};
const CODIGO = nodo("Evaluar").parameters.jsCode;

const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;

// El reloj se sustituye porque la politica de avisos ES una funcion del tiempo:
// sin poder mover «ahora» no se puede probar que un fallo se calla a las 24 h y
// se recuerda a las 72.
async function evaluar(nodos, memoria = {}, ahora = "2026-09-25T11:45:00.000Z") {
  const $ = (nombre) => {
    if (!(nombre in nodos)) {
      throw new Error(`No node named '${nombre}' was executed`);
    }
    return { first: () => ({ json: nodos[nombre] }) };
  };
  const Real = Date;
  class Fija extends Real {
    constructor(...a) { if (a.length === 0) super(ahora); else super(...a); }
    static now() { return new Real(ahora).getTime(); }
  }
  globalThis.Date = Fija;
  try {
    const fn = new AsyncFunction("$", "$getWorkflowStaticData", CODIGO);
    const salida = await fn($, () => memoria);
    return { ...salida[0].json, memoria };
  } finally {
    globalThis.Date = Real;
  }
}

async function lanza(nodos, memoria = {}, ahora) {
  try {
    await evaluar(nodos, memoria, ahora);
    return null;
  } catch (e) {
    return e.message;
  }
}

let fallos = 0;
function ok(etiqueta, cond, detalle = "") {
  console.log((cond ? "  OK   " : "  FALLO") + ` ${etiqueta}`
    + (detalle ? `  ${detalle}` : ""));
  if (!cond) fallos++;
}

// --------------------------------------------------------------------------
// Entradas: lo que cada nodo deja cuando todo va bien, y variantes.
// --------------------------------------------------------------------------
const SALUD_OK = JSON.stringify({
  estado: "listo", modelo: "efficientnet_b0_320px", umbral: 0.4258,
  calibrador: "efficientnet_b0_320px_lote24_4+20ep",
});

const bien = (cambios = {}) => Object.assign({
  Configuracion: { chat_equipo: "987654321" },
  // MEDIDO contra el n8n real el 25-09-2026: una consulta de
  // solo DELETE sin RETURNING sale del nodo como `{success: true}`. ESO ES EL
  // CASO BUENO. El `{}` que deja «Always Output Data» cuando no hay ni eso se
  // prueba aparte, mas abajo.
  Limpieza: { success: true },
  "Base de datos viva": { uno: 1 },
  "Salud del copiloto": { statusCode: 200, cuerpo: SALUD_OK },
  "Placas rechazadas 7 dias": {
    consultas: 31, intentos_placa: 25, dicom_invalido: 1, envio_como_foto: 0,
    por_codigo: { dicom_invalido: 1, no_autorizado: 2 },
  },
  "Caducados sin borrar": { caducados: 0 },
  // Medido contra el n8n real: 403 «Authorization data is wrong!».
  "Webhook del paciente": { statusCode: 403, cuerpo: "Authorization data is wrong!" },
  "Webhook del profesional": { statusCode: 403, cuerpo: "Authorization data is wrong!" },
}, cambios);

const HORA = 3600000;
const DIA = 24 * HORA;
const T0 = new Date("2026-09-25T11:45:00.000Z").getTime();
const enIso = (ms) => new Date(ms).toISOString();

// Invariante que se comprueba en TODOS los textos de esta prueba: un aviso con
// un `undefined` dentro es un aviso que nadie sabe leer.
const BASURA = ["undefined", "NaN", "[object Object]", "null%", "Infinity"];
function sinBasura(etiqueta, texto) {
  const encontrada = BASURA.filter((b) => texto.includes(b));
  ok(`${etiqueta}: el texto no lleva basura de JS`, encontrada.length === 0,
    encontrada.join(","));
}

async function principal() {
console.log("A. ocho dias seguidos con todo bien: habla una vez y calla seis");
{
  // Se simulan dias CONSECUTIVOS con la misma memoria, que es como corre de
  // verdad: `evaluar` muta el objeto igual que `$getWorkflowStaticData` en n8n.
  const memoria = {};
  const dias = [];
  for (let d = 0; d <= 7; d++) {
    dias.push(await evaluar(bien(), memoria, enIso(T0 + d * DIA)));
  }
  const primera = dias[0];
  ok("la primera corrida manda un «todo bien»", primera.avisar && primera.latido,
    JSON.stringify({ avisar: primera.avisar, latido: primera.latido }));
  ok("...que dice para que sirve ese mensaje",
    /una vez por semana/.test(primera.texto) && /no está corriendo/.test(primera.texto));
  ok("...y nombra las comprobaciones que pasan, sin inventar cuantas son",
    primera.texto.includes("Las 8 comprobaciones pasan"), primera.texto.slice(0, 200));
  ok("...con la hora de Guayaquil y no en UTC",
    primera.texto.includes("2026-09-25 06:45"), primera.texto.split("\n")[0]);
  sinBasura("todo bien", primera.texto);

  // Esta es la mitad del valor del workflow: un aviso diario deja de leerse.
  ok("del segundo al septimo dia no dice NADA",
    dias.slice(1, 7).every((d) => d.avisar === false),
    JSON.stringify(dias.slice(1, 7).map((d) => d.avisar)));
  ok("a los 7 dias vuelve el latido: el canal se prueba una vez por semana",
    dias[7].avisar === true && dias[7].latido === true);
  ok("y en ninguno de los ocho dias se acusa de un hueco que no hubo",
    dias.every((d) => !d.fallando.includes("corridas")));
}

console.log("\nB. el copiloto caido (el escenario del brief: apagarlo)");
{
  const roto = bien({
    "Salud del copiloto": { error: "connect ECONNREFUSED 172.18.0.2:8000" },
  });
  const m = {};
  const caido = await evaluar(roto, m, enIso(T0));
  ok("avisa", caido.avisar && caido.fallando.includes("copiloto"),
    JSON.stringify(caido.fallando));
  ok("dice QUE pasa, con el sitio exacto",
    /copiloto-mcp:8000\/salud/.test(caido.texto));
  ok("dice QUE EFECTO tiene para quien usa el sistema",
    /el profesional/i.test(caido.texto) && /radiografía/.test(caido.texto));
  ok("y dice QUE HACER, con el comando escrito",
    /Qué hacer:/.test(caido.texto)
    && /docker compose -p copiloto-mcp/.test(caido.texto));
  ok("avisa de los 19 s de arranque, para no concluir en falso",
    /19 s/.test(caido.texto));
  sinBasura("copiloto caido", caido.texto);

  // La trampa que pide el brief: el mismo fallo, dia tras dia.
  const dia1 = await evaluar(roto, m, enIso(T0 + DIA));
  ok("al dia siguiente NO lo repite", dia1.avisar === false
    && dia1.callados.includes("copiloto"), JSON.stringify(dia1.callados));
  const dia2 = await evaluar(roto, m, enIso(T0 + 2 * DIA));
  ok("ni al segundo", dia2.avisar === false);
  const dia3 = await evaluar(roto, m, enIso(T0 + 3 * DIA));
  ok("a las 72 h lo recuerda una vez", dia3.avisar === true
    && dia3.recordados.includes("copiloto"), JSON.stringify(dia3.recordados));
  ok("...y el recordatorio dice desde cuando dura",
    /sigue desde el 2026-09-25/.test(dia3.texto), dia3.texto.slice(0, 300));
  const dia4 = await evaluar(roto, m, enIso(T0 + 4 * DIA));
  ok("y despues del recordatorio vuelve a callar", dia4.avisar === false);

  const arreglado = await evaluar(bien(), m, enIso(T0 + 5 * DIA));
  ok("cuando se arregla, lo dice", arreglado.avisar === true
    && arreglado.resueltos.includes("copiloto") && /Resuelto/.test(arreglado.texto));
  sinBasura("resuelto", arreglado.texto);
  const dia6 = await evaluar(bien(), m, enIso(T0 + 6 * DIA));
  ok("y despues se calla otra vez", dia6.avisar === false);
}

console.log("\nC. las otras formas de estar mal el copiloto");
{
  const quinientos = await evaluar(bien({
    "Salud del copiloto": { statusCode: 500, cuerpo: "Internal Server Error" },
  }), {});
  ok("un 500 cuenta como fallo y lo dice",
    quinientos.fallando.includes("copiloto") && /HTTP 500/.test(quinientos.texto));
  const arrancando = await evaluar(bien({
    "Salud del copiloto": { statusCode: 200, cuerpo: JSON.stringify({ estado: "cargando" }) },
  }), {});
  ok("un 200 que no dice «listo» tambien: el modelo no cargo",
    arrancando.fallando.includes("copiloto")
    && /estado="cargando"/.test(arrancando.texto));
  const html = await evaluar(bien({
    "Salud del copiloto": { statusCode: 200, cuerpo: "<html>502 Bad Gateway</html>" },
  }), {});
  ok("un 200 con HTML dentro no se traga como bueno",
    html.fallando.includes("copiloto"));
  sinBasura("html", html.texto);
}

console.log("\nD. la base de datos y la limpieza");
{
  const sinBase = await evaluar(bien({
    "Base de datos viva": { error: 'getaddrinfo ENOTFOUND copiloto-bd' },
  }), {});
  ok("un SELECT 1 que no vuelve avisa",
    sinBase.fallando.includes("base") && /docker logs --tail 50 copiloto-bd/.test(sinBase.texto));
  const vacio = await evaluar(bien({ "Base de datos viva": {} }), {});
  ok("y un nodo que no deja datos cuenta como FALLO, no como bien",
    vacio.fallando.includes("base"));

  const limpiezaMal = await evaluar(bien({
    Limpieza: { error: 'relation "cuestionarios" does not exist' },
  }), {});
  ok("la limpieza con error avisa", limpiezaMal.fallando.includes("limpieza"));
  ok("...y manda a bd/limpieza.sql, que es donde se arregla",
    /bd\/limpieza\.sql/.test(limpiezaMal.texto));
  ok("...y dice que lo que se queda sin borrar son datos de pacientes",
    /7 días/.test(limpiezaMal.texto));
  ok("el `{success: true}` que devuelve de verdad el nodo no es un fallo",
    (await evaluar(bien(), {})).fallando.includes("limpieza") === false);
  ok("ni el `{}` de «Always Output Data» cuando no vuelve ni eso",
    (await evaluar(bien({ Limpieza: {} }), {})).fallando.includes("limpieza") === false);

  const quedan = await evaluar(bien({ "Caducados sin borrar": { caducados: 14 } }), {});
  ok("si quedan cuestionarios caducados, avisa con el numero",
    quedan.fallando.includes("caducados") && /14 cuestionarios/.test(quedan.texto));
  const noSeSabe = await evaluar(bien({
    "Caducados sin borrar": { error: "canceling statement due to statement timeout" },
  }), {});
  ok("y si no se pudo contar, tambien: la duda no es silencio",
    noSeSabe.fallando.includes("caducados"));
  sinBasura("caducados", quedan.texto);
}

console.log("\nE. el umbral de las placas: avisa cuando pasa algo, no cuando hay poco dato");
{
  const caso = async (dicom, intentos, extra = {}) => await evaluar(bien({
    "Placas rechazadas 7 dias": Object.assign({
      consultas: intentos + 3, intentos_placa: intentos, dicom_invalido: dicom,
      envio_como_foto: 0, por_codigo: { dicom_invalido: dicom },
    }, extra),
  }), {});
  ok("3 de 11 (27 %) avisa", (await caso(3, 11)).fallando.includes("placas"));
  ok("1 de 3 (33 %) NO avisa: una placa suelta no es una senal",
    !(await caso(1, 3)).fallando.includes("placas"));
  ok("2 de 5 (40 %) NO avisa por el mismo motivo",
    !(await caso(2, 5)).fallando.includes("placas"));
  ok("3 de 20 (15 %) NO avisa: por debajo del 20 % del §16",
    !(await caso(3, 20)).fallando.includes("placas"));
  ok("4 de 4 (100 %) avisa", (await caso(4, 4)).fallando.includes("placas"));
  ok("ninguna placa en 7 dias no es un fallo",
    !(await caso(0, 0)).fallando.includes("placas"));

  const aviso = await caso(4, 11, { envio_como_foto: 3, por_codigo: { dicom_invalido: 4, envio_como_foto: 3, no_autorizado: 1 } });
  ok("el aviso lleva la cuenta cruda y el porcentaje, no solo el porcentaje",
    /4 de 11/.test(aviso.texto) && /36\.4 %/.test(aviso.texto), aviso.texto.match(/.*placas.*/)?.[0]);
  ok("...dice la hipotesis util: que las estan mandando como foto",
    /como foto/.test(aviso.texto) && /recomprime/.test(aviso.texto));
  ok("...y pide el fichero que hay que pedir",
    /\.dcm/.test(aviso.texto));
  ok("...y avisa de que fuera_de_alcance NO es un problema tecnico",
    /fuera_de_alcance/.test(aviso.texto) && /correcto/.test(aviso.texto));
  ok("...y desglosa los codigos de la ventana",
    /envio_como_foto 3/.test(aviso.texto), aviso.texto);
  sinBasura("placas", aviso.texto);

  const roto = await evaluar(bien({ "Placas rechazadas 7 dias": { error: "boom" } }), {});
  ok("si la consulta no da numeros, avisa de que no se pudo medir",
    roto.fallando.includes("placas") && /No se pudo medir/.test(roto.texto));
  const cadenas = await evaluar(bien({
    "Placas rechazadas 7 dias": {
      consultas: "31", intentos_placa: "11", dicom_invalido: "4",
      envio_como_foto: "0", por_codigo: {},
    },
  }), {});
  ok("y aguanta que la base devuelva los recuentos como cadenas",
    cadenas.fallando.includes("placas") && /4 de 11/.test(cadenas.texto));
}

console.log("\nF. los webhooks de los dos bots");
{
  const cuatro04 = await evaluar(bien({
    "Webhook del paciente": { statusCode: 404, cuerpo: '{"code":404,"message":"The requested webhook \\"POST copiloto-paciente\\" is not registered."}' },
  }), {});
  ok("un 404 avisa de que el bot esta mudo",
    cuatro04.fallando.includes("webhook_paciente")
    && /mudo/.test(cuatro04.texto));
  ok("...y manda a comprobar las dos cosas que pueden estar mal",
    /está activo/.test(cuatro04.texto) && /copiloto-paciente/.test(cuatro04.texto));
  ok("...y remata con el lado de Telegram, que esto no ve",
    /verificar_webhooks\.py/.test(cuatro04.texto));
  sinBasura("webhook 404", cuatro04.texto);

  const abierto = await evaluar(bien({
    "Webhook del profesional": { statusCode: 200, cuerpo: '{"message":"Workflow was started"}' },
  }), {});
  ok("un 200 -sin secreto- avisa de que la puerta del §4.2 desaparecio",
    abierto.fallando.includes("webhook_profesional")
    && /SIN el secreto/.test(abierto.texto));
  ok("...y explica lo que eso permite",
    /cualquiera/.test(abierto.texto) && /chat_id/.test(abierto.texto));

  const raro = await evaluar(bien({
    "Webhook del paciente": { statusCode: 502, cuerpo: "Bad Gateway" },
  }), {});
  ok("un 502 del proxy tambien avisa",
    raro.fallando.includes("webhook_paciente") && /HTTP 502/.test(raro.texto));
  const sinRed = await evaluar(bien({
    "Webhook del paciente": { error: "ETIMEDOUT" },
  }), {});
  ok("y si la sonda no llega, se dice que no se pudo comprobar",
    sinRed.fallando.includes("webhook_paciente")
    && /No se pudo comprobar/.test(sinRed.texto));
}

console.log("\nG. que esto mismo haya corrido (la tercera pata del §16)");
{
  const hueco = await evaluar(bien(), { ultima_corrida: enIso(T0 - 50 * HORA), ultimo_latido: enIso(T0 - 2 * HORA) });
  ok("un hueco de 50 h avisa", hueco.fallando.includes("corridas")
    && /50 h/.test(hueco.texto));
  ok("...y dice las dos causas: desactivado, o corrio y no pudo avisar",
    /desactivado/.test(hueco.texto) && /rojo/.test(hueco.texto));
  const aldia = await evaluar(bien(), { ultima_corrida: enIso(T0 - DIA), ultimo_latido: enIso(T0 - 2 * HORA) });
  ok("24 h no es un hueco", !aldia.fallando.includes("corridas"));
  const primera = await evaluar(bien(), {});
  ok("la primera corrida no se acusa de un hueco que no existe",
    !primera.fallando.includes("corridas"));
  ok("y la memoria guarda la corrida para poder verlo manana",
    typeof primera.memoria.ultima_corrida === "string");
}

console.log("\nH. sin destino para el aviso");
{
  const mensaje = await lanza(bien({ Configuracion: { chat_equipo: "" } }), {});
  ok("si hay algo que avisar y no hay chat, la ejecucion sale EN ROJO",
    mensaje !== null && /chat_equipo/.test(mensaje), String(mensaje).slice(0, 160));
  ok("...y el error dice lo que se iba a avisar, que si no se pierde",
    /todo bien|comprobaci/.test(String(mensaje)));
  const callado = await evaluar(bien({ Configuracion: { chat_equipo: "" } }),
    { ultimo_latido: enIso(T0 - HORA) });
  ok("pero un dia sin nada que decir no molesta a nadie",
    callado.avisar === false);
}

console.log("\nI. todo roto a la vez: el mensaje sigue cabiendo en Telegram");
{
  const todo = await evaluar({
    Configuracion: { chat_equipo: "987654321" },
    Limpieza: { error: "no se pudo conectar" },
    "Base de datos viva": { error: "no se pudo conectar" },
    "Salud del copiloto": { error: "ECONNREFUSED" },
    "Placas rechazadas 7 dias": { error: "no se pudo conectar" },
    "Caducados sin borrar": { error: "no se pudo conectar" },
    "Webhook del paciente": { statusCode: 404, cuerpo: "no" },
    "Webhook del profesional": { statusCode: 404, cuerpo: "no" },
  }, { ultima_corrida: enIso(T0 - 60 * HORA) });
  ok("las 8 comprobaciones fallan", todo.fallando.length === 8,
    JSON.stringify(todo.fallando));
  ok("el texto no pasa del limite de Telegram", todo.texto.length <= 3900 + 120,
    String(todo.texto.length));
  ok("...y si se recorta, lo dice y dice donde esta el resto",
    todo.texto.length < 3900 || /recortado/.test(todo.texto));
  ok("...y el primer fallo, que es el que se lee, sigue completo",
    /Qué hacer:/.test(todo.texto.slice(0, 1200)));
  sinBasura("todo roto", todo.texto);
}

console.log("\nJ. cada fallo, por separado, dice que hacer");
{
  const casos = {
    limpieza: bien({ Limpieza: { error: "x" } }),
    base: bien({ "Base de datos viva": { error: "x" } }),
    copiloto: bien({ "Salud del copiloto": { error: "x" } }),
    placas: bien({ "Placas rechazadas 7 dias": { consultas: 14, intentos_placa: 11, dicom_invalido: 4, envio_como_foto: 0, por_codigo: {} } }),
    caducados: bien({ "Caducados sin borrar": { caducados: 2 } }),
    webhook_paciente: bien({ "Webhook del paciente": { statusCode: 404, cuerpo: "x" } }),
    webhook_profesional: bien({ "Webhook del profesional": { statusCode: 404, cuerpo: "x" } }),
  };
  for (const [id, nodos] of Object.entries(casos)) {
    const r = await evaluar(nodos, {});
    const hay = r.fallando.includes(id);
    const dice = /Qué hacer:/.test(r.texto);
    // Un aviso util nombra un sitio concreto: un comando, un fichero o una
    // pantalla de n8n. «Algo falla» no es un aviso.
    const concreto = /docker |bd\/limpieza\.sql|pruebas\/|en n8n/.test(r.texto);
    ok(`${id}: avisa, dice que hacer y nombra un sitio concreto`,
      hay && dice && concreto, JSON.stringify({ hay, dice, concreto }));
    sinBasura(id, r.texto);
  }
  const corridas = await evaluar(bien(), { ultima_corrida: enIso(T0 - 60 * HORA) });
  ok("corridas: avisa, dice que hacer y nombra un sitio concreto",
    corridas.fallando.includes("corridas") && /Qué hacer:/.test(corridas.texto)
    && /en n8n/.test(corridas.texto));
}

console.log("\nK. dos fallos a la vez se cuentan y se numeran");
{
  const dos = await evaluar(bien({
    "Salud del copiloto": { error: "x" },
    "Caducados sin borrar": { caducados: 3 },
  }), {});
  ok("el encabezado dice cuantas fallan",
    /2 comprobaciones fallan/.test(dos.texto), dos.texto.split("\n")[0]);
  ok("y van numeradas", /\n1\. /.test(dos.texto) && /\n2\. /.test(dos.texto));
  const una = await evaluar(bien({ "Caducados sin borrar": { caducados: 3 } }), {});
  ok("con una sola, el encabezado esta en singular",
    /1 comprobación falla/.test(una.texto), una.texto.split("\n")[0]);
}

console.log("\nL. las dos medidas del dia van rotuladas y en su propia linea");
{
  // Antes iban pegadas en una sola frase -«… 0 de 1 en 7 días. No queda
  // ninguno.»- y el final no se sabia de que hablaba.
  const r = await evaluar(bien(), {});
  const lineas = r.texto.split("\n");
  ok("hay una linea «Medido hoy:» sola", lineas.includes("Medido hoy:"),
    JSON.stringify(lineas.slice(-3)));
  ok("las placas van en su linea rotulada",
    lineas.some((l) => l.startsWith("• Placas: ")));
  ok("y los caducados en la suya",
    lineas.some((l) => l.startsWith("• Cuestionarios caducados: ")));
  const mal = await evaluar(bien({ "Caducados sin borrar": { caducados: 9 } }), {});
  ok("tambien cuando una de las dos es la que falla",
    mal.texto.split("\n").some((l) => /^• Cuestionarios caducados: 9 /.test(l)),
    JSON.stringify(mal.texto.split("\n").slice(-3)));
}

console.log(fallos ? `\n${fallos} FALLOS` : "\nTODO VERDE");
process.exit(fallos ? 1 : 0);
}

principal().catch((e) => { console.error(e); process.exit(1); });
