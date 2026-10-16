# SmartBilling — Frontend

Static UI over the BILLING service (`/v1/billing/*`), signing in against AUTH.
No framework: HTML5, Vanilla JS (ES modules) and CSS3, responsive.

## Layout

```
portal/billing/
├── index.html            shell: sidebar, topbar, page host, modal, toasts
├── login.html            sign-in against AUTH
├── css/base.css          copy of the SmartDecisions sheet
├── css/billing.css       what is BILLING's own
└── js/
    ├── app.js                  entry of index.html: sections and role gate
    ├── login.js                entry of login.html
    ├── auth.js                 JWT helpers (email, role)
    ├── config.js               service URLs and storage keys
    ├── ui.js                   toast, modal, formatters
    ├── services/
    │   ├── apiClient.js        transport, local or remote base
    │   ├── AuthService.js      POST /v1/auth/login and storage
    │   └── BillingService.js   every /v1/billing/* endpoint
    └── pages/
        ├── CounterPage.js      the counter: search or scan, sell, print
        ├── CashPage.js         the user's till of the day
        ├── CashSessionsPage.js every till, closed by the manager
        ├── SalesPage.js        issued notes and their cancellation
        ├── CatalogPage.js      products and their lots
        ├── PurchasesPage.js    receiving stock
        ├── DashboardPage.js    sales, expiring lots, low stock
        ├── SettingsPage.js     the shop's settings
        └── TicketPrinter.js    58/80 mm thermal ticket
```

## URLs

Constants in `js/config.js`. The `*_LOCAL` URLs only apply when the page is
served from localhost.

## Roles

The menu reads the `role` claim of the JWT. Receiving stock, the tills of
everyone and the settings are for `ADMIN` and `MANAGER`; the router hides the
rest of what a role cannot use.
