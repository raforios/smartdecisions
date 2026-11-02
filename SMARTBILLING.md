# SmartBilling

> Estado del producto, decisiones vigentes y lo que falta. Se lee al retomar
> SmartBilling. Las reglas técnicas viven en `CLAUDE.md`; el detalle técnico,
> en `services/billing/README.md` y `docs/siat/SIAT.md`. Es independiente de
> SmartDecisions: no se mezclan ni se condicionan (Rafael, 26-oct-2026).

## Producto

Facturación y punto de venta para comercios en Bolivia, como SaaS de
BearSoft, con las farmacias como primer vertical. Se vende solo o junto a
SmartDecisions.

- **Backend:** BILLING (FastAPI sobre Lambda, sólo DynamoDB).
- **Portal:** `portal/billing/` en `smartbilling.bearsoft.com.bo` (bucket
  `bearsoft-smartbilling-portal`, CloudFront `EWVWU4A03ZZ4Z`).
- **SIN:** facturación electrónica en línea, modalidad computarizada, contra el
  ambiente piloto. Sistema autorizado "sistema.SmartBilling", estado EN
  PRUEBAS, con nuestro NIT 4746720010.

## Finalizado (desplegado y probado en vivo contra el piloto)

- Mostrador, caja y egresos, recepción por lotes (PEPS y vencimientos),
  catálogo, ventas, tablero.
- Facturación: emisión en línea, anulación hasta el día 9 del mes siguiente,
  QR, ticket con la representación gráfica, interruptor en Configuración.
- Maestro de clientes con su NIT o CI.
- Contingencia automática fuera de línea: paquetes al SIN y regla programada
  cada 5 minutos (`billing-siat-contingency`).
- Pagos combinados con su código del SIN; QR separado en transferencia
  bancaria (7) y billetera móvil (32).
- Factura por correo (PDF + XML) desde `facturas@bearsoft.com.bo`, reenvío
  desde Ventas y aviso de anulación al comprador.
- Facturas manuales de contingencia (CAFC): registro del CAFC, transcripción y
  envío; historial de CUFD de 7 días. **Desplegado, sin probar en el piloto.**

## Estado actual

**En pausa desde el 30-oct-2026** (Rafael): todo lo hecho está desplegado; no
se avanza hasta tener lo que falta, para no gastar tiempo sin avances.

- **Correo:** el dominio está verificado en SES, pero la cuenta sigue en
  sandbox: a un comprador real todavía no le llega. La solicitud de producción
  vive en el caso de AWS Support 179319997000226, reabierto el 29-oct. No hay
  que cerrarlo hasta que AWS decida.
- **Datos de prueba:** THE PHARMA queda con la facturación apagada y el
  producto CONS-TI dado de baja después de cada prueba.

## Pendiente para retomar

1. **CAFC del piloto** con nuestro NIT. Antes de pedirlo afuera, releer todos
   los manuales y PDFs que ya tenemos. Rafael irá al SIN la semana del 2-nov.
   Con el CAFC, probar la transcripción y el envío en el piloto.
2. **Notas de crédito-débito:** no empezadas.
3. **Pruebas de certificación fase I** del SIN (`docs/siat/SIAT.md`, sección
   de la fase I).
4. **SES:** esperar la respuesta de AWS en el caso reabierto.
5. **Ideas aprobadas, sin fecha:** factura por WhatsApp, Libro de Ventas del
   SIN para el contador, aviso de CUFD y certificado por vencer.

## Decisiones vigentes

- El interruptor de facturación va en Configuración, apagado por defecto.
- El QR se genera en el backend (`segno`).
- El correo sale de BearSoft, no del comercio, porque es nuestro SaaS (Amazon
  SES). Los rebotes se cubren con la lista de supresión de SES hasta tener
  clientes.
- Los textos del PDF y del correo viven en `billing_parameters`: es la única
  excepción a la regla de "sin texto en el backend" (`CLAUDE.md` §6).
- Pagos con QR: transferencia bancaria si es de banco a banco; billetera móvil
  si es de una aplicación a la cuenta o al revés.
- Factura transcrita: descuenta stock y no entra en la caja; la diferencia se
  anota en la nota del cierre.
- Conseguir el CAFC le toca a cada contribuyente; en las pruebas, el
  contribuyente es BearSoft.
