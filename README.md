# MaxPkg Packager

`maxpkg-packager.ms` is a drag-and-drop developer tool for building universal
MaxPkg-compatible `.mzp` packages from a product folder.

## Current MVP

- Saves and loads settings from `maxpkg-packager.ini` next to the script.
- Generates a package UUID.
- Validates required metadata, runtime/entry pairing, included files, safe SVG
  icons, hooks, output folder, and relative package paths.
- Generates `manifest.ini`, `manifest.json`, `mzp.run`, and optional
  `maxpkg-button.mcr`.
- Copies selected package files and optional `icons/icon.svg`.
- Builds the final output as `<packageGuid>.mzp`.

The generated package installs into:

```text
(getDir #temp) + "\\maxpkg\\packages\\<packageGuid>\\"
```

It does not install the MaxPkg Toolbar or Runtime. If either global runtime hook
exists, `mzp.run` refreshes it safely after installation.
