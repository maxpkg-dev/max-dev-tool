# How To Release MaxPkg Packager

This file describes how Codex should prepare a new release of `maxpkg-packager.ms`.

Important: never commit, never push, and never create a git tag for this release process. The user checks the result and handles git manually.

## Release Flow

1. Ask the user which version bump is needed:
   - `patch`
   - `minor`
   - `major`

   Most releases will be `patch`, but always ask first.

2. Read the current version from the script header:

   ```ini
   [INFO]
   VERSION=1.0.3
   ```

3. Increase the version according to the selected bump.

4. Update `VERSION` in `[INFO]`.

5. Complete the API synchronization check described below.

6. Add a release notes section before `[SCRIPT]`.

7. Tell the user exactly what was changed, including whether the public API changed.

8. Stop. Do not commit. Do not push.

## API Synchronization Check

Every release must review whether its changes affect the public `MaxPkgPackerApi` contract. Do not prepare a release until the implementation, schema, documentation, and tests agree.

An API update is required when a change adds, removes, renames, validates, persists, or changes the behavior of:

- a package option or its allowed values;
- Files List operations;
- changelog operations or changelog types;
- Build Path Rules;
- Extra Macros;
- validation, build, log, save, reload, or GUID behavior;
- JSON response fields, operation names, error codes, index rules, or safety behavior;
- any public method exposed by `MaxPkgPackerApi`.

When the API is affected, update all applicable items:

1. The `MaxPkgPackerApi` implementation in `maxpkg-packager.ms`.
2. `apiSchemaJson()`, including method and writable-option discovery.
3. The API version when compatibility changes:
   - keep the version for documentation-only corrections;
   - increase the minor version for backward-compatible additions;
   - increase the major version for breaking changes.
4. `maxpkg-api.md`, including signatures, constraints, response examples, error behavior, and the recommended Max Ultra MCP workflow.
5. `tests/maxpkg-api-smoke.ms` so the changed behavior is exercised.
6. The API link or summary in `README.md` when its location, purpose, or entry workflow changes.

Run `tests/maxpkg-api-smoke.ms` in an already-open 3ds Max instance through Max Ultra MCP. Require the exact result:

```text
MAXPKG_API_SMOKE_OK
```

For build-related changes, also verify that `build()` returns `ok: true`, `data.exists: true`, and an existing `.mzp` output path.

If the release does not affect the API, explicitly record in the release review that the API was checked and no API or documentation update was required.

## Version Bump Rules

Versions use this format:

```text
major.minor.patch
```

Each part goes from `0` to `9`. If a part would go above `9`, increase the previous part and reset the following parts.

Examples:

```text
1.0.3 + patch = 1.0.4
1.0.9 + patch = 1.1.0
1.9.9 + patch = 2.0.0
2.4.0 + minor = 2.5.0
2.9.0 + minor = 3.0.0
2.3.4 + major = 3.0.0
```

## Release Notes Format

Release notes must be inserted before `[SCRIPT]`.

Use a section named with the new version:

```ini
[1.0.3]
+ Added: Extra macros for additional package buttons=
+ Added: Extra macro .ms to .mse compile option=
* Changed: Extra macros respect Build Path Remap during build and install=
* Changed: Runtime install notification now supports newInstallation with packageInstalled fallback=
```

Supported release note prefixes:

```text
+ Added:
- Fixed:
* Changed:
- Deleted:
** Improved:
```

Each release note line must end with `=`, because the script reads these sections with INI functions.

## Final Response

After updating the file, respond with:

- the old version;
- the new version;
- the release notes that were added;
- a reminder that no commit or push was performed.

The user will review, commit, and push manually.
