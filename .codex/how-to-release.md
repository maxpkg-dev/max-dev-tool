# How To Release MaxPkg Packager

How an agent prepares a release of MaxPkg Packager 2.x, and how the user publishes it.

Important: an agent never commits, pushes, tags or publishes. It prepares and checks; the user runs `release.bat`
(or git and gh by hand).

## Rules that must never break

Users update from what is on `main`. Older copies look for fixed paths, so:

- `maxpkg-packager.ms`, `_install.ms` and `_uninstall.ms` stay in the repository root. Version 1.x downloads exactly
  these three when it updates itself (it then runs the new `maxpkg-packager.ms`, and saves it as UTF-16).
- These two files are also the ones every package is built with. `release.py` packs them into the application
  archive as `assets/hooks/`; an installed copy reads them from there (`core/hooks.py`), copies them into a project's
  `max-package\` when it opens the project, and puts them into every `.mzp`. Change them only in the root.
- `release/update.json` stays where it is: every installed 2.x copy checks it (`UPDATE_URL`) and the launcher reads it
  on a first install.
- What `main` serves is stored byte for byte: `.gitattributes` keeps `-text` for the launcher, the two hooks and
  `release/**`. `update.json` holds their SHA-256; with `core.autocrlf` Git would commit them with LF instead of the
  hashed CRLF and every update would be refused. `release.py` stops when a rule is missing. Before pushing, the files
  in the index must hash to the values in `update.json` (`git show :maxpkg-packager.ms | sha256sum`).
- `release/maxpkg-packager-1.x.ms` stays where it is and keeps `UPDATE=` pointing to itself: it is version 1.2.1 for
  3ds Max older than 2022 (a copy of commit `3727cfd`, UTF-16). The launcher and the installer offer it there, and
  because it only updates to itself it never turns into version 2 again. `release.py` refuses to build without it.
- The launcher keeps its `[INFO]` header (`NAME`, `VERSION`, `UPDATE=...main/maxpkg-packager.ms`) and its notes
  sections with `=` at the end of every line: 1.x reads them with INI functions. It stays ASCII with CRLF.
- The launcher keeps working with everything already installed: `current.json` (`version`, `dir`, `sha256`,
  `previous`, `previousDir`), `v<version>\python\bootstrap.py`, the environment variables `MAXPKG_PACKAGER_PROJECT`,
  `MAXPKG_PACKAGER_HEADLESS`, `MAXPKG_PACKAGER_SETUP`, and the MAXScript globals `MaxPkgPackerApi`,
  `MaxPkgPackagerHeadless`, `MaxPkgPackagerSetup`.
- A project's files are only ever read from `max-package\` (and moved there from the 1.x names). Nothing new may
  appear in a project's root besides `maxpkg-packager.ms` and `max-package\`.
- The code runs on Python 3.7 / PySide2 (3ds Max 2022) and Python 3.13 / PySide6 (3ds Max 2027). Older 3ds Max is
  caught before any Python runs, in the launcher and in the installer's `install.ms` (both check
  `(maxVersion())[1] < 24000`), and offered version 1.2.1 instead.
- The installer asset is always named `MaxPkgPackager.mzp` (the README links `releases/latest/download/` to it).

## Release flow (agent)

1. Ask the user which bump is needed: `patch`, `minor` or `major` (usually `patch`, but always ask).
2. Read the current version from `maxpkg-src/python/maxpkgpackager/__init__.py` (`__version__`). It must equal
   `VERSION` in the `[INFO]` header of `maxpkg-packager.ms`.
3. Raise both to the new version (`major.minor.patch`, each part 0-999; a higher part resets the lower ones).
4. Add a section for the new version to the launcher header, before `[SCRIPT]`:

   ```ini
   [2.0.1]
   + Added: Short user-facing note=
   - Fixed: Short user-facing note=
   * Changed: Short user-facing note=
   ** Improved: Short user-facing note=
   ```

   Users of 1.x see these notes when they update; users of 2.x in the update pill.
5. Complete the API check below.
6. Run the tests with the Python of 3ds Max 2027 and 2022 (all must pass):

   ```bash
   "C:\Program Files\Autodesk\3ds Max 2027\Python\python.exe" -I -m unittest discover -s tests -p "test_*.py"
   "C:\Program Files\Autodesk\3ds Max 2022\Python37\python.exe" -I -m unittest discover -s tests -p "test_*.py"
   ```

7. Run `python maxpkg-src/tools/release.py` (without `--publish`). It checks the launcher (ASCII, CRLF, version,
   notes) and writes:
   - `release/maxpkg-packager-app-<version>.zip` and `release/update.json`: what installed copies update from.
     Committed.
   - `release/MaxPkgPackager.mzp`: the installer people download, also what testers get. Attached to the GitHub
     release, not committed.
   - `release/release-notes.md`: the text of the GitHub release. Not committed.
8. Do the update rehearsal below in 3ds Max 2022 and 2027 (through Max Ultra MCP when it is available). Never in the
   user's own profile: always set `LOCALAPPDATA` to the rehearsal profile first, and set it back afterwards.
   Also open the packager once at interface size 125 % (a test profile whose `MaxPkgPackager\settings.json` has
   `"ui_scale": "1.25"`): at 100 % the font code is skipped, so a font bug only shows on scaled screens. Open the
   Logs window, a menu and the log panel, and switch the theme once.
9. Tell the user the old and new version, the notes, whether the API changed, what the rehearsal showed, and that
   nothing was committed; then that `release.bat` publishes it.

## Update rehearsal

`python maxpkg-src/tools/update_check.py` copies what `main` will serve to a local server (only the addresses
differ), makes a project of 1.2.1 that updates from it and an empty profile, prints the MAXScript to run and serves
until Ctrl+C. In 3ds Max, with `LOCALAPPDATA` set to the rehearsal profile:

1. 1.x to the new version: `fileIn` the 1.x project's `maxpkg-packager.ms`. 1.x opens, downloads
   `maxpkg-packager.ms`, `_install.ms`, `_uninstall.ms` (see the server's log) and shows "MaxPkg Packer Updated".
   Press Restart (or `fileIn` the same file). Expected: the 1.x window closes; the server serves
   `release/update.json` and the archive; the packager opens on that project with its data ("Bitmap Collector",
   1 file, entry `test.ms`, 10 changelog items); the project root holds only `max-package`, `maxpkg-packager.ms` and
   `test.ms`; `max-package\_install.ms` and `_uninstall.ms` are byte for byte the ones in the repository root.
2. Installer: `fileIn` `release/MaxPkgPackager.mzp`. Expected: the setup window; Install into the rehearsal's
   `scratch` folder puts only `maxpkg-packager.ms` there; Open the packager opens it there, and `max-package`
   appears with `_install.ms` and `_uninstall.ms`.
3. A 2.x copy updates through `core/updater.py` (covered by `UpdaterTests`) and the launcher's offline install (the
   installer step above).
4. 3ds Max older than 2022, when the launcher, `install.ms` or the 1.x copy changed: with no old 3ds Max at hand, use
   copies of the served launcher and of `install.ms` with `local maxRelease = 22000`, the question answered (`true`)
   and `getSavePath` replaced by a scratch folder. Expected: the project gets `maxpkg-packager.ms` version 1.2.1 whose
   `UPDATE` is `release/maxpkg-packager-1.x.ms`; 1.x opens, checks that address on start and stays 1.2.1; from the
   installer only one question is asked.

## Publishing (the user)

Double-click `release.bat` on `main` (merge the work branch into `main` first). It runs the tests, builds `release/`
and the installer, shows what would be committed and asks. After "y" it commits everything, pushes `main` and creates
the GitHub release `v<version>` with `release/MaxPkgPackager.mzp` and `release/release-notes.md` (gh, signed in). It
stops without asking when the branch is not `main` or the version is already published.

By hand: commit and push `main`, then

```bash
gh release create v<version> release/MaxPkgPackager.mzp --target main --title "MaxPkg Packager <version>" --notes-file release/release-notes.md
```

## API check

`maxpkg-src/python/maxpkgpackager/api.py` is the public contract for AI agents (`MaxPkgPackerApi`). When a release adds,
removes, renames or changes an option, method, response field, error code or validation rule:

1. Update `api.py` (including `getSchema()`); raise `API_VERSION` (minor for additions, major for breaking changes).
2. Update `docs/ai-agents.md`.
3. Update `tests/test_api.py` so the change is exercised.

If the release does not touch the API, say that the API was checked and needed no change.
