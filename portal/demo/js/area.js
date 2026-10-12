'use strict';

/**
 * The frame of an area page that runs no analysis (Clientes, Parámetros):
 * the session, the user chip and the exit. The analysis pages get the same
 * from `analyses/core.js`.
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!window.SD_AUTH.requireAuth()) return;
    const { qs } = window.SD_UI;
    qs('#userChip').textContent = window.SD_AUTH.getEmail() || 'usuario';
    qs('#logoutButton').addEventListener('click', () => window.SD_AUTH.logout());
    window.SD_SESSION.mountChip('sessionChip', '');
});
