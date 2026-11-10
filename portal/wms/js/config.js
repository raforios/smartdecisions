/**
 * WMS — service endpoints and storage keys.
 *
 * Same convention as SmartBilling's `js/config.js`: plain constants, read by
 * the shared session modules (`common/js/session/`) through `/js/config.js`.
 */
export const AUTH_URL = 'https://api.bearsoft.com.bo';
// There is no local AUTH: a page served from localhost signs in through the
// same gateway.
export const AUTH_URL_LOCAL = 'https://api.bearsoft.com.bo';

/** Where an unauthenticated visitor is sent. */
export const LOGIN_PATH = 'login.html';

/** Key the JWT is kept under. Its own key: the WMS is sold on its own. */
export const STORAGE_TOKEN_KEY = 'wms_jwt';

/** "Recordar mi correo" keeps the e-mail only, under its own key. */
export const REMEMBER_EMAIL_KEY = 'wms_login_email';
