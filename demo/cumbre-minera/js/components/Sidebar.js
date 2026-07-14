/**
 * Sidebar navigation. Renders config.menu and exposes a setActive() helper
 * for the hash-based router driving the dashboard.
 */
export class Sidebar {
    /**
     * Returns the menu items the given role is allowed to see. An item without a
     * 'roles' list is visible to everyone; a null role sees only such items.
     */
    static allowedItems(config, role) {
        return config.menu.filter(
            item => !item.roles || (role && item.roles.includes(role))
        );
    }

    static render(config, role) {
        const items = Sidebar.allowedItems(config, role).map(item => `
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
