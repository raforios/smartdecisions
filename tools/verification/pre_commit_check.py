'''
    The gate a commit goes through: `verify_service.py` over every own service
    the staged files touch, and over `tools/` when it is touched too.

    Run by the PreToolUse hook on `git commit` (`.claude/settings.json`). It
    exits 2 when a check fails, which blocks the commit and hands the report
    back, so a red service can no longer be committed because nobody ran the
    verification by hand (Rafael, 4-nov-2026).

    Usage:
        python tools/verification/pre_commit_check.py
'''
import subprocess
import sys
from pathlib import Path

from verify_checks import PRODUCT_SERVICES

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT.parent / '.venv' / 'bin' / 'python'
VERIFY = ROOT / 'tools' / 'verification' / 'verify_service.py'


def staged_targets() -> list[str]:
    '''
        The verify_service arguments the staged files call for.

        Returns:
            list[str]: `services/<name>` per touched own service, and `--tools`
                when `tools/` is touched.
    '''
    names = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd = ROOT,
                           capture_output = True, text = True, check = True).stdout.split()
    targets = sorted({f'services/{parts[1]}' for parts in (Path(name).parts for name in names)
                      if len(parts) > 2 and parts[0] == 'services'
                      and parts[1] in PRODUCT_SERVICES})
    if any(name.startswith('tools/') and name.endswith('.py') for name in names):
        targets.append('--tools')
    return targets


def main() -> int:
    '''
        Verifies what the commit touches.

        Returns:
            int: 0 when everything passed or nothing needs it; 2 to block.
    '''
    failed = []
    for target in staged_targets():
        result = subprocess.run([str(PYTHON), str(VERIFY), target], cwd = ROOT,
                                capture_output = True, text = True, check = False)
        if result.returncode != 0:
            failed.append(f'{target}\n{result.stdout[-2000:]}')
    if failed:
        print('Commit blocked: verify_service failed.\n\n' + '\n\n'.join(failed), file = sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
