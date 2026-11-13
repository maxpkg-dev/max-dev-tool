# MaxPkg Packager for AI agents

This guide is for AI agents and scripts that package a 3ds Max tool for [maxpkg.dev](https://maxpkg.dev) without
clicking through the packager window. Everything a person can do in the window can be done through
`MaxPkgPackerApi`.

API version: `2.1.0` (packager 2.0.1). Method and option names are those of the MaxScript packager 1.x API, so
existing automation keeps working; what changed is listed at the end.

## Rules for agents

- **The project root stays clean.** It may contain only the user's own files, `maxpkg-packager.ms` and the
  `max-package` folder. Never write other files (notes, JSON, listings, logs) into the project root. Put anything you
  create for packaging inside `max-package/`.
- **Requires 3ds Max 2022 or newer** (Python 3.7+ and Qt are part of 3ds Max). The packaged tool's minimum 3ds Max
  version is also 2022 or newer.
- Run mutations one at a time and read each response before the next dependent call.
- Never change an existing `packageGuid`: it is the package identity on maxpkg.dev.
- Never upload, publish or push anything unless the user asks for it.

## Load the API

Use Max Ultra MCP: list instances, select the intended 3ds Max, then run MaxScript.

**Without the window** (recommended for agents):

```maxscript
global MaxPkgPackagerHeadless = true
fileIn @"C:\Projects\MyTool\maxpkg-packager.ms"
MaxPkgPackagerHeadless = false
MaxPkgPackerApi.ping()
```

**With the window** (the user watches; every API change appears in the window at once):

```maxscript
fileIn @"C:\Projects\MyTool\maxpkg-packager.ms"
MaxPkgPackerApi.ping()
```

The project is the folder that contains `maxpkg-packager.ms`. To work on another folder, call
`MaxPkgPackerApi.openProject @"C:\Projects\OtherTool"`.

If the project has no `maxpkg-packager.ms` yet, copy the official file into its root first:
<https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/maxpkg-packager.ms>. On the first run it installs the
packager into the user profile (`%LOCALAPPDATA%\MaxPkgPackager`); this needs internet once.

> In one Max Ultra MCP call, `fileIn` and the first `MaxPkgPackerApi` call work together. If a call answers
> "Unknown property ... in undefined", run `fileIn` in its own call first.

## Responses

Every method returns one JSON string. Parse the outer MCP result, then this inner string:

```json
{"ok": true, "operation": "files.add", "data": {}, "warnings": [], "errors": []}
```

An error item is `{"code": "...", "message": "..."}`. Stop the dependent workflow when `ok` is `false`; fix the
arguments or the project and retry. Codes: `NO_PROJECT`, `UNKNOWN_OPTION`, `INVALID_VALUE`, `INVALID_INDEX`,
`FILE_NOT_FOUND`, `FOLDER_NOT_FOUND`, `OUTSIDE_PROJECT`, `FILE_EXCLUDED`, `FILE_NOT_IN_PACKAGE`, `FILE_IN_USE`,
`GUID_EXISTS`, `DUPLICATE`, `VALIDATION`, `BUILD_FAILED`, `INTERNAL_ERROR`.

Collection indexes are **1-based**. Every mutation saves the project at once.

## Methods

| Area | Methods |
| --- | --- |
| Discovery | `ping()`, `getSchema()`, `getState()`, `openProject folder` |
| Persistence | `save()`, `reload()` (re-reads the files; unsaved window edits are discarded) |
| Options | `getOption name`, `setOption name value`, `setOptions pairs` |
| Identity | `generateGuid replaceExisting:false` |
| Files | `listFiles()`, `addFile path`, `addFolder path`, `removeFile indexOrRelativePath force:false`, `clearFiles force:false`, `setEntry relativePath [compileEntry]` |
| Changelog | `listChangelog()`, `addChangelog type text`, `updateChangelog index type text`, `removeChangelog index`, `clearChangelog()` |
| Build path remap | `listBuildPathRules()`, `addBuildPathRule source target`, `updateBuildPathRule index source target`, `removeBuildPathRule index`, `clearBuildPathRules()` |
| Extra macros | `listExtraMacros()`, `addExtraMacro relativePath buttonName compileScript:false showInQuadMenu:false`, `updateExtraMacro index ...`, `removeExtraMacro index`, `clearExtraMacros()` |
| Result | `validate()`, `build()`, `getLog()`, `clearLogEntries()` |

`setOptions` accepts a MaxScript array of pairs, a Python dict or a JSON object string. It checks every value before
applying any, applies `version` first (each version has its own date, channel, minimum 3ds Max and changelog) and
saves once.

### Options

| Option | Value |
| --- | --- |
| `packageName`, `buttonName` | A-Z, a-z, 0-9, space, `-`, `_` |
| `packageGuid` | UUID or empty; prefer `generateGuid()` |
| `description` | Up to 500 characters |
| `developerName` | Text |
| `license` | `Free`, `Shareware`, `Commercial`, `Open source`, `Trial` |
| `licenseUrl`, `documentationUrl`, `homepageUrl`, `purchaseUrl` | Optional `http(s)://` web addresses with a real site name; `example.com` becomes `https://example.com` |
| `purchaseButtonLabel` | `Buy`, `Purchase`, `Get license`, `Donate`, `Support`, `Sponsor` |
| `createMacroButton`, `showInToolbar` | `true` / `false` (new project: `true`) |
| `compileEntry` | `true` / `false` (new project: `true`): compile the `.ms` entry into `.mse` while building |
| `customInstallScript`, `customUninstallScript` | An existing `.ms` inside the project, or empty |
| `outputFolder` | Folder; default `max-package\dist` |
| `svgIconFile` | A square, safe SVG; it is copied to `max-package\icon.svg` |
| `entryFile` | A file already added, `.ms`, `.mse` or `.py`; `setEntry` does the same |
| `version` | `major.minor.patch`, each 0-999 |
| `releaseChannel` | `stable`, `beta`, `alpha`. Only `stable` appears in the MaxPkg Manager catalog; `beta` / `alpha` are only on maxpkg.dev and not recommended there (a validation warning). Use `stable` unless the user asks for a test release |
| `releaseDate` | `YYYY-MM-DD` |
| `min3dsMax` | `2022` up to next year |

Changelog types: `Added`, `Fixed`, `Changed`, `Removed`, `Improved`.

## Complete example

```maxscript
global MaxPkgPackagerHeadless = true
fileIn @"C:\Projects\MyTool\maxpkg-packager.ms"
MaxPkgPackagerHeadless = false

MaxPkgPackerApi.setOptions #(
    #("packageName", "My Tool"),
    #("buttonName", "My Tool"),
    #("description", "Automates the current workflow."),
    #("developerName", "Studio Name"),
    #("license", "Commercial"),
    #("version", "1.2.0"),
    #("releaseChannel", "stable"),
    #("min3dsMax", "2022"),
    #("svgIconFile", @"C:\Projects\MyTool\icon.svg")
)
MaxPkgPackerApi.generateGuid()          -- only for a new package
MaxPkgPackerApi.addFile @"C:\Projects\MyTool\main.ms"
MaxPkgPackerApi.addFolder @"C:\Projects\MyTool\resources"
MaxPkgPackerApi.setEntry "main.ms" true
MaxPkgPackerApi.addChangelog "Added" "First release"
MaxPkgPackerApi.validate()
MaxPkgPackerApi.build()
```

Every package gets the MaxPkg install and uninstall windows (`_install.ms`, `_uninstall.ms`). They ship with the
packager, which keeps a copy in `max-package`; there is nothing to add, download or edit. For project-specific work
at install or removal, set `customInstallScript` / `customUninstallScript`.

Require `ok == true`, `data.exists == true` and an existing `data.outputFile` from `build()`. The archive is
`max-package\dist\<slug>@<version>@<guid>.mzp`. Test it in 3ds Max before the user uploads it on maxpkg.dev.

## Recommended workflow

1. Select the 3ds Max instance; load the API (headless).
2. `ping()`, `getSchema()`, `getState()`: read what is already configured.
3. Set the options (one `setOptions`), keep an existing GUID, generate one only for a new package.
4. Add every runtime file the tool needs (`addFile` / `addFolder`); not tests, sources of other tools, backups or
   old installers.
5. `setEntry` to the script the button runs.
6. Write the changelog of this version.
7. `validate()`: fix every error (each names the field), repeat until `ok`.
8. `build()`, then `getState()` for the final state.

## Changes from the 1.x API

- The project files live in `max-package/` (`project.ini`, `changelog.ini`, `icon.svg`, `_install.ms`,
  `_uninstall.ms` and `dist/`). Files of a 1.x project move there automatically on first open.
- `openProject`, `setEntry`, `getOption` and the headless mode are new.
- `_install.ms` and `_uninstall.ms` are part of every package (API 2.1.0). `addStandardHook` is no longer needed; it
  is kept for older automation and downloads nothing. `standardHooks` in `getState()` is always `true` for both.
- `validate()` reports problems as `errors` with `ok: false`; each has `field` and `where` (tab -> field).
- `min3dsMax` starts at 2022.
