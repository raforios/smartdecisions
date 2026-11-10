# WMS — Frontend

Static UI of the warehouse management system, signing in against AUTH.
No framework: HTML5, Vanilla JS (ES modules) and CSS3, on `portal/common/`.

Until the `wms` service exists, `js/store.js` keeps the data in the browser
(`localStorage`) behind async functions shaped like the future API, and seeds
a sample facility. Replacing that file with calls to `/v1/wms/*` is the only
change the pages need.

## Layout

```
portal/wms/
├── index.html            page host; the frame is drawn by common/js/frame.js
├── login.html            sign-in (common/js/session/login.js)
├── common -> ../common   shared with SmartDecisions and SmartBilling
├── css/wms.css           the plan and its side panel
└── js/
    ├── app.js            menu and sections
    ├── config.js         AUTH URL and storage keys
    ├── codes.js          location codes: aisle, bay and side (A1P3R5N2)
    ├── plan.js           SVG plan in metres: drag, snap, no overlaps
    ├── store.js          data until the service exists
    ├── ui.js             page helpers and the save bar
    └── pages/
        ├── FacilitiesPage.js    facilities and their data
        ├── FacilityPlanPage.js  warehouses on the facility plan
        ├── WarehousePage.js     aisles and elements of a warehouse
        └── HistoryPage.js       saved versions and their changes
```

## Run locally

```bash
cd portal/wms && python3 -m http.server 8090 --bind 127.0.0.1
```
