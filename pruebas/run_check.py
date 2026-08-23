from app.analizadores.analizador_diccionario_tablas import extraer_columnas, extraer_llamadas_extendedproperty, verificar_diccionario_tablas

sql='CREATE TABLE Cliente (IdVenta INT NOT NULL, IdCliente INT NULL);'
dicts="EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Tabla de clientes', @level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Cliente'"
print('SQL:', sql)
print('columnas->', extraer_columnas(sql))
print('llamadas->', extraer_llamadas_extendedproperty(dicts))
res = verificar_diccionario_tablas(sql, dicts)
print('hallazgos->', [ (h.regla, h.mensaje) for h in res ])
