/**
 * Location codes: what a rack, a pallet or a floor zone is called by where it
 * stands. `A1P3R5N2` reads warehouse 1, aisle 3, rack 5, level 2.
 *
 * Along an aisle the number is the bay where the element stands, the way
 * warehouses mark their racks: the aisle is divided into bays of a fixed
 * length counted from its start (its left end, or its top end when it runs
 * down the plan), odd numbers on one side and even on the other. Moving a
 * rack changes its own code only; the others keep theirs, so their labels
 * stay valid. Two elements cannot share a bay on the same side.
 */

/** Bay length when the aisle does not say, in metres: a standard rack. */
export const DEFAULT_BAY_M = 6;

/** How far from an aisle an element still belongs to it, in metres. */
const AISLE_REACH_M = 2.5;

/** Whether an aisle runs across the plan (true) or down it (false). */
export function runsAcross(aisle) {
    return aisle.width_m >= aisle.length_m;
}

/** The empty gap between two rectangles, 0 when they touch or overlap. */
function gap(one, other) {
    const dx = Math.max(other.pos_x_m - (one.pos_x_m + one.width_m),
                        one.pos_x_m - (other.pos_x_m + other.width_m), 0);
    const dy = Math.max(other.pos_y_m - (one.pos_y_m + one.length_m),
                        one.pos_y_m - (other.pos_y_m + other.length_m), 0);
    return Math.hypot(dx, dy);
}

/** The aisle an element sits beside, or null when it is away from all of them. */
export function nearestAisle(element, aisles) {
    let best = null;
    let bestGap = AISLE_REACH_M;
    aisles.forEach((aisle) => {
        const distance = gap(element, aisle);
        if (distance <= bestGap) {
            best = aisle;
            bestGap = distance;
        }
    });
    return best;
}

/** The bay and side of an element along its aisle: its number there. */
function bayNumber(element, aisle) {
    const across = runsAcross(aisle);
    const centre = across ? element.pos_x_m + element.width_m / 2 : element.pos_y_m + element.length_m / 2;
    const start = across ? aisle.pos_x_m : aisle.pos_y_m;
    const bay = Math.max(0, Math.floor((centre - start) / (aisle.bay_m || DEFAULT_BAY_M)));
    const middle = across ? aisle.pos_y_m + aisle.length_m / 2 : aisle.pos_x_m + aisle.width_m / 2;
    const side = (across ? element.pos_y_m + element.length_m / 2 : element.pos_x_m + element.width_m / 2) < middle ? 0 : 1;
    return bay * 2 + 1 + side;
}

/**
 * Every element with the aisle it sits beside and its number there.
 * Elements away from every aisle are numbered among themselves, by position.
 */
export function assignAisles(elements, aisles) {
    const loose = [];
    const placed = elements.map((element) => {
        const aisle = nearestAisle(element, aisles);
        const next = { ...element, aisle_id: aisle ? aisle.id : null };
        if (aisle) next.number = bayNumber(next, aisle);
        else loose.push(next);
        return next;
    });
    loose.sort((one, other) => one.pos_y_m - other.pos_y_m || one.pos_x_m - other.pos_x_m)
        .forEach((item, index) => { item.number = index + 1; });
    return placed;
}

/** Elements that ended up with the same aisle and number: a bay taken twice. */
export function sharedBays(elements) {
    const seen = new Map();
    return elements.filter((element) => {
        if (!element.aisle_id) return false;
        const key = `${element.aisle_id}:${element.number}`;
        if (seen.has(key)) return true;
        seen.set(key, element.id);
        return false;
    });
}

/** `A1P3R5`: the element's own code, without its level. */
export function elementCode(warehouse, aisles, types, element) {
    const aisle = aisles.find((one) => one.id === element.aisle_id);
    const type = types.find((one) => one.code === element.type);
    return `A${warehouse.number}${aisle ? `P${aisle.number}` : ''}${type ? type.code_letter : '?'}${element.number}`;
}

/** Every location of an element: one per level, or the element itself. */
export function locationCodes(warehouse, aisles, types, element) {
    const code = elementCode(warehouse, aisles, types, element);
    const type = types.find((one) => one.code === element.type);
    if (!type || !type.has_levels) return [code];
    return Array.from({ length: element.levels }, (_, index) => `${code}N${index + 1}`);
}
