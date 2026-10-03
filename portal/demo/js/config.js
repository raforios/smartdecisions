'use strict';

/**
 * SmartDecisions demo — service endpoint configuration.
 *
 * Hosted statically (S3 + CloudFront) per environment by simply replacing
 * the URLs below. No build step required.
 *
 * Every microservice is published under one domain, api.bearsoft.com.bo:
 * the gateway routes /v1/<service>/... to that service's Lambda, so the base
 * is the same for all of them. They stay separate keys so one service can be
 * pointed at localhost while developing it.
 */
window.SD_CONFIG = {
    // --- Base services (shared by every BearSoft product) ---
    AUTH_URL:          'https://api.bearsoft.com.bo',
    EVENTS_URL:        'https://api.bearsoft.com.bo',
    FILES_URL:         'https://api.bearsoft.com.bo',
    ML_FUNCTIONS_URL:  'https://api.bearsoft.com.bo',

    // --- SmartDecisions services ---
    INGEST_URL:        'https://api.bearsoft.com.bo',
    OPTIMIZATION_URL:  'https://api.bearsoft.com.bo',
    ANALYTICS_URL:     'https://api.bearsoft.com.bo',
    MINING_URL:        'https://api.bearsoft.com.bo',
    QUOTES_URL:        'https://api.bearsoft.com.bo',

    // Capa de interpretación. Definirla es lo que hace aparecer el botón
    // "¿Qué significa esto?" en cada vista: sin ella el portal funciona igual,
    // sólo que sin explicaciones.
    AI_URL:            'https://api.bearsoft.com.bo',

    // S3 bucket where large sales files are staged (direct-to-S3 upload via
    // pre-signed URL, bypassing the ~10 MB API Gateway limit).
    INGEST_BUCKET:     'ml-data-file-handler',

    // Storage keys used by sessionStorage (kept here so module pages
    // don't reinvent constants).
    STORAGE_TOKEN_KEY:  'sd_token',
    STORAGE_EMAIL_KEY:  'sd_user_email',

    // Absolute path to the login page, used by auth/api helpers when they
    // need to bounce the user back. Adjust if the demo is mounted under
    // a different prefix (e.g. '/portal/demo/index.html').
    LOGIN_PATH:         '/index.html',

    // Where a SELLER lands: the phone screen of Rutas, not the module menu.
    SELLER_HOME:        '/routes/vendedor.html',
    // How far (metres) the phone may be from the plan's first/last stop to
    // open or close a route. Sent with each request; the service enforces it.
    GEOFENCE_METERS:    150,
    // A reading worse than this (metres of accuracy reported by the device) is
    // refused: a laptop located by Wi-Fi or IP can be kilometres off, and a
    // visit registered there is worse than none.
    GPS_MAX_ACCURACY_METERS: 100
};
