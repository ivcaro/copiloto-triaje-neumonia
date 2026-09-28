// node tests/formulario.mjs — la lógica del formulario de la sesión, sin navegador.
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { Formulario } = require("../pruebas/formulario/formulario.js");

let ok = 0;
function prueba(nombre, fn) { fn(); ok += 1; console.log("OK  " + nombre); }

const datos = (modo) => ({
  lectura: 2, modo,
  practica: [{ id: "pr-1", placa: "placas/pr-1.png", vineta: "práctica", mensaje: "M0", control: false }],
  casos: [
    { id: "c-1", placa: "placas/c-1.png", vineta: "v1", mensaje: "M1", control: false },
    { id: "c-2", placa: "placas/c-2.png", vineta: "v2", mensaje: null, control: true },
  ],
});
const conNotas = { banda: "alta", porcentaje: 80, correccion: 5, utilidad: 4, lenguaje: 5 };

prueba("la práctica va primero y el CSV la marca", () => {
  const e = Formulario.nuevoEstado(datos("simple"));
  assert.equal(Formulario.casoActual(e).id, "pr-1");
  Formulario.abrir(e, 1000);
  Formulario.enviar(e, conNotas, 4000);
  assert.equal(e.fase, "casos");
  assert.equal(Formulario.casoActual(e).id, "c-1");
  assert.equal(e.respuestas[0].practica, true);
  assert.equal(e.respuestas[0].segundos, 3);
});

prueba("el tiempo va de abrir a enviar, y sin abrir no se envía", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  assert.throws(() => Formulario.enviar(e, { banda: "baja", porcentaje: 5 }, 10), /no se abrió/);
  Formulario.abrir(e, 100);
  Formulario.abrir(e, 500);                       // abrir dos veces no reinicia el reloj
  Formulario.enviar(e, conNotas, 2600);
  assert.equal(e.respuestas[0].segundos, 2.5);
  assert.equal(e.respuestas[0].abierto_en, 100);
  assert.equal(e.respuestas[0].enviado_en, 2600);
});

prueba("con mensaje en modo simple las notas son obligatorias; en un control, no", () => {
  const e = Formulario.nuevoEstado({ lectura: 2, modo: "simple", practica: [], casos: datos("simple").casos });
  Formulario.abrir(e, 0);
  assert.throws(() => Formulario.enviar(e, { banda: "alta", porcentaje: 80 }, 1000), /notas/);
  Formulario.enviar(e, conNotas, 1000);
  assert.equal(e.respuestas[0].correccion, 5);
  Formulario.abrir(e, 2000);
  Formulario.enviar(e, { banda: "baja", porcentaje: 10 }, 3000);   // c-2 es control: sin notas
  assert.equal(e.respuestas[1].control, true);
  assert.equal(e.respuestas[1].correccion, "");
  assert.equal(Formulario.terminado(e), true);
  assert.equal(Formulario.casoActual(e), null);
});

prueba("no hay vuelta atrás: el índice solo crece", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  assert.equal(typeof Formulario.retroceder, "undefined");
  Formulario.abrir(e, 0); Formulario.enviar(e, conNotas, 1);
  assert.equal(e.indice, 1);
  Formulario.abrir(e, 2); Formulario.enviar(e, { banda: "baja", porcentaje: 0 }, 3);
  assert.equal(e.fase, "fin");
  assert.throws(() => Formulario.enviar(e, conNotas, 4), /no hay caso/);
});

prueba("modo secuencial: primero sin ayuda, luego se revela y se pide la segunda respuesta", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "secuencial", practica: [], casos: datos("secuencial").casos });
  Formulario.abrir(e, 0);
  const r = Formulario.enviar(e, { banda: "intermedia", porcentaje: 40 }, 30000);
  assert.equal(r.revelar, true);
  assert.equal(e.indice, 0);                          // el caso no ha avanzado
  assert.throws(() => Formulario.enviar(e, conNotas, 31000), /falta la respuesta/);
  Formulario.enviarConAyuda(e, { banda: "alta", porcentaje: 85, correccion: 4, utilidad: 5, lenguaje: 4 }, 45000);
  const f = e.respuestas[0];
  assert.equal(f.banda, "intermedia"); assert.equal(f.porcentaje, 40); assert.equal(f.segundos, 30);
  assert.equal(f.banda_con, "alta"); assert.equal(f.porcentaje_con, 85); assert.equal(f.segundos_con, 15);
  assert.equal(f.utilidad, 5);
  assert.equal(e.indice, 1);
  Formulario.abrir(e, 50000);
  const r2 = Formulario.enviar(e, { banda: "baja", porcentaje: 5 }, 51000);   // c-2 no tiene mensaje
  assert.equal(r2.revelar, false);
  assert.equal(e.fase, "fin");
});

prueba("el CSV lleva las columnas en orden y escapa comas, comillas y saltos", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  Formulario.abrir(e, 0);
  Formulario.enviar(e, Object.assign({}, conNotas, { comentario: 'dudo, "quizá"\nver base' }), 1500);
  const lineas = Formulario.aCSV(e).split("\n");
  assert.equal(lineas[0], Formulario.COLUMNAS.join(","));
  assert.equal(lineas[0].split(",").length, 17);
  assert.ok(lineas[1].startsWith("1,1,c-1,false,false,alta,80,0,1500,1.5,,,,5,4,5,"));
  assert.ok(lineas[1].endsWith('"dudo, ""quizá""'));
  assert.equal(lineas[2], "ver base\"");
});

prueba("banda o porcentaje inválidos se rechazan sin avanzar", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  Formulario.abrir(e, 0);
  assert.throws(() => Formulario.enviar(e, { banda: "media", porcentaje: 50, correccion: 3, utilidad: 3, lenguaje: 3 }, 1), /banda/);
  assert.throws(() => Formulario.enviar(e, { banda: "alta", porcentaje: 101, correccion: 3, utilidad: 3, lenguaje: 3 }, 1), /porcentaje/);
  assert.throws(() => Formulario.enviar(e, { banda: "alta", porcentaje: 7.5, correccion: 3, utilidad: 3, lenguaje: 3 }, 1), /porcentaje/);
  assert.throws(() => Formulario.enviar(e, { banda: "alta", porcentaje: 70, correccion: 0, utilidad: 3, lenguaje: 3 }, 1), /notas/);
  assert.equal(e.indice, 0);
  assert.equal(e.respuestas.length, 0);
});

console.log(ok + " OK");
