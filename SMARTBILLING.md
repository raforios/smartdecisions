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
  PRUEBAS, con el NIT de Rafael, 4746720010.

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

1. **CAFC del piloto** con el NIT de Rafael. Antes de pedirlo afuera, releer todos
   los manuales y PDFs que ya tenemos. Rafael irá al SIN la semana del 2-nov.
   Con el CAFC, probar la transcripción y el envío en el piloto.
2. **Notas de crédito-débito:** no empezadas.
3. **Pruebas de certificación fase I** del SIN (`docs/siat/SIAT.md`, sección
   de la fase I).
4. **SES:** esperar la respuesta de AWS en el caso reabierto.
5. **Ideas aprobadas, sin fecha:** factura por WhatsApp, Libro de Ventas del
   SIN para el contador, aviso de CUFD y certificado por vencer.
6. **Proveedores y pedidos** (Rafael, 04-oct, nunca programado): «puede
   recibir por partes y quedar pendientes»; recibir sin pedido previo: «sí»;
   producto–proveedor: «debemos mantener el registro de todo». Rafael, 2-nov:
   «esto debemos terminar». También lo usa el chat (`idea/plan_chat.md`, 6.2).
7. **Traspaso entre sucursales** (Rafael, 04-oct): «algunas empresas tienen 2
   sucursales y pueden tener exceso de inventario en una y desean llevar a la
   otra para tener disponibilidad, no lo compliques».
8. **Lo común a todos los rubros** (plan de rubros, 10-oct): marca y
   categoría en el producto («Laboratorio» pasa a ser marca; «Requiere
   receta» queda como rasgo de farmacia) y el vendedor en la venta.
9. **SmartBilling → SmartDecisions:** cada venta del mostrador entra al
   análisis. Es la fase 12.1 del plan único.
10. **Máscaras por rubro, sin fecha:** farmacia (la de hoy), comida rápida en
    sala (mesas, combos, comanda; la producción queda fuera) y los demás
    rubros (ferretería, librería, minimercado, ropa), cada uno definido con
    Rafael antes de programarse.

El orden de trabajo vive en el plan único,
`docs/smartdecisions/plan.md` (fase 12).

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
