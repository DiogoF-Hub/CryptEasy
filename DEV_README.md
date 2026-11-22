# CryptEasy: developer guide

How to work on CryptEasy day to day. For what the app does, see [README.md](README.md).

## 1. Prerequisites

- [uv](https://docs.astral.sh/uv/). It installs Python 3.13 itself, from `.python-version`.
- GNU Make.
- **Windows:** use Git Bash. Install make with `winget install ezwinports.make` or `choco install make`, or run the uv command behind each target (they are listed in the `Makefile`).

```bash
git clone https://github.com/DiogoF-Hub/CryptEasy.git
cd CryptEasy
make install
```

## 2. uv

uv manages Python, the virtual environment (`.venv`), and dependencies. **Never use `pip` directly.**

| Task | Command |
|---|---|
| Install exactly what `uv.lock` says | `uv sync --locked` (= `make install`) |
| Add a runtime dependency | `uv add flask` |
| Add a dev-only tool | `uv add --dev pytest` (goes into `[dependency-groups] dev`) |
| Remove a dependency | `uv remove flask` |
| Upgrade one locked dependency | `uv lock --upgrade-package flask` |
| Run a command in the project env | `uv run <cmd>`, e.g. `uv run python -m crypteasy` |
| Show or bump the version | `uv version` / `uv version --bump patch` (see section 7) |

- Always commit `pyproject.toml` **and** `uv.lock` together. CI installs with `--locked` and fails if the two disagree.
- Adding a dependency is a team decision. Mention it in the PR description.

## 3. Makefile

Run `make help` to list every target.

| Target | What it does |
|---|---|
| `make install` | Install locked dependencies |
| `make run` | Start the app in its own window (pywebview) |
| `make lint` | Ruff lint + format check, no changes (CI runs this) |
| `make format` | Auto-fix safe lint issues and format the code |
| `make test` | Fast tests, without `@slow` (CI runs this) |
| `make test-core` / `test-keystore` / `test-ui` | Tests for one part of the code |
| `make test-slow` / `make test-all` | Large-file tests only / every test |
| `make build` | Build the one-file executable into `dist/` |
| `make smoke` | Run the built executable without its window (`--no-window`) and check it answers on 127.0.0.1 |
| `make clean` | Remove `build/`, `dist/`, caches |

Extra pytest arguments: `make test ARGS="-x -k header"`.

The CI workflow runs the same uv commands as these targets. If you change a target, change `.github/workflows/ci.yml` in the same PR.

## 4. Linting and formatting

- Tool: [Ruff](https://docs.astral.sh/ruff/), pinned in `pyproject.toml` so everyone gets the same rules.
- Rules (`[tool.ruff.lint]`): pycodestyle (`E`, `W`), pyflakes (`F`), import sorting (`I`), bugbear (`B`), pyupgrade (`UP`), and **bandit security checks (`S`)**. `assert` is allowed in `tests/`.
- Before every push: `make format`, then `make lint`.
- `Resources/` is gitignored, so Ruff skips it.
- Silencing a rule on one line (`# noqa: S603`) needs a short comment explaining why. Never use a bare `# noqa`.

## 5. Tests

- Layout: `tests/core/`, `tests/keystore/`, `tests/ui/`, one per part of the code and `make test-*` target.
- The UI tests run twice: once on the fake backend (`[demo]`) and once on the real `core/` + `keystore/` (`[real]`). CI has no screen, so tests never open the window.
- Mark tests that take minutes or GBs of disk with `@pytest.mark.slow`. Run them before a release with `make test-slow`.
- Tests never touch your real key store. Set `CRYPTEASY_HOME` to `tmp_path`.

Environment variables the app understands:

| Variable | Effect |
|---|---|
| `CRYPTEASY_HOME=<dir>` | Use `<dir>` instead of the per-user data folder (`%APPDATA%\CryptEasy`, `~/.local/share/CryptEasy`) |
| `CRYPTEASY_NO_WINDOW=1` (or `--no-window`) | Start Flask only, no window (used by `make smoke` / CI). `CRYPTEASY_NO_BROWSER=1` still works too |
| `CRYPTEASY_FAKE_BACKEND=1` | Run the interface on the fake backend (demo mode, a "Demo mode" banner shows) |

## 6. Branches and pull requests

- `main` is protected. **Only the repository owner merges into it**, and only through pull requests. Nobody pushes to `main` directly.
- Each member works on their own long-lived branch: `diogo-dev`, `enryou-dev`, `c0mp-dev`, `s11nay-dev`.
- CI runs on every push to a `*-dev` branch and on every PR into `main`.

Daily loop:

1. `git switch <name>-dev`
2. Bring in the latest `main`: `git fetch origin && git merge origin/main`. Resolve any conflicts, then run `make test`.
3. Commit small steps. Before pushing, run `make format && make lint && make test`.
4. `git push`, and check that CI is green on your branch.
5. When a task is finished, open a PR `<name>-dev → main` with `Closes #<issue>` in the description. Someone else in the team reviews it.
6. The owner merges it once CI is green and the review is approved. Then fill in **Actual (h)** on the board.

Notes:

- A PR contains **everything on your branch that isn't in `main` yet**. Open PRs often so they stay small and easy to review.
- The owner merges with **"Create a merge commit"**, not "Squash" or "Rebase". With long-lived branches, a squash or rebase merge puts different commits on `main` than on your branch, so your next `git merge origin/main` runs into conflicts on work that was already merged.
- Work is planned in one-week sprints, one issue per task on the [board](https://github.com/users/DiogoF-Hub/projects/1). Move your card to **In Progress** when you start, it goes to **Done** when the PR closes the issue.

## 7. Versioning and releases

The `version` field in `pyproject.toml` is the single source of truth. Change it only with `uv version` (format: [PEP 440](https://peps.python.org/pep-0440/)).

```bash
uv version --bump patch               # 0.1.0    -> 0.1.1     bug fixes
uv version --bump minor               # 0.1.1    -> 0.2.0     new features
uv version --bump major --bump rc     # 0.2.0    -> 1.0.0rc1  release candidate
uv version --bump stable              # 1.0.0rc1 -> 1.0.0     final
```

To release:

1. Commit the bump on its own (it changes only `pyproject.toml` and `uv.lock`) on your `-dev` branch, and open a PR into `main`.
2. When the owner merges it, CI does the rest (section 8).

Each version can be released once. CI refuses a version whose tag `v<version>` already exists, so bump again instead.

## 8. CI (`.github/workflows/ci.yml`)

| Job | Runs on | When | Does |
|---|---|---|---|
| `lint` | Linux | every PR, every push to `main` or a `*-dev` branch | `ruff check` + `ruff format --check`; problems show as annotations on the PR |
| `test` | Linux + Windows | every PR, every push to `main` or a `*-dev` branch | `pytest -m "not slow"` |
| `build-check` | Ubuntu 22.04 + Windows | every PR, every push to a `*-dev` branch | builds the exe and smoke-tests it, so a packaging problem shows before the release |
| `version` | Linux | push to `main` | Did `version` change? Is it pre-release (`a`/`b`/`rc`/`dev`)? |
| `build` | Ubuntu 22.04 + Windows | version changed, lint + tests green | PyInstaller one-file build, smoke test, package |
| `release` | Linux | after `build` | Creates tag `v<version>` and a GitHub Release with both executables + `SHA256SUMS` |

Notes:

- Only the `release` job can write to the repo (`contents: write`). Everything else is read-only.
- Actions are pinned to full commit SHAs. To update one, take the SHA of the new release tag from the action's own repository.
- The Linux build uses the older Ubuntu 22.04 runner: a PyInstaller binary only runs on systems with the same or newer glibc.
- A run on a `-dev` branch is cancelled when you push again to that branch; runs on `main` never are.
- While a PR is open, a push to its branch runs CI twice (once for the push, once for the PR). That's expected.

## 9. Building locally

```bash
make build    # dist/crypteasy or dist/crypteasy.exe
make smoke
```

PyInstaller cannot cross-compile. A Windows build needs Windows, and a Linux build needs Linux.

On Linux, `make build` also needs the GTK dev packages (pywebview's window uses GTK), on Debian / Ubuntu: `sudo apt install libgirepository1.0-dev libcairo2-dev`. Only the Python side of GTK goes into the binary, GTK and WebKit2GTK come from the user's system.
