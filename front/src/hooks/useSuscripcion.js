import { useEffect, useRef, useState } from "react";
import { suscribir } from "../lib/subscripciones";

/**
 * useSuscripcion — hook propio para GraphQL Subscriptions.
 * Hermano de useGraphQLQuery, pero en lugar de pedir una vez, se queda
 * escuchando y actualiza `dato` cada vez que el servidor manda algo.
 *
 *   const { dato, estado, error } = useSuscripcion(SUB, { id }, { omitir: !id });
 *
 * `alRecibir` (opcional) se llama con cada dato, útil para avisos o
 * para recargar otra consulta.
 */
export function useSuscripcion(query, variables = {}, { omitir = false, alRecibir } = {}) {
  const [dato, setDato] = useState(null);
  const [estado, setEstado] = useState(omitir ? "cerrado" : "conectando");
  const [error, setError] = useState(null);

  // Guardamos el callback en una ref para no reconectar cada render
  const callback = useRef(alRecibir);
  callback.current = alRecibir;

  const clave = JSON.stringify(variables);

  useEffect(() => {
    if (omitir) return undefined;
    setError(null);
    setDato(null); // nueva suscripción: no mostrar datos de la anterior
    const cancelar = suscribir(query, variables, {
      onDato: (d) => {
        setDato(d);
        callback.current?.(d);
      },
      onError: setError,
      onEstado: setEstado,
    });
    return cancelar;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, clave, omitir]);

  return { dato, estado, error };
}
