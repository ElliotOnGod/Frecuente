import { useEffect, useState } from "react";
import { graphqlRequest } from "../../../lib/graphql";
import { iconoDe, pesos } from "../../../lib/formato";
import { Skeleton } from "../Skeleton";
import SoloAdmin from "./SoloAdmin";

const QUERY = `
  query Inventario {
    categorias { id nombre }
    productos { id nombre descripcion precio stock imagenUrl categoriaId }
  }
`;

const CAMPOS = "id nombre descripcion precio stock imagenUrl categoriaId";

const MUTATION_CREAR = `
  mutation Crear($input: ProductoInput!) { crearProducto(input: $input) { ${CAMPOS} } }
`;
const MUTATION_ACTUALIZAR = `
  mutation Actualizar($id: Int!, $input: ProductoUpdateInput!) {
    actualizarProducto(id: $id, input: $input) { ${CAMPOS} }
  }
`;
const MUTATION_ELIMINAR = `
  mutation Eliminar($id: Int!) { eliminarProducto(id: $id) }
`;

const STOCK_BAJO = 10;
const VACIO = { nombre: "", descripcion: "", precio: "", stock: "", categoriaId: "" };

function validar(f) {
  const e = {};
  if (!f.nombre.trim()) e.nombre = "Escribe el nombre.";
  if (f.precio === "" || Number(f.precio) < 0) e.precio = "Precio de 0 o más.";
  if (f.stock === "" || !Number.isInteger(Number(f.stock)) || Number(f.stock) < 0)
    e.stock = "Un número entero de 0 o más.";
  if (!f.categoriaId) e.categoriaId = "Elige una categoría.";
  return e;
}

