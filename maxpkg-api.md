# MaxPkg Automation API

MaxPkg Packager exposes a public MaxScript object named `MaxPkgPackerApi`. It is intended for AI agents and automation clients that control an already-open 3ds Max instance through Max Ultra MCP.

API version: `1.0.0`.

The API can read and edit every saved packager option, manage package files, changelog entries, build-path rules and extra macros, validate the package, and build the final `.mzp`.

## Load and connect

1. In Max Ultra MCP, list live 3ds Max instances and explicitly select one if more than one is connected.
2. Run the project's `maxpkg-packager.ms` with `max_run_script_file`.
3. Call `MaxPkgPackerApi.ping()` with `max_run_script`.
4. Parse the returned MaxScript string as JSON.

Example MaxScript:

```maxscript
MaxPkgPackerApi.ping()
```

Successful response:

```json
{
  "ok": true,
  "operation": "api.ping",
  "data": {
    "apiVersion": "1.0.0",
    "packagerVersion": "1.2.0",
    "projectRoot": "C:\\Projects\\MyTool\"
  },
  "warnings": [],
  "errors": []
}
```

The MCP result contains this JSON as the string returned by 3ds Max. Always parse that inner string before inspecting `ok`, `data`, or `errors`.

## Agent safety rules

- Load the packager copy located in the target project root. Its folder defines the project boundary and the locations of `maxpkg-packager.ini`, `maxpkg-changelog.ini`, and `maxpkg-icon.svg`.
- Use verbatim MaxScript path strings for Windows paths, for example `@"C:\Projects\MyTool\main.ms"`.
- Do not insert unescaped user text directly into MaxScript source. Escape it as a MaxScript string literal first.
- Run mutations serially. Read the response and require `ok == true` before the next dependent operation.
- Prefer `setOptions` over many `setOption` calls.
- Collection indexes are 1-based. Re-list a collection after additions or removals before using another index.
- Set `version` before editing its changelog. Changelog entries are stored per version.
- Use `force: true` only after deciding that clearing entry-file or extra-macro references is intended.
- Call `validate()` before `build()`, even though build performs its own validation.
- Never infer a successful build only from the call completing. Require `ok == true` and `data.exists == true`.

## Response envelope

Every API method returns JSON with the same top-level shape:

```json
{
  "ok": true,
  "operation": "files.add",
  "data": {},
  "warnings": [],
  "errors": []
}
```

An error item contains a stable machine-readable `code` and a human-readable `message`:

```json
{
  "ok": false,
  "operation": "files.remove",
  "data": {},
  "warnings": [],
  "errors": [
    {
      "code": "FILE_IN_USE",
      "message": "File is used by entryFile or Extra Macros. Pass force: true to clear dependent references."
    }
  ]
}
```

Do not continue a dependent workflow after an unsuccessful response. Correct the arguments or package state and retry the failed operation.

## Discovery and state

### `ping()`

Checks that the API object is loaded and returns API version, packager version, and project root.

### `getSchema()`

Returns the supported method names, writable option names, response shape, and index base. Agents should call it before automation when compatibility is uncertain.

### `getState()`

Returns the complete current state:

- project and persistence paths;
- calculated output file;
- all options;
- package files;
- changelog items for the active version;
- build-path rules;
- extra macros.

### `save()`

Writes the current state to the project INI and changelog files and refreshes the UI.

### `reload()`

Discards unsaved in-memory state, reloads the project files, refreshes the UI, and returns the new complete state.

All public mutation methods save synchronously, so an extra `save()` is normally unnecessary.

## Options

### `setOption optionName optionValue`

Validates, applies, saves, and returns one option.

```maxscript
MaxPkgPackerApi.setOption "releaseChannel" "beta"
```

### `setOptions optionPairs`

Validates the full array before applying it, then saves once. Each item must be a two-element MaxScript array.

```maxscript
MaxPkgPackerApi.setOptions #(
    #("packageName", "My Tool"),
    #("buttonName", "My Tool"),
    #("description", "Automates the current workflow."),
    #("developerName", "Studio Name"),
    #("license", "Commercial"),
    #("createMacroButton", true),
    #("showInToolbar", true),
    #("version", "1.2.0"),
    #("releaseChannel", "stable"),
    #("releaseDate", "2026-08-26"),
    #("min3dsMax", "2022")
)
```

The writable options are:

| Option | Type and constraints |
| --- | --- |
| `packageName` | String; only A-Z, a-z, digits, spaces, hyphen, underscore |
| `buttonName` | String; same character rules as package name |
| `packageGuid` | Empty string or UUID |
| `description` | String, at most 500 characters |
| `developerName` | String |
| `license` | `Free`, `Shareware`, `Commercial`, `Open source`, `Trial`, or empty |
| `licenseUrl` | String |
| `documentationUrl` | String |
| `homepageUrl` | String |
| `purchaseUrl` | String |
| `purchaseButtonLabel` | `Buy`, `Purchase`, `Get license`, `Donate`, `Support`, or `Sponsor` |
| `createMacroButton` | Boolean |
| `showInToolbar` | Boolean |
| `customInstallScript` | Empty or existing author `.ms` file inside the project root |
| `customUninstallScript` | Empty or existing author `.ms` file inside the project root |
| `outputFolder` | Folder path |
| `svgIconFile` | Empty or existing safe SVG file; a selected file is copied to project-root `maxpkg-icon.svg` |
| `entryFile` | Empty or a file already present in Files List; must end in `.ms`, `.mse`, or `.py` |
| `compileEntry` | Boolean; compilation is valid only for a `.ms` entry |
| `version` | `major.minor.patch`; every component is 0-999 |
| `releaseChannel` | `stable`, `alpha`, or `beta` |
| `releaseDate` | `YYYY-MM-DD` |
| `min3dsMax` | A year returned by the packager's supported-year list |

