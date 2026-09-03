'use strict';

/**
 * SmartDecisions demo — service endpoint configuration.
 *
 * Hosted statically (S3 + CloudFront) per environment by simply replacing
 * the URLs below. No build step required.
 *
 * Each microservice lives behind its own API Gateway. All of them are
 * deployed and productive; point a URL at localhost only while developing
 * that particular service.
 */
window.SD_CONFIG = {
    // --- Base services (shared by every BearSoft product) ---
    AUTH_URL:          'https://32652ile50.execute-api.us-east-1.amazonaws.com',
    EVENTS_URL:        'https://uyrs6ucto3.execute-api.us-east-1.amazonaws.com',
    FILES_URL:         'https://ek2xktuyr4.execute-api.us-east-1.amazonaws.com',
    ML_FUNCTIONS_URL:  'https://g7o9aq6cf6.execute-api.us-east-1.amazonaws.com',

    // --- SmartDecisions services ---
    INGEST_URL:        'https://544nho7nk4.execute-api.us-east-1.amazonaws.com',
    OPTIMIZATION_URL:  'https://yejyqw3716.execute-api.us-east-1.amazonaws.com',
    ANALYTICS_URL:     'https://u0prf8qr12.execute-api.us-east-1.amazonaws.com',
    MINING_URL:        'https://jvxmqeg601.execute-api.us-east-1.amazonaws.com/minig_analysis',
    QUOTES_URL:        'https://w61p0ef0w7.execute-api.us-east-1.amazonaws.com/quotes',

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
    LOGIN_PATH:         '/index.html'
};
