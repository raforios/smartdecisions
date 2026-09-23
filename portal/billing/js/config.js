/**
 * BILLING — service endpoints.
 *
 * Same convention as `portal/demo/js/config.js`: plain constants, no fetch of
 * a JSON at boot. The app is served statically, so a missing config file was
 * one more thing that could break a till at opening time.
 *
 * The local URLs only take effect when the page itself is served from
 * localhost, which is what `resolveBases` decides.
 */
export const AUTH_URL = 'https://32652ile50.execute-api.us-east-1.amazonaws.com';
export const AUTH_URL_LOCAL = 'https://32652ile50.execute-api.us-east-1.amazonaws.com';

// Filled in with the API Gateway URL once BILLING is deployed. Until then the
// local service answers on 3004.
export const BILLING_URL = 'http://localhost:3004/billing';
export const BILLING_URL_LOCAL = 'http://localhost:3004/billing';

/** Where an unauthenticated visitor is sent. */
export const LOGIN_PATH = 'login.html';

/** Key the JWT is kept under. Its own key: BILLING is sold on its own. */
export const STORAGE_TOKEN_KEY = 'billing_jwt';
