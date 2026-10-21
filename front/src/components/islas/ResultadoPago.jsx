import { useEffect, useState } from "react";
import { useStore } from "../../store/useStore";
import { RUTAS } from "../../lib/formato";
import { confirmarPago } from "../../lib/pagos";
import { confirmarPagoMembresia } from "../../lib/membresias";

/**
 * ResultadoPago — /pago/resultado?pedido=N&metodo=…  (o ?membresia=N)
 *
 * Aquí regresan Mercado Pago y PayPal (sandbox). Las pasarelas agregan
 * sus propios parámetros:
 *   Mercado Pago:  payment_id (o collection_id), status, external_reference
 *   PayPal:        token (= id de la orden), PayerID; cancelado=1 si se salió
 *
 * NO se confía en el "status" de la URL: solo se pasan los ids al backend,
 * que le pregunta al proveedor y decide. Luego se va a la página del pedido.
 */
export default function ResultadoPago() {
  const sesion = useStore((s) => s.sesion);
  const params = new URLSearchParams(window.location.search);
  // Mercado Pago regresa external_reference: "37" (pedido) o "M5" (membresía)
  const ref = params.get("external_reference") || "";
  const membresiaId = Number(params.get("membresia") || (ref.startsWith("M") ? ref.slice(1) : 0));
  const pedidoId = membresiaId ? 0 : Number(params.get("pedido") || ref);
  const destino = membresiaId ? RUTAS.miMembresia : RUTAS.pedidoDetalle(pedidoId);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!sesion || (!pedidoId && !membresiaId)) return;

    const input = membresiaId ? { membresiaId } : { pedidoId };
    const pagoMp = params.get("payment_id") || params.get("collection_id");
    if (pagoMp && pagoMp !== "null") input.paymentId = pagoMp;
    if (params.get("token") && !params.get("cancelado")) input.paypalToken = params.get("token");

    (membresiaId ? confirmarPagoMembresia(input) : confirmarPago(input))
      .then(() => window.location.replace(destino))
      .catch((err) => setError(err.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sesion, pedidoId, membresiaId]);

  if (!pedidoId && !membresiaId) {
    return (
      <>
        <h1>No reconocimos este pago</h1>
        <a className="cf-btn" href={RUTAS.cuenta}>Ver mis pedidos</a>
      </>
    );
  }

  if (!sesion) {
    return (
      <>
        <h1>Revisando tu pago</h1>
        <p className="cf-vacio">Tu sesión se cerró. Entra de nuevo para confirmar el pago.</p>
        <a className="cf-btn" href={RUTAS.login(window.location.pathname + window.location.search)}>
          Iniciar sesión
        </a>
      </>
    );
  }

  if (error) {
    return (
      <>
        <h1>No pudimos confirmar el pago</h1>
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
        <a className="cf-btn" href={destino}>{membresiaId ? "Ir a mi membresía" : "Ir a mi pedido"}</a>
      </>
    );
  }

  return (
    <>
      <h1>Revisando tu pago…</h1>
      <p className="cf-caption">Estamos confirmando con la pasarela. No cierres esta ventana.</p>
      <div className="cf-skeleton" style={{ height: "8px", maxWidth: "320px" }} />
    </>
  );
}
