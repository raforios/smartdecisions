'''
    The language sweeps of `/constitucion` over what changed in the working
    tree: comments and docstrings in English (`.py`, `.js`, `.css`, `.html`),
    and codes in English (Enum members and closed options).

    Run by the Stop hook (`.claude/settings.json`) at the end of every turn,
    so the sweep no longer depends on remembering to run it (Rafael,
    4-nov-2026). With findings it answers `decision: block`, which keeps the
    turn open to fix them; when the hook already blocked once in a row
    (`stop_hook_active`) it only reports, so it cannot loop. The skill runs
    the same script.

    Usage:
        python tools/verification/language_gate.py            # report
        echo '{}' | python tools/verification/language_gate.py --hook
'''
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

# pylint: disable=wrong-import-position
from verify_checks import PRODUCT_SERVICES
from verify_service import SPANISH_CODE_WORDS, codes_in
# pylint: enable=wrong-import-position

# Unmistakable Spanish markers. 'no', 'es', 'la', 'el', 'un', 'sin', 'con' and
# 'a' are left out on purpose: they exist in English or match English words.
SPANISH = re.compile(
    r'\b(que|los|las|del|por|para|como|cuando|cada|toda|todos|hay|pero|porque|'
    r'acá|así|sólo|según|entre|desde|hasta|esto|esta|este|estos|sus|cuál|'
    r'está|están|más|aquí|qué|dónde|archivo|cliente|producto|venta|ventas|'
    r'cobro|cobros|fecha|días|monto|saldo|crédito|plazo|factura|facturas|'
    r'tramo|tramos|política|almacén|demanda|cobertura)\b', re.I)
# A comment may quote a contract value ('CREDITO', 'Crédito') on purpose.
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
COMMENT_MARK = re.compile(r'^(//|/\*\*?|\*/?|<!--)\s*|\s*(\*/|-->)$')

SWEPT = ('.py', '.js', '.css', '.html')


def _is_own(path: Path) -> bool:
    '''
        Whether a path belongs to BearSoft: tools/, portal/ and the ten own
        services; the clients' services are reported, never swept here.

        Args:
            path (Path): Path relative to the repository root.

        Returns:
            bool: True when it is BearSoft's.
    '''
    parts = path.parts
    if 'services' not in parts:
        return True
    index = parts.index('services')
    return len(parts) > index + 1 and parts[index + 1] in PRODUCT_SERVICES


def _git(*args: str) -> list[str]:
    '''
        The words a git command prints, run at the repository root.

        Args:
            *args (str): The git arguments.

        Returns:
            list[str]: Its output, split on whitespace.
    '''
    return subprocess.run(['git', *args], cwd = ROOT, capture_output = True, text = True,
                          check = True).stdout.split()


def changed_files() -> list[Path]:
    '''
        The files the working tree changed or added, own and sweepable.

        Returns:
            list[Path]: Paths relative to the repository root.
    '''
    names = set(_git('diff', '--name-only', 'HEAD')) | set(_git('ls-files', '--others',
                                                                '--exclude-standard'))
    return sorted(Path(name) for name in names
                  if Path(name).suffix in SWEPT and (ROOT / name).exists()
                  and _is_own(Path(name)))


def _comment_body(
    path: Path,
    stripped: str
) -> str:
    '''
        The prose of a line when it is a comment or a docstring line.

        Args:
            path (Path): The file, whose suffix says how it comments.
            stripped (str): The line, trimmed.

        Returns:
            str: The prose; empty when the line is code.
    '''
    if path.suffix == '.py':
        if stripped.startswith('#'):
            return stripped.lstrip('#').strip()
        return stripped.strip("'").strip('"') if stripped.startswith(("'''", '"""')) else ''
    return COMMENT_MARK.sub('', stripped) if stripped.startswith(('//', '/*', '*', '<!--')) else ''


def findings() -> list[str]:
    '''
        Spanish comments and Spanish codes in the changed files.

        Returns:
            list[str]: One `path:line  text` per finding.
    '''
    found = []
    for path in changed_files():
        source = (ROOT / path).read_text(encoding = 'utf-8')
        for number, line in enumerate(source.splitlines(), 1):
            body = QUOTED.sub('', _comment_body(path, line.strip()))
            if body and len(SPANISH.findall(body)) >= 2:
                found.append(f'{path}:{number}  comment: {line.strip()[:70]}')
        if path.suffix == '.py' and 'services' in path.parts and 'tests' not in path.parts:
            for number, code in codes_in(ast.parse(source)):
                if SPANISH_CODE_WORDS & set(code.upper().split('_')):
                    found.append(f'{path}:{number}  code: {code}')
    return found


def main() -> int:
    '''
        Reports, or answers the Stop hook.

        Returns:
            int: 0 always; the hook reads the JSON it prints.
    '''
    hook = '--hook' in sys.argv
    already = json.loads(sys.stdin.read() or '{}').get('stop_hook_active') if hook else False
    found = findings()
    if not hook:
        print('\n'.join(found + [f'findings: {len(found)}']))
        return 0
    if found:
        report = 'Spanish in code (CLAUDE.md §1, /constitucion):\n' + '\n'.join(found[:20])
        print(json.dumps({'systemMessage': report} if already else
                         {'decision': 'block', 'reason': report + '\nFix them before ending.'}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
