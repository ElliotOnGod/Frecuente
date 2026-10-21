import { useState } from "react";
import { useGraphQLQuery } from "../../hooks/useGraphQLQuery";
import { useStore } from "../../store/useStore";
import { pesos, RUTAS } from "../../lib/formato";
import { QUERY_PEDIDO, confirmarPago } from "../../lib/pagos";
import { QUERY_MEMBRESIA, confirmarPagoMembresia } from "../../lib/membresias";
import { Skeleton } from "./Skeleton";

/* ------------------------------------------------------------------ */
/*  Datos de prueba                                                    */
/* ------------------------------------------------------------------ */

/**
 * Tarjetas de prueba. Igual que las "tarjetas de prueba" de Mercado Pago,
 * PayPal o Stripe: son números inventados que pasan la validación (Luhn)
 * y cada uno produce siempre el mismo resultado.
 *
 * La pasarela SOLO acepta estos números, así que nadie puede escribir su
 * tarjeta real. Además, el número completo nunca sale del navegador: al
 * backend solo se le manda el resultado (aprobado / rechazado / pendiente).
 */
const TARJETAS_PRUEBA = {
  // Tarjetas de prueba de Mercado Pago México: el resultado depende del
  // NOMBRE DEL TITULAR (APRO, FUND, OTHE…), igual que en su sandbox.
  "5474925432670366": { mp: true, efecto: "Mercado Pago · crédito" },
  "4075595716483764": { mp: true, efecto: "Mercado Pago · crédito" },
  "371180303257522": { mp: true, efecto: "Mercado Pago · crédito" },
  "5579053461482647": { mp: true, efecto: "Mercado Pago · débito" },
  "4189141221267633": { mp: true, efecto: "Mercado Pago · débito" },
  // Tarjetas de prueba genéricas: el resultado depende del número
  "4242424242424242": { resultado: "aprobado", efecto: "Se aprueba" },
  "5555555555554444": { resultado: "aprobado", efecto: "Se aprueba" },
  "378282246310005": { resultado: "aprobado", efecto: "Se aprueba" },
  "4000000000009995": { resultado: "rechazado", motivo: "fondos insuficientes", efecto: "Sin fondos" },
  "4000000000000002": { resultado: "rechazado", motivo: "decisión del banco", efecto: "El banco la rechaza" },
  "4000000000000069": { resultado: "rechazado", motivo: "tarjeta vencida", efecto: "Vencida (para el banco)" },
  "4000000000000127": { resultado: "rechazado", motivo: "código de seguridad incorrecto", efecto: "CVV incorrecto" },
};

/**
 * Códigos de titular de Mercado Pago. Con una tarjeta de prueba de MP,
 * el nombre que escribes decide el resultado. Cualquier otro nombre se aprueba.
 */
const CODIGOS_MP = {
  APRO: { resultado: "aprobado" },
  CONT: { resultado: "pendiente" },
  OTHE: { resultado: "rechazado", motivo: "error general" },
  CALL: { resultado: "rechazado", motivo: "falta autorizarlo con el banco" },
  FUND: { resultado: "rechazado", motivo: "fondos insuficientes" },
  SECU: { resultado: "rechazado", motivo: "código de seguridad inválido" },
  EXPI: { resultado: "rechazado", motivo: "problema con la fecha de vencimiento" },
  FORM: { resultado: "rechazado", motivo: "error en el formulario" },
  LOCK: { resultado: "rechazado", motivo: "tarjeta deshabilitada" },
  BLAC: { resultado: "rechazado", motivo: "tarjeta en lista negra" },
};

/** Resultado de una tarjeta de prueba (para las de MP, según el titular). */
function resultadoDe(numero, titular) {
  const prueba = TARJETAS_PRUEBA[numero];
  if (!prueba.mp) return prueba;
  return CODIGOS_MP[titular.trim().toUpperCase()] ?? CODIGOS_MP.APRO;
}

/** Ficha de OXXO: el pago queda pendiente hasta que se paga en tienda. */
const OXXO = {
  id: "oxxo",
  tipo: "efectivo",
  nombre: "Efectivo en OXXO",
  detalle: "Genera una ficha que queda pendiente de pago",
  resultado: "pendiente",
};

