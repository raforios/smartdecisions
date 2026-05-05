/**
 * Sidebar navigation. Renders config.menu and exposes a setActive() helper
 * for the hash-based router driving the dashboard.
 */
export class Sidebar {
    static render(config) {
        const items = config.menu.map(item => `
            <div class="nav-item" data-module="${item.module}" data-id="${item.id}">
                <i class="${item.icon}"></i>
                <span>${item.label}</span>
            </div>
        `).join('');

        return `
            <h4>Operación</h4>
            ${items}
        `;
    }

    static initInteractions({ onSelect }) {
        document.querySelectorAll('.nav-item').forEach(el => {
            el.addEventListener('click', () => {
                const module = el.dataset.module;
                const id = el.dataset.id;
                if (onSelect) onSelect({ id, module });
            });
        });
    }

    static setActive(moduleId) {
        document.querySelectorAll('.nav-item').forEach(el => {
            el.classList.toggle('active', el.dataset.module === moduleId);
        });
    }
}