/** Formulario para crear o editar (en un modal). */
function FormularioProducto({ producto, categorias, onCerrar, onGuardado }) {
  const editando = Boolean(producto);
  const [f, setF] = useState(
    editando
      ? {
          nombre: producto.nombre,
          descripcion: producto.descripcion,
          precio: String(producto.precio),
          stock: String(producto.stock),
          categoriaId: String(producto.categoriaId),
        }
      : { ...VACIO, categoriaId: String(categorias[0]?.id ?? "") }
  );
  const [errores, setErrores] = useState({});
  const [error, setError] = useState(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    const esc = (e) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [onCerrar]);

  const campo = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));

  const enviar = async (e) => {
    e.preventDefault();
    const errs = validar(f);
    setErrores(errs);
    if (Object.keys(errs).length) return;

    setEnviando(true);
    setError(null);
    const input = {
      nombre: f.nombre.trim(),
      descripcion: f.descripcion.trim(),
      precio: Number(f.precio),
      stock: Number(f.stock),
      categoriaId: Number(f.categoriaId),
    };
    try {
      const data = editando
        ? await graphqlRequest(MUTATION_ACTUALIZAR, { id: producto.id, input })
        : await graphqlRequest(MUTATION_CREAR, { input });
      onGuardado(editando ? data.actualizarProducto : data.crearProducto, !editando);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  const entrada = (k, etiqueta, props = {}) => (
    <div className="cf-campo">
      <label className="cf-label" htmlFor={`prod-${k}`}>{etiqueta}</label>
      <input
        id={`prod-${k}`}
        className="cf-input"
        value={f[k]}
        onChange={campo(k)}
        aria-invalid={errores[k] ? "true" : undefined}
        aria-describedby={errores[k] ? `prod-${k}-err` : undefined}
        {...props}
      />
      {errores[k] && <span id={`prod-${k}-err`} className="cf-ayuda cf-ayuda--error">{errores[k]}</span>}
    </div>
  );

  return (
    <div className="cf-modal-fondo" onClick={onCerrar}>
      <form
        className="cf-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="form-prod-titulo"
        onClick={(e) => e.stopPropagation()}
        onSubmit={enviar}
        noValidate
      >
        <div className="cf-modal__barra">
          <h2 id="form-prod-titulo" style={{ margin: 0 }}>
            {editando ? `Editar ${producto.nombre}` : "Nuevo producto"}
          </h2>
          <button type="button" className="cf-btn cf-btn--icono" aria-label="Cerrar" onClick={onCerrar}>
            ✕
          </button>
        </div>

        {error && (
          <p className="cf-alerta cf-alerta--error" role="alert">
            <span className="cf-icon" aria-hidden="true">!</span> {error}
          </p>
        )}

        <div style={{ marginTop: "var(--espacio-md)" }}>
          {entrada("nombre", "Nombre", { autoFocus: true })}
          <div className="cf-campo">
            <label className="cf-label" htmlFor="prod-descripcion">Descripción</label>
            <textarea
              id="prod-descripcion"
              className="cf-input cf-textarea"
              rows={3}
              value={f.descripcion}
              onChange={campo("descripcion")}
            />
          </div>
          <div className="cf-form-fila">
            {entrada("precio", "Precio (MXN)", { type: "number", min: 0, step: "0.5", inputMode: "decimal" })}
            {entrada("stock", "Stock (piezas)", { type: "number", min: 0, step: 1, inputMode: "numeric" })}
          </div>
          <div className="cf-campo">
            <label className="cf-label" htmlFor="prod-cat">Categoría</label>
            <select
              id="prod-cat"
              className="cf-input"
              value={f.categoriaId}
              onChange={campo("categoriaId")}
              aria-invalid={errores.categoriaId ? "true" : undefined}
            >
              {categorias.map((c) => (
                <option key={c.id} value={c.id}>{c.nombre}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="cf-acciones" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="cf-btn cf-btn--secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" className="cf-btn" disabled={enviando}>
            {enviando ? "Guardando…" : editando ? "Guardar cambios" : "Crear producto"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Contenido() {
  const [productos, setProductos] = useState(null);
  const [categorias, setCategorias] = useState([]);
  const [error, setError] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [filtro, setFiltro] = useState("");
  const [soloBajo, setSoloBajo] = useState(false);
  const [editando, setEditando] = useState(undefined); // undefined = cerrado, null = nuevo
  const [borrando, setBorrando] = useState(null);
  const [stockRapido, setStockRapido] = useState({});

  useEffect(() => {
    graphqlRequest(QUERY)
      .then((d) => {
        setProductos(d.productos);
        setCategorias(d.categorias);
      })
      .catch((e) => setError(e.message));
  }, []);

  const nombreCat = (id) => categorias.find((c) => c.id === id)?.nombre ?? "—";

  const guardado = (p, nuevo) => {
    setProductos((lista) => (nuevo ? [...lista, p] : lista.map((x) => (x.id === p.id ? p : x))));
    setEditando(undefined);
    setAviso(nuevo ? `Se creó ${p.nombre}.` : `Se guardaron los cambios de ${p.nombre}.`);
  };

  const guardarStock = async (p) => {
    const valor = Number(stockRapido[p.id]);
    if (!Number.isInteger(valor) || valor < 0) {
      setError("El stock debe ser un número entero de 0 o más.");
      return;
    }
    setError(null);
    try {
      const d = await graphqlRequest(MUTATION_ACTUALIZAR, { id: p.id, input: { stock: valor } });
      setProductos((l) => l.map((x) => (x.id === p.id ? d.actualizarProducto : x)));
      setStockRapido(({ [p.id]: _, ...resto }) => resto);
      setAviso(`Stock de ${p.nombre}: ${valor} piezas.`);
    } catch (e) {
      setError(e.message);
    }
  };

  const eliminar = async (p) => {
    setError(null);
    try {
      await graphqlRequest(MUTATION_ELIMINAR, { id: p.id });
      setProductos((l) => l.filter((x) => x.id !== p.id));
      setAviso(`Se eliminó ${p.nombre}.`);
    } catch (e) {
      setError(e.message);
    }
    setBorrando(null);
  };

  const visibles = (productos ?? []).filter(
    (p) =>
      p.nombre.toLowerCase().includes(filtro.toLowerCase()) && (!soloBajo || p.stock <= STOCK_BAJO)
  );

  return (
    <>
      <div className="cf-admin__encabezado">
        <h1>Productos</h1>
        <button className="cf-btn" onClick={() => setEditando(null)} disabled={!categorias.length}>
          + Nuevo producto
        </button>
      </div>

      {aviso && (
        <p className="cf-alerta cf-alerta--success" role="status">
          <span className="cf-icon" aria-hidden="true">✓</span> {aviso}
        </p>
      )}
      {error && (
        <p className="cf-alerta cf-alerta--error" role="alert">
          <span className="cf-icon" aria-hidden="true">!</span> {error}
        </p>
      )}

      <div className="cf-filtros__fila">
        <label className="cf-sr" htmlFor="filtro-prod">Buscar producto</label>
        <input
          id="filtro-prod"
          className="cf-input"
          type="search"
          placeholder="Buscar por nombre"
          value={filtro}
          onChange={(e) => setFiltro(e.target.value)}
        />
        <label className="cf-check">
          <input type="checkbox" checked={soloBajo} onChange={(e) => setSoloBajo(e.target.checked)} />
          Solo stock bajo (≤ {STOCK_BAJO})
        </label>
      </div>

      <div className="cf-panel cf-tabla-scroll">
        <table className="cf-tabla">
          <thead>
            <tr>
              <th>Producto</th>
              <th>Categoría</th>
              <th className="cf-num">Precio</th>
              <th>Stock</th>
              <th><span className="cf-sr">Acciones</span></th>
            </tr>
          </thead>
          <tbody>
            {!productos && !error &&
              [1, 2, 3, 4].map((n) => (
                <tr key={n}><td colSpan={5}><Skeleton alto="20px" /></td></tr>
              ))}

            {productos && visibles.length === 0 && (
              <tr><td colSpan={5} className="cf-vacio" style={{ textAlign: "center" }}>Sin resultados.</td></tr>
            )}

            {visibles.map((p) => {
              const sucio = stockRapido[p.id] !== undefined && Number(stockRapido[p.id]) !== p.stock;
              return (
                <tr key={p.id}>
                  <td>
                    <span className="cf-prod-celda">
                      <span className="cf-prod-celda__icono" aria-hidden="true">{iconoDe(p.categoriaId)}</span>
                      <span>
                        {p.nombre}
                        <span className="cf-caption cf-bloque">#{p.id}</span>
                      </span>
                    </span>
                  </td>
                  <td>{nombreCat(p.categoriaId)}</td>
                  <td className="cf-num">{pesos(p.precio)}</td>
                  <td>
                    <span className="cf-stock">
                      <input
                        className="cf-input cf-input--corto"
                        type="number"
                        min="0"
                        aria-label={`Stock de ${p.nombre}`}
                        value={stockRapido[p.id] ?? p.stock}
                        onChange={(e) => setStockRapido((s) => ({ ...s, [p.id]: e.target.value }))}
                        onKeyDown={(e) => e.key === "Enter" && sucio && guardarStock(p)}
                      />
                      {sucio ? (
                        <button className="cf-btn cf-btn--secundario" onClick={() => guardarStock(p)}>
                          Guardar
                        </button>
                      ) : p.stock === 0 ? (
                        <span className="cf-estado cf-estado--error">Agotado</span>
                      ) : p.stock <= STOCK_BAJO ? (
                        <span className="cf-estado cf-estado--aviso">Bajo</span>
                      ) : null}
                    </span>
                  </td>
                  <td>
                    {borrando === p.id ? (
                      <span className="cf-acciones">
                        <button className="cf-btn cf-btn--peligro" onClick={() => eliminar(p)}>Eliminar</button>
                        <button className="cf-btn cf-btn--secundario" onClick={() => setBorrando(null)}>No</button>
                      </span>
                    ) : (
                      <span className="cf-acciones">
                        <button className="cf-btn cf-btn--secundario" onClick={() => setEditando(p)}>Editar</button>
                        <button
                          className="cf-btn cf-btn--icono"
                          aria-label={`Eliminar ${p.nombre}`}
                          onClick={() => setBorrando(p.id)}
                        >
                          🗑
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="cf-ayuda">
        Un producto que ya aparece en pedidos no se puede eliminar; ponle stock 0 para dejar de venderlo.
      </p>

      {editando !== undefined && (
        <FormularioProducto
          producto={editando}
          categorias={categorias}
          onCerrar={() => setEditando(undefined)}
          onGuardado={guardado}
        />
      )}
    </>
  );
}

/** AdminProductos — /admin/productos: inventario, precios y altas/bajas. */
export default function AdminProductos() {
  return (
    <SoloAdmin>
      <Contenido />
    </SoloAdmin>
  );
}