/** Cuentas de prueba y las tarjetas que ya tienen guardadas. */
const CUENTAS_PRUEBA = [
  {
    correo: "comprador@prueba.frecuente",
    password: "prueba1234",
    nombre: "Comprador de prueba",
    tarjetas: [{ numero: "4242424242424242", titular: "COMPRADOR PRUEBA", vence: "12/30" }],
    oxxo: true,
    efecto: "Tiene una Visa con fondos y OXXO. Puede agregar más tarjetas.",
  },
  {
    correo: "sinfondos@prueba.frecuente",
    password: "prueba1234",
    nombre: "Comprador sin fondos",
    tarjetas: [{ numero: "4000000000009995", titular: "SIN FONDOS", vence: "08/29" }],
    efecto: "Su tarjeta guardada no tiene fondos: agrega otra para pagar.",
  },
  {
    correo: "nueva@prueba.frecuente",
    password: "prueba1234",
    nombre: "Cuenta nueva",
    tarjetas: [],
    efecto: "No tiene tarjetas guardadas: captura una en el formulario.",
  },
  {
    correo: "oxxo@prueba.frecuente",
    password: "prueba1234",
    nombre: "Pago en efectivo (OXXO)",
    tarjetas: [],
    oxxo: true,
    efecto: "El pago queda pendiente, como una ficha que aún no se paga.",
  },
];

/** Pagar sin cuenta: entra directo al formulario de tarjeta. */
const INVITADO = { correo: "", nombre: "Invitado (sin cuenta)", tarjetas: [] };

const TEXTO_BOTON = { tarjeta: "Pagar", efectivo: "Generar ficha de" };

/* ------------------------------------------------------------------ */
/*  Validación de tarjetas                                             */
/* ------------------------------------------------------------------ */

const soloDigitos = (s) => s.replace(/\D/g, "");

/** Marca según los primeros dígitos (BIN). */
export function marcaDe(numero) {
  if (/^3[47]/.test(numero)) return "American Express";
  if (/^4/.test(numero)) return "Visa";
  if (/^(5[1-5]|2(2[2-9]|[3-6]\d|7[01]|720))/.test(numero)) return "Mastercard";
  return null;
}

/** Algoritmo de Luhn: el dígito verificador que usan todas las tarjetas. */
export function luhnValido(numero) {
  let suma = 0;
  let doble = false;
  for (let i = numero.length - 1; i >= 0; i--) {
    let d = Number(numero[i]);
    if (doble) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    suma += d;
    doble = !doble;
  }
  return numero.length > 0 && suma % 10 === 0;
}

/** Pone espacios como en la tarjeta: 4-4-4-4 (Amex: 4-6-5). */
function formatearNumero(digitos) {
  if (/^3[47]/.test(digitos)) {
    return [digitos.slice(0, 4), digitos.slice(4, 10), digitos.slice(10, 15)].filter(Boolean).join(" ");
  }
  return digitos.slice(0, 16).replace(/(\d{4})(?=\d)/g, "$1 ");
}

/** "1228" → "12/28" mientras se escribe. */
function formatearVence(texto) {
  const d = soloDigitos(texto).slice(0, 4);
  return d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
}

