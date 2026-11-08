import { useState } from "react";
import { iconoDe } from "../../lib/formato";
import { srcsetImagen, urlImagen } from "../../lib/imagenes";

/**
 * Foto — imagen de un producto o categoría dentro de un marco (.cf-figura).
 *
 * - Carga diferida (loading="lazy"): las fotos de abajo no se descargan
 *   hasta que el usuario hace scroll.
 * - Si no hay foto, o la URL falla, muestra el icono de la categoría como
 *   antes, así nunca queda un hueco roto.
 * - Mientras carga, el marco tiene el color neutro del manual.
 */
export default function Foto({ src, alt = "", categoriaId, ancho = 600, className = "", prioridad = false }) {
  const [fallo, setFallo] = useState(false);
  const [lista, setLista] = useState(false);
  const url = urlImagen(src, ancho);

  return (
    <div className={`cf-figura ${className}`.trim()} aria-hidden={!url || fallo ? "true" : undefined}>
      {url && !fallo ? (
        <img
          className={`cf-figura__img${lista ? " cf-figura__img--lista" : ""}`}
          src={url}
          srcSet={srcsetImagen(src, ancho)}
          alt={alt}
          loading={prioridad ? "eager" : "lazy"}
          decoding="async"
          onLoad={() => setLista(true)}
          onError={() => setFallo(true)}
        />
      ) : (
        <span className="cf-figura__icono">{iconoDe(categoriaId)}</span>
      )}
    </div>
  );
}
