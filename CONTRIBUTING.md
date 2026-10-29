# How changes get into master

`master` is what everyone builds from, so nothing reaches it except through a pull request.
GitHub enforces this for everyone, the maintainer included: no direct pushes, no force pushes,
the branch can't be deleted, and a pull request merges only once the `audit` check passes, the
branch is up to date and every review conversation is resolved. GitHub doesn't require an
approving review; reviewing every pull request (CodeRabbit's, below) is this project's rule.

## The process

1. **Branch from `master`**, one branch per piece of work, named for it (`linux-build`,
   `menu-fade-blink`). Contributors without write access fork the repository and branch there.
2. **Commit on the branch.** Keep commits focused, with messages that say what changed and why.
   Never commit game material: no game files, executables, archives, generated translations of the
   game's code, logs or captures (see [Legal](README.md#legal)). Run `python -I tools/audit_repo.py`
   before pushing.
3. **Open a pull request into `master`.** Its description says what changed, what was built
   (Windows or Linux; an SDK patch in `tools/patches` means rebuilding the SDK with
   `tools/setup.ps1`), and what was tested in play and what wasn't.
4. **Before it can merge:**
   - the `audit` check passes (`.github/workflows/audit.yml`). It runs the same script over
     every commit (`--history`), so a file added and then deleted on a branch still fails it;
   - the branch is up to date with `master`;
   - every review conversation is resolved. CodeRabbit reviews each pull request. Fix what holds
     up; answer what doesn't with the reason; then resolve the thread.
5. **Merge with a merge commit** (the "Create a merge commit" button), so a pull request's
   history stays together in `master`.

## Releases

Releases are tagged on `master` once the pull requests that make them are merged. **They are
source only:** never attach builds, game files or private test packages. Players build from their
own disc ([docs/SETUP.md](docs/SETUP.md)).
