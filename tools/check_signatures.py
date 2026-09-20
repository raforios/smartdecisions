'''
    Function signature format check — and fix.

    A signature with more than one parameter is written one parameter per
    line, indented four spaces, with the closing parenthesis and the return
    annotation on their own line — whatever its length:

        async def store_companion(
            dynamodb_resource: ServiceResource,
            dataset: Dict[str, Any],
            result: Any
        ) -> BaseModel:

    Hanging-indent signatures ("def f(a: int,\\n          b: int) -> X:") are
    reported, and rewritten with --fix. The shared boilerplate follows the
    same rule; only third-party code is skipped.

    Usage:
        python tools/check_signatures.py services/ingest            # report
        python tools/check_signatures.py services/ingest --fix      # rewrite
'''
import ast
import sys
from pathlib import Path

SKIP_DIRS = {'.venv', 'node_modules', '__pycache__'}


def _signature_span(node: ast.AST, lines: list[str]) -> tuple[int, int]:
    '''
        Lines (0-based, inclusive) the signature occupies: from `def` to the
        line holding the colon that opens the body.

        Args:
            node (ast.AST): Function node.
            lines (list[str]): File lines.

        Returns:
            tuple[int, int]: First and last line of the signature.
    '''
    start = node.lineno - 1
    first_body = node.body[0].lineno - 1
    end = start
    for index in range(start, first_body):
        stripped = lines[index].split('#', 1)[0].rstrip()
        if stripped.endswith(':'):
            end = index
            break
    return start, end


def _needs_fix(lines: list[str], start: int, end: int) -> bool:
    '''
        A multi-line signature is fine only if every parameter sits on its
        own line at a four-space deeper indent and the closing parenthesis
        opens the last line.

        Args:
            lines (list[str]): File lines.
            start (int): First signature line.
            end (int): Last signature line.

        Returns:
            bool: True when the signature breaks the format.
    '''
    if end == start:
        # One line is fine for a single parameter; two or more go vertical.
        code = lines[start].split('#', 1)[0]
        params = code.split('(', 1)[1]
        return len(_split_top_level(_split_params(params)[0], ',')) > 1
    header = lines[start]
    if not header.split('#', 1)[0].rstrip().endswith('('):
        return True
    indent = len(header) - len(header.lstrip()) + 4
    depth = 0
    for index in range(start + 1, end):
        code = lines[index].split('#', 1)[0].rstrip()
        # A parameter whose default spans lines (a Query(...) with its
        # description) is one parameter: its continuation sits deeper.
        if depth == 0 and len(code) - len(code.lstrip()) != indent:
            return True
        depth += code.count('(') + code.count('[') - code.count(')') - code.count(']')
        if depth == 0 and not code.endswith(',') and index != end - 1:
            return True
    return not lines[end].lstrip().startswith(')')


def _strip_comments(lines: list[str]) -> tuple[str, dict[int, str]]:
    '''
        Separates the code of a signature from the comments inside it, which
        travel with the parameter they follow.

        Args:
            lines (list[str]): Signature lines.

        Returns:
            tuple[str, dict[int, str]]: Code as one string, and the comment
                found on each (0-based) signature line.
    '''
    comments: dict[int, str] = {}
    stripped = []
    for index, line in enumerate(lines):
        code, _, comment = line.partition('#')
        if comment and code.strip():
            comments[index] = comment.strip()
        stripped.append(code if comment else line)
    return '\n'.join(stripped), comments


def _split_top_level(text: str, separator: str) -> list[str]:
    '''
        Splits on a separator, ignoring the ones nested inside brackets.

        Args:
            text (str): Text to split.
            separator (str): Single character to split on.

        Returns:
            list[str]: The pieces, stripped and non-empty.
    '''
    pieces, depth, current = [], 0, ''
    for char in text:
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth -= 1
        if char == separator and depth == 0:
            pieces.append(current)
            current = ''
        else:
            current += char
    pieces.append(current)
    return [' '.join(piece.split()) for piece in pieces if piece.strip()]


