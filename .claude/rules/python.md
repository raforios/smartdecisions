---
paths:
  - "services/**/*.py"
  - "tools/**/*.py"
---

# Estándares de código Python

Se cargan solos al tocar cualquier `.py` del proyecto.

## Convenciones

- **Idioma:** inglés en variables, funciones, clases, comentarios y docstrings.
- **Type hints obligatorios** en argumentos, retornos y atributos, con sintaxis
  moderna: `list[str]`, `dict[str, Any]`, `str | None`. Nunca `List`, `Dict`,
  `Optional` ni `Union` de `typing` (decisión de Rafael, 07-oct-2026); de
  `typing` sólo se importa lo que no tiene forma nativa, como `Any`.
- **Los comentarios explican el porqué** —la intención, la regla de negocio, la
  trampa que se evitó— nunca el cómo.

## Formato

- Espacios alrededor de `=` en argumentos con nombre: `a = 1`, nunca `a=1`.
- Comilla simple `'` para strings; `'''` o `"""` sólo en docstrings.
- Línea máxima: **100 caracteres**.
- Máximo **5** argumentos por función. Si hacen falta más, se agrupan en un
  modelo Pydantic o una dataclass.
- **Firma con más de un parámetro: un parámetro por línea**, sin importar el
  largo, con sangría de cuatro espacios, y el paréntesis de cierre con la
  anotación de retorno en su propia línea. Nunca sangría colgante ni varios
  parámetros en una línea.

  ```python
  async def store_companion(
      dynamodb_resource: ServiceResource,
      dataset: dict[str, Any],
      result: Any
  ) -> BaseModel:
  ```

  Se comprueba y se corrige con `python tools/check_signatures.py <servicio> [--fix]`.
- Sin nombres de un solo carácter, salvo `i`, `j` en iteradores simples.
- **Pylint 10.00** antes de dar algo por terminado. Un `disable` sólo con un
  comentario que diga por qué la regla no aplica ahí.

## Docstrings

```python
def calculate_metrics(
    interactions: InteractionsSchema,
    strict: bool
) -> MetricsSchema:
    '''
        Calculates performance metrics from the user interactions.

        Args:
            interactions (InteractionsSchema): Raw interactions to score.
            strict (bool): If True, applies rigorous filtering.

        Returns:
            MetricsSchema: The calculated score and accuracy.

        Raises:
            ValueError: If there are no interactions.
    '''
```

## Errores y logging

- **Nunca `try-except: pass`.** Se capturan excepciones específicas.
- En FastAPI, `HTTPException` con el código adecuado.
- Siempre un `logger` configurado.
- **Variables reservadas:** `message` para INFO; `error_msg` para WARNING y ERROR.

## Seguridad

- **SQL:** métodos del ORM o parámetros bind. Prohibido f-strings en queries.
- **Asincronismo:** I/O bound con `async def` + `await`; CPU bound intensivo en
  `def` síncrono, para no bloquear el event loop.

## Estructuras de datos

DTOs Pydantic o dataclasses, **no diccionarios sueltos**. `rows: list[dict[str,
Any]]` como contrato entre capas es una corrección ya hecha una vez.

## Tests

- Un test por función nueva en `services/`.
- **`tests/test_controllers.py` obligatorio**: cada endpoint debe devolver su
  modelo armado. Los servicios pasaron a devolver DTOs mientras los controllers
  seguían expandiéndolos con `**`, y eso revienta sólo al correr el endpoint: la
  suite quedaba verde y la API devolvía 500.
- **Verifica que un test nuevo falla contra el código roto** antes de darlo por
  bueno. Un test que pasa en ambos casos no prueba nada.
