import { useEffect, useState } from 'react';
import { IconoCopiar, IconoImagen, IconoMira } from '../../components/Iconos';

/**
 * Botones al pie de cada hallazgo del plan: ver la captura del operador (como la que se pega en el
 * informe), copiarla o ir al diagrama del plan, con la consulta elegida y su operador marcado.
 */
export function CapturaHallazgo({ hallazgo, sentencias = [], archivo, onIrAlPlan }) {
  const [captura, setCaptura] = useState(null);
  const [visible, setVisible] = useState(false);
  const [estado, setEstado] = useState('');

  // Un grupo por consulta, con sus operadores sin repetir (una observación puede abarcar varias consultas).
  const grupos = [...new Set((hallazgo.nodos ?? []).map((n) => n.consulta))]
    .map((consulta) => ({
      sentencia: sentencias.find((item) => item.numero === consulta),
      nodoIds: [...new Set(hallazgo.nodos.filter((n) => n.consulta === consulta).map((n) => n.nodo))],
    }))
    .filter((grupo) => grupo.sentencia && grupo.nodoIds.length);
  const consulta = grupos[0]?.sentencia.numero;

  useEffect(() => () => {
    if (captura) URL.revokeObjectURL(captura.url);
  }, [captura]);

  if (!grupos.length) return null;

  const obtener = async () => {
    if (captura) return captura;
    // El generador (con react-dom/server) se carga solo al pedir la primera imagen.
    const { crearCapturaPlan } = await import('./capturaPlan');
    const nueva = await crearCapturaPlan({ grupos, archivo, regla: hallazgo.regla });
    setCaptura(nueva);
    return nueva;
  };

  const conAviso = (accion, texto) => async () => {
    try {
      await accion();
      if (texto) {
        setEstado(texto);
        setTimeout(() => setEstado(''), 1800);
      }
    } catch (error) {
      setEstado(error.message || 'No se pudo crear la imagen.');
    }
  };

  const alVer = conAviso(async () => {
    await obtener();
    setVisible((actual) => !actual);
  });

  const alCopiar = conAviso(async () => {
    // El portapapeles recibe la promesa: así el navegador no pierde el permiso mientras se dibuja.
    const promesa = obtener().then((resultado) => resultado.blob);
    await navigator.clipboard.write([new ClipboardItem({ 'image/png': promesa })]);
  }, 'Imagen copiada');

  // Lleva al diagrama de abajo: la primera consulta de la observación, con sus operadores marcados.
  const alIrAlPlan = () => onIrAlPlan?.({ consulta, nodos: grupos[0].nodoIds, clave: Date.now() });

  return (
    <div className="captura-hallazgo">
      <div className="captura-acciones">
        {/* Opción A elegida por la usuaria (13 nov.): el mismo estilo que «Ver en el código». */}
        <button type="button" className="captura-boton" onClick={alVer}>
          <IconoImagen />{visible ? 'Ocultar imagen' : 'Ver imagen del plan'}
        </button>
        <button type="button" className="captura-boton" onClick={alCopiar}><IconoCopiar />Copiar imagen</button>
        {onIrAlPlan && <button type="button" className="captura-boton" onClick={alIrAlPlan}><IconoMira />Ir al plan</button>}
        {estado && <span className="captura-estado" role="status">{estado}</span>}
      </div>
      {visible && captura && <img className="captura-imagen" src={captura.url} width={captura.ancho} alt={`Captura del plan: ${hallazgo.regla}`} />}
    </div>
  );
}
