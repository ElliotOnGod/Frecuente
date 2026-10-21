import { iconoDe, RUTAS } from "../../lib/formato";

/** CategoryGrid — rejilla de tarjetas de categoría. Cada una lleva a su página. */
export default function CategoryGrid({ categorias = [] }) {
  return (
    <div className="cf-categorias">
      {categorias.map((c) => (
        <a key={c.id} className="cf-card cf-card--accion" href={RUTAS.categoria(c.id)}>
          <div className="cf-figura" aria-hidden="true">{iconoDe(c.id)}</div>
          <div className="cf-card__cuerpo">
            <h3 className="cf-card__titulo">{c.nombre}</h3>
            <p className="cf-caption">{c.descripcion}</p>
            <span className="cf-insignia">{c.productos?.length ?? 0} productos</span>
          </div>
        </a>
      ))}
    </div>
  );
}
