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
        events       every controller reports usage to EVENTS, and every
                     write is audited

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
# The eleven services BearSoft owns, in the four groups of SMARTDECISIONS.md.
# AUTH, EVENTS, FILES and ML_FUNCTIONS were missing until 27-09-2026, so they
# accumulated findings nobody ever saw: a sweep that skips a service is a
# sweep that certifies it by omission.
PRODUCT_SERVICES = (
    # SmartDecisions
    'ingest', 'analytics', 'optimization', 'mining_analysis', 'quotes', 'ai',
    # SmartBilling
    'billing',
    # Genéricos y obligatorios
    'auth', 'events', 'files',
    # Capacitación
    'ml_functions',
)
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


# A function has to be this long before the same body in two services means
# duplication rather than coincidence: a three-line getter repeats honestly.
_CROSS_SERVICE_MIN_LINES = 8

# Copied into several services and genuinely duplicated, but they are
# boilerplate that was never promoted to `utils.py`: the Decimal conversion
# DynamoDB forces on everyone. Listed here so the debt is visible instead of
# drowning every other finding. Promoting them touches the boilerplate, which
# needs Rafael's go-ahead.
_PENDING_BOILERPLATE = ('to_dynamo', 'from_dynamo', 'get_caller')

# ANALYTICS and OPTIMIZATION read the dataset INGEST produced, straight from
# S3 and with the same two helpers. It is real duplication and a real crossing
# of the bucket rule, and it predates the rule. Rafael's call on 28-09-2026:
# FILES goes into the service that needs it —INGEST— and these two follow when
# each is worked on, not by symmetry. Listed so the debt stays visible.
_PENDING_DATASET_READERS = ('_read_dataframe', 'get_dataset_metadata')


def _service_bodies(service: Path) -> tuple[tuple[str, str], ...]:
    '''
        The comparable body of every own function of a service.

        Args:
            service (Path): Service directory.

        Returns:
            tuple[tuple[str, str], ...]: Pairs of body dump and where it lives.
    '''
    bodies = []
    for path in _own_files(service):
        # `main.py` is the service shell —health check, CORS, the scheduled
        # entry point— and it is identical on purpose: that is the uniformity
        # rule, not duplication.
        if 'tests' in path.parts or path.name == 'main.py':
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name not in _PENDING_BOILERPLATE \
                    and node.name not in _PENDING_DATASET_READERS \
                    and node.end_lineno - node.lineno >= _CROSS_SERVICE_MIN_LINES:
                bodies.append((_body_signature(node),
                               f'{path.relative_to(service)}:{node.name}'))
    return tuple(bodies)


def check_cross_service_duplicates(service: Path) -> tuple[bool, str]:
    '''
        No function of this service repeated in another one.

        `check_duplicates` only ever looked inside a single service, so on
        27-09-2026 a client master copied into a second microservice —571
        lines, the business rule among them— passed every check. Two services
        holding one rule is not DRY, it is two rules waiting to disagree:
        whoever owns the capability serves it and the rest ask.
    '''
    mine = dict(_service_bodies(service))
    hits = []
    for other in (ROOT / 'services' / name for name in PRODUCT_SERVICES):
        if other.name == service.name or not other.is_dir():
            continue
        for body, where in _service_bodies(other):
            if body in mine:
                hits.append(f'{mine[body]} = {other.name}/{where}')
    return not hits, ('; '.join(sorted(set(hits))[:4])
                      + ' — un dueño lo sirve, el resto lo piden') if hits else 'none'


# FILES is the bucket's owner, so it is the one service that holds an S3
# client. The single line allowed elsewhere is INGEST reading a STATIC
# template: FILES cannot hand a file back AS a file —its reader parses and
# returns rows— and `CLAUDE.md` §9 names exactly that case.
_S3_ALLOWED: dict[str, tuple[str, ...]] = {
    'files': ('controllers/files.py',),
    'ingest': ('services/ingest_utils.py',),
    # Pending, by Rafael's decision of 28-09-2026: they read the dataset
    # INGEST produced and they migrate when each is worked on.
    'analytics': ('services/analytics_utils.py',),
    'optimization': ('services/optimization_utils.py',),
}


