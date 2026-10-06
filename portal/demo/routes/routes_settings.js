'use strict';

/**
 * Rutas — "Configuración": the company's optional base point. Routes start and
 * end where the seller is unless a plan asks for this point.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.isAuthenticated()) return;
    const { qs, toast, setButtonBusy } = window.SD_UI;
    const T = window.SD_TRACK;

    const fields = () => ({
        name: qs('#baseName').value.trim(),
        latitude: qs('#baseLat').value === '' ? null : Number(qs('#baseLat').value),
        longitude: qs('#baseLon').value === '' ? null : Number(qs('#baseLon').value)
    });

    async function load() {
        try {
            const current = await T.settings.get();
            const base = current.base_point;
            qs('#baseName').value = base ? base.name : '';
            qs('#baseLat').value = base ? base.latitude : '';
            qs('#baseLon').value = base ? base.longitude : '';
            T.note(qs('#baseNote'), base ? '' : 'Sin punto de partida: las rutas son abiertas.');
        } catch (error) {
            T.note(qs('#baseNote'), T.errorText(error, 'No se pudo leer la configuración.'), 'error');
        }
    }

    async function save(basePoint) {
        const done = setButtonBusy(qs('#baseSave'), 'Guardando…');
        try {
            await T.settings.save({ base_point: basePoint });
            toast(basePoint ? 'Punto de partida guardado.' : 'Punto de partida quitado.', 'success');
            await load();
        } catch (error) {
            T.note(qs('#baseNote'), T.errorText(error, 'No se pudo guardar.'), 'error');
        } finally {
            done();
        }
    }

    qs('#baseHere').addEventListener('click', () => {
        if (!navigator.geolocation) {
            T.note(qs('#baseNote'), 'Este navegador no da la ubicación.', 'error');
            return;
        }
        navigator.geolocation.getCurrentPosition((position) => {
            qs('#baseLat').value = position.coords.latitude.toFixed(6);
            qs('#baseLon').value = position.coords.longitude.toFixed(6);
        }, () => T.note(qs('#baseNote'), 'No se pudo obtener la ubicación.', 'error'));
    });

    qs('#baseSave').addEventListener('click', () => {
        const base = fields();
        if (!base.name || base.latitude === null || base.longitude === null) {
            T.note(qs('#baseNote'), 'Completa nombre, latitud y longitud.', 'error');
            return;
        }
        save(base);
    });
    qs('#baseClear').addEventListener('click', () => save(null));

    T.onShow('settings', load);
});
