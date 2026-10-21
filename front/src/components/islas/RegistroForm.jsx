import { useEffect, useState } from "react";
import { graphqlRequest } from "../../lib/graphql";
import { useStore } from "../../store/useStore";
import { RUTAS, destinoSeguro } from "../../lib/formato";

const MUTATION_REGISTRO = `
  mutation RegistrarUsuario($input: RegistroInput!) {
    registrarUsuario(input: $input) {
      token
      usuario { id nombre email telefono rol }
    }
  }
`;

const PASSWORD_MIN = 8;
const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const TELEFONO_DIGITOS = 10; // número a 10 dígitos de México

/** Revisa el formulario antes de mandarlo; regresa { campo: mensaje }. */
function validar({ nombre, email, telefono, password, confirmar }) {
  const errores = {};
  if (!nombre.trim()) errores.nombre = "Escribe tu nombre.";
  if (!EMAIL_RE.test(email.trim())) errores.email = "Escribe un correo válido.";
  // Es opcional, pero si lo escriben debe tener exactamente 10 dígitos
  if (telefono && !new RegExp(`^\\d{${TELEFONO_DIGITOS}}$`).test(telefono))
    errores.telefono = `El teléfono debe tener ${TELEFONO_DIGITOS} dígitos, solo números.`;
  if (password.length < PASSWORD_MIN)
    errores.password = `Usa al menos ${PASSWORD_MIN} caracteres.`;
  if (confirmar !== password) errores.confirmar = "Las contraseñas no coinciden.";
  return errores;
}

/**
 * RegistroForm — crea la cuenta y deja la sesión iniciada en un solo paso.
 * Valida en el navegador (para avisar rápido) y el backend vuelve a validar.
 */
export default function RegistroForm() {
  const sesion = useStore((s) => s.sesion);
  const iniciarSesion = useStore((s) => s.iniciarSesion);

  const siguiente = destinoSeguro(
    new URLSearchParams(window.location.search).get("siguiente")
  );

  const [campos, setCampos] = useState({
    nombre: "",
    email: "",
    telefono: "",
    password: "",
    confirmar: "",
  });
  const [errores, setErrores] = useState({});
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (sesion) window.location.replace(siguiente);
  }, [sesion, siguiente]);

  const cambiar = (e) => {
    const { name } = e.target;
    let { value } = e.target;
    // El teléfono solo acepta dígitos: se quitan letras y símbolos al escribir o pegar
    if (name === "telefono") value = value.replace(/\D/g, "").slice(0, TELEFONO_DIGITOS);
    setCampos((c) => ({ ...c, [name]: value }));
    if (errores[name]) setErrores((er) => ({ ...er, [name]: undefined }));
  };

  const enviar = async (e) => {
    e.preventDefault();
    const encontrados = validar(campos);
    setErrores(encontrados);
    if (Object.keys(encontrados).length) return;

    setEnviando(true);
    setError(null);
    try {
      const data = await graphqlRequest(MUTATION_REGISTRO, {
        input: {
          nombre: campos.nombre.trim(),
          email: campos.email.trim(),
          telefono: campos.telefono.trim(),
          password: campos.password,
        },
      });
      iniciarSesion(data.registrarUsuario);
      window.location.href = siguiente;
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  const campo = (name, etiqueta, props = {}) => (
    <div className="cf-campo">
      <label className="cf-label" htmlFor={`reg-${name}`}>{etiqueta}</label>
      <input
        id={`reg-${name}`}
        name={name}
        className="cf-input"
        value={campos[name]}
        onChange={cambiar}
        aria-invalid={errores[name] ? "true" : undefined}
        aria-describedby={errores[name] ? `reg-${name}-error` : undefined}
        {...props}
      />
      {errores[name] && (
        <span id={`reg-${name}-error`} className="cf-ayuda cf-ayuda--error">
          {errores[name]}
        </span>
      )}
    </div>
  );

  return (
    <div className="cf-auth">
      <h1>Crea tu cuenta</h1>
      <p className="cf-caption">Con tu cuenta registras pedidos y consultas tu historial.</p>

      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <form className="cf-panel" onSubmit={enviar} noValidate>
        {campo("nombre", "Nombre", { autoComplete: "name", required: true })}
        {campo("email", "Correo", { type: "email", autoComplete: "email", required: true })}
        {campo("telefono", "Teléfono (opcional, 10 dígitos)", {
          type: "tel",
          autoComplete: "tel-national",
          inputMode: "numeric",
          maxLength: TELEFONO_DIGITOS,
          placeholder: "3312345678",
        })}
        {campo("password", "Contraseña", {
          type: "password",
          autoComplete: "new-password",
          required: true,
        })}
        {campo("confirmar", "Confirma tu contraseña", {
          type: "password",
          autoComplete: "new-password",
          required: true,
        })}

        <button className="cf-btn cf-btn--bloque" type="submit" disabled={enviando}>
          {enviando ? "Creando cuenta…" : "Crear cuenta"}
        </button>
      </form>

      <p className="cf-auth__alterna">
        ¿Ya tienes cuenta? <a href={RUTAS.login(siguiente)}>Inicia sesión</a>
      </p>
    </div>
  );
}
