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

5. Add a release notes section before `[SCRIPT]`.

6. Tell the user exactly what was changed.

7. Stop. Do not commit. Do not push.

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