/** Valida el formulario completo. Regresa { errores, tarjeta }. */
export function validarTarjeta({ numero, titular, vence, cvv }, hoy = new Date()) {
  const errores = {};
  const digitos = soloDigitos(numero);
  const marca = marcaDe(digitos);
  const largo = marca === "American Express" ? 15 : 16;

  if (!digitos) errores.numero = "Escribe el número de la tarjeta.";
  else if (!marca) errores.numero = "Solo aceptamos Visa, Mastercard y American Express.";
  else if (digitos.length !== largo) errores.numero = `El número debe tener ${largo} dígitos.`;
  else if (!luhnValido(digitos)) errores.numero = "El número no es válido, revísalo.";
  else if (!TARJETAS_PRUEBA[digitos]) {
    errores.numero = "Esta pasarela es de prueba: usa una de las tarjetas de prueba de abajo, nunca tu tarjeta real.";
  }

  const nombre = titular.trim().replace(/\s+/g, " ");
  if (!nombre) errores.titular = "Escribe el nombre como aparece en la tarjeta.";
  else if (!/^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ .'-]{3,40}$/.test(nombre)) {
    errores.titular = "Solo letras y espacios (3 a 40 caracteres).";
  }

  const m = /^(\d{2})\/(\d{2})$/.exec(vence);
  if (!m) errores.vence = "Usa el formato MM/AA.";
  else {
    const mes = Number(m[1]);
    const anio = 2000 + Number(m[2]);
    // La tarjeta sirve hasta el último día de su mes de vencimiento
    const finDeMes = new Date(anio, mes, 0, 23, 59, 59);
    if (mes < 1 || mes > 12) errores.vence = "El mes debe ir de 01 a 12.";
    else if (finDeMes < hoy) errores.vence = "La tarjeta ya venció.";
    else if (anio > hoy.getFullYear() + 20) errores.vence = "Revisa el año de vencimiento.";
  }

  const largoCvv = marca === "American Express" ? 4 : 3;
  if (!new RegExp(`^\\d{${largoCvv}}$`).test(cvv)) {
    errores.cvv = `El código de seguridad tiene ${largoCvv} dígitos.`;
  }

  if (Object.keys(errores).length) return { errores, tarjeta: null };
  return { errores, tarjeta: crearMedio({ numero: digitos, titular: nombre, vence }) };
}

/**
 * Convierte una tarjeta en "medio de pago" guardable. Solo se queda la
 * marca, los últimos 4 dígitos, el titular y el vencimiento: ni el número
 * completo ni el CVV se guardan en ningún lado.
 */
function crearMedio({ numero, titular, vence }) {
  const prueba = resultadoDe(numero, titular);
  const marca = marcaDe(numero);
  const ultimos = numero.slice(-4);
  return {
    id: `${marca}-${ultimos}-${vence}-${titular.toUpperCase()}`,
    tipo: "tarjeta",
    nombre: `${marca} •••• ${ultimos}`,
    detalle: `${titular.toUpperCase()} · vence ${vence}`,
    resultado: prueba.resultado,
    motivo: prueba.motivo,
  };
}

const mediosDeCuenta = (cuenta) => [
  ...cuenta.tarjetas.map(crearMedio),
  ...(cuenta.oxxo ? [OXXO] : []),
];

/* ------------------------------------------------------------------ */
/*  Paso 1: iniciar sesión en la pasarela                              */
/* ------------------------------------------------------------------ */

