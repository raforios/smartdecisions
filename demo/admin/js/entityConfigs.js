/**
 * Configuration shared by EntityPanel for the four CMS entities.
 *
 * Each entry describes:
 *   - title:      Section header.
 *   - service:    Methods on CmsAdminService used to interact with the
 *                 backend (list/create/get/update/delete).
 *   - columns:    Field names rendered in the listing table, in order.
 *   - fields:     Form fields rendered by EntityPanel (used for both
 *                 Create and Update; on Update non-Optional fields are
 *                 pre-filled from the loaded item).
 *   - subPath:    Subfolder under cmsAssetsPath where this entity's
 *                 uploads land in S3.
 *
 * Field types: text, textarea, number, date, datetime, checkbox, select,
 *              file. File fields produce a paired `<refName>_s3_bucket`
 *              + `<refName>_s3_key` payload after the upload resolves.
 */
export const ENTITY_CONFIGS = {
    news: {
        title: 'Noticias',
        subPath: 'news',
        service: {
            list: 'listNews',
            create: 'createNews',
            get: 'getNews',
            update: 'updateNews',
            delete: 'deleteNews',
        },
        columns: [
            { key: 'title', label: 'Título' },
            { key: 'type', label: 'Tipo' },
            { key: 'lang', label: 'Idioma' },
            { key: 'is_published', label: 'Pub.', type: 'bool' },
            { key: 'updated_at', label: 'Modificado', type: 'datetime' },
        ],
        fields: [
            { name: 'lang', label: 'Idioma', type: 'select',
              options: [{value: 'es', label: 'Español'}, {value: 'en', label: 'English'}],
              default: 'es' },
            { name: 'type', label: 'Tipo', type: 'select', required: true,
              options: [
                  { value: 'press', label: 'Nota de prensa' },
                  { value: 'communique', label: 'Comunicado' },
                  { value: 'photo', label: 'Fotografía' },
                  { value: 'article', label: 'Artículo' },
              ] },
            { name: 'title', label: 'Título', type: 'text', required: true,
              maxLength: 255 },
            { name: 'summary', label: 'Resumen', type: 'textarea', maxLength: 500 },
            { name: 'body', label: 'Cuerpo', type: 'textarea' },
            { name: 'image', label: 'Imagen (subir)', type: 'file',
              refName: 'image', accept: 'image/*' },
            { name: 'external_url', label: 'URL externa', type: 'text', maxLength: 500 },
            { name: 'published_at', label: 'Publicado en', type: 'datetime' },
            { name: 'is_published', label: 'Publicado', type: 'checkbox', default: true },
            { name: 'sort_order', label: 'Orden', type: 'number', default: 0 },
        ],
    },
    documents: {
        title: 'Documentos',
        subPath: 'documents',
        service: {
            list: 'listDocuments',
            create: 'createDocument',
            get: 'getDocument',
            update: 'updateDocument',
            delete: 'deleteDocument',
        },
        columns: [
            { key: 'title', label: 'Título' },
            { key: 'doc_type', label: 'Formato' },
            { key: 'lang', label: 'Idioma' },
            { key: 'doc_date', label: 'Fecha' },
            { key: 'is_published', label: 'Pub.', type: 'bool' },
        ],
        fields: [
            { name: 'lang', label: 'Idioma', type: 'select',
              options: [{value: 'es', label: 'Español'}, {value: 'en', label: 'English'}],
              default: 'es' },
            { name: 'title', label: 'Título', type: 'text', required: true,
              maxLength: 255 },
            { name: 'doc_type', label: 'Formato', type: 'text', required: true,
              maxLength: 50, placeholder: 'PDF, DOC, LEY...' },
            { name: 'doc_date', label: 'Fecha', type: 'date' },
            { name: 'file', label: 'Archivo (subir)', type: 'file',
              refName: 'file', accept: '' },
            { name: 'file_external_url', label: 'URL externa (alterna)',
              type: 'text', maxLength: 500 },
            { name: 'is_published', label: 'Publicado', type: 'checkbox', default: true },
            { name: 'sort_order', label: 'Orden', type: 'number', default: 0 },
        ],
    },
    slides: {
        title: 'Slider',
        subPath: 'slides',
        service: {
            list: 'listSlides',
            create: 'createSlide',
            get: 'getSlide',
            update: 'updateSlide',
            delete: 'deleteSlide',
        },
        columns: [
            { key: 'title', label: 'Título' },
            { key: 'lang', label: 'Idioma' },
            { key: 'is_active', label: 'Activo', type: 'bool' },
            { key: 'sort_order', label: 'Orden' },
        ],
        fields: [
            { name: 'lang', label: 'Idioma', type: 'select',
              options: [{value: 'es', label: 'Español'}, {value: 'en', label: 'English'}],
              default: 'es' },
            { name: 'title', label: 'Título', type: 'text', required: true,
              maxLength: 255 },
            { name: 'description', label: 'Descripción', type: 'textarea',
              maxLength: 500 },
            { name: 'image', label: 'Imagen (subir)', type: 'file',
              refName: 'image', accept: 'image/*' },
            { name: 'link_url', label: 'Link al hacer clic', type: 'text',
              maxLength: 500 },
            { name: 'is_active', label: 'Activo', type: 'checkbox', default: true },
            { name: 'sort_order', label: 'Orden', type: 'number', default: 0 },
        ],
    },
    entities: {
        title: 'Entidades',
        subPath: 'entities',
        service: {
            list: 'listEntities',
            create: 'createEntity',
            get: 'getEntity',
            update: 'updateEntity',
            delete: 'deleteEntity',
        },
        columns: [
            { key: 'name', label: 'Nombre' },
            { key: 'url', label: 'URL' },
            { key: 'is_active', label: 'Activo', type: 'bool' },
            { key: 'sort_order', label: 'Orden' },
        ],
        fields: [
            { name: 'name', label: 'Nombre', type: 'text', required: true,
              maxLength: 100 },
            { name: 'short_description', label: 'Descripción breve',
              type: 'textarea', maxLength: 255 },
            { name: 'url', label: 'URL', type: 'text', required: true,
              maxLength: 500, placeholder: 'https://...' },
            { name: 'logo', label: 'Logo (subir)', type: 'file',
              refName: 'logo', accept: 'image/*' },
            { name: 'is_active', label: 'Activo', type: 'checkbox', default: true },
            { name: 'sort_order', label: 'Orden', type: 'number', default: 0 },
        ],
    },
};
