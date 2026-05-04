/**
 * app.js — Bootstrap del sistema CMS.
 *
 * Principio: Composition Root — único lugar donde se crean las dependencias.
 * Patrón: Component Registry — auto-monta componentes desde atributos data-component.
 *
 * Uso en HTML:
 *   <div data-component="header" data-config="config/navigation.json"></div>
 *   <div data-component="price-ticker" data-source="json"></div>
 *   <div data-component="hero" data-config="config/home-content.json"></div>
 *   <div data-component="slider" data-interval="5000"></div>
 *   <div data-component="documents" data-source="json"></div>
 *   <div data-component="content-section" data-section="entidades"></div>
 *   <div data-component="footer" data-config="config/social.json"></div>
 */

import { eventBus }                   from './core/EventBus.js';
import { DataService }                 from './services/DataService.js';
import { HeaderComponent }             from './components/HeaderComponent.js';
import { FooterComponent }             from './components/FooterComponent.js';
import { PriceTickerComponent }        from './components/PriceTickerComponent.js';
import { HeroComponent }               from './components/HeroComponent.js';
import { SliderComponent }             from './components/SliderComponent.js';
import { DocumentsComponent }          from './components/DocumentsComponent.js';
import { ContentSectionComponent }     from './components/ContentSectionComponent.js';
import { ThemeManager }                from './utils/ThemeManager.js';

// ─── Registro de componentes ─────────────────────────────────────────────────
// Clave: valor del atributo data-component  →  Clase del componente
const COMPONENT_REGISTRY = new Map([
  ['header',          HeaderComponent],
  ['footer',          FooterComponent],
  ['price-ticker',    PriceTickerComponent],
  ['hero',            HeroComponent],
  ['slider',          SliderComponent],
  ['documents',       DocumentsComponent],
  ['content-section', ContentSectionComponent],
]);

// ─── Bootstrap ───────────────────────────────────────────────────────────────

async function bootstrap() {
  // 1. Cargar configuración global
  let appConfig;
  try {
    const res = await fetch('config/app.config.json');
    appConfig = await res.json();
  } catch {
    console.warn('[App] No se pudo cargar app.config.json, usando defaults.');
    appConfig = { api: {}, features: {} };
  }

  // 2. Instanciar servicios compartidos
  const dataService = new DataService({
    apiBaseUrl:     appConfig.api?.baseUrl ?? '',
    timeout:        appConfig.api?.timeout ?? 8000,
    retries:        appConfig.api?.retries ?? 2,
    fallbackToJson: appConfig.api?.fallbackToJson ?? true,
  });

  // 3. Inicializar el gestor de temas
  const themeManager = new ThemeManager(eventBus);
  themeManager.init();

  // 4. Montar todos los componentes declarados en el HTML
  const mountPoints = document.querySelectorAll('[data-component]');

  const mountPromises = Array.from(mountPoints).map(async (el) => {
    const componentName = el.dataset.component;
    const ComponentClass = COMPONENT_REGISTRY.get(componentName);

    if (!ComponentClass) {
      console.warn(`[App] Componente desconocido: '${componentName}'`);
      return;
    }

    try {
      const instance = new ComponentClass(el, dataService, eventBus);
      await instance.init();

      // Guardar referencia para posible destroy() posterior
      el._componentInstance = instance;
    } catch (error) {
      console.error(`[App] Error montando '${componentName}':`, error);
    }
  });

  await Promise.allSettled(mountPromises);

  // 5. Emitir evento de app lista (otros scripts pueden escuchar)
  eventBus.emit('app:ready', { config: appConfig });

  console.info('[App] ✅ CMS iniciado correctamente.');
}

// ─── Iniciar cuando el DOM esté listo ────────────────────────────────────────
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', bootstrap);
} else {
  bootstrap();
}

// ─── API pública para scripts externos ───────────────────────────────────────
export { eventBus, COMPONENT_REGISTRY };
