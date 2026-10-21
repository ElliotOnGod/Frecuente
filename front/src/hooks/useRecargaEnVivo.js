import { useEffect, useRef, useState } from "react";
import { useEnVivo } from "../store/enVivo";

/**
 * useRecargaEnVivo — regresa un número que sube cada vez que llega un
 * aviso en vivo de los tipos indicados. Se le pasa a useGraphQLQuery como
 * `recarga` para que la pantalla se actualice sola.
 *
 * Espera un momento (por defecto 600 ms) por si llegan varios avisos
 * juntos, y así recarga una sola vez.
 */
export function useRecargaEnVivo(tipos, espera = 600) {
  const ultimo = useEnVivo((s) => s.ultimo);
  const [recarga, setRecarga] = useState(0);
  const timer = useRef(null);

  useEffect(() => {
    if (!ultimo || !tipos.includes(ultimo.tipo)) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setRecarga((n) => n + 1), espera);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ultimo]);

  // Al salir de la página se cancela la recarga pendiente
  useEffect(() => () => clearTimeout(timer.current), []);

  return recarga;
}
