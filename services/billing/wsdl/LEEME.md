# WSDL de los servicios del SIAT

Son los del **ambiente de pruebas (piloto)**, bajados el 04-oct. Para producción
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
| `facturacion.wsdl` | Recepción y anulación de factura |
| `sincronizacion.wsdl` | Catálogos paramétricos, actividades, productos |

## De dónde se sacan (piloto)

| Archivo | URL |
|---|---|
| `codigos.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/FacturacionCodigos?wsdl` |
| `facturacion.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/ServicioFacturacionCompraVenta?wsdl` |
| `sincronizacion.wsdl` | `https://pilotosiatservicios.impuestos.gob.bo/v2/FacturacionSincronizacion?wsdl` |

Disponibles y no usados todavía: `FacturacionOperaciones` (eventos
significativos y puntos de venta, para contingencia),
`ServicioFacturacionDocumentoAjuste` (notas de crédito y débito) y
`ServicioRecepcionCompras`.

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
