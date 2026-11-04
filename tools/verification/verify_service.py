'''
    One command for every mechanical check a service must pass before it is
    reported as done. Prints one PASS/FAIL line per check and exits non-zero
    on any failure, so the result cannot be misread as "probably fine".

    Checks:
        tests        pytest, all green
        pylint       10.00/10 over services/ controllers/ routes/ schemas/ tests/
        signatures   one parameter per line (tools/verification/check_signatures.py)
        type-hints   every parameter and return annotated (tests exempt)
        size         no own file at or above the split threshold (800 lines)
        duplicates   no two functions with the same body inside the service
        except-pass  no `except ...: pass`
        env-shorthand  no comma and no brace inside a .env value
        getenv       no `os.getenv` / `os.environ` outside environment.py
        modern-typing  `list[str]`, `str | None`: no List/Dict/Optional/Union
                     from typing, boilerplate and tests included
        log-vars     WARNING/ERROR logs use `error_msg`, INFO uses `message`
        code-language  Enum members and closed options in English
        events       every controller reports usage to EVENTS, and every
                     write is audited

    `--all` and `--tools` also check `tools/`: the same Python rules apply
    there, and nothing else watches it. Each tool is linted the way it runs,
    with the repository root and the service it imports on the path.

    Usage:
        python tools/verification/verify_service.py services/ingest [services/analytics ...]
        python tools/verification/verify_service.py --all
        python tools/verification/verify_service.py --tools
'''
import ast
import os
import re
import subprocess
import sys
from pathlib import Path

from verify_checks import (
    check_comment_language,
    check_cross_service_duplicates,
    check_direct_s3,
    check_duplicates,
    check_endpoint_coverage,
    check_env_shorthand,
    check_events,
    check_except_pass,
    check_foreign_tables,
    check_getenv,
    check_imports,
    check_log_vars,
    check_modern_typing,
    check_pylint,
    check_signatures,
    check_size,
    check_tests,
    check_type_hints,
    ROOT,
    PRODUCT_SERVICES,
    run_command
)



# Spanish words that turn up in business codes. A code the backend stores or
# returns is English (CLAUDE.md §1); the Spanish the client writes is mapped.
# The SIN is the tax office's acronym, not the preposition, so it is not here.
SPANISH_CODE_WORDS = frozenset({
    'EFECTIVO', 'TARJETA', 'TRANSFERENCIA', 'BILLETERA', 'MOVIL', 'CONTADO', 'CREDITO',
    'DEBITO', 'VENTA', 'VENTAS', 'COMPRA', 'COMPRAS', 'CERRADO', 'ABIERTO', 'ENCONTRADO',
    'PENDIENTE', 'ANULADO', 'ANULADA', 'ACTIVO', 'INACTIVO', 'PAGADO', 'COBRADO', 'CLIENTE',
    'PRODUCTO', 'PROVEEDOR', 'FACTURA', 'NOTA', 'CAJA', 'GASTO', 'INGRESO', 'EGRESO',
    'DEVOLUCION', 'VENDEDOR', 'ALTA', 'BAJA', 'MEDIA', 'OTRO', 'OTROS'
})


def _codes_in(tree: ast.AST) -> list[tuple[int, str]]:
    '''
        The codes a module declares: the names and values of every Enum
        member, and every value offered as `allowed`.
    '''
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
                'Enum' in ast.unparse(base) for base in node.bases):
            for item in node.body:
                if isinstance(item, ast.Assign) and isinstance(item.value, ast.Constant):
                    found += [(item.lineno, target.id) for target in item.targets
                              if isinstance(target, ast.Name)]
                    found.append((item.lineno, str(item.value.value)))
        if isinstance(node, ast.keyword) and node.arg == 'allowed' \
                and isinstance(node.value, (ast.Tuple, ast.List)):
            found += [(element.lineno, str(element.value)) for element in node.value.elts
                      if isinstance(element, ast.Constant)]
    return found


def check_code_language(service: Path) -> tuple[bool, str]:
    '''
        Codes in English: Enum members and closed options.

        `CLAUDE.md` §1. On 4-nov-2026 the means of payment went in as
        EFECTIVO and TARJETA, copying older codes that broke the same rule;
        comment-language never looked at values, so nothing went red.
    '''
    hits = []
    for path in sorted(service.rglob('*.py')):
        if '__pycache__' in path.parts or 'tests' in path.parts:
            continue
        for number, code in _codes_in(ast.parse(path.read_text())):
            if SPANISH_CODE_WORDS & set(code.upper().split('_')):
                hits.append(f'{path.relative_to(service)}:{number} {code}')
    return not hits, ', '.join(hits[:5]) if hits else 'none'


