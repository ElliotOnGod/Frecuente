import { useEffect, useState } from "react";
import { graphqlRequest } from "../../lib/graphql";
import { useStore } from "../../store/useStore";
import { RUTAS, destinoSeguro } from "../../lib/formato";

const MUTATION_LOGIN = `
  mutation IniciarSesion($email: String!, $password: String!) {
    iniciarSesion(email: $email, password: $password) {
      token
      usuario { id nombre email telefono rol }
    }
  }
`;

/**
 * LoginForm — formulario controlado de inicio de sesión.
 * Al entrar guarda { token, usuario } en el store y regresa a la página de
 * donde venía (?siguiente=/checkout, por ejemplo).
 */
export default function LoginForm() {
  const sesion = useStore((s) => s.sesion);
  const iniciarSesion = useStore((s) => s.iniciarSesion);

  const siguiente = destinoSeguro(
    new URLSearchParams(window.location.search).get("siguiente")
  );

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  // Si ya hay sesión no tiene caso mostrar el formulario
  useEffect(() => {
    if (sesion) window.location.replace(siguiente);
  }, [sesion, siguiente]);

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const data = await graphqlRequest(MUTATION_LOGIN, { email, password });
      iniciarSesion(data.iniciarSesion);
      window.location.href = siguiente;
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <div className="cf-auth">
      <h1>Inicia sesión</h1>
      <p className="cf-caption">Entra con tu cuenta para registrar pedidos y ver tu historial.</p>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <form className="cf-panel" onSubmit={enviar} noValidate>
        <div className="cf-campo">
          <label className="cf-label" htmlFor="login-email">Correo</label>
          <input
            id="login-email"
            className="cf-input"
            type="email"
            autoComplete="email"
            required
            value={email}
            aria-invalid={error ? "true" : undefined}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div className="cf-campo">
          <label className="cf-label" htmlFor="login-password">Contraseña</label>
          <input
            id="login-password"
            className="cf-input"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            aria-invalid={error ? "true" : undefined}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        <button
          className="cf-btn cf-btn--bloque"
          type="submit"
          disabled={enviando || !email || !password}
        >
          {enviando ? "Entrando…" : "Iniciar sesión"}
        </button>
      </form>

      <p className="cf-auth__alterna">
        ¿No tienes cuenta? <a href={RUTAS.registro(siguiente)}>Crea una</a>
      </p>
    </div>
  );
}
