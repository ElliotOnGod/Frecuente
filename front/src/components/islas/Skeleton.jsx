/** Skeleton — bloque de carga genérico. */
export function Skeleton({ alto = "16px", ancho = "100%" }) {
  return <div className="cf-skeleton" style={{ height: alto, width: ancho }} />;
}

/** SkeletonGrid — rejilla de tarjetas fantasma mientras llega el backend. */
export function SkeletonGrid({ cantidad = 4 }) {
  return (
    <div className="cf-catalogo" aria-hidden="true">
      {Array.from({ length: cantidad }, (_, i) => (
        <div className="cf-card" key={i}>
          <Skeleton alto="150px" />
          <div className="cf-card__cuerpo">
            <Skeleton alto="20px" ancho="80%" />
            <Skeleton alto="14px" ancho="60%" />
            <Skeleton alto="14px" ancho="40%" />
          </div>
        </div>
      ))}
    </div>
  );
}
