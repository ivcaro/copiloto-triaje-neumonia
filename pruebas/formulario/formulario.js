// Lógica del formulario de la sesión con el médico (spec de SP5 §5.2, §5.4, §5.8).
// Sin DOM a propósito: `tests/formulario.mjs` la carga en node y `index.html`
// solo pinta el estado y llama a estas funciones.
//
// Lo que este fichero hace cumplir:
//   - un caso por pantalla y sin volver atrás: no existe ninguna función que
//     retroceda; `indice` solo crece;
//   - el tiempo de triaje va de abrir el caso a enviar la banda, con el reloj
//     que se le pasa (Date.now() en el navegador; un contador en las pruebas);
//   - en modo "simple" (lecturas 1 y 2) el mensaje, si lo hay, se muestra con
//     el caso y las tres notas se piden en el mismo envío; en modo
//     "secuencial" (plan B) el mensaje se revela DESPUÉS de enviar la banda
//     sin ayuda y se pide una segunda respuesta con las notas;
//   - los casos de práctica van primero y salen en el CSV marcados.
(function (raiz) {
  "use strict";

  const BANDAS = ["baja", "intermedia", "alta"];
  const NOTAS = ["correccion", "utilidad", "lenguaje"];
  const COLUMNAS = ["lectura", "orden", "id", "practica", "control", "banda", "porcentaje",
    "abierto_en", "enviado_en", "segundos", "banda_con", "porcentaje_con", "segundos_con",
    "correccion", "utilidad", "lenguaje", "comentario"];

  function nuevoEstado(datos) {
    if (!datos || !Array.isArray(datos.casos) || !Array.isArray(datos.practica)) {
      throw new Error("datos sin casos o sin práctica");
    }
    return {
      lectura: datos.lectura,
      preparacion: datos.preparacion,
      modo: datos.modo === "secuencial" ? "secuencial" : "simple",
      practica: datos.practica.map((c) => Object.assign({}, c, { practica: true })),
      casos: datos.casos.map((c) => Object.assign({}, c, { practica: false })),
      fase: datos.practica.length ? "practica" : "casos",
      indice: 0, abierto_en: null, revelado_en: null, pendiente: null, respuestas: [],
    };
  }

  // Lo que el médico ve de cada caso: si algo de esto cambió, las respuestas
  // guardadas son de otros casos aunque los ids coincidan.
  const LO_QUE_SE_VE = ["id", "placa", "vineta", "mensaje"];

  function mismosCasos(a, b) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) { return false; }
    for (let i = 0; i < a.length; i++) {
      for (const k of LO_QUE_SE_VE) {
        if (a[i][k] !== b[i][k]) { return false; }
      }
    }
    return true;
  }

  // Decide si un estado guardado en localStorage sirve para esta carga de la
  // página (misma lectura, misma preparación —la marca de preparar_sesion
  // que distingue el ensayo y cada elección—, y los mismos casos y práctica,
  // en el mismo orden y con la misma placa, viñeta y mensaje) y, si sirve,
  // cómo retomarlo: el caso a medias reinicia su reloj; la respuesta
  // pendiente de un plan B ya revelado se conserva con su reloj reiniciado;
  // una lectura terminada se devuelve intacta para que la pantalla final
  // vuelva a mostrarse.
  function retomar(previo, datos, ahora) {
    if (!previo || previo.lectura !== datos.lectura || previo.preparacion !== datos.preparacion ||
        !mismosCasos(previo.casos, datos.casos) || !mismosCasos(previo.practica, datos.practica)) {
      return nuevoEstado(datos);
    }
    if (previo.fase === "fin") { return previo; }
    previo.abierto_en = null;
    if (previo.pendiente) { previo.revelado_en = ahora; }
    return previo;
  }

  function lista(e) { return e.fase === "practica" ? e.practica : e.casos; }
  function casoActual(e) { return e.fase === "fin" ? null : (lista(e)[e.indice] || null); }
  function terminado(e) { return e.fase === "fin"; }

  function abrir(e, ahora) {
    if (e.fase !== "fin" && e.abierto_en === null) { e.abierto_en = ahora; }
    return e;
  }

  // Vacío antes de Number(): Number("") y Number(null) valen 0, y un
  // porcentaje sin escribir no es un 0 %.
  function vacio(v) { return v === null || v === undefined || String(v).trim() === ""; }

  function validarBanda(r) {
    if (!BANDAS.includes(r.banda)) { throw new Error("elija una banda: baja, intermedia o alta"); }
    if (vacio(r.porcentaje)) { throw new Error("falta el porcentaje: un entero de 0 a 100"); }
    const p = Number(r.porcentaje);
    if (!Number.isInteger(p) || p < 0 || p > 100) { throw new Error("el porcentaje es un entero de 0 a 100"); }
  }

  function validarNotas(r) {
    for (const k of NOTAS) {
      if (vacio(r[k])) { throw new Error("faltan notas: las tres van de 1 a 5"); }
      const v = Number(r[k]);
      if (!Number.isInteger(v) || v < 1 || v > 5) { throw new Error("las tres notas van de 1 a 5"); }
    }
  }

  function filaBase(e, c, r, ahora) {
    return {
      lectura: e.lectura, orden: e.indice + 1, id: c.id, practica: c.practica, control: !!c.control,
      banda: r.banda, porcentaje: Number(r.porcentaje),
      abierto_en: e.abierto_en, enviado_en: ahora, segundos: (ahora - e.abierto_en) / 1000,
      banda_con: "", porcentaje_con: "", segundos_con: "",
      correccion: "", utilidad: "", lenguaje: "", comentario: r.comentario || "",
    };
  }

  function enviar(e, r, ahora) {
    const c = casoActual(e);
    if (!c) { throw new Error("no hay caso abierto: la lectura terminó"); }
    if (e.pendiente) { throw new Error("falta la respuesta con el mensaje"); }
    if (e.abierto_en === null) { throw new Error("el caso no se abrió"); }
    validarBanda(r);
    const fila = filaBase(e, c, r, ahora);
    if (c.mensaje && e.modo === "simple") {
      validarNotas(r);
      for (const k of NOTAS) { fila[k] = Number(r[k]); }
    }
    if (c.mensaje && e.modo === "secuencial") {
      e.pendiente = fila;
      e.revelado_en = ahora;
      return { estado: e, revelar: true };
    }
    return avanzar(e, fila);
  }

  function enviarConAyuda(e, r, ahora) {
    if (!e.pendiente) { throw new Error("no hay mensaje revelado"); }
    validarBanda(r);
    validarNotas(r);
    const fila = e.pendiente;
    fila.banda_con = r.banda;
    fila.porcentaje_con = Number(r.porcentaje);
    fila.segundos_con = (ahora - e.revelado_en) / 1000;
    for (const k of NOTAS) { fila[k] = Number(r[k]); }
    if (r.comentario) { fila.comentario = r.comentario; }
    e.pendiente = null;
    e.revelado_en = null;
    return avanzar(e, fila);
  }

  function avanzar(e, fila) {
    e.respuestas.push(fila);
    e.abierto_en = null;
    e.indice += 1;
    if (e.indice >= lista(e).length) {
      if (e.fase === "practica" && e.casos.length) { e.fase = "casos"; e.indice = 0; }
      else { e.fase = "fin"; }
    }
    return { estado: e, revelar: false };
  }

  function celda(v) {
    const s = (v === null || v === undefined) ? "" : String(v);
    return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  function aCSV(e) {
    const lineas = [COLUMNAS.join(",")];
    for (const f of e.respuestas) { lineas.push(COLUMNAS.map((k) => celda(f[k])).join(",")); }
    return lineas.join("\n") + "\n";
  }

  raiz.Formulario = { BANDAS, NOTAS, COLUMNAS, nuevoEstado, retomar, casoActual, terminado, abrir, enviar, enviarConAyuda, aCSV };
})(typeof module !== "undefined" && module.exports ? module.exports : window);
