import { useStore } from "../../store/useStore";
import { RUTAS } from "../../lib/formato";

/** CartButton — acceso al carrito con contador de piezas (isla de la TopBar). */
export default function CartButton() {
  const piezas = useStore((s) => s.carrito.reduce((a, i) => a + i.cantidad, 0));

  return (
    <a className="cf-btn cf-btn--secundario" href={RUTAS.carrito}>
      <span aria-hidden="true">🛒</span> Carrito
      {piezas > 0 && (
        <span className="cf-contador" aria-label={`${piezas} piezas`}>
          {piezas}
        </span>
      )}
    </a>
  );
}
