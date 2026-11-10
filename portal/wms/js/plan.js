/**
 * The plan: an SVG drawn in metres, with rectangles that are dragged into
 * place. The same drawing serves the facility (its warehouses) and each
 * warehouse (its aisles and elements), and, read-only, a version from the
 * history.
 *
 * Rules the plan keeps while dragging: a rectangle snaps to half a metre,
 * stays inside the plan, and never lands on another one — while it overlaps
 * it turns red, and if it is dropped there it goes back to where it was.
 */

const SVG_NS = 'http://www.w3.org/2000/svg';
const SNAP_M = 0.5;

/** Whether two rectangles share any area (touching edges do not). */
export function overlaps(one, other) {
    return one.pos_x_m < other.pos_x_m + other.width_m && other.pos_x_m < one.pos_x_m + one.width_m &&
        one.pos_y_m < other.pos_y_m + other.length_m && other.pos_y_m < one.pos_y_m + one.length_m;
}

/** The first free spot for a new rectangle, scanning from the plan's top-left corner. */
export function freeSpot(item, others, width, length) {
    for (let y = 1; y + item.length_m <= length; y += 1) {
        for (let x = 1; x + item.width_m <= width; x += 1) {
            const probe = { ...item, pos_x_m: x, pos_y_m: y };
            if (!others.some((other) => overlaps(probe, other))) return { x, y };
        }
    }
    return null;
}

const snap = (value) => Math.round(value / SNAP_M) * SNAP_M;
const node = (name, attributes = {}) => {
    const element = document.createElementNS(SVG_NS, name);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
};

export class PlanEditor {
    /**
     * @param {object} options
     * @param {HTMLElement} options.host - Where the SVG goes.
     * @param {number} options.width - The plan's width, in metres.
     * @param {number} options.length - The plan's length, in metres.
     * @param {Function} options.look - item → {fill, stroke, label, sub, kind}.
     * @param {boolean} [options.readOnly]
     * @param {Function} [options.onSelect] - item | null.
     * @param {Function} [options.onDrop] - (item, x, y) after a valid drop.
     * @param {Function} [options.onOpen] - item, on double click.
     * @param {Function} [options.onBlocked] - item, when a drop lands on another one.
     * @param {string} [options.defs] - SVG patterns the looks may name as fills.
     */
    constructor(options) {
        Object.assign(this, { items: [], selectedId: null, drag: null }, options);
        this.svg = node('svg', { class: 'plan-svg', viewBox: `0 0 ${this.width} ${this.length}`,
                                 role: 'img', 'aria-label': 'Plano' });
        this.host.replaceChildren(this.svg);
        if (!this.readOnly) {
            this.svg.addEventListener('pointermove', (event) => this.move(event));
            this.svg.addEventListener('pointerup', (event) => this.release(event));
            this.svg.addEventListener('pointerdown', (event) => {
                if (event.target === this.svg || event.target.classList.contains('plan-floor')) this.select(null);
            });
        }
    }

    setItems(items) {
        this.items = items;
        this.render();
    }

    select(id) {
        this.selectedId = id;
        this.render();
        if (this.onSelect) this.onSelect(this.items.find((item) => item.id === id) || null);
    }

    /** Pointer position in plan metres. */
    point(event) {
        const at = this.svg.createSVGPoint();
        at.x = event.clientX;
        at.y = event.clientY;
        return at.matrixTransform(this.svg.getScreenCTM().inverse());
    }

    grab(event, item) {
        if (this.readOnly) return;
        event.stopPropagation();
        const at = this.point(event);
        this.drag = { id: item.id, dx: at.x - item.pos_x_m, dy: at.y - item.pos_y_m,
                      from: { x: item.pos_x_m, y: item.pos_y_m }, moved: false };
        this.svg.setPointerCapture(event.pointerId);
        if (this.selectedId !== item.id) this.select(item.id);
    }

    move(event) {
        if (!this.drag) return;
        const item = this.items.find((one) => one.id === this.drag.id);
        const at = this.point(event);
        const x = Math.min(Math.max(snap(at.x - this.drag.dx), 0), this.width - item.width_m);
        const y = Math.min(Math.max(snap(at.y - this.drag.dy), 0), this.length - item.length_m);
        if (x === item.pos_x_m && y === item.pos_y_m) return;
        item.pos_x_m = x;
        item.pos_y_m = y;
        this.drag.moved = true;
        this.drag.blocked = this.items.some((other) => other.id !== item.id && overlaps(item, other));
        this.render();
    }

    release(event) {
        if (!this.drag) return;
        const { id, from, moved, blocked } = this.drag;
        this.drag = null;
        if (this.svg.hasPointerCapture(event.pointerId)) this.svg.releasePointerCapture(event.pointerId);
        const item = this.items.find((one) => one.id === id);
        if (!moved) return;
        const { pos_x_m: x, pos_y_m: y } = item;
        // The drop is offered to the page from where it started: the page
        // decides (and may ask the user) before anything changes.
        item.pos_x_m = from.x;
        item.pos_y_m = from.y;
        this.render();
        if (blocked) {
            if (this.onBlocked) this.onBlocked(item);
            return;
        }
        if (this.onDrop) this.onDrop(item, x, y);
    }

