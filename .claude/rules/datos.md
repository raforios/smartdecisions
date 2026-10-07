---
paths:
  - "services/*/schemas/*.py"
  - "services/*/models/*.py"
  - "services/*/services/*.py"
  - "services/*/routes/*.py"
---

# Datos — propiedad, normalización y canales de entrada

Se cargan solos al tocar una capa que escribe o lee datos del cliente.
Amplían `CLAUDE.md` §8 y §9; no los contradicen.

## Propiedad

Cada conjunto que entra —por archivo o por API, de ventas, cobros, stock,
visitas o rutas— queda grabado con **el usuario autenticado que lo cargó**.

- No se acepta una carga sin dueño.
- El dueño **no se deriva del contenido** del archivo.
- Ningún proceso posterior lee un dato sin volver a pasar por él.

## Normalización

Lo que describe **al cliente** —nombre, coordenadas, dirección, zona, ciudad,
canal, tipo de local, contacto— vive **una sola vez** en el maestro de
clientes. El archivo de transacciones sólo lo identifica.

1. Un cliente que no existe **se da de alta**; uno que ya existe **no se
   reescribe**: sólo se completan los campos que el maestro tenía vacíos. Una
   recarga no puede deshacer una corrección.
2. Lo que el archivo no traiga **se toma del maestro**. Cargar ventas sin
   coordenadas no puede apagar Rutas si esas coordenadas ya se conocían.
3. El maestro se alimenta desde **tres puertas**: la carga de archivo, el API y
   el terreno —un vendedor que visita una dirección nueva da de alta al cliente
   ahí mismo.
4. Sobrescribir es un acto **explícito y aparte** (`PATCH` del cliente), nunca
   el efecto secundario de volver a leer un archivo.

Coordenada exactamente 0 = sin dato, no el Golfo de Guinea.

## Canales de entrada

Todo proceso de carga expone **los dos**:

| Canal | Cómo |
|---|---|
| **API** | DTOs Pydantic con identificadores en inglés, mismo validador y mismos códigos de error que el archivo. Aceptación parcial: la fila inválida se aparta con su motivo y el resto entra. |
| **Archivo** | Sube por **FILES** a S3; el servicio lo lee por su clave. El binario no atraviesa API Gateway (límite de 10 MB), igual que en BINARIA. |

Las cabeceras del archivo van en **castellano**; los campos del API, en inglés.
El mapeador entre ambos se deriva del contrato, nunca se escribe a mano.
