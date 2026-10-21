import { useStore } from "../../store/useStore";
import { RUTAS } from "../../lib/formato";

/** SessionMenu — en la TopBar: "Iniciar sesión" o el nombre del usuario
 *  (y el acceso al panel si la cuenta es de administrador). */
export default function SessionMenu() {
  const sesion = useStore((s) => s.sesion);

  if (!sesion) {
    const aqui = window.location.pathname + window.location.search;
    const enLogin = ["/login", "/registro"].includes(window.location.pathname);
    return (
      <a
        className="cf-btn cf-btn--icono cf-sesion"
        href={enLogin ? RUTAS.login() : RUTAS.login(aqui)}
      >
        Iniciar sesión
      </a>
    );
  }

  const primerNombre = sesion.usuario.nombre.split(" ")[0];
  const enPanel = window.location.pathname.startsWith(RUTAS.admin);
  return (
    <>
      {sesion.usuario.rol === "admin" && (
        <a
          className="cf-btn cf-btn--icono cf-sesion"
          href={RUTAS.admin}
          aria-current={enPanel ? "page" : undefined}
        >
          <span aria-hidden="true">📊</span> Panel
        </a>
      )}
      <a className="cf-btn cf-btn--icono cf-sesion" href={RUTAS.cuenta}>
        <span aria-hidden="true">👤</span> {primerNombre}
      </a>
    </>
  );
}