`max3dsMax` is calculated by the packager and is read-only.

### `generateGuid replaceExisting:false`

Generates and saves a UUID. If a GUID already exists, pass `replaceExisting: true` explicitly.

## Package files

### `listFiles()`

Returns every source path, project-relative path, remapped build path, existence flag, and 1-based index.

### `addFile sourceFilePath`

Adds one existing file. The path must be eligible for the project Files List.

```maxscript
MaxPkgPackerApi.addFile @"C:\Projects\MyTool\main.ms"
```

Adding an already-present source is idempotent and returns `added: false`.

### `addFolder sourceFolderPath`

Recursively adds eligible files from an existing folder and returns the added and total counts.

### `removeFile fileIdentifier force:false`

Removes a file by absolute source path or project-relative path. If it is the entry file or is referenced by an extra macro, the default call fails with `FILE_IN_USE`. With `force: true`, dependent references are cleared.

```maxscript
MaxPkgPackerApi.removeFile "scripts\\main.ms" force:true
```

### `clearFiles force:false`

Clears Files List. The default call is rejected while entry-file or extra-macro references exist. `force: true` also clears those references.

## Changelog

Supported types are `Added`, `Fixed`, `Changed`, `Removed`, and `Improved`. Type matching is case-insensitive and returned values are canonicalized.

### `listChangelog()`

Returns the active version and its indexed entries.

### `addChangelog itemType itemText`

```maxscript
MaxPkgPackerApi.addChangelog "Added" "Max Ultra MCP automation API"
```

### `updateChangelog itemIndex itemType itemText`

```maxscript
MaxPkgPackerApi.updateChangelog 1 "Improved" "Expanded automation coverage"
```

### `removeChangelog itemIndex`

Removes one 1-based entry.

### `clearChangelog()`

Clears all entries for the active version only.

## Build-path rules

Rules remap project-relative source folders to folders in the built package.

- `listBuildPathRules()`
- `addBuildPathRule sourceFolder targetFolder`
- `updateBuildPathRule ruleIndex sourceFolder targetFolder`
- `removeBuildPathRule ruleIndex`
- `clearBuildPathRules()`

An empty target folder means the package root:

```maxscript
MaxPkgPackerApi.addBuildPathRule "source" ""
```

Use normalized relative folder names. Absolute paths, parent traversal, and unsafe folder values are rejected.

## Extra macros

An extra macro references a script already in Files List.

- `listExtraMacros()`
- `addExtraMacro relativeFilePath buttonName compileScript:false showInQuadMenu:false`
- `updateExtraMacro macroIndex relativeFilePath buttonName compileScript:false showInQuadMenu:false`
- `removeExtraMacro macroIndex`
- `clearExtraMacros()`

Example:

```maxscript
MaxPkgPackerApi.addExtraMacro "tools\\cleanup.ms" "Cleanup" compileScript:true showInQuadMenu:true
```

Button names must be unique after identifier normalization. Only `.ms` files can be compiled. When an extra macro uses the entry file, both compile settings must agree.

## Validation, build, and log

### `validate()`

Runs full package validation. On failure, `ok` is false and `data.log` contains the color-coded packager log entries.

### `build()`

Validates and builds the package. A successful response includes:

```json
{
  "outputFile": "C:\\Projects\\MyTool\\dist\\my-tool@1.2.0@GUID.mzp",
  "exists": true,
  "log": ["[OK] Package built successfully"]
}
```

### `getLog()`

Returns all current in-memory log entries.

### `clearLogEntries()`

Clears the in-memory log and refreshes the log window.

## Recommended Max Ultra MCP workflow

1. Select the intended live 3ds Max instance.
2. Load the target project's `maxpkg-packager.ms`.
3. Call `ping()`, `getSchema()`, and `getState()`.
4. Add the required source files.
5. Apply metadata with one `setOptions` call.
6. Add build-path rules and extra macros.
7. Set the target version, then manage its changelog.
8. Call `validate()` and resolve every returned error.
9. Call `build()`.
10. Require `ok == true`, `data.exists == true`, and verify the returned output path.
11. Call `getState()` for the final persisted state.

## Complete example

```maxscript
MaxPkgPackerApi.addFile @"C:\Projects\MyTool\main.ms"

MaxPkgPackerApi.setOptions #(
    #("packageName", "My Tool"),
    #("buttonName", "My Tool"),
    #("packageGuid", "12345678-1234-1234-1234-123456789abc"),
    #("description", "Example package controlled through Max Ultra MCP."),
    #("developerName", "Studio Name"),
    #("license", "Free"),
    #("createMacroButton", true),
    #("showInToolbar", true),
    #("outputFolder", @"C:\Projects\MyTool\dist"),
    #("svgIconFile", @"C:\Projects\MyTool\icon.svg"),
    #("entryFile", "main.ms"),
    #("compileEntry", true),
    #("version", "1.0.0"),
    #("releaseChannel", "stable"),
    #("releaseDate", "2026-08-26"),
    #("min3dsMax", "2022")
)

MaxPkgPackerApi.addChangelog "Added" "Initial MaxPkg release"
MaxPkgPackerApi.validate()
MaxPkgPackerApi.build()
```

Each line above is shown separately for clarity. In an agent workflow, inspect each JSON response before running the next dependent call.
