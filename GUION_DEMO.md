> Guion de la demostración de SmartDecisions. Los números son los de
> `ventas_demo.xlsx` (ver `SMARTDECISIONS.md` §4.4); si cambia el generador,
> actualizar los dos. Requiere el frontend desplegado.

# Guion de demo comercial (10 minutos)

### Antes de la reunión

| Cosa | Estado |
|---|---|
| Dataset cargado | Subir `ventas_demo.xlsx` **antes** de la reunión y dejar la sesión abierta: la carga tarda y no aporta al relato |
| Credenciales | Listas para copiar y pegar |
| Navegador | Sesión nueva, sin caché vieja, dev tools cerrados |
| Respaldo | Capturas de las cuatro pantallas clave por si falla la red |

### 1. El problema (1 min)

> "Una distribuidora mediana toma sus decisiones comerciales con la intuición del
> gerente y un reporte de ventas que solo dice cuánto se vendió. No usa un ERP
> analítico porque cuesta caro, tarda meses y necesita un consultor. Pero **sí
> tiene** un archivo de ventas. SmartDecisions convierte ese archivo en una lista
> de acciones concretas, con su valor en bolivianos, en menos de un minuto."

Diferenciador en pantalla: `Afinidad × Drop Size = Oportunidad Comercial Real`.

### 2. Resumen Comercial (3 min) — "¿cómo vamos?"

Abrir el módulo. Bs 1,17 M de venta, 24 meses de tendencia, estacionalidad con el
pico de noviembre.

**El momento que engancha es Rentabilidad:**

> "Miren esto. LÁCTEOS vende Bs 192.161 y deja 12%. NUTRICIÓN vende menos de la
> mitad y deja 29%. El reporte de ventas que ustedes reciben hoy pone a LÁCTEOS
> arriba. **El que más vende casi nunca es el que más deja**, y esa diferencia no
> la ve nadie hasta que alguien la calcula."

Seguir con Concentración: cuántos clientes hacen el 80% de la venta, y el ABC.

### 3. Oportunidades (3 min) — "¿qué le ofrezco a cada cliente?"

964 acciones en 260 puntos de venta, Bs 61.900 de venta potencial.

> "Esto no es un tablero que muestra lo obvio. Le dice a su vendedor: *a esta
> tienda no le estás vendiendo esta categoría y deberías, porque tiendas con su
> mismo patrón de compra la venden bien*. Con el monto esperado al lado."

Abrir el drill-down de un producto y mostrar los comercios interesados con su
motivo y probabilidad.

### 4. Salud de Cartera (1,5 min) — "¿a quién estoy por perder?"

> "25 clientes en riesgo. No 103: **25**, ordenados por lo que está en juego,
> para que un vendedor los trabaje esta semana. Los que ya se fueron hace más de
> seis meses están en otra lista, porque eso es una campaña de reactivación, no
> una visita."

### 5. Rutas (1,5 min) — el cierre visual

Abrir el mapa. Es el momento más vistoso: calles reales, paradas numeradas y
coloreadas por valor del cliente.

> "Los mismos clientes del archivo, agrupados por cercanía en días de visita, y
> ordenados para recorrer menos. Cada parada dice a quién visita, cuánto compra y
> qué ofrecerle. Un 5% menos de kilómetros es combustible que no se gasta."

### 6. Cierre (30 s)

> "Todo lo que vio salió de **un solo archivo de ventas**. Sin ERP, sin
> instalación, sin proyecto de integración. El siguiente paso es que traiga un
> archivo de su negocio a una sesión de trabajo y vea sus propias oportunidades.
> ¿Cuándo le queda?"

### Si algo falla

| Falla | Cómo recuperar |
|---|---|
| El archivo no carga | Tener otra sesión con el dataset ya cargado en una pestaña aparte |
| Un análisis tarda | La afinidad es el más pesado. Hablar mientras calcula: es buen momento para explicar qué está haciendo |
| El mapa no carga | Depende de OSRM público. Pasar a Cartera y volver después; si insiste, mostrar la captura |
| Sin internet | Ir a las capturas. No improvisar con la consola |
| **"¿Y mis datos?"** | El archivo queda en el bucket S3 del cliente vía el servicio FILES. Sin terceros, sin entrenamiento cruzado, y se borra cuando termina la prueba |
| **"¿Los datos del demo son reales?"** | Decir la verdad: vienen de una operación real de consumo masivo, anonimizada; el costo y el historial extendido son simulados y **está declarado en una hoja del propio archivo**. Esa honestidad genera más confianza que fingir |
