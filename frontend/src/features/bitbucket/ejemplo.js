/**
 * Pull request de ejemplo para «Ver ejemplo» de la pestaña Bitbucket, con la misma forma que devolverá
 * POST /api/bitbucket/leer. Usa los scripts de ejemplo de los módulos, así la revisión del paso 3 es real.
 */
import {
  DEMO_INDICES, DEMO_NORMAL, DEMO_REPORTE, DEMO_TABLA, DICCIONARIO_TABLA, SQL_PROCEDIMIENTO, SQL_TABLA,
} from '../../config/ejemplos';

export const ENLACE_EJEMPLO = 'https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129/overview';

export const PR_EJEMPLO = {
  origen: {
    tipo: 'pr',
    espacio: 'cajaica',
    repositorio: 'objetos-base-de-datos',
    referencia: '129',
    enlace: ENLACE_EJEMPLO,
    titulo: 'Ejemplo: clientes y reportes de Gestión de Datos',
    autor: 'Ejemplo de Genesis',
  },
  archivos: [
    {
      id: 'a1', ruta: 'Tablas/TB_cliente_datos.sql', estado: 'agregado', tipo: 'tabla', objeto: 'TB_cliente_datos',
      contenido: DEMO_TABLA, pareja: null, dudoso: false, motivo: 'Tiene CREATE TABLE.',
    },
    {
      id: 'a2', ruta: 'Indices/TB_cliente_datos_IX.sql', estado: 'agregado', tipo: 'indices', objeto: 'TB_cliente_datos',
      contenido: DEMO_INDICES, pareja: 'a1', dudoso: false, motivo: 'Tiene CREATE INDEX sobre TB_cliente_datos.',
    },
    {
      id: 'a3', ruta: 'Tablas/CLICKTOPAY.Cliente.sql', estado: 'agregado', tipo: 'tabla', objeto: 'CLICKTOPAY.Cliente',
      contenido: SQL_TABLA, pareja: null, dudoso: false, motivo: 'Tiene CREATE TABLE.',
    },
    {
      id: 'a4', ruta: 'Diccionarios/CLICKTOPAY.Cliente_DD.sql', estado: 'agregado', tipo: 'diccionario_tabla',
      objeto: 'CLICKTOPAY.Cliente', contenido: DICCIONARIO_TABLA, pareja: 'a3', dudoso: false,
      motivo: 'Documenta la tabla CLICKTOPAY.Cliente con sp_addextendedproperty.',
    },
    {
      id: 'a5', ruta: 'Procedimientos/dbo.PA_Cliente_Upd_Estado.sql', estado: 'modificado', tipo: 'procedimiento',
      objeto: 'dbo.PA_Cliente_Upd_Estado', contenido: DEMO_NORMAL, pareja: null, dudoso: false,
      motivo: 'Actualiza datos (Upd): es un procedimiento.',
    },
    {
      id: 'a6', ruta: 'Procedimientos/dbo.PA_GDD_Cliente_Sel_Resumen.sql', estado: 'modificado', tipo: 'reporte',
      objeto: 'dbo.PA_GDD_Cliente_Sel_Resumen', contenido: DEMO_REPORTE, pareja: null, dudoso: false,
      motivo: 'Empieza con PA_GDD_: reporte de Gestión de Datos.',
    },
    {
      id: 'a7', ruta: 'Procedimientos/CLICKTOPAY.PA_Cliente_Sel_PorId.sql', estado: 'agregado', tipo: 'procedimiento',
      objeto: 'CLICKTOPAY.PA_Cliente_Sel_PorId', contenido: SQL_PROCEDIMIENTO, pareja: null, dudoso: true,
      motivo: 'Solo consulta datos (Sel): puede ser un reporte o un procedimiento.',
    },
    {
      id: 'a8', ruta: 'Esquemas/CLICKTOPAY.sql', estado: 'agregado', tipo: 'esquema', objeto: 'CLICKTOPAY',
      contenido: 'CREATE SCHEMA CLICKTOPAY;', pareja: null, dudoso: false, motivo: 'Tiene CREATE SCHEMA.',
    },
    {
      id: 'a9', ruta: 'Scripts/Cliente_datos_iniciales.sql', estado: 'agregado', tipo: 'datos', objeto: null,
      contenido: "INSERT INTO CLICKTOPAY.Cliente (cNombre) VALUES ('Cliente de prueba');", pareja: null, dudoso: false,
      motivo: 'Solo inserta datos.',
    },
  ],
};