    render() {
        const { width, length } = this;
        // Redrawing replaces the shapes: keyboard focus goes back to the selected one.
        const hadFocus = this.svg.contains(document.activeElement);
        const minor = width > 80 ? 5 : 1;
        this.svg.replaceChildren(node('rect', { class: 'plan-floor', x: 0, y: 0, width, height: length }));
        if (this.defs) {
            const defs = node('defs');
            defs.innerHTML = this.defs;
            this.svg.prepend(defs);
        }
        const grid = node('g', { class: 'plan-grid' });
        for (let x = minor; x < width; x += minor) {
            grid.append(node('line', { x1: x, y1: 0, x2: x, y2: length, class: x % (minor * 5) ? '' : 'is-major' }));
        }
        for (let y = minor; y < length; y += minor) {
            grid.append(node('line', { x1: 0, y1: y, x2: width, y2: y, class: y % (minor * 5) ? '' : 'is-major' }));
        }
        this.svg.append(grid, this.ruler());
        // Aisles under everything else, so a rack beside one is never hidden.
        const ordered = [...this.items].sort((one, other) =>
            (this.look(one).kind === 'aisle' ? 0 : 1) - (this.look(other).kind === 'aisle' ? 0 : 1));
        ordered.forEach((item) => this.svg.append(this.shape(item)));
        if (hadFocus && this.selectedId) {
            const selected = this.svg.querySelector(`[data-id="${this.selectedId}"]`);
            if (selected) selected.focus();
        }
    }

    /** A scale bar in the corner: what ten metres look like on this plan. */
    ruler() {
        const step = this.width > 80 ? 10 : 5;
        const y = this.length - 1.2;
        const group = node('g', { class: 'plan-ruler' });
        group.append(node('line', { x1: 1, y1: y, x2: 1 + step, y2: y }));
        const label = node('text', { x: 1 + step / 2, y: y - 0.5 });
        label.textContent = `${step} m`;
        group.append(label);
        return group;
    }

    shape(item) {
        const look = this.look(item);
        const blocked = this.drag && this.drag.id === item.id && this.drag.blocked;
        const classes = ['plan-item', `is-${look.kind}`];
        if (item.id === this.selectedId) classes.push('is-selected');
        if (blocked) classes.push('is-blocked');
        const group = node('g', { class: classes.join(' '), tabindex: this.readOnly ? -1 : 0,
                                  'data-id': item.id });
        group.append(node('rect', { x: item.pos_x_m, y: item.pos_y_m, width: item.width_m, height: item.length_m,
                                    rx: look.kind === 'warehouse' ? 0.6 : 0.15, fill: look.fill, stroke: look.stroke }));
        const size = Math.max(0.5, Math.min(item.width_m, item.length_m) * (look.kind === 'warehouse' ? 0.12 : 0.55));
        const text = node('text', { x: item.pos_x_m + item.width_m / 2, y: item.pos_y_m + item.length_m / 2,
                                    'font-size': Math.min(size, look.kind === 'warehouse' ? 3.2 : 1.1) });
        text.textContent = look.label;
        group.append(text);
        if (look.sub) {
            const sub = node('text', { class: 'plan-sub', x: item.pos_x_m + item.width_m / 2,
                                       y: item.pos_y_m + item.length_m / 2 + size * 1.1,
                                       'font-size': Math.min(size * 0.6, 1.8) });
            sub.textContent = look.sub;
            group.append(sub);
        }
        const title = node('title');
        title.textContent = look.title || look.label;
        group.append(title);
        if (!this.readOnly) {
            group.addEventListener('pointerdown', (event) => this.grab(event, item));
            group.addEventListener('dblclick', () => this.onOpen && this.onOpen(item));
            group.addEventListener('keydown', (event) => this.nudge(event, item));
        }
        return group;
    }

    /** Arrow keys move the selected rectangle half a metre: dragging without a mouse. */
    nudge(event, item) {
        const steps = { ArrowLeft: [-SNAP_M, 0], ArrowRight: [SNAP_M, 0], ArrowUp: [0, -SNAP_M], ArrowDown: [0, SNAP_M] };
        if (event.key === 'Enter' && this.onOpen) {
            this.onOpen(item);
            return;
        }
        if (!steps[event.key]) return;
        event.preventDefault();
        const [dx, dy] = steps[event.key];
        const x = Math.min(Math.max(item.pos_x_m + dx, 0), this.width - item.width_m);
        const y = Math.min(Math.max(item.pos_y_m + dy, 0), this.length - item.length_m);
        const probe = { ...item, pos_x_m: x, pos_y_m: y };
        if (this.items.some((other) => other.id !== item.id && overlaps(probe, other))) {
            if (this.onBlocked) this.onBlocked(item);
            return;
        }
        if (this.onDrop) this.onDrop(item, x, y);
    }
}