function LoginPasarela({ metodo, onEntrar }) {
  const [correo, setCorreo] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);

  const entrar = (e) => {
    e.preventDefault();
    const cuenta = CUENTAS_PRUEBA.find(
      (c) => c.correo === correo.trim().toLowerCase() && c.password === password
    );
    if (!cuenta) {
      setError("Correo o contraseña incorrectos. Usa una de las cuentas de prueba de abajo.");
      return;
    }
    setPassword("");
    onEntrar(cuenta);
  };

  const usar = (c) => {
    setCorreo(c.correo);
    setPassword(c.password);
    setError(null);
  };

  return (
    <>
      <h2 className="cf-panel__titulo">Inicia sesión para pagar</h2>
      <p className="cf-caption" style={{ marginTop: 0 }}>
        Pago con {metodo} · entorno de prueba de Frecuente
      </p>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <form onSubmit={entrar} noValidate autoComplete="off">
        <div className="cf-campo">
          <label className="cf-label" htmlFor="pasarela-correo">Correo de la cuenta de prueba</label>
          <input
            id="pasarela-correo"
            className="cf-input"
            type="email"
            autoComplete="off"
            value={correo}
            aria-invalid={error ? "true" : undefined}
            onChange={(e) => setCorreo(e.target.value)}
          />
        </div>
        <div className="cf-campo">
          <label className="cf-label" htmlFor="pasarela-password">Contraseña</label>
          <input
            id="pasarela-password"
            className="cf-input"
            type="password"
            autoComplete="off"
            value={password}
            aria-invalid={error ? "true" : undefined}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <button className="cf-btn cf-btn--bloque" type="submit" disabled={!correo || !password}>
          Iniciar sesión
        </button>
      </form>

      <button
        type="button"
        className="cf-btn cf-btn--secundario cf-btn--bloque"
        style={{ marginTop: "var(--espacio-sm)" }}
        onClick={() => onEntrar(INVITADO)}
      >
        Pagar con tarjeta sin iniciar sesión
      </button>

      <div className="cf-cuentas-prueba">
        <p className="cf-label" style={{ margin: 0 }}>Cuentas de prueba</p>
        <p className="cf-caption" style={{ marginTop: 0 }}>
          No uses tu cuenta real: aquí solo funcionan estas. Contraseña de todas: <code>prueba1234</code>
        </p>
        <ul>
          {CUENTAS_PRUEBA.map((c) => (
            <li key={c.correo}>
              <span>
                <strong>{c.nombre}</strong>
                <span className="cf-caption cf-bloque">{c.correo} · {c.efecto}</span>
              </span>
              <button type="button" className="cf-btn cf-btn--secundario" onClick={() => usar(c)}>
                Usar
              </button>
            </li>
          ))}
        </ul>
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Formulario para capturar una tarjeta                               */
/* ------------------------------------------------------------------ */

const VACIO = { numero: "", titular: "", vence: "", cvv: "" };

function FormularioTarjeta({ onAgregar, onCancelar, puedeCancelar }) {
  const [campos, setCampos] = useState(VACIO);
  const [errores, setErrores] = useState({});

  const digitos = soloDigitos(campos.numero);
  const marca = marcaDe(digitos);
  const esAmex = marca === "American Express";

  const cambiar = (nombre, valor) => {
    setCampos((c) => ({ ...c, [nombre]: valor }));
    if (errores[nombre]) setErrores((e) => ({ ...e, [nombre]: undefined }));
  };

  const enviar = (e) => {
    e.preventDefault();
    const { errores: errs, tarjeta } = validarTarjeta(campos);
    if (!tarjeta) {
      setErrores(errs);
      // Lleva el foco al primer campo con error
      const primero = ["numero", "titular", "vence", "cvv"].find((k) => errs[k]);
      document.getElementById(`tarjeta-${primero}`)?.focus();
      return;
    }
    setCampos(VACIO); // el número y el CVV no se quedan en memoria
    onAgregar(tarjeta);
  };

  /** Llena el formulario con una tarjeta de prueba. */
  const usarPrueba = (numero) => {
    setCampos((c) => ({
      ...c,
      numero: formatearNumero(numero),
      vence: TARJETAS_PRUEBA[numero].mp ? "11/30" : "12/30",
      cvv: /^3[47]/.test(numero) ? "1234" : "123",
      // Con las de Mercado Pago se propone APRO; cámbialo para otro resultado
      titular: TARJETAS_PRUEBA[numero].mp ? "APRO" : c.titular,
    }));
    setErrores({});
    document.getElementById("tarjeta-titular")?.focus();
  };

  const campo = (nombre, etiqueta, props) => (
    <div className="cf-campo">
      <label className="cf-label" htmlFor={`tarjeta-${nombre}`}>{etiqueta}</label>
      <input
        id={`tarjeta-${nombre}`}
        className="cf-input"
        autoComplete="off"
        value={campos[nombre]}
        aria-invalid={errores[nombre] ? "true" : undefined}
        aria-describedby={errores[nombre] ? `tarjeta-${nombre}-error` : undefined}
        {...props}
      />
      {errores[nombre] && (
        <span id={`tarjeta-${nombre}-error`} className="cf-ayuda cf-ayuda--error">
          {errores[nombre]}
        </span>
      )}
    </div>
  );

  return (
    <form className="cf-tarjeta-form" onSubmit={enviar} noValidate autoComplete="off">
      <div className="cf-tarjeta-form__titulo">
        <p className="cf-label" style={{ margin: 0 }}>Agregar tarjeta</p>
        {marca && <span className="cf-estado cf-estado--info">{marca}</span>}
      </div>

      {campo("numero", "Número de tarjeta", {
        inputMode: "numeric",
        placeholder: "4242 4242 4242 4242",
        maxLength: 19,
        className: "cf-input cf-input--tarjeta",
        onChange: (e) => cambiar("numero", formatearNumero(soloDigitos(e.target.value))),
      })}

      {campo("titular", "Nombre del titular", {
        placeholder: "Como en la tarjeta",
        maxLength: 40,
        style: { textTransform: "uppercase" },
        onChange: (e) => cambiar("titular", e.target.value),
      })}

      <div className="cf-form-fila">
        {campo("vence", "Vencimiento", {
          inputMode: "numeric",
          placeholder: "MM/AA",
          maxLength: 5,
          onChange: (e) => cambiar("vence", formatearVence(e.target.value)),
        })}
        {campo("cvv", "CVV", {
          type: "password",
          inputMode: "numeric",
          placeholder: esAmex ? "4 dígitos" : "3 dígitos",
          maxLength: esAmex ? 4 : 3,
          onChange: (e) => cambiar("cvv", soloDigitos(e.target.value)),
        })}
      </div>

      <div className="cf-acciones cf-acciones--envolver">
        <button className="cf-btn" type="submit">Agregar tarjeta</button>
        {puedeCancelar && (
          <button className="cf-btn cf-btn--secundario" type="button" onClick={onCancelar}>
            Cancelar
          </button>
        )}
      </div>

      <div className="cf-cuentas-prueba">
        <p className="cf-label" style={{ margin: 0 }}>Tarjetas de prueba</p>
        <p className="cf-caption" style={{ marginTop: 0 }}>
          Entorno de prueba: solo se aceptan estos números. Usa cualquier vencimiento
          futuro y cualquier CVV.
        </p>
        <p className="cf-caption" style={{ marginTop: 0 }}>
          Con las de <strong>Mercado Pago</strong>, el nombre del titular decide el resultado:{" "}
          <code>APRO</code> se aprueba, <code>CONT</code> queda pendiente, <code>FUND</code> sin
          fondos, <code>SECU</code> CVV inválido, <code>OTHE</code> rechazada.
        </p>
        <ul>
          {Object.entries(TARJETAS_PRUEBA).map(([numero, t]) => (
            <li key={numero}>
              <span>
                <code className="cf-tarjeta-numero">{formatearNumero(numero)}</code>
                <span className="cf-caption cf-bloque">{marcaDe(numero)} · {t.efecto}</span>
              </span>
              <button type="button" className="cf-btn cf-btn--secundario" onClick={() => usarPrueba(numero)}>
                Usar
              </button>
            </li>
          ))}
        </ul>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/*  Paso 2: elegir con qué pagar (o capturar una tarjeta nueva)         */
/* ------------------------------------------------------------------ */

/**
 * Si una tarjeta se rechaza, el cliente se queda aquí, ve el motivo y
 * puede elegir otra o capturar una nueva, igual que en la pasarela real.
 * Solo se sale cuando el pago se aprueba, queda pendiente (OXXO) o el
 * cliente decide volver a la tienda.
 */
function ElegirMedio({ cuenta, cargo, onCambiarCuenta }) {
  const [medios, setMedios] = useState(() => mediosDeCuenta(cuenta));
  const [elegido, setElegido] = useState(() => mediosDeCuenta(cuenta)[0]?.id ?? null);
  const [agregando, setAgregando] = useState(() => mediosDeCuenta(cuenta).length === 0);
  const [rechazos, setRechazos] = useState([]); // medios que ya fallaron en esta sesión
  const [rechazo, setRechazo] = useState(null); // último rechazo, para el aviso
  const [aviso, setAviso] = useState(null);
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  const medio = medios.find((m) => m.id === elegido);

  const agregar = (tarjeta) => {
    // Si ya estaba (misma tarjeta, vencimiento y titular), solo se selecciona
    setMedios((ms) => (ms.some((m) => m.id === tarjeta.id) ? ms : [...ms, tarjeta]));
    setRechazos((r) => r.filter((id) => id !== tarjeta.id));
    setElegido(tarjeta.id);
    setAgregando(false);
    setRechazo(null);
    setAviso(`Agregaste tu ${tarjeta.nombre}.`);
  };

  const pagar = async () => {
    setEnviando(true);
    setError(null);
    setRechazo(null);
    setAviso(null);
    try {
      await cargo.confirmar(medio.resultado);
      if (medio.resultado === "rechazado") {
        // El intento queda registrado, pero el cliente sigue en la pasarela
        setRechazos((r) => (r.includes(medio.id) ? r : [...r, medio.id]));
        setRechazo(medio);
        setEnviando(false);
        const siguiente = medios.find((m) => m.id !== medio.id && !rechazos.includes(m.id));
        if (siguiente) setElegido(siguiente.id);
        else setAgregando(true); // ya no quedan opciones: abre el formulario
        return;
      }
      window.location.replace(cargo.destino);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <>
      <div className="cf-pasarela__cuenta">
        <span>
          <span className="cf-caption cf-bloque">Pagando como</span>
          <strong>{cuenta.nombre}</strong>
          {cuenta.correo && <span className="cf-caption cf-bloque">{cuenta.correo}</span>}
        </span>
        <button className="cf-link" onClick={onCambiarCuenta} disabled={enviando}>
          {cuenta.correo ? "Cambiar de cuenta" : "Iniciar sesión"}
        </button>
      </div>

      {rechazo && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span>
          Tu {rechazo.nombre} fue rechazada por {rechazo.motivo}. Elige otro medio
          o agrega una tarjeta nueva; {cargo.tipo === "pedido" ? "tu pedido sigue apartado" : "tu membresía sigue reservada"}.
        </p>
      )}

      {aviso && (
        <p className="cf-alerta cf-alerta--success" role="status">
          <span className="cf-icon" aria-hidden="true">✓</span> {aviso}
        </p>
      )}

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      {medios.length > 0 && (
        <fieldset className="cf-metodos" disabled={enviando}>
          <legend className="cf-label">¿Con qué quieres pagar?</legend>
          {medios.map((m) => (
            <label key={m.id} className="cf-metodo" data-elegido={elegido === m.id ? "true" : undefined}>
              <input
                type="radio"
                name="medio"
                value={m.id}
                checked={elegido === m.id}
                onChange={() => setElegido(m.id)}
              />
              <span className="cf-metodo__texto">
                <strong>{m.nombre}</strong>
                <span className="cf-caption">{m.detalle}</span>
              </span>
              {rechazos.includes(m.id) && <span className="cf-estado cf-estado--error">Rechazada</span>}
            </label>
          ))}
        </fieldset>
      )}

      {agregando ? (
        <FormularioTarjeta
          onAgregar={agregar}
          onCancelar={() => setAgregando(false)}
          puedeCancelar={medios.length > 0}
        />
      ) : (
        <button
          className="cf-btn cf-btn--secundario cf-btn--bloque"
          onClick={() => {
            setAgregando(true);
            setAviso(null);
          }}
          disabled={enviando}
        >
          + Agregar tarjeta
        </button>
      )}

      {medio && !agregando && (
        <button
          className="cf-btn cf-btn--bloque"
          onClick={pagar}
          disabled={enviando}
          style={{ marginTop: "var(--espacio-md)" }}
        >
          {enviando ? "Procesando…" : `${TEXTO_BOTON[medio.tipo]} ${pesos(cargo.total)}`}
        </button>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ */
/*  Página                                                             */
/* ------------------------------------------------------------------ */

/**
 * Convierte un pedido o una membresía en un "cargo" con lo que la
 * pasarela necesita saber: cuánto, qué referencia, a dónde regresar y
 * cómo confirmar el resultado. Así la misma pasarela cobra las dos cosas.
 */
function aCargo(tipo, id, data) {
  if (tipo === "membresia") {
    const m = data?.membresia;
    if (!m) return null;
    return {
      tipo,
      total: m.precio,
      metodoNombre: m.pago?.metodoNombre,
      descripcion: `Membresía ${m.plan?.nombre} · ${m.referencia} · 30 días`,
      pagado: m.pago?.estado === "aprobado",
      abierto: m.estado === "pendiente",
      destino: RUTAS.miMembresia,
      confirmar: (simulacion) => confirmarPagoMembresia({ membresiaId: id, simulacion }),
    };
  }
  const p = data?.pedido;
  if (!p) return null;
  return {
    tipo,
    total: p.total,
    metodoNombre: p.pago?.metodoNombre,
    descripcion: `Pedido ${p.referencia} · ${p.piezas} pieza${p.piezas === 1 ? "" : "s"}`,
    pagado: p.pago?.estado === "aprobado",
    abierto: p.estado === "registrado",
    destino: RUTAS.pedidoDetalle(id),
    confirmar: (simulacion) => confirmarPago({ pedidoId: id, simulacion }),
  };
}

/**
 * PasarelaSimulada — /pago/simulado?pedido=N  o  /pago/simulado?membresia=N
 *
 * Sustituye a Mercado Pago / PayPal cuando el backend está en
 * PAGOS_MODO=simulado (la demo en clase). Reproduce el recorrido de la
 * pasarela real — iniciar sesión, capturar o elegir tarjeta, reintentar si
 * se rechaza — pero está marcada como prueba, no copia el diseño de ningún
 * proveedor, solo acepta tarjetas de prueba y no cobra nada.
 */
export default function PasarelaSimulada() {
  const sesion = useStore((s) => s.sesion);
  const params = new URLSearchParams(window.location.search);
  const tipo = params.get("membresia") ? "membresia" : "pedido";
  const id = Number(params.get(tipo));

  const consulta = useGraphQLQuery(
    tipo === "membresia" ? QUERY_MEMBRESIA : QUERY_PEDIDO,
    { id },
    { omitir: !id || !sesion }
  );
  const [cuenta, setCuenta] = useState(null);

  const { loading, error } = consulta;
  const cargo = aCargo(tipo, id, consulta.data);
  const volver = tipo === "membresia" ? RUTAS.miMembresia : RUTAS.pedidoDetalle(id);

  if (!sesion) {
    return (
      <>
        <h1>Pasarela de prueba</h1>
        <p className="cf-vacio">Inicia sesión en la tienda para continuar con tu pago.</p>
        <a className="cf-btn" href={RUTAS.login(window.location.pathname + window.location.search)}>
          Iniciar sesión
        </a>
      </>
    );
  }

  return (
    <div className="cf-pasarela">
      <p className="cf-alerta" role="note">
        <span className="cf-icon" aria-hidden="true">i</span>
        Pasarela de prueba del proyecto. No se cobra nada y solo acepta tarjetas
        de prueba; nunca escribas tu tarjeta real. Con las llaves de sandbox,
        aquí aparecería la página real del proveedor.
      </p>

      <div className="cf-panel">
        {loading && <Skeleton alto="64px" />}

        {(error || (!loading && !cargo)) && (
          <p className="cf-alerta cf-alerta--error" role="alert">
            <span className="cf-icon" aria-hidden="true">!</span>
            {error || `No encontramos este ${tipo === "membresia" ? "cobro de membresía" : "pedido"}.`}
          </p>
        )}

        {cargo && (
          <>
            <div className="cf-pasarela__resumen">
              <span className="cf-caption">Total a pagar</span>
              <strong className="cf-pasarela__monto">{pesos(cargo.total)}</strong>
              <span className="cf-caption">Frecuente · {cargo.descripcion}</span>
            </div>

            {cargo.pagado ? (
              <a className="cf-btn" href={cargo.destino}>Esto ya está pagado</a>
            ) : !cargo.abierto ? (
              <a className="cf-btn" href={cargo.destino}>Ya no tiene un pago pendiente</a>
            ) : !cuenta ? (
              <LoginPasarela metodo={cargo.metodoNombre} onEntrar={setCuenta} />
            ) : (
              <ElegirMedio
                key={cuenta.correo || "invitado"}
                cuenta={cuenta}
                cargo={cargo}
                onCambiarCuenta={() => setCuenta(null)}
              />
            )}
          </>
        )}
      </div>

      <a className="cf-link" href={volver}>Volver a la tienda sin pagar</a>
    </div>
  );
}
