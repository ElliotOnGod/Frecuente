/**
 * subscripciones.js — cliente mínimo de GraphQL Subscriptions.
 *
 * Habla el protocolo "graphql-transport-ws" (el estándar actual, el mismo
 * que usan Apollo y la librería graphql-ws) sobre un WebSocket nativo del
 * navegador, sin dependencias:
 *
 *   navegador                               servidor (Strawberry)
 *   ── connection_init {Authorization} ──▶
 *   ◀──────────────────── connection_ack ──
 *   ── subscribe {query, variables} ─────▶
 *   ◀──────────────────── next {data} ─────   (uno por cada aviso)
 *   ◀──────────────────── next {data} ─────
 *   ── complete ─────────────────────────▶    (al salir de la página)
 *
 * El navegador no deja poner encabezados en un WebSocket, por eso el token
 * de sesión viaja en el payload de connection_init.
 *
 * Si se cae la conexión (se reinicia el backend, se va el internet) vuelve
 * a conectar solo, esperando 1 s, 2 s, 4 s… hasta 15 s entre intentos.
 */
import { useStore } from "../store/useStore";

const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000/graphql";
// http://… → ws://…   https://… → wss://…
const WS_URL = API_URL.replace(/^http/, "ws");

/**
 * Se suscribe y regresa una función para cancelar.
 *
 * @param {string} query       subscription { … }
 * @param {object} variables
 * @param {object} callbacks   { onDato(data), onError(mensaje), onEstado(estado) }
 *        estado: "conectando" | "en_vivo" | "reconectando" | "cerrado"
 */
export function suscribir(query, variables = {}, { onDato, onError, onEstado } = {}) {
  let ws = null;
  let cerrado = false;
  let intentos = 0;
  let temporizador = null;

  const estado = (e) => onEstado?.(e);

  const conectar = () => {
    if (cerrado) return;
    estado(intentos === 0 ? "conectando" : "reconectando");
    ws = new WebSocket(WS_URL, "graphql-transport-ws");

    ws.onopen = () => {
      const token = useStore.getState().sesion?.token;
      ws.send(
        JSON.stringify({
          type: "connection_init",
          payload: token ? { Authorization: `Bearer ${token}` } : {},
        })
      );
    };

    ws.onmessage = (evento) => {
      let msg;
      try {
        msg = JSON.parse(evento.data);
      } catch {
        return;
      }
      switch (msg.type) {
        case "connection_ack":
          intentos = 0;
          estado("en_vivo");
          ws.send(JSON.stringify({ id: "1", type: "subscribe", payload: { query, variables } }));
          break;
        case "next":
          if (msg.payload?.errors?.length) {
            // Error de la subscription (por ejemplo, sin permisos): no se reintenta
            onError?.(msg.payload.errors[0].message);
            cancelar();
          } else {
            onDato?.(msg.payload.data);
          }
          break;
        case "error":
          onError?.(msg.payload?.[0]?.message || "Error en la conexión en vivo");
          cancelar();
          break;
        case "ping":
          ws.send(JSON.stringify({ type: "pong" }));
          break;
        case "complete":
          cancelar();
          break;
        default:
          break;
      }
    };

    ws.onclose = () => {
      if (cerrado) return;
      // Reintento con espera creciente (backoff exponencial)
      intentos += 1;
      estado("reconectando");
      const espera = Math.min(15000, 1000 * 2 ** (intentos - 1));
      temporizador = setTimeout(conectar, espera);
    };
  };

  const cancelar = () => {
    if (cerrado) return;
    cerrado = true;
    clearTimeout(temporizador);
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ id: "1", type: "complete" }));
      } catch {
        /* ya se estaba cerrando */
      }
    }
    ws?.close();
    estado("cerrado");
  };

  conectar();
  return cancelar;
}
