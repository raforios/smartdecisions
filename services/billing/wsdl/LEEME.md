# WSDL de los servicios del SIAT

Son los del **ambiente de pruebas (piloto)**, bajados el 04-oct (codigos, facturacion, sincronizacion) y el 26-oct (operaciones, ajuste, compras). Para producción
se reemplazan por los del ambiente 1.

## Por qué van en disco y no se bajan

`zeep` descarga el WSDL cuando construye el cliente. En Lambda eso sería una
llamada de red **en cada arranque en frío**, y una caída del SIAT se volvería
una caída nuestra. Leyéndolos de disco: cero red al arrancar, y el contrato
queda versionado con el código, así que no puede cambiar bajo nuestros pies sin
un commit.

## Qué archivos son

`services/billing/services/billing_siat_client.py` los busca por nombre en `SIAT_WSDL_DIR` (`wsdl`, relativo a la raíz del servicio: viajan dentro del ZIP del Lambda):

| Archivo | Servicios que trae |
|---|---|
| `codigos.wsdl` | CUIS, CUFD, verificación de NIT |
| `facturacion.wsdl` | Factura compra-venta: recepción individual, por paquete y masiva, anulación y su reversión |
| `sincronizacion.wsdl` | Catálogos paramétricos, leyendas, actividades, productos, fecha y hora |
| `operaciones.wsdl` | Puntos de venta y eventos significativos (contingencia) |
| `ajuste.wsdl` | Notas de crédito y débito |
| `compras.wsdl` | Registro de compras |

**Cada uno viene en dos archivos.** El SIN publica la mitad de cada servicio
(los tipos y las operaciones) en un segundo WSDL que el primero importa por
URL. Así bajado, zeep salía a buscarla en cada arranque en frío. Se bajó
también esa mitad como `<servicio>_types.wsdl` y el `location` del import
apunta al archivo local (26-oct). Si se vuelven a bajar, hay que repetir
ese cambio.

## De dónde se sacan (piloto)

Las direcciones son las de la solicitud de autorización N.º 9741:

| Archivo | URL |
|---|---|
| `codigos.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/FacturacionCodigos?wsdl` |
| `facturacion.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/ServicioFacturacionCompraVenta?wsdl` |
| `sincronizacion.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/FacturacionSincronizacion?wsdl` |
| `operaciones.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/FacturacionOperaciones?wsdl` |
| `ajuste.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/ServicioFacturacionDocumentoAjuste?wsdl` |
| `compras.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/ServicioRecepcionCompras?wsdl` |

La mitad importada de cada uno es la misma URL con `?wsdl=<Nombre>.wsdl`, como
lo dice su `wsdl:import`.

El token viaja en el header `apikey` como `TokenApi <token>`: sin ese prefijo
el SIAT responde «API KEY NO VALIDO».

Hay un WSDL por ambiente. El que se ponga acá tiene que corresponder al
`SIAT_ENVIRONMENT` del `.env` (1 producción, 2 pruebas): un código pedido en un
ambiente no sirve en el otro.

## Cómo comprobar que quedaron bien

```bash
cd services/billing
../../../.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from services import billing_siat_client as c
print(c._client(c.SERVICE_CODES).service._operations.keys())
"
```

Si lista las operaciones, el WSDL se leyó. Si responde `SIAT_WSDL_MISSING`, el
archivo no está o tiene otro nombre.
