import { useEffect, useState } from "react";
import { diaCorto, pesos, pesosCortos } from "../../../lib/formato";

/**
 * Gráficas del panel, hechas a mano con SVG (sin librerías) y con los
 * tokens del manual, así respetan el modo oscuro automáticamente.
 *
 * Reglas que siguen:
 *  - Una sola serie por gráfica → un solo color (Tostado), sin leyenda;
 *    el título dice qué es.
 *  - Ejes y rejilla discretos; los textos usan colores de texto, no el de la serie.
 *  - Tooltip al pasar el mouse o con el teclado, y vista de tabla como alternativa.
 */

/** Ancho real del contenedor, para dibujar el SVG sin deformar el texto. */
function useAncho() {
  // Ref de función: se vuelve a medir aunque el lienzo se desmonte
  // (por ejemplo al cambiar a la vista de tabla y regresar).
  const [nodo, ref] = useState(null);
  const [ancho, setAncho] = useState(600);
  useEffect(() => {
    if (!nodo) return;
    const obs = new ResizeObserver(([e]) => setAncho(Math.max(280, e.contentRect.width)));
    obs.observe(nodo);
    return () => obs.disconnect();
  }, [nodo]);
  return [ref, ancho];
}

/** Escala "bonita" para el eje: 0, 2 000, 4 000… */
function topeBonito(max) {
  if (max <= 0) return 100;
  const p = 10 ** Math.floor(Math.log10(max));
  const n = max / p;
  const paso = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  return paso * p;
}

/** Barra con las esquinas de arriba redondeadas (4px) y base recta. */
function barra(x, y, w, h, r = 4) {
  if (h <= 0) return "";
  const rr = Math.min(r, w / 2, h);
  return `M${x},${y + h} V${y + rr} Q${x},${y} ${x + rr},${y} H${x + w - rr} Q${x + w},${y} ${x + w},${y + rr} V${y + h} Z`;
}

/** Ventas por día: columnas verticales con tooltip. */
export function GraficaVentas({ puntos }) {
  const [ref, ancho] = useAncho();
  const [activo, setActivo] = useState(null);
  const [tabla, setTabla] = useState(false);

  const alto = 240;
  const m = { arriba: 12, derecha: 8, abajo: 28, izquierda: 56 };
  const w = ancho - m.izquierda - m.derecha;
  const h = alto - m.arriba - m.abajo;

  const tope = topeBonito(Math.max(...puntos.map((p) => p.total), 0));
  const marcas = [0, 0.25, 0.5, 0.75, 1].map((f) => f * tope);
  const banda = w / Math.max(puntos.length, 1);
  const anchoBarra = Math.max(2, banda - 2); // 2px de separación entre barras
  // Etiquetas del eje x sin encimarse: aprox. una cada 56px
  const cadaN = Math.max(1, Math.ceil(56 / banda));

  const y = (v) => m.arriba + h - (v / tope) * h;
  const p = activo != null ? puntos[activo] : null;

  return (
    <figure className="cf-grafica">
      <div className="cf-grafica__barra">
        <figcaption>
          <h2 className="cf-panel__titulo">Ventas por día</h2>
          <span className="cf-caption">Pedidos con pago aprobado, en pesos</span>
        </figcaption>
        <button className="cf-link" onClick={() => setTabla((t) => !t)}>
          {tabla ? "Ver gráfica" : "Ver como tabla"}
        </button>
      </div>

      {tabla ? (
        <div className="cf-tabla-scroll cf-tabla-scroll--alta">
          <table className="cf-tabla">
            <thead>
              <tr><th>Día</th><th className="cf-num">Pedidos</th><th className="cf-num">Ventas</th></tr>
            </thead>
            <tbody>
              {puntos.map((d) => (
                <tr key={d.fecha}>
                  <td>{diaCorto(d.fecha)}</td>
                  <td className="cf-num">{d.pedidos}</td>
                  <td className="cf-num">{pesos(d.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div ref={ref} className="cf-grafica__lienzo" onMouseLeave={() => setActivo(null)}>
          <svg
            width={ancho}
            height={alto}
            role="img"
            aria-label={`Ventas por día de ${diaCorto(puntos[0]?.fecha)} a ${diaCorto(puntos.at(-1)?.fecha)}`}
          >
            {marcas.map((v) => (
              <g key={v}>
                <line
                  x1={m.izquierda}
                  x2={ancho - m.derecha}
                  y1={y(v)}
                  y2={y(v)}
                  className={v === 0 ? "cf-grafica__base" : "cf-grafica__rejilla"}
                />
                <text x={m.izquierda - 8} y={y(v)} dy="0.32em" textAnchor="end" className="cf-grafica__eje">
                  {pesosCortos(v)}
                </text>
              </g>
            ))}

            {puntos.map((d, i) => {
              const x = m.izquierda + i * banda + 1;
              return (
                <g key={d.fecha}>
                  <path
                    d={barra(x, y(d.total), anchoBarra, m.arriba + h - y(d.total))}
                    className="cf-grafica__marca"
                    data-activa={activo === i ? "true" : undefined}
                  />
                  {i % cadaN === 0 && (
                    <text x={x + anchoBarra / 2} y={alto - 8} textAnchor="middle" className="cf-grafica__eje">
                      {diaCorto(d.fecha)}
                    </text>
                  )}
                  {/* Zona de hover más grande que la barra, para atinarle fácil */}
                  <rect
                    x={m.izquierda + i * banda}
                    y={m.arriba}
                    width={banda}
                    height={h}
                    fill="transparent"
                    tabIndex={0}
                    aria-label={`${diaCorto(d.fecha)}: ${pesos(d.total)}, ${d.pedidos} pedidos`}
                    onMouseEnter={() => setActivo(i)}
                    onFocus={() => setActivo(i)}
                    onBlur={() => setActivo(null)}
                  />
                </g>
              );
            })}
          </svg>

          {p && (
            <div
              className="cf-tooltip"
              style={{
                left: Math.min(
                  Math.max(m.izquierda + activo * banda + banda / 2, 70),
                  ancho - 70
                ),
                top: Math.max(y(p.total) - 8, 0),
              }}
              role="status"
            >
              <strong>{pesos(p.total)}</strong>
              <span>{diaCorto(p.fecha)} · {p.pedidos} pedido{p.pedidos === 1 ? "" : "s"}</span>
            </div>
          )}
        </div>
      )}
    </figure>
  );
}

/**
 * Barras horizontales con etiqueta directa (nombre a la izquierda,
 * valor a la derecha). Para comparar pocas categorías.
 */
export function BarrasHorizontales({ titulo, subtitulo, filas, formato = pesos, detalle }) {
  const max = Math.max(...filas.map((f) => f.valor), 0) || 1;
  return (
    <figure className="cf-grafica">
      <figcaption>
        <h2 className="cf-panel__titulo">{titulo}</h2>
        {subtitulo && <span className="cf-caption">{subtitulo}</span>}
      </figcaption>
      <ul className="cf-barras">
        {filas.map((f) => (
          <li key={f.clave} className="cf-barras__fila" title={`${f.nombre}: ${formato(f.valor)}${detalle ? ` · ${detalle(f)}` : ""}`}>
            <span className="cf-barras__nombre">{f.nombre}</span>
            <span className="cf-barras__pista" aria-hidden="true">
              <span className="cf-barras__marca" style={{ width: `${(f.valor / max) * 100}%` }} />
            </span>
            <span className="cf-barras__valor">
              {formato(f.valor)}
              {detalle && <span className="cf-caption"> · {detalle(f)}</span>}
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
