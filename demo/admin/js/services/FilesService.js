/**
 * FilesService — uploads binary assets to the FILES microservice and
 * returns the S3 reference (bucket + key) so the CMS admin form can
 * persist it on the matching `*_s3_bucket` / `*_s3_key` fields.
 *
 * Uses multipart/form-data (the FILES endpoint expects `file`,
 * `bucket_name` and `file_path`). The Authorization header is taken
 * from the admin's stored JWT — FILES validates the same token issued
 * by AUTH.
 */
import { resolveBases, request, authHeader } from './apiClient.js';

export class FilesService {
    constructor({ filesBaseUrl, filesBaseUrlFallback,
                  cmsAssetsBucket, cmsAssetsPath = '' } = {}) {
        this.bases = resolveBases({
            remote: filesBaseUrl, local: filesBaseUrlFallback,
        });
        this.bucket = cmsAssetsBucket;
        this.basePath = cmsAssetsPath;
    }

    /**
     * Uploads a File/Blob to S3 under `${basePath}${subPath}/`. Returns
     * `{ bucket, key, url }`. Throws on auth/HTTP errors.
     */
    async upload(file, subPath = '') {
        if (!this.bucket) {
            throw new Error('cmsAssetsBucket no configurado en config.json');
        }
        const formData = new FormData();
        formData.append('file', file);
        formData.append('bucket_name', this.bucket);
        formData.append('file_path', _composePath(this.basePath, subPath));

        const response = await request(this.bases, '/upload', {
            method: 'POST',
            headers: authHeader(),
            body: formData,
        });
        if (response.status === 401) {
            localStorage.removeItem('admin_jwt');
            throw new Error('Sesión expirada — vuelve a iniciar sesión.');
        }
        if (!response.ok) {
            const payload = await response.json().catch(() => null);
            throw new Error(payload?.detail || `HTTP ${response.status}`);
        }
        const data = await response.json();
        return {
            bucket: this.bucket,
            key: data.file_key,
            url: data.url,
        };
    }
}

function _composePath(base, sub) {
    const parts = [base, sub].map(p => (p || '').replace(/^\/|\/$/g, '')).filter(Boolean);
    return parts.length ? parts.join('/') + '/' : '';
}
