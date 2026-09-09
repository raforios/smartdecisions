'''
    Deploys the SmartDecisions demo portal, stamping every asset with the hash
    of its own content.

    The reason this exists: a browser holding `minerales.js?v=2` never asks for
    it again when the file changes but the number does not, and bumping that
    number by hand is exactly the step that gets skipped. Here the query string
    *is* the content, so a changed file always gets a new URL and an unchanged
    one keeps its cache.

    Usage:
        python -m tools.deploy_demo_portal                  # informa qué haría
        python -m tools.deploy_demo_portal --yes            # estampa, sube, invalida
        python -m tools.deploy_demo_portal --yes --only minerales
'''
import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional


PORTAL_ROOT = Path(__file__).resolve().parent.parent / 'portal' / 'demo'
BUCKET = 'bearsoft-smartdecisions-landing'
DISTRIBUTION_ID = 'EXP60FDO0MJVI'
PROFILE = 'deploy_ml'

# Local .js/.css references only: an absolute URL belongs to somebody else's
# cache policy and must not be rewritten.
_ASSET_REFERENCE = re.compile(
    r'(?P<attr>(?:src|href)=")(?P<path>(?!https?://)[^"?]+\.(?:js|css))(?:\?v=[^"]*)?"'
)


def _fingerprint(path: Path) -> str:
    '''
        Returns a short content hash of a file.

        Args:
            path (Path): File to fingerprint.

        Returns:
            str: First 10 hexadecimal characters of its SHA-256.
    '''
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def _stamp(page: Path) -> bool:
    '''
        Rewrites every local asset reference of one page with its content hash.

        Args:
            page (Path): HTML file to rewrite.

        Returns:
            bool: True when the file changed on disk.
    '''
    original = page.read_text(encoding = 'utf-8')

    def _replace(match: 're.Match[str]') -> str:
        target = (page.parent / match.group('path')).resolve()
        if not target.exists():
            print(f'  aviso: {page.name} apunta a {match.group("path")}, que no existe')
            return match.group(0)
        return f'{match.group("attr")}{match.group("path")}?v={_fingerprint(target)}"'

    updated = _ASSET_REFERENCE.sub(_replace, original)
    if updated == original:
        return False
    page.write_text(updated, encoding = 'utf-8')
    return True


def _run(command: List[str]) -> None:
    '''
        Runs a command and stops the deploy if it fails.

        Args:
            command (List[str]): Command and arguments.

        Raises:
            SystemExit: If the command returns a non-zero status.
    '''
    result = subprocess.run(command, check = False)
    if result.returncode != 0:
        raise SystemExit(f'Falló: {" ".join(command)}')


def _pages(only: Optional[str]) -> List[Path]:
    '''
        Returns the HTML pages to stamp.

        Args:
            only (str | None): Restrict to one module directory.

        Returns:
            List[Path]: Pages found under the portal.
    '''
    root = PORTAL_ROOT / only if only else PORTAL_ROOT
    return sorted(root.rglob('*.html'))


def _publish(only: Optional[str]) -> None:
    '''
        Uploads the portal and invalidates the distribution.

        Args:
            only (str | None): Restrict to one module directory.
    '''
    source = PORTAL_ROOT / only if only else PORTAL_ROOT
    target = f's3://{BUCKET}/{only}/' if only else f's3://{BUCKET}/'
    _run(['aws', 's3', 'sync', str(source), target,
          '--profile', PROFILE, '--no-progress', '--exclude', '.*'])

    paths = [f'/{only}/*'] if only else ['/*']
    _run(['aws', 'cloudfront', 'create-invalidation',
          '--distribution-id', DISTRIBUTION_ID, '--paths', *paths,
          '--profile', PROFILE, '--query', 'Invalidation.Status', '--output', 'text'])


def main() -> int:
    '''
        Entry point of the deploy.

        Returns:
            int: 0 on success, 1 when there is nothing to deploy.
    '''
    parser = argparse.ArgumentParser(description = 'Despliega el portal demo.')
    parser.add_argument('--yes', action = 'store_true',
                        help = 'Estampa, sube e invalida. Sin esto solo informa.')
    parser.add_argument('--only', default = None,
                        help = 'Limita a un módulo (ej: minerales).')
    args = parser.parse_args()

    pages = _pages(args.only)
    if not pages:
        print('No se encontraron páginas.')
        return 1

    print(f'Páginas: {len(pages)}')
    changed = [page for page in pages if _stamp(page)]
    for page in changed:
        print(f'  re-estampada {page.relative_to(PORTAL_ROOT)}')
    if not changed:
        print('  ningún hash cambió.')

    if not args.yes:
        print('Simulación: no se subió nada. Repite con --yes.')
        return 0

    _publish(args.only)
    print('Despliegue terminado.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
