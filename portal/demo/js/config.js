'use strict';

/**
 * SmartDecisions demo — service endpoint configuration.
 *
 * Hosted statically (S3 + CloudFront) per environment by simply replacing
 * the URLs below. No build step required.
 *
 * Each microservice lives behind its own API Gateway. AUTH / EVENTS /
 * FILES / ML_FUNCTIONS are already in production (real URLs). The three
 * SmartDecisions-specific services (INGEST, OPTIMIZATION, ANALYTICS)
 * are still pending deploy and run on localhost during dev.
 */
window.SD_CONFIG = {
    // --- Productive (deployed on AWS API Gateway) ---
    AUTH_URL:          'https://32652ile50.execute-api.us-east-1.amazonaws.com',
    EVENTS_URL:        'https://uyrs6ucto3.execute-api.us-east-1.amazonaws.com',
    FILES_URL:         'https://ek2xktuyr4.execute-api.us-east-1.amazonaws.com',
    ML_FUNCTIONS_URL:  'https://g7o9aq6cf6.execute-api.us-east-1.amazonaws.com',

    // --- Pending deploy (TODO: replace with API Gateway URLs once deployed) ---
    INGEST_URL:        'https://544nho7nk4.execute-api.us-east-1.amazonaws.com',
    OPTIMIZATION_URL:  'https://yejyqw3716.execute-api.us-east-1.amazonaws.com',
    ANALYTICS_URL:     'https://u0prf8qr12.execute-api.us-east-1.amazonaws.com',

    // Storage keys used by sessionStorage (kept here so module pages
    // don't reinvent constants).
    STORAGE_TOKEN_KEY:  'sd_token',
    STORAGE_EMAIL_KEY:  'sd_user_email',

    // Absolute path to the login page, used by auth/api helpers when they
    // need to bounce the user back. Adjust if the demo is mounted under
    // a different prefix (e.g. '/portal/demo/index.html').
    LOGIN_PATH:         '/index.html'
};
