'use strict';

/**
 * Every amount the backend sends as Money {bob, usd, usdt} is drawn here, so
 * a screen shows the three side by side and in the same way everywhere:
 * bolivianos, the official dollar and USDT. The currency selector of a page
 * only picks which of the three a chart draws.
 */
(function () {

    const CURRENCIES = [
        { key: 'bob', label: 'Bs' },
        { key: 'usd', label: 'USD' },
        { key: 'usdt', label: 'USDT' }
    ];
    // The selector speaks ISO codes; the payload, the keys above.
    const KEY_OF = { BOB: 'bob', USD: 'usd', USDT: 'usdt' };

    function format(value, decimals) {
        if (value == null || isNaN(value)) return '—';
        return Number(value).toLocaleString('es-BO', {
            minimumFractionDigits: decimals, maximumFractionDigits: decimals
        });
    }

    /** The three cells of one amount in a table row, with an optional class. */
    function cells(money, decimals = 2, extraClass = '') {
        const cls = `numeric money-cell${extraClass ? ` ${extraClass}` : ''}`;
        return CURRENCIES.map(({ key }) =>
            `<td class="${cls}">${format(money && money[key], decimals)}</td>`
        ).join('');
    }

    /** The value of a metric card: three columns, each with its currency. */
    function card(money) {
        return '<div class="money3">' + CURRENCIES.map(({ key, label }) =>
            `<span class="money3-col"><span class="money3-label">${label}</span>` +
            `<span class="money3-value">${format(money && money[key], 0)}</span></span>`
        ).join('') + '</div>';
    }

    /** One line for a hint: "Bs 1.000 · USD 84 · USDT 84". */
    function inline(money, decimals = 0) {
        return CURRENCIES.map(({ key, label }) =>
            `${label} ${format(money && money[key], decimals)}`).join(' · ');
    }

    /** The difference of two amounts, currency by currency. */
    function minus(left, right) {
        const result = {};
        CURRENCIES.forEach(({ key }) => {
            result[key] = (left && right) ? left[key] - right[key] : null;
        });
        return result;
    }

    /** What a chart draws: the amount in the currency the selector names. */
    function pick(money, currency) {
        if (money == null || typeof money !== 'object') return money;
        return money[KEY_OF[currency] || 'bob'];
    }

    /** "Dólar oficial de hoy Bs 11,85 · USDT Bs 11,90". */
    function ratesNote(rates) {
        if (!rates) return '';
        return `Dólar oficial de hoy Bs ${format(rates.usd, 2)} · ` +
            `USDT Bs ${format(rates.usdt, 2)}.`;
    }

    /**
     * A header cell marked `data-money` becomes three columns under it
     * (Bs, USD, USDT); the other cells span both header rows. Runs once per
     * table, so calling it again is harmless.
     */
    function expandHeaders(root) {
        (root || document).querySelectorAll('table').forEach((table) => {
            const row = table.querySelector('thead tr');
            if (!row || table.dataset.moneyExpanded || !row.querySelector('th[data-money]')) {
                return;
            }
            const sub = document.createElement('tr');
            sub.className = 'money-subhead';
            row.querySelectorAll('th').forEach((th) => {
                if (th.hasAttribute('data-money')) {
                    th.colSpan = CURRENCIES.length;
                    th.classList.add('money-group');
                    CURRENCIES.forEach(({ label }) => {
                        const cell = document.createElement('th');
                        cell.className = 'numeric';
                        cell.textContent = label;
                        sub.appendChild(cell);
                    });
                } else {
                    th.rowSpan = 2;
                }
            });
            row.after(sub);
            table.dataset.moneyExpanded = 'true';
        });
    }

    window.SD_MONEY = { cells, card, inline, minus, pick, ratesNote, expandHeaders };
})();
