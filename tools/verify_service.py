'''
    One command for every mechanical check a service must pass before it is
    reported as done. Prints one PASS/FAIL line per check and exits non-zero
    on any failure, so the result cannot be misread as "probably fine".

    Checks:
        tests        pytest, all green
        pylint       10.00/10 over services/ controllers/ routes/ schemas/ tests/
        signatures   one parameter per line (tools/check_signatures.py)
        type-hints   every parameter and return annotated (tests exempt)
        size         no own file at or above the split threshold (800 lines)
        duplicates   no two functions with the same body inside the service
        except-pass  no `except ...: pass`
        env-shorthand  no comma and no brace inside a .env value
        getenv       no `os.getenv` / `os.environ` outside environment.py
        log-vars     WARNING/ERROR logs use `error_msg`, INFO uses `message`

    Usage:
        python tools/verify_service.py services/ingest [services/analytics ...]
        python tools/verify_service.py --all
'''
import ast
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_SERVICES = ('ingest', 'analytics', 'optimization', 'mining_analysis', 'quotes', 'ai')
BOILERPLATE = {'api_exceptions.py', 'crud.py', 'crud_dyb.py', 'db_connection.py',
               'environment.py', 'exceptions.py', 'logger_config.py', 'security.py',
               'utils.py'}
SPLIT_AT = 800
LINT_TARGETS = ('services', 'controllers', 'routes', 'schemas', 'tests')


def _own_files(service: Path) -> list[Path]:
    '''
        The service's own Python files: no boilerplate, no tests, no venv.

        Args:
            service (Path): Service directory.

        Returns:
            list[Path]: Files to check.
    '''
    return [
        path for path in service.rglob('*.py')
        if path.name not in BOILERPLATE
        and 'tests' not in path.parts
        and '.venv' not in path.parts
        and '__pycache__' not in path.parts
    ]


def _run(service: Path, *command: str) -> tuple[int, str]:
    '''
        Runs a command inside the service directory.

        Args:
            service (Path): Working directory.
            *command (str): Command and arguments.

        Returns:
            tuple[int, str]: Exit code and combined output.
    '''
    completed = subprocess.run(
        command, cwd = service, capture_output = True, text = True, check = False
    )
    return completed.returncode, completed.stdout + completed.stderr


def check_tests(service: Path) -> tuple[bool, str]:
    '''pytest over tests/, all green.'''
    if not (service / 'tests').is_dir():
        return False, 'no tests/ directory'
    code, output = _run(service, sys.executable, '-m', 'pytest', 'tests/', '-q')
    summary = next((line for line in reversed(output.splitlines()) if 'passed' in line
                    or 'failed' in line or 'error' in line), output[-200:])
    return code == 0, summary.strip()


def check_pylint(service: Path) -> tuple[bool, str]:
    '''Pylint 10.00 over the five layers and the tests.'''
    targets = [target for target in LINT_TARGETS if (service / target).is_dir()]
    code, output = _run(service, sys.executable, '-m', 'pylint', *targets)
    rated = re.search(r'rated at ([0-9.]+)/10', output)
    findings = [line for line in output.splitlines() if re.match(r'^[a-z_/]+\.py:\d+', line)]
    score = rated.group(1) if rated else '?'
    detail = f'{score}/10' + (f' — {findings[0]}' if findings else '')
    return code == 0 and score == '10.00', detail


def check_signatures(service: Path) -> tuple[bool, str]:
    '''One parameter per line in every multi-line signature.'''
    code, output = _run(ROOT, sys.executable, 'tools/check_signatures.py', str(service))
    return code == 0, output.strip().splitlines()[-1] if output.strip() else 'ok'


def check_size(service: Path) -> tuple[bool, str]:
    '''No own file at or above the split threshold.'''
    sizes = sorted(
        ((sum(1 for _ in path.open()), path) for path in _own_files(service)), reverse = True
    )
    if not sizes:
        return True, 'no files'
    biggest, path = sizes[0]
    over = [f'{p.relative_to(service)} ({n})' for n, p in sizes if n >= SPLIT_AT]
    return not over, (', '.join(over) + ' — partir por funcionalidad') if over \
        else f'largest {path.relative_to(service)} ({biggest})'


def _body_signature(node: ast.AST) -> str:
    '''Function body without its docstring, as a comparable dump.'''
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(
            getattr(body[0], 'value', None), ast.Constant):
        body = body[1:]
    return ast.dump(ast.Module(body = body, type_ignores = []), annotate_fields = False)


