import { useStore } from "../../../store/useStore";
import { RUTAS } from "../../../lib/formato";

/**
 * SoloAdmin — envuelve las islas del panel. Si no hay sesión de admin
 * muestra un aviso en lugar del contenido.
 *
 * Es solo para la interfaz: la seguridad real está en el backend, que
 * rechaza cualquier operación de admin con un token de cliente.
 */
export default function SoloAdmin({ children }) {
  const sesion = useStore((s) => s.sesion);

  if (!sesion) {
    const aqui = window.location.pathname + window.location.search;
    return (
      <div className="cf-auth">
        <h1>Panel de administración</h1>
        <p className="cf-caption">Entra con una cuenta de administrador para continuar.</p>
        <a className="cf-btn cf-btn--bloque" href={RUTAS.login(aqui)}>Iniciar sesión</a>
      </div>
    );
  }

  if (sesion.usuario.rol !== "admin") {
    return (
      <div className="cf-auth">
        <h1>Sin acceso</h1>
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span>
          Tu cuenta no tiene permisos de administrador.
        </p>
        <a className="cf-btn cf-btn--secundario" href={RUTAS.inicio}>Volver a la tienda</a>
      </div>
    );
  }

  return children;
}
