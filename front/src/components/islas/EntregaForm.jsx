import { useEffect, useRef, useState } from "react";
import { pesos } from "../../lib/formato";
import { ESTADOS_MX, buscarCodigoPostal, cotizarEnvio, cpValido } from "../../lib/envios";
import { LOCAL } from "../../lib/local";
import { Skeleton } from "./Skeleton";

/**
 * EntregaForm — cómo llega el pedido (parte del checkout).
 *
 *  - Recoger en el local: sin costo.
 *  - Envío a domicilio: al escribir el código postal se llenan solos el
 *    estado, la ciudad y la lista de colonias (Envia Geocodes). Con CP y
 *    estado se cotiza con las paqueterías (Envia.com) y el cliente elige.
 *
 * El estado vive en Checkout ({ tipo, direccion, opcion }); este componente
 * lo cambia con `onCambio(prev => nuevo)`.
 */
export default function EntregaForm({ valor, onCambio, items }) {
  const { tipo, direccion, opcion } = valor;
  const [colonias, setColonias] = useState([]);
  const [otraColonia, setOtraColonia] = useState(false);
  const [cpInfo, setCpInfo] = useState({ cargando: false, error: null, texto: "" });
  const [opciones, setOpciones] = useState([]);
  const [cotizacion, setCotizacion] = useState({ cargando: false, error: null });

  const cambiarDireccion = (campo, v) =>
    onCambio((prev) => ({
      ...prev,
      direccion: { ...prev.direccion, [campo]: v },
      // Cambiar CP o estado invalida la cotización anterior
      opcion: campo === "cp" || campo === "estado" ? null : prev.opcion,
    }));

  // 1. Código postal → estado, ciudad y colonias
  useEffect(() => {
    if (tipo !== "domicilio" || !cpValido(direccion.cp)) {
      setColonias([]);
      setCpInfo({ cargando: false, error: null, texto: "" });
      return;
    }
    let vigente = true;
    setCpInfo({ cargando: true, error: null, texto: "" });
    buscarCodigoPostal(direccion.cp)
      .then((info) => {
        if (!vigente) return;
        setColonias(info.colonias);
        setOtraColonia(false);
        setCpInfo({ cargando: false, error: null, texto: `${info.ciudad}, ${info.estadoNombre}` });
        onCambio((prev) => ({
          ...prev,
          direccion: {
            ...prev.direccion,
            estado: info.estado || prev.direccion.estado,
            ciudad: info.ciudad || prev.direccion.ciudad,
            colonia: info.colonias.includes(prev.direccion.colonia) ? prev.direccion.colonia : "",
          },
        }));
      })
      .catch((err) => vigente && setCpInfo({ cargando: false, error: err.message, texto: "" }));
    return () => {
      vigente = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo, direccion.cp]);

  // 2. Cotizar cuando ya hay CP + estado (y cada vez que cambia el carrito)
  const llaveItems = JSON.stringify(items);
  const ultima = useRef("");
  useEffect(() => {
    if (tipo !== "domicilio" || !cpValido(direccion.cp) || !direccion.estado || items.length === 0) {
      setOpciones([]);
      return;
    }
    const llave = `${direccion.cp}|${direccion.estado}|${llaveItems}`;
    ultima.current = llave;
    setCotizacion({ cargando: true, error: null });
    const espera = setTimeout(() => {
      cotizarEnvio(direccion, items)
        .then((lista) => {
          if (ultima.current !== llave) return;
          setOpciones(lista);
          setCotizacion({ cargando: false, error: null });
          // Conserva la paquetería elegida si sigue disponible; si no, la más barata
          onCambio((prev) => {
            const misma = lista.find(
              (o) => o.paqueteria === prev.opcion?.paqueteria && o.servicio === prev.opcion?.servicio
            );
            return { ...prev, opcion: misma ?? lista[0] ?? null };
          });
        })
        .catch((err) => {
          if (ultima.current !== llave) return;
          setOpciones([]);
          setCotizacion({ cargando: false, error: err.message });
          onCambio((prev) => ({ ...prev, opcion: null }));
        });
    }, 350);
    return () => clearTimeout(espera);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo, direccion.cp, direccion.estado, llaveItems]);

  return (
    <section className="cf-panel" aria-labelledby="titulo-entrega">
      <h2 id="titulo-entrega" className="cf-panel__titulo">Entrega</h2>

      <fieldset className="cf-metodos">
        <legend className="cf-sr">¿Cómo quieres recibir tu pedido?</legend>
        <label className="cf-metodo" data-elegido={tipo === "recoger" ? "true" : undefined}>
          <input type="radio" name="entrega" checked={tipo === "recoger"}
            onChange={() => onCambio((prev) => ({ ...prev, tipo: "recoger" }))} />
          <span className="cf-metodo__texto">
            <strong>Recoger en el local</strong>
            <span className="cf-caption">{LOCAL.calle}, {LOCAL.colonia} · sin costo</span>
          </span>
        </label>
        <label className="cf-metodo" data-elegido={tipo === "domicilio" ? "true" : undefined}>
          <input type="radio" name="entrega" checked={tipo === "domicilio"}
            onChange={() => onCambio((prev) => ({ ...prev, tipo: "domicilio" }))} />
          <span className="cf-metodo__texto">
            <strong>Envío a domicilio u oficina</strong>
            <span className="cf-caption">Cotizamos con Estafeta, FedEx y DHL a todo México</span>
          </span>
        </label>
      </fieldset>

      {tipo === "domicilio" && (
        <>
          <div className="cf-form-grid" style={{ marginTop: "var(--espacio-md)" }}>
            <div className="cf-campo">
              <label className="cf-label" htmlFor="env-cp">Código postal</label>
              <input id="env-cp" className="cf-input" inputMode="numeric" autoComplete="postal-code"
                maxLength={5} value={direccion.cp}
                onChange={(e) => cambiarDireccion("cp", e.target.value.replace(/\D/g, "").slice(0, 5))} />
              <span className="cf-ayuda" aria-live="polite">
                {cpInfo.cargando ? "Buscando…" : cpInfo.error ?? cpInfo.texto}
              </span>
            </div>
            <div className="cf-campo">
              <label className="cf-label" htmlFor="env-estado">Estado</label>
              <select id="env-estado" className="cf-input" value={direccion.estado}
                onChange={(e) => cambiarDireccion("estado", e.target.value)}>
                <option value="">Elige…</option>
                {ESTADOS_MX.map(([clave, nombre]) => <option key={clave} value={clave}>{nombre}</option>)}
              </select>
            </div>
            <div className="cf-campo">
              <label className="cf-label" htmlFor="env-ciudad">Ciudad o municipio</label>
              <input id="env-ciudad" className="cf-input" autoComplete="address-level2" value={direccion.ciudad}
                onChange={(e) => cambiarDireccion("ciudad", e.target.value)} />
            </div>
            <div className="cf-campo">
              <label className="cf-label" htmlFor="env-colonia">Colonia</label>
              {colonias.length > 0 && !otraColonia ? (
                <select id="env-colonia" className="cf-input" value={direccion.colonia}
                  onChange={(e) => (e.target.value === "__otra"
                    ? (setOtraColonia(true), cambiarDireccion("colonia", ""))
                    : cambiarDireccion("colonia", e.target.value))}>
                  <option value="">Elige…</option>
                  {colonias.map((c) => <option key={c} value={c}>{c}</option>)}
                  <option value="__otra">Otra (escribirla)</option>
                </select>
              ) : (
                <input id="env-colonia" className="cf-input" value={direccion.colonia}
                  onChange={(e) => cambiarDireccion("colonia", e.target.value)} />
              )}
            </div>
            <div className="cf-campo cf-campo--ancho">
              <label className="cf-label" htmlFor="env-calle">Calle</label>
              <input id="env-calle" className="cf-input" autoComplete="address-line1" value={direccion.calle}
                onChange={(e) => cambiarDireccion("calle", e.target.value)} />
            </div>
            <div className="cf-campo">
              <label className="cf-label" htmlFor="env-numero">Número (ext. e int.)</label>
              <input id="env-numero" className="cf-input" value={direccion.numero}
                onChange={(e) => cambiarDireccion("numero", e.target.value)} />
            </div>
            <div className="cf-campo">
              <label className="cf-label" htmlFor="env-nombre">Quién recibe</label>
              <input id="env-nombre" className="cf-input" autoComplete="name" value={direccion.nombre}
                onChange={(e) => cambiarDireccion("nombre", e.target.value)} />
            </div>
            <div className="cf-campo">
              <label className="cf-label" htmlFor="env-tel">Teléfono (10 dígitos)</label>
              <input id="env-tel" className="cf-input" inputMode="tel" autoComplete="tel-national" maxLength={10}
                value={direccion.telefono}
                onChange={(e) => cambiarDireccion("telefono", e.target.value.replace(/\D/g, "").slice(0, 10))} />
            </div>
            <div className="cf-campo cf-campo--ancho">
              <label className="cf-label" htmlFor="env-ref">Referencias (opcional)</label>
              <input id="env-ref" className="cf-input" maxLength={200} placeholder="Entre calles, color de la fachada…"
                value={direccion.referencias} onChange={(e) => cambiarDireccion("referencias", e.target.value)} />
            </div>
          </div>

          <h3 className="cf-subtitulo">Paquetería</h3>
          {!cpValido(direccion.cp) || !direccion.estado ? (
            <p className="cf-ayuda">Escribe tu código postal para ver las opciones de envío.</p>
          ) : cotizacion.cargando ? (
            <div className="cf-metodos"><Skeleton alto="56px" /><Skeleton alto="56px" /></div>
          ) : cotizacion.error ? (
            <p className="cf-alerta cf-alerta--error" role="alert">
              <span className="cf-icon" aria-hidden="true">!</span> {cotizacion.error}
            </p>
          ) : (
            <fieldset className="cf-metodos">
              <legend className="cf-sr">Elige la paquetería</legend>
              {opciones.map((o) => {
                const elegida = opcion?.token === o.token;
                return (
                  <label key={o.token} className="cf-metodo" data-elegido={elegida ? "true" : undefined}>
                    <input type="radio" name="paqueteria" checked={elegida}
                      onChange={() => onCambio((prev) => ({ ...prev, opcion: o }))} />
                    <span className="cf-metodo__texto">
                      <strong>{o.descripcion}</strong>
                      <span className="cf-caption">Llega en {o.dias}</span>
                    </span>
                    <strong>{pesos(o.costo)}</strong>
                    {o.modo !== "real" && (
                      <span className="cf-estado cf-estado--info">{o.modo === "sandbox" ? "Sandbox" : "Prueba"}</span>
                    )}
                  </label>
                );
              })}
            </fieldset>
          )}
        </>
      )}
    </section>
  );
}
