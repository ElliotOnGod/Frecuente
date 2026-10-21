import { useEffect, useState } from "react";
import { graphqlRequest } from "../lib/graphql";

/**
 * useGraphQLQuery — hook propio de fetching.
 * Devuelve { data, loading, error } y se reejecuta cuando cambia la query
 * o las variables. Se reutiliza en el catálogo, la categoría y el modal.
 *
 * `omitir` evita la petición cuando todavía no hay nada que pedir
 * (por ejemplo, el modal cerrado).
 *
 * `recarga` es un número: cuando cambia, se vuelve a pedir sin borrar lo
 * que ya se mostraba (lo usa el backoffice al recibir un aviso en vivo).
 */
export function useGraphQLQuery(query, variables = {}, { omitir = false, recarga = 0 } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!omitir);
  const [error, setError] = useState(null);

  const clave = JSON.stringify(variables);

  useEffect(() => {
    if (omitir) {
      setLoading(false);
      return;
    }

    let vigente = true;
    setLoading(true);
    setError(null);

    graphqlRequest(query, variables)
      .then((res) => {
        if (vigente) setData(res);
      })
      .catch((err) => {
        if (vigente) setError(err.message);
      })
      .finally(() => {
        if (vigente) setLoading(false);
      });

    return () => {
      vigente = false;
    };
  }, [query, clave, omitir, recarga]);

  return { data, loading, error };
}
