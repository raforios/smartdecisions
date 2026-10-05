# Instrucciones de revisión

Las lee `/code-review` (y cualquier agente revisor) antes de reportar. Las
reglas de fondo están en `CLAUDE.md` y `.claude/rules/`; aquí sólo se dice
qué buscar, qué es grave y qué no se reporta.

## Pasadas

- **Bugs:** errores de lógica, casos borde rotos, regresiones silenciosas.
- **Propiedad de los datos:** el dueño es parte de la consulta, no un filtro
  posterior; un recurso ajeno responde igual que uno inexistente (§8).
- **Contrato con el cliente:** el backend devuelve datos y códigos en `Enum`,
  nunca texto de UI (§6).
- **Configuración:** decisiones de negocio en el `.env`, variables requeridas,
  sin `os.getenv` suelto ni valores por defecto inventados (§5).
- **Servicios base:** `Depends` de `security.py` en cada endpoint,
  `@handle_service_errors` en todo controlador y `@audit_event` en los que
  cambian algo (§7).
- **Especificación:** si el cambio tiene `docs/cambios/<cambio>/`, el código
  cumple `spec.md` y respeta las restricciones de `intent.md`.

## Qué es grave

Se marca **Grave** sólo lo que:

- expone datos de otro dueño o permite operar sobre ellos;
- pierde o corrompe datos en silencio (stock, montos, facturas);
- rompe una restricción de `intent.md`;
- modifica el boilerplate o crea carpetas dentro de un microservicio (§3).

El estilo y los nombres son detalles menores.

## Límite de detalles menores

Como máximo cinco por revisión; el resto se resume como un número.

## No reportar

- Los `deploy.config`: son de despliegue, no código.
- Lo que ya caza `tools/verify_service.py` (Pylint, firmas, type hints,
  tamaño, `except` mudo, comas en el `.env`).
