/**
 * Footer for the operator dashboard. Minimal — branding lives in the topbar.
 */
export class Footer {
    static render(config) {
        const year = config.event.year || new Date().getFullYear();
        return `
            <footer class="event-footer">
                © ${year} <strong>${config.event.fullName}</strong> — ${config.event.organizer}
            </footer>
        `;
    }
}