def check_duplicates(service: Path) -> tuple[bool, str]:
    '''No two functions with the same body (four lines or more).'''
    seen = defaultdict(list)
    for path in _own_files(service):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.end_lineno - node.lineno >= 4:
                seen[_body_signature(node)].append(f'{path.relative_to(service)}:{node.name}')
    dupes = [' = '.join(places) for places in seen.values() if len(places) > 1]
    # The companion controllers are the same adapter on purpose and say so.
    dupes = [d for d in dupes if 'controllers/' not in d or 'ingest_' not in d]
    return not dupes, ('; '.join(dupes) + ' — parametrizar una sola función') if dupes else 'none'


def check_except_pass(service: Path) -> tuple[bool, str]:
    '''No silent except.'''
    hits = []
    for path in _own_files(service):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 \
                    and isinstance(node.body[0], ast.Pass):
                hits.append(f'{path.relative_to(service)}:{node.lineno}')
    return not hits, ', '.join(hits) if hits else 'none'


def check_env_shorthand(service: Path) -> tuple[bool, str]:
    '''
        No comma and no brace inside a .env value.

        The deploy hands the whole file to `--environment Variables={...}`,
        where a comma separates variables and a brace opens a nested
        structure. A URL template written as `LME_{symbol}_cash` aborted a
        deployment after the code had already been uploaded.
    '''
    env = service / '.env'
    if not env.exists():
        return True, 'no .env'
    bad = []
    for number, line in enumerate(env.read_text().splitlines(), 1):
        code = line.split('#', 1)[0]
        if '=' not in code:
            continue
        value = code.split('=', 1)[1]
        offenders = [name for character, name in ((',', 'coma'), ('{', 'llave'),
                                                  ('}', 'llave')) if character in value]
        if offenders:
            bad.append(f'.env:{number} ({offenders[0]})')
    return not bad, ', '.join(bad) if bad else 'none'


def check_getenv(service: Path) -> tuple[bool, str]:
    '''Configuration only through load_and_validate_env_vars.'''
    hits = []
    for path in _own_files(service):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r'os\.(getenv|environ)', line) and not line.lstrip().startswith('#'):
                hits.append(f'{path.relative_to(service)}:{number}')
    return not hits, ', '.join(hits) if hits else 'none'


def check_log_vars(service: Path) -> tuple[bool, str]:
    '''`logger.warning/error(error_msg)` and `logger.info(message)`.'''
    hits = []
    for path in _own_files(service):
        for number, line in enumerate(path.read_text().splitlines(), 1):
            match = re.search(r'logger\.(info|warning|error|debug)\((\w+)\)', line)
            if not match:
                continue
            level, variable = match.groups()
            expected = 'error_msg' if level in ('warning', 'error') else 'message'
            if variable != expected:
                hits.append(f'{path.relative_to(service)}:{number} ({level} uses {variable})')
    return not hits, ', '.join(hits[:5]) if hits else 'none'


def check_type_hints(service: Path) -> tuple[bool, str]:
    '''
        Every parameter and every return annotated (`.claude/rules/python.md`).
        `self`/`cls` and `__init__` returns are exempt; endpoints are not — the
        return is the response model, and QUOTES writes it.
    '''
    hits = []
    for path in _own_files(service):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            params = (args.posonlyargs + args.args + args.kwonlyargs
                      + ([args.vararg] if args.vararg else [])
                      + ([args.kwarg] if args.kwarg else []))
            untyped = [param.arg for param in params
                       if param.annotation is None and param.arg not in ('self', 'cls')]
            problems = []
            if untyped:
                problems.append('params ' + ','.join(untyped))
            if node.returns is None and node.name != '__init__':
                problems.append('return')
            if problems:
                where = f'{path.relative_to(service)}:{node.lineno} {node.name}'
                hits.append(f'{where} ({"; ".join(problems)})')
    if not hits:
        return True, 'none'
    more = f' … +{len(hits) - 5}' if len(hits) > 5 else ''
    return False, ', '.join(hits[:5]) + more


CHECKS = (
    ('tests', check_tests),
    ('pylint', check_pylint),
    ('signatures', check_signatures),
    ('type-hints', check_type_hints),
    ('size', check_size),
    ('duplicates', check_duplicates),
    ('except-pass', check_except_pass),
    ('env-shorthand', check_env_shorthand),
    ('getenv', check_getenv),
    ('log-vars', check_log_vars),
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
    if '--all' in sys.argv or not args:
        targets = [ROOT / 'services' / name for name in PRODUCT_SERVICES]
    else:
        targets = [(ROOT / arg) if not Path(arg).is_absolute() else Path(arg) for arg in args]
    results = [verify(target) for target in targets]
    failed = [target.name for target, ok in zip(targets, results) if not ok]
    print('FAILED: ' + ', '.join(failed) if failed else 'ALL PASS')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
