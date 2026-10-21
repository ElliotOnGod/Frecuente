/**
 * graphqlRequest — cliente GraphQL mínimo sobre fetch.
 * Lo usan el hook useGraphQLQuery, los formularios de sesión y Checkout.
 *
 * Si hay sesión, manda el token en  Authorization: Bearer <token>.
 * Si el backend avisa que la sesión expiró, la cierra en el store.
 *
 * En Astro las variables de entorno visibles en el navegador llevan el
 * prefijo PUBLIC_ (antes era VITE_API_URL).
 */
import { useStore } from "../store/useStore";

const API_URL = import.meta.env.PUBLIC_API_URL || "http://localhost:8000/graphql";
const SESION_EXPIRADA = "Tu sesión expiró";

export async function graphqlRequest(query, variables = {}) {
  const token = useStore.getState().sesion?.token;

  const res = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ query, variables }),
  });

  if (!res.ok) {
    throw new Error(`El servidor respondió ${res.status}. ¿Está corriendo el backend?`);
  }

  const json = await res.json();
  if (json.errors?.length) {
    const mensaje = json.errors[0].message;
    if (mensaje.startsWith(SESION_EXPIRADA)) useStore.getState().cerrarSesion();
    throw new Error(mensaje);
  }
  return json.data;
}
