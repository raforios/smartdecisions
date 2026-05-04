# 🏛️ MMM Bolivia — Arquitectura CMS

Sistema de componentes web para el sitio del Ministerio de Minería y Metalurgia.

---

## 📐 Arquitectura General

```
demo/
├── config/                    ← Datos dinámicos (JSON)
│   ├── app.config.json        ← Configuración global (API, features, etc.)
│   ├── navigation.json        ← Menú de navegación
│   ├── minerals.json          ← Cotizaciones de fallback
│   ├── home-content.json      ← Contenido de la página principal
│   ├── documents.json         ← Documentos y normativas
│   └── social.json            ← Redes sociales y footer
├── css/
│   ├── styles.css             ← Estilos globales (existente)
│   └── components.css         ← Estilos del sistema de componentes (nuevo)
├── js/
│   ├── app.js                 ← Bootstrap principal (punto de entrada)
│   ├── core/
│   │   └── EventBus.js        ← Sistema pub/sub entre componentes
│   ├── services/
│   │   └── DataService.js     ← Servicio único de datos (JSON + API)
│   ├── components/
│   │   ├── BaseComponent.js   ← Clase base abstracta (ciclo de vida)
│   │   ├── HeaderComponent.js ← Navbar dinámico
│   │   ├── FooterComponent.js ← Pie de página dinámico
│   │   ├── PriceTickerComponent.js ← Ticker de cotizaciones
│   │   ├── HeroComponent.js   ← Hero con animación canvas
│   │   ├── SliderComponent.js ← Carrusel de imágenes
│   │   ├── DocumentsComponent.js ← Grid de documentos con filtros
│   │   └── ContentSectionComponent.js ← Secciones genéricas
│   └── utils/
│       └── ThemeManager.js    ← Gestión de tema claro/oscuro
├── index.html
├── institucional.html
├── documentacion.html
└── mercados.html
```

---

## 🔌 Cómo usar los componentes en HTML

Los componentes se declaran en el HTML mediante atributos `data-component`:

```html
<!-- Navbar -->
<div data-component="header" data-config="config/navigation.json"></div>

<!-- Ticker de precios (JSON local) -->
<div data-component="price-ticker" data-source="json" data-json-fallback="config/minerals.json"></div>

<!-- Ticker de precios (API con fallback) -->
<div data-component="price-ticker" data-source="api" data-endpoint="/prices" data-json-fallback="config/minerals.json"></div>

<!-- Hero con canvas -->
<header data-component="hero" data-config="config/home-content.json" data-height="75vh"></header>

<!-- Carrusel -->
<div data-component="slider" data-config="config/home-content.json" data-interval="5000"></div>

<!-- Documentos (JSON) -->
<div data-component="documents" data-source="json" data-json="config/documents.json"></div>

<!-- Documentos (API con fallback) -->
<div data-component="documents" data-source="api" data-endpoint="/docs" data-json="config/documents.json"></div>

<!-- Sección de contenido genérica -->
<div data-component="content-section" data-section="entidades" data-config="config/home-content.json"></div>

<!-- Footer -->
<div data-component="footer" data-config="config/social.json"></div>
```

---

## ➕ Agregar un nuevo componente

1. Crear `js/components/MiComponente.js` extendiendo `BaseComponent`:

```js
import { BaseComponent } from './BaseComponent.js';

export class MiComponente extends BaseComponent {
  #data = null;

  async _loadData() {
    this.#data = await this._dataService.loadJson(this._attr('config', 'config/mi-data.json'));
  }

  _render() {
    this._el.innerHTML = `<div>${this.#data.titulo}</div>`;
  }

  _bindEvents() {
    // eventos con cleanup automático usando this._listen()
  }
}
```

2. Registrarlo en `js/app.js`:

```js
import { MiComponente } from './components/MiComponente.js';

const COMPONENT_REGISTRY = new Map([
  // ... existentes
  ['mi-componente', MiComponente],   // ← agregar aquí
]);
```

3. Usarlo en HTML:

```html
<div data-component="mi-componente" data-config="config/mi-data.json"></div>
```

---

## 🔄 Comunicación entre componentes (EventBus)

```js
import { eventBus } from './js/core/EventBus.js';

// Emitir un evento
eventBus.emit('datos:actualizados', { items: [...] });

// Escuchar un evento
const unsub = eventBus.on('datos:actualizados', ({ items }) => {
  console.log(items);
});

// Cancelar suscripción
unsub();
```

Eventos globales predefinidos:

| Evento            | Cuándo se emite                  | Payload            |
|-------------------|----------------------------------|--------------------|
| `app:ready`       | Bootstrap completado             | `{ config }`       |
| `theme:toggle`    | Usuario hace clic en tema        | —                  |
| `theme:changed`   | Tema aplicado                    | `{ isDark, theme }`|

---

## 🗃️ DataService — Estrategias de datos

| Método                            | Descripción                                      |
|-----------------------------------|--------------------------------------------------|
| `loadJson(path)`                  | Lee un JSON local con caché de 1 minuto          |
| `fetchApi(endpoint, options?)`    | Llama al API con reintentos y timeout            |
| `fetchWithFallback(ep, jsonPath)` | Intenta API → si falla, usa JSON local           |
| `clearCache()`                    | Limpia la caché completa                         |

---

## 🔧 Cambiar la URL del API

Editar `config/app.config.json`:

```json
{
  "api": {
    "baseUrl": "https://mi-api.com/v1/mining-analysis",
    "timeout": 8000,
    "retries": 2,
    "fallbackToJson": true
  }
}
```

---

## 👤 Creado por

**Rafael Ríos Bascón** — [raforios@gmail.com](mailto:raforios@gmail.com)
