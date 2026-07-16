# MaxPkg Packager

`maxpkg-packager.ms` is a drag-and-drop developer tool for building universal
MaxPkg-compatible `.mzp` packages from a product folder.

## Current MVP

- Saves and loads settings from `maxpkg-packager.ini` next to the script.
- Generates a package UUID.
- Validates required metadata, runtime/entry pairing, included files, safe SVG
  icons, hooks, output folder, and relative package paths.
- Generates `manifest.ini`, `manifest.json`, `mzp.run`, and `mzp.run.ms`.
- Copies selected package files and optional `icons/icon.svg`.
- When `Create 3dsMax Macro Button` is enabled, `mzp.run.ms` generates the
  macro button in the current 3ds Max `getDir #userMacros` folder and loads it.
- Installs the optional SVG icon into the current 3ds Max `getDir #userIcons`
  folder as `<packageGuid>.svg` before loading the generated macro button.
- Builds the final output as `<packageGuid>.mzp`.

The generated package installs into:

```text
$temp\<packageGuid>\
```

`mzp.run` is generated as a native MZP command file. It extracts the package and
runs `mzp.run.ms`. The entry script installs the optional icon, generates and
loads the macro button when requested by `manifest.ini`, then runs root
`install.ms` when it exists. Runtime setup belongs in the package's own
`install.ms`.
