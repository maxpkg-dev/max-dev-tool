# MaxPkg Packager - working rules

- **Releases:** follow `.codex/how-to-release.md`: the rules that must never break (paths older copies read from
  `main`), the release flow and the update rehearsal (`maxpkg-src/tools/update_check.py`). Never commit, push, tag or
  publish: the user runs `release.bat`.
- **MAXScript:** `.codex/coding-rules.md`.
- **Layout:** `maxpkg-packager.ms` (the launcher, ASCII + CRLF), `_install.ms` and `_uninstall.ms` stay in the root
  (1.x updates them from there); the application is in `maxpkg-src/` (`python/`, `assets/`, `tools/`); what installed
  copies update from is in `release/` (with `maxpkg-packager-1.x.ms`, the pinned 1.2.1 for 3ds Max older than 2022);
  tests in `tests/`. Keep the root this small.
- **A user's project** gets only `maxpkg-packager.ms` and `max-package/` in its root, nothing else, ever.
- **After every change:** run the tests with the Python of 3ds Max 2027 and 2022, then relaunch the packager in the
  user's 3ds Max: `fileIn @"<repository>\maxpkg-packager.ms"`. Test anything that installs or updates in a separate
  `LOCALAPPDATA`, never in the user's own profile.
