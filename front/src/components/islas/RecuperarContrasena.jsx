/**
 * RecuperarContrasena — recuperación de contraseña (RQF4 y RQF5).
 *
 * Sin `?token=` en la dirección: pide el correo y solicita el enlace
 * (solicitarRecuperacion). El servidor responde siempre el mismo mensaje,
 * tenga o no cuenta el correo (RQNF11).
 * Con `?token=`: es el enlace del correo; pide la contraseña nueva y la
 * fija con restablecerContrasena. El enlace vence a los 30 minutos y sirve
 * una sola vez (RQNF12 y RQNF13); el servidor rechaza contraseñas de menos
 * de 8 caracteres (RQNF14).
 */
import { useState } from "react";
import { graphqlRequest } from "../../lib/graphql";
import { RUTAS } from "../../lib/formato";

const MUTATION_SOLICITAR = `
  mutation SolicitarRecuperacion($correo: String!) {
    solicitarRecuperacion(correo: $correo)
  }
`;

const MUTATION_RESTABLECER = `
  mutation RestablecerContrasena($token: String!, $contrasena: String!) {
    restablecerContrasena(token: $token, contrasena: $contrasena)
  }
`;

const PASSWORD_MIN = 8;

function Alerta({ tipo, children }) {
  return (
    <p className={`cf-alerta cf-alerta--${tipo}`} role={tipo === "error" ? "alert" : "status"}>
      <span className="cf-icon" aria-hidden="true">{tipo === "error" ? "!" : "✓"}</span> {children}
    </p>
  );
}

function PedirEnlace() {
  const [correo, setCorreo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [mensaje, setMensaje] = useState(null);
  const [error, setError] = useState(null);

  const enviar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      const data = await graphqlRequest(MUTATION_SOLICITAR, { correo });
      setMensaje(data.solicitarRecuperacion);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <>
      <h1>¿Olvidaste tu contraseña?</h1>
      <p className="cf-caption">
        Escribe el correo de tu cuenta y te mandamos un enlace para crear una contraseña nueva.
      </p>
      {mensaje && <Alerta tipo="success">{mensaje}</Alerta>}
      {error && <Alerta tipo="error">{error}</Alerta>}
      <form className="cf-panel" onSubmit={enviar} noValidate>
        <div className="cf-campo">
          <label className="cf-label" htmlFor="recuperar-correo">Correo</label>
          <input
            id="recuperar-correo"
            className="cf-input"
            type="email"
            autoComplete="email"
            required
            value={correo}
            onChange={(e) => setCorreo(e.target.value)}
          />
        </div>
        <button className="cf-btn cf-btn--bloque" type="submit" disabled={enviando || !correo.trim()}>
          {enviando ? "Enviando…" : "Enviar enlace"}
        </button>
      </form>
    </>
  );
}

function NuevaContrasena({ token }) {
  const [contrasena, setContrasena] = useState("");
  const [confirmar, setConfirmar] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState(null);
  const [error, setError] = useState(null);

  const enviar = async (e) => {
    e.preventDefault();
    if (contrasena !== confirmar) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setEnviando(true);
    setError(null);
    try {
      const data = await graphqlRequest(MUTATION_RESTABLECER, { token, contrasena });
      setListo(data.restablecerContrasena);
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  if (listo) {
    return (
      <>
        <h1>Contraseña nueva lista</h1>
        <Alerta tipo="success">{listo}</Alerta>
        <a className="cf-btn cf-btn--bloque" href={RUTAS.login()}>Iniciar sesión</a>
      </>
    );
  }

  return (
    <>
      <h1>Crea tu contraseña nueva</h1>
      <p className="cf-caption">Usa al menos {PASSWORD_MIN} caracteres. Este enlace sirve una sola vez.</p>
      {error && (
        <Alerta tipo="error">
          {error} {error.includes("enlace") && <a href={RUTAS.recuperar}>Pedir otro enlace</a>}
        </Alerta>
      )}
      <form className="cf-panel" onSubmit={enviar} noValidate>
        <div className="cf-campo">
          <label className="cf-label" htmlFor="recuperar-nueva">Contraseña nueva</label>
          <input
            id="recuperar-nueva"
            className="cf-input"
            type="password"
            autoComplete="new-password"
            required
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
          />
        </div>
        <div className="cf-campo">
          <label className="cf-label" htmlFor="recuperar-confirmar">Confirma tu contraseña</label>
          <input
            id="recuperar-confirmar"
            className="cf-input"
            type="password"
            autoComplete="new-password"
            required
            value={confirmar}
            onChange={(e) => setConfirmar(e.target.value)}
          />
        </div>
        <button className="cf-btn cf-btn--bloque" type="submit" disabled={enviando || !contrasena || !confirmar}>
          {enviando ? "Guardando…" : "Guardar contraseña"}
        </button>
      </form>
    </>
  );
}

export default function RecuperarContrasena() {
  const token = new URLSearchParams(window.location.search).get("token");
  return (
    <div className="cf-auth">
      {token ? <NuevaContrasena token={token} /> : <PedirEnlace />}
      <p className="cf-auth__alterna">
        ¿Ya la recordaste? <a href={RUTAS.login()}>Inicia sesión</a>
      </p>
    </div>
  );
}
