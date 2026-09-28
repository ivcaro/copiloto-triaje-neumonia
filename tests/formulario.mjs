// node tests/formulario.mjs — la lógica del formulario de la sesión, sin navegador.
import { createRequire } from "node:module";
import assert from "node:assert/strict";

const require = createRequire(import.meta.url);
const { Formulario } = require("../pruebas/formulario/formulario.js");

let ok = 0;
function prueba(nombre, fn) { fn(); ok += 1; console.log("OK  " + nombre); }

const PREPARACION = "20261006-20261005T101010";
const datos = (modo) => ({
  lectura: 2, modo, preparacion: PREPARACION,
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

prueba("retomar: sin estado guardado o con otra lectura, arranca de cero", () => {
  const d = datos("simple");
  const fresco = Formulario.retomar(null, d, 0);
  assert.equal(fresco.indice, 0);
  assert.equal(fresco.respuestas.length, 0);
  assert.equal(fresco.fase, "practica");

  const previoOtraLectura = Formulario.nuevoEstado({ lectura: 1, modo: "simple", preparacion: PREPARACION,
    practica: [], casos: d.casos });
  const otro = Formulario.retomar(previoOtraLectura, d, 0);      // d.lectura es 2
  assert.equal(otro.fase, "practica");                           // arrancó de cero, con la práctica de d
  assert.equal(otro.respuestas.length, 0);
});

prueba("retomar: si los ids de los casos no coinciden con los datos actuales, arranca de cero", () => {
  const d = datos("simple");
  const previo = Formulario.nuevoEstado(d);
  Formulario.abrir(previo, 0);
  Formulario.enviar(previo, conNotas, 500);                      // termina la práctica
  const otrosDatos = { lectura: 2, modo: "simple", preparacion: PREPARACION, practica: d.practica,
    casos: [{ id: "z-9", placa: "placas/z-9.png", vineta: "otro run", mensaje: null, control: true }] };
  const nuevo = Formulario.retomar(previo, otrosDatos, 1000);
  assert.equal(nuevo.respuestas.length, 0);
  assert.equal(nuevo.casos[0].id, "z-9");
});

prueba("retomar: mismos ids a mitad de lectura conserva las respuestas y reinicia el reloj del caso interrumpido", () => {
  const d = datos("simple");
  const previo = Formulario.nuevoEstado(d);
  Formulario.abrir(previo, 0);
  Formulario.enviar(previo, conNotas, 500);                      // termina la práctica, entra en casos
  Formulario.abrir(previo, 1000);                                // c-1 abierto pero no enviado
  const retomado = Formulario.retomar(previo, d, 9000);
  assert.equal(retomado.respuestas.length, 1);
  assert.equal(retomado.fase, "casos");
  assert.equal(retomado.indice, 0);
  assert.equal(retomado.abierto_en, null);
  assert.equal(retomado.pendiente, null);
});

prueba("retomar en plan B tras revelar conserva la respuesta pendiente y reinicia su reloj", () => {
  const d = { lectura: 1, modo: "secuencial", practica: [], casos: datos("secuencial").casos };
  const previo = Formulario.nuevoEstado(d);
  Formulario.abrir(previo, 0);
  const r = Formulario.enviar(previo, { banda: "intermedia", porcentaje: 40 }, 30000);
  assert.equal(r.revelar, true);
  const retomado = Formulario.retomar(previo, d, 100000);
  assert.notEqual(retomado.pendiente, null);
  assert.equal(retomado.revelado_en, 100000);
  Formulario.enviarConAyuda(retomado, { banda: "alta", porcentaje: 85, correccion: 4, utilidad: 5, lenguaje: 4 }, 103000);
  const fila = retomado.respuestas[0];
  assert.equal(fila.banda, "intermedia"); assert.equal(fila.segundos, 30);
  assert.equal(fila.banda_con, "alta"); assert.equal(fila.segundos_con, 3);
});

prueba("un porcentaje o una nota vacíos se rechazan: no son un 0", () => {
  const e = Formulario.nuevoEstado({ lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos });
  Formulario.abrir(e, 0);
  for (const vacio of ["", "  ", null, undefined]) {
    assert.throws(() => Formulario.enviar(e, Object.assign({}, conNotas, { porcentaje: vacio }), 1), /porcentaje/);
    assert.throws(() => Formulario.enviar(e, Object.assign({}, conNotas, { utilidad: vacio }), 1), /notas/);
  }
  const s = Formulario.nuevoEstado({ lectura: 1, modo: "secuencial", practica: [], casos: datos("secuencial").casos });
  Formulario.abrir(s, 0);
  Formulario.enviar(s, { banda: "baja", porcentaje: "0" }, 10);     // un 0 escrito sí vale
  assert.throws(() => Formulario.enviarConAyuda(s, Object.assign({}, conNotas, { porcentaje: "" }), 20), /porcentaje/);
  assert.equal(e.respuestas.length, 0);
  assert.equal(s.respuestas.length, 0);
  assert.equal(s.pendiente.porcentaje, 0);
});

prueba("nuevoEstado copia la preparación de los datos", () => {
  assert.equal(Formulario.nuevoEstado(datos("simple")).preparacion, PREPARACION);
});

prueba("retomar: otra preparación con los mismos casos arranca de cero (el ensayo no contamina)", () => {
  const d = datos("simple");
  const previo = Formulario.nuevoEstado(d);
  Formulario.abrir(previo, 0);
  Formulario.enviar(previo, conNotas, 500);
  const otra = Object.assign({}, d, { preparacion: "20261001-20260930T090000" });
  const r = Formulario.retomar(JSON.parse(JSON.stringify(previo)), otra, 1000);
  assert.equal(r.respuestas.length, 0);
  assert.equal(r.fase, "practica");
  assert.equal(r.preparacion, "20261001-20260930T090000");
  // y con la misma preparación sí retoma (tras pasar por localStorage)
  assert.equal(Formulario.retomar(JSON.parse(JSON.stringify(previo)), d, 1000).respuestas.length, 1);
});

prueba("retomar: misma preparación pero otra viñeta, placa o mensaje arranca de cero", () => {
  const d = datos("simple");
  const previo = Formulario.nuevoEstado(d);
  Formulario.abrir(previo, 0);
  Formulario.enviar(previo, conNotas, 500);
  const cambiar = (k, v) => Object.assign({}, d, {
    casos: d.casos.map((c, i) => (i === 1 ? Object.assign({}, c, { [k]: v }) : c)) });
  for (const [k, v] of [["vineta", "otra viñeta"], ["placa", "placas/otra.png"], ["mensaje", "M9"]]) {
    const r = Formulario.retomar(JSON.parse(JSON.stringify(previo)), cambiar(k, v), 1000);
    assert.equal(r.respuestas.length, 0, k);
    assert.equal(r.casos[1][k], v);
  }
});

prueba("retomar con la lectura terminada la deja intacta, con sus respuestas", () => {
  const d = { lectura: 1, modo: "simple", practica: [], casos: datos("simple").casos };
  const previo = Formulario.nuevoEstado(d);
  Formulario.abrir(previo, 0); Formulario.enviar(previo, conNotas, 1);
  Formulario.abrir(previo, 2); Formulario.enviar(previo, { banda: "baja", porcentaje: 0 }, 3);
  assert.equal(previo.fase, "fin");
  const retomado = Formulario.retomar(previo, d, 9999);
  assert.equal(retomado.fase, "fin");
  assert.equal(retomado.respuestas.length, 2);
  assert.equal(Formulario.terminado(retomado), true);
});

console.log(ok + " OK");