def _split_params(rest: str) -> tuple[str, str]:
    '''
        Cuts what follows the opening parenthesis of a signature into the
        parameter list and the tail (return annotation and colon).

        Args:
            rest (str): Signature text after the first '('.

        Returns:
            tuple[str, str]: Parameters and tail.
    '''
    depth = 0
    for position, char in enumerate(rest):
        depth += char in '([{'
        depth -= char in ')]}'
        if depth < 0:
            return rest[:position], rest[position + 1:]
    return rest, ''


def _rebuild(lines: list[str], start: int, end: int) -> list[str]:
    '''
        Rewrites one signature in the canonical layout, keeping comments and
        decorators untouched.

        Args:
            lines (list[str]): File lines.
            start (int): First signature line.
            end (int): Last signature line.

        Returns:
            list[str]: The replacement lines.
    '''
    text, comments = _strip_comments(lines[start:end + 1])
    base_indent = lines[start][:len(lines[start]) - len(lines[start].lstrip())]
    head, rest = text.split('(', 1)
    params_text, tail = _split_params(rest)
    body = [f'{base_indent}    {param},' for param in _split_top_level(params_text, ',')]
    if body:
        body[-1] = body[-1][:-1]
    header, body = _place_comments(f'{head.rstrip()}(', body, comments, end == start)
    tail = ' '.join(tail.split())
    closing = f'{base_indent}) {tail}' if tail.startswith('->') else f'{base_indent}){tail}'
    return [header] + body + [closing]


def _place_comments(
    header: str,
    body: list[str],
    comments: dict[int, str],
    was_one_line: bool
) -> tuple[str, list[str]]:
    '''
        Puts the comments of the old signature back where pylint reads them.

        A comment on a one-line signature covered the whole def: an
        unused-argument goes to every parameter, anything else to the header,
        where the function-level messages are reported. In a multi-line one
        the comment belongs to the parameter declared on its line.

        Args:
            header (str): The `def name(` line.
            body (list[str]): One parameter per line.
            comments (dict[int, str]): Comment per old signature line.
            was_one_line (bool): Whether the old signature had one line.

        Returns:
            tuple[str, list[str]]: Header and body with the comments placed.
    '''
    for index, comment in comments.items():
        if not body:
            continue
        if was_one_line and 'unused-argument' in comment:
            body = [f'{line} # {comment}' for line in body]
        elif was_one_line:
            header = f'{header} # {comment}'
        else:
            position = min(max(index - 1, 0), len(body) - 1)
            body[position] = f'{body[position]} # {comment}'
    return header, body


def check(path: Path, fix: bool) -> list[tuple[int, str]]:
    '''
        Reports (and optionally fixes) the offending signatures of one file.

        Args:
            path (Path): Python file.
            fix (bool): Rewrite in place.

        Returns:
            list[tuple[int, str]]: (line, function name) of each finding.
    '''
    source = path.read_text()
    lines = source.split('\n')
    tree = ast.parse(source)
    findings = []
    for node in sorted(
        (n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
        key = lambda n: -n.lineno
    ):
        start, end = _signature_span(node, lines)
        if _needs_fix(lines, start, end):
            findings.append((start + 1, node.name))
            if fix:
                lines[start:end + 1] = _rebuild(lines, start, end)
    if fix and findings:
        path.write_text('\n'.join(lines))
    return sorted(findings)


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 1 when findings remain unfixed, 0 otherwise.
    '''
    fix = '--fix' in sys.argv
    roots = [Path(arg) for arg in sys.argv[1:] if not arg.startswith('--')]
    total = 0
    for root in roots:
        paths = [root] if root.is_file() else sorted(root.rglob('*.py'))
        for path in paths:
            if SKIP_DIRS & set(path.parts):
                continue
            for line, name in check(path, fix):
                total += 1
                print(f'{path}:{line}: {name}' + (' (fixed)' if fix else ''))
    print(f'{total} signature(s) ' + ('rewritten' if fix else 'out of format'))
    return 0 if fix or total == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
