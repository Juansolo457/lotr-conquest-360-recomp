"""Tests for tools/audit_repo.py, run in throwaway git repositories (CI runs them too).

    python -I tools/test_audit_repo.py

Each case builds a small history in a temporary folder and runs the audit there, by its path,
the way CI does.
"""
import os
import subprocess
import sys
import tempfile

AUDIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'audit_repo.py')


def git(repo, *args):
    subprocess.run(['git', '-c', 'user.name=test', '-c', 'user.email=test@localhost',
                    '-c', 'commit.gpgsign=false', *args],
                   cwd=repo, check=True, capture_output=True)


def write(repo, path, data):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, 'wb') as f:
        f.write(data)


def audit(repo, *args):
    run = subprocess.run([sys.executable, '-I', AUDIT, *args], cwd=repo, capture_output=True,
                         text=True)
    return run.returncode, run.stdout


def case_shared_blob_in_history():
    """One blob under an allowed path and a prohibited one, the prohibited copy since deleted:
    --history must still fail on it."""
    with tempfile.TemporaryDirectory() as repo:
        git(repo, 'init', '-q')
        same = b'the same bytes under two names\n'
        write(repo, 'docs/notes.txt', same)
        write(repo, 'private/notes.txt', same)
        git(repo, 'add', '-A')
        git(repo, 'commit', '-q', '-m', 'both')
        git(repo, 'rm', '-q', '--cached', 'private/notes.txt')
        git(repo, 'commit', '-q', '-m', 'drop the private copy')
        code, out = audit(repo)
        assert code == 0, f'index audit should pass once the copy is gone:\n{out}'
        code, out = audit(repo, '--history')
        assert code == 1 and 'private/notes.txt' in out, f'history audit missed it:\n{out}'


def add_symlink(repo, path, target):
    """Stage a symlink without creating one on disk (Windows needs a privilege for that)."""
    blob = subprocess.run(['git', 'hash-object', '-w', '--stdin'], cwd=repo, input=target.encode(),
                          check=True, capture_output=True).stdout.decode().strip()
    git(repo, 'update-index', '--add', '--cacheinfo', f'120000,{blob},{path}')


def case_removed_symlink_in_history():
    """A symlink, since deleted: --history must flag it by its mode (120000)."""
    with tempfile.TemporaryDirectory() as repo:
        git(repo, 'init', '-q')
        add_symlink(repo, 'docs/link', 'private/game.xex')
        git(repo, 'commit', '-q', '-m', 'add a symlink')
        git(repo, 'rm', '-q', '--cached', 'docs/link')
        git(repo, 'commit', '-q', '-m', 'drop it')
        code, out = audit(repo, '--history')
        assert code == 1 and 'symlink' in out, f'history audit missed the symlink:\n{out}'


def case_symlink_at_exempt_path():
    """The scaffolding exemption covers that file's contents, not a symlink in its place."""
    with tempfile.TemporaryDirectory() as repo:
        git(repo, 'init', '-q')
        add_symlink(repo, 'port/generated/rexglue.cmake', '../../private/lotrc.bin')
        git(repo, 'commit', '-q', '-m', 'a symlink at the exempt path')
        code, out = audit(repo)
        assert code == 1 and 'symlink' in out, f'the exemption hid a symlink:\n{out}'


def case_clean_history():
    with tempfile.TemporaryDirectory() as repo:
        git(repo, 'init', '-q')
        write(repo, 'docs/notes.txt', b'nothing from the game\n')
        git(repo, 'add', '-A')
        git(repo, 'commit', '-q', '-m', 'clean')
        code, out = audit(repo, '--history')
        assert code == 0, f'a clean history should pass:\n{out}'


def main():
    cases = [case_shared_blob_in_history, case_removed_symlink_in_history,
             case_symlink_at_exempt_path, case_clean_history]
    for case in cases:
        case()
        print(f'ok  {case.__name__}')
    print(f'test_audit_repo: {len(cases)} passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