CHECKS = (
    ('tests', check_tests),
    ('imports', check_imports),
    ('endpoint-coverage', check_endpoint_coverage),
    ('pylint', check_pylint),
    ('signatures', check_signatures),
    ('type-hints', check_type_hints),
    ('size', check_size),
    ('duplicates', check_duplicates),
    ('except-pass', check_except_pass),
    ('env-shorthand', check_env_shorthand),
    ('getenv', check_getenv),
    ('modern-typing', check_modern_typing),
    ('log-vars', check_log_vars),
    ('comment-language', check_comment_language),
    ('code-language', check_code_language),
    ('cross-duplicates', check_cross_service_duplicates),
    ('direct-s3', check_direct_s3),
    ('foreign-tables', check_foreign_tables),
    ('events', check_events),
)

# Checks that REPORT a backlog instead of blocking a delivery. Endpoint
# coverage is one: it is a real gap and the number has to stay visible, but
# closing 60-odd endpoints is planned work, not something that should stop a
# service from shipping the day the check was written.
ADVISORY = ('endpoint-coverage',)


TOOLS = ROOT / 'tools'

# How a tool says which service it imports: `ROOT / 'services' / 'ingest'` or
# `Path('services/ingest')`.
TOOL_SERVICE = re.compile(r"'services'\s*/\s*'(\w+)'|Path\('services/(\w+)'\)")


def _tool_pythonpath(path: Path) -> str:
    '''
        The path a tool runs with: the repository root (`python -m tools.x`),
        its own folder (`python tools/x.py`), and the service it imports.

        Args:
            path (Path): The tool.

        Returns:
            str: Value for PYTHONPATH.
    '''
    source = path.read_text()
    match = TOOL_SERVICE.search(source)
    service = next((group for group in match.groups() if group), None) if match else None
    parts = [str(ROOT), str(path.parent)]
    parts += [str(ROOT / 'services' / service)] if service else []
    return os.pathsep.join(parts)


def check_tools_pylint(tools: Path) -> tuple[bool, str]:
    '''Pylint 10.00 on every tool, each with its own path; duplicates across all.'''
    findings = []
    for path in sorted(tools.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        completed = subprocess.run(
            [sys.executable, '-m', 'pylint', f'--rcfile={ROOT / ".pylintrc"}',
             '--disable=duplicate-code', str(path)],
            cwd = ROOT, capture_output = True, text = True, check = False,
            env = {**os.environ, 'PYTHONPATH': _tool_pythonpath(path)}
        )
        findings += [line for line in completed.stdout.splitlines()
                     if re.match(r'^tools/\S+\.py:\d+', line)]
    code, output = run_command(ROOT, sys.executable, '-m', 'pylint',
                               f'--rcfile={ROOT / ".pylintrc"}',
                               '--disable=all', '--enable=duplicate-code', 'tools')
    if code:
        findings += [line for line in output.splitlines() if 'R0801' in line]
    return not findings, (f'{len(findings)} finding(s) — {findings[0]}' if findings else '10.00/10')


TOOL_CHECKS = (
    ('pylint', check_tools_pylint),
    ('signatures', check_signatures),
    ('type-hints', check_type_hints),
    ('size', check_size),
    ('except-pass', check_except_pass),
    ('modern-typing', check_modern_typing),
    ('comment-language', check_comment_language),
)


def verify(service: Path) -> bool:
    '''
        Runs every check on one service and prints the report.

        Args:
            service (Path): Service directory.

        Returns:
            bool: True when everything passed.
    '''
    print(f'== {service.name}')
    all_ok = True
    for name, check in CHECKS:
        ok, detail = check(service)
        advisory = name in ADVISORY
        all_ok &= ok or advisory
        label = 'PASS' if ok else ('TODO' if advisory else 'FAIL')
        print(f'  {label}  {name:<12} {detail}')
    return all_ok


def verify_tools() -> bool:
    '''
        Runs the checks that apply to `tools/` and prints the report.

        Returns:
            bool: True when everything passed.
    '''
    print('== tools')
    all_ok = True
    for name, check in TOOL_CHECKS:
        ok, detail = check(TOOLS)
        all_ok &= ok
        print(f'  {"PASS" if ok else "FAIL"}  {name:<12} {detail}')
    return all_ok


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 when every service passed, 1 otherwise.
    '''
    args = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    only_tools = '--tools' in sys.argv and not args and '--all' not in sys.argv
    if only_tools:
        targets = []
    elif '--all' in sys.argv or not args:
        targets = [ROOT / 'services' / name for name in PRODUCT_SERVICES]
    else:
        targets = [(ROOT / arg) if not Path(arg).is_absolute() else Path(arg) for arg in args]
    results = [verify(target) for target in targets]
    failed = [target.name for target, ok in zip(targets, results) if not ok]
    if ('--all' in sys.argv or '--tools' in sys.argv) and not verify_tools():
        failed.append('tools')
    print('FAILED: ' + ', '.join(failed) if failed else 'ALL PASS')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
