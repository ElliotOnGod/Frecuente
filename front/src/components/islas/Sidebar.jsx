import { RUTAS } from "../../lib/formato";

/** Sidebar — navegación rápida entre categorías. */
export default function Sidebar({ categorias = [], actual = null }) {
  return (
    <aside className="cf-sidebar">
      <h2 className="cf-label">Categorías</h2>
      <ul className="cf-sidebar__lista">
        {categorias.map((c) => (
          <li key={c.id}>
            <a
              className="cf-sidebar__btn"
              href={RUTAS.categoria(c.id)}
              aria-current={c.id === actual ? "page" : undefined}
            >
              {c.nombre}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
