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
export const AUTH_URL = 'https://api.bearsoft.com.bo';
export const AUTH_URL_LOCAL = 'https://32652ile50.execute-api.us-east-1.amazonaws.com';

// Production, verified against the deployed API Gateway: the service answers
// under /v1/billing. The local one stays on 3004 and only takes effect when the
// page itself is served from localhost.
export const BILLING_URL = 'https://api.bearsoft.com.bo';
export const BILLING_URL_LOCAL = 'http://localhost:3004';

/** Where an unauthenticated visitor is sent. */
export const LOGIN_PATH = 'login.html';

/** Key the JWT is kept under. Its own key: BILLING is sold on its own. */
export const STORAGE_TOKEN_KEY = 'billing_jwt';