def check_direct_s3(service: Path) -> tuple[bool, str]:
    '''
        Only FILES talks to the bucket.

        Every other service asks FILES, forwarding the caller's token. INGEST
        grew its own S3 client because the four-sheet workbook it used to read
        could not come back through a reader that returns one flat table; the
        workbook is gone and so is the reason.
    '''
    allowed = _S3_ALLOWED.get(service.name, ())
    hits = []
    for path in _own_files(service):
        where = str(path.relative_to(service))
        if where in allowed:
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if "boto3.client('s3')" in line or 'boto3.resource(\'s3\')' in line:
                hits.append(f'{where}:{number}')
    return not hits, (', '.join(hits) + ' — se pide a FILES') if hits else 'none'


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


# Spanish function words that do not also read as English, code or a quoted
# rule. A comment carrying one of them was written in the wrong language.
_SPANISH_MARKERS = re.compile(
    r'\b(el|la|los|las|del|una|unos|unas|por|para|que|con|su|sus|sin|más|'
    r'cuando|porque|esta|este|esto|acá|allá|desde|hasta|pero|aunque|cada|'
    r'como|donde|ya|así|sólo|solo|también|entre|sobre|hacia|según|debe|'
    r'puede|tiene|hay|son|está|están|ser|estar|un|unos|se|al|lo|les|ni|'
    r'muy|sus|nunca|siempre|entonces|además)\b',
    re.IGNORECASE
)
# A comment may quote the Spanish rule it implements; the quote is evidence,
# not prose. Only unquoted Spanish counts.
_QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'|`[^`]*`')
# How many Spanish markers a line needs before it is called Spanish. One is a
# borrowed noun ("la paz", "el alto"); three is a sentence.
_SPANISH_THRESHOLD = 3
_DOCSTRING_THRESHOLD = 4


def _is_spanish(
    text: str,
    threshold: int
) -> bool:
    '''
        Whether a piece of prose reads as Spanish rather than English.

        Args:
            text (str): Comment or docstring body.
            threshold (int): How many markers make it Spanish.

        Returns:
            bool: True when it is Spanish.
    '''
    stripped = _QUOTED.sub(' ', text)
    return len(_SPANISH_MARKERS.findall(stripped)) >= threshold


def check_comment_language(service: Path) -> tuple[bool, str]:
    '''
        Comments AND docstrings in English.

        `CLAUDE.md` §1: the code and its internal documentation are in English,
        strictly; Spanish is for what the user reads. Docstrings count — they
        are the documentation, and scanning only `#` lines let a whole Spanish
        docstring through on 27-09-2026.
    '''
    hits = []
    # Unlike every other check this one looks at EVERY file: the tests, and
    # the boilerplate too. Language is not a property of who owns the file.
    # Skipping the boilerplate is how six Spanish comments landed in
    # `services/utils.py` on 28-09-2026 with the check reporting green.
    for path in sorted(service.rglob('*.py')):
        if '__pycache__' in path.parts:
            continue
        source = path.read_text()
        # Contiguous `#` lines are ONE comment and are judged as one. Judged
        # line by line, a two-line comment in plain Spanish slipped through on
        # 28-09-2026 because neither half reached the threshold on its own —
        # and the green that check produced is what let it ship.
        block, block_line = [], 0
        for number, line in enumerate(source.splitlines() + [''], 1):
            stripped = line.lstrip()
            if stripped.startswith('#'):
                if not block:
                    block_line = number
                # A quote left open runs to the end of the line: the comment is
                # English quoting a Spanish rule across two lines.
                block.append(re.split(r'["\'`]', stripped.lstrip('#'), maxsplit = 1)[0])
                continue
            if block and _is_spanish(' '.join(block), _SPANISH_THRESHOLD):
                hits.append(f'{path.relative_to(service)}:{block_line}')
            block = []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Module, ast.ClassDef,
                                     ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            # A docstring is several sentences, so it needs a higher bar than a
            # one-line comment before a borrowed noun makes it look Spanish.
            if doc and _is_spanish(doc, _DOCSTRING_THRESHOLD):
                hits.append(f'{path.relative_to(service)}:{getattr(node, "lineno", 1)}')
    return not hits, ', '.join(sorted(hits)[:5]) if hits else 'none'


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


# HTTP verbs that change something. What they change has to be auditable:
# who did it, to which row, and what it looked like before.
WRITING_VERBS = ('post', 'put', 'patch', 'delete')

# A POST that only reads is a query: a filter whose criteria do not fit in a
# URL, or a what-if calculation. Auditing those would fill the trail with
# reads, so the convention is that a controller that changes nothing says so
# in its name.
QUERY_PREFIXES = ('get_', 'list_', 'filter_', 'search_', 'preview_')


def _decorator_names(node: ast.AST) -> set[str]:
    '''
        The names of the decorators on a function, however they are written.

        Args:
            node (ast.AST): The function definition.

        Returns:
            set[str]: Decorator names, without their arguments.
    '''
    names = set()
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name):
            names.add(target.id)
        elif isinstance(target, ast.Attribute):
            names.add(target.attr)
    return names


def _audited_controllers(service: Path) -> tuple[set[str], set[str]]:
    '''
        Which controllers carry each decorator.

        Args:
            service (Path): Service directory.

        Returns:
            tuple[set[str], set[str]]: (with handle_service_errors, with audit_event).
    '''
    logged, audited = set(), set()
    for path in (service / 'controllers').glob('*.py'):
        tree = ast.parse(path.read_text(encoding = 'utf-8'))
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            names = _decorator_names(node)
            if 'handle_service_errors' in names:
                logged.add(node.name)
            if 'audit_event' in names:
                audited.add(node.name)
    return logged, audited


def _controllers_by_verb(service: Path) -> dict[str, set[str]]:
    '''
        The controllers each route calls, grouped by HTTP verb.

        Args:
            service (Path): Service directory.

        Returns:
            dict[str, set[str]]: {verb: controller names}.
    '''
    found: dict[str, set[str]] = defaultdict(set)
    for path in (service / 'routes').glob('*.py'):
        tree = ast.parse(path.read_text(encoding = 'utf-8'))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            verbs = {name for name in _decorator_names(node) if name in WRITING_VERBS}
            verbs |= {name for name in _decorator_names(node) if name == 'get'}
            for call in ast.walk(node):
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) \
                        and call.func.id.endswith('_controller'):
                    for verb in verbs:
                        found[verb].add(call.func.id)
    return found


def check_events(service: Path) -> tuple[bool, str]:
    '''
        Every controller reports to EVENTS, and every write is audited.

        AUTH, EVENTS and FILES are the three services every product leans on,
        and the two decorators of `utils.py` are how a service talks to EVENTS:
        `handle_service_errors` sends the usage log, `audit_event` sends the
        audit trail. A service that skips them is invisible: nobody can say who
        cancelled that note or how often a screen is used.

        EVENTS itself is the exception, and the only one: it is the service the
        decorators post TO. Auditing the creation of an audit record would
        write an audit record per audit record, without end.
    '''
    if service.name == 'events':
        return True, 'EVENTS no se audita a sí mismo'
    if not (service / 'controllers').is_dir():
        return True, 'no controllers/'

    logged, audited = _audited_controllers(service)
    by_verb = _controllers_by_verb(service)
    every = {name for names in by_verb.values() for name in names}

    missing_log = sorted(every - logged)
    writing = {name for verb in WRITING_VERBS for name in by_verb.get(verb, ())}
    writing = {name for name in writing if not name.startswith(QUERY_PREFIXES)}
    missing_audit = sorted(writing - audited)

    problems = []
    if missing_log:
        problems.append(f'sin usage_log: {", ".join(missing_log[:4])}'
                        + (f' … +{len(missing_log) - 4}' if len(missing_log) > 4 else ''))
    if missing_audit:
        problems.append(f'sin audit: {", ".join(missing_audit[:4])}'
                        + (f' … +{len(missing_audit) - 4}' if len(missing_audit) > 4 else ''))
    return not problems, '; '.join(problems) if problems else 'none'


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
    ('comment-language', check_comment_language),
    ('cross-duplicates', check_cross_service_duplicates),
    ('direct-s3', check_direct_s3),
    ('events', check_events),
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
