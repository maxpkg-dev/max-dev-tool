# MaxPkg Packager

`maxpkg-packager.ms` helps 3ds Max developers build clean MaxPkg-compatible `.mzp` packages.

Put the packager into the root folder of your script project, run it in 3ds Max, fill in the package information, add your files, choose the entry file, and build the final `.mzp` archive.

The script keeps its settings next to your project, so every package can have its own metadata, changelog, icon, and build output.

## AI-Assisted Packaging

These ready-to-use prompts can help prepare an existing 3ds Max project with Codex or Claude Code:

- [MaxPkg Adaptation Prompt](maxpkg-adaptation-prompt.md) - adapt an existing script to the MaxPkg installation flow while preserving its runtime behavior.
- [MaxPkg Full Onboarding Prompt](maxpkg-full-onboarding-prompt.md) - complete the adaptation, configure MaxPkg Packager, build and verify the package, and prepare the marketplace listing and upload instructions.
- [MaxPkg Automation API](maxpkg-api.md) - control every package option, file list, changelog, build-path rule, extra macro, validation, and build operation from Max Ultra MCP or MaxScript.
- [Recommended MaxScript Coding Rules](code-rules.md) - practical conventions for safe identifiers, functions, paths, UI code, generated scripts, validation, and maintainable MaxScript.

Use the adaptation prompt when you only need the project code prepared for MaxPkg. Use the full onboarding prompt when you want the AI agent to handle the complete packaging workflow and leave you with a tested `.mzp` plus the content needed for maxpkg.dev.

Share the coding rules with your AI agent before it edits MaxScript so generated code follows safer naming and implementation conventions.

## Requirements

- Autodesk 3ds Max.
- A script project that you want to package.
- `maxpkg-packager.ms`.
- A valid square SVG icon.
- Python support in 3ds Max only if your package entry file is `.py`.

Supported entry files:

```text
.ms
.mse
.py
```

## Quick Start

1. Download and extract the MaxPkg repository.
2. Copy `maxpkg-packager.ms` into the root folder of your own project.
3. If needed, copy `_install.ms`, `_uninstall.ms`, or both into the same project folder.
4. Open 3ds Max.
5. Run `maxpkg-packager.ms` from `Scripting > Run Script...`, or drag it into a viewport.
6. Fill the required fields in the packager window.
7. Add your package files.
8. Select an entry file and click `Use Selected`.
9. Add at least one changelog item for the current version.
10. Fix anything shown by the `Has Issues` status.
11. Click `Build MZP`.

The package will be created in the output folder. By default, that is:

```text
<project-root>\dist
```

## Project Folder

The folder that contains `maxpkg-packager.ms` is treated as the package root.

After downloading and extracting the MaxPkg repository, copy `maxpkg-packager.ms` into the folder of the project you want to package. If the project needs the optional installer or uninstaller, copy `_install.ms`, `_uninstall.ms`, or both into that same folder.

Example:

```text
MyTool\
  maxpkg-packager.ms
  _install.ms          optional
  _uninstall.ms        optional
  main.ms
  helpers\
    ui.ms
  data\
    presets.json
```

Keep one copy of `maxpkg-packager.ms` inside each project you package. This keeps the project settings, changelog, icon, and optional hooks nicely separated.

## Project Support Files

The project folder may contain these support files next to `maxpkg-packager.ms`:

- `maxpkg-packager.ini` - saved project settings.
- `maxpkg-changelog.ini` - changelog entries, grouped by version.
- `maxpkg-icon.svg` - the selected icon copied into the project root.
- `_install.ms` - optional installer hook that you copy from this repository when needed.
- `_uninstall.ms` - optional uninstaller hook that you copy from this repository when needed.
- `dist\*.mzp` - built package archives.

The packager creates and maintains its INI, changelog, icon, and output files. It does not create the optional hooks; copy those templates into the project yourself when needed.

## Interface Overview

The packager uses four tabs:

- `1. Info` - package identity, description, developer, and license.
- `2. Setup` - macro button, toolbar metadata, and optional hook status.
- `3. Files` - output folder, SVG icon, package files, and entry file.
- `4. Release` - version, release date, 3ds Max version, channel, and changelog.

At the top you will see a status button:

- `Ready` means the package has the required information.
- `Has Issues` means something still needs to be fixed.

Click the status button to open the log. The log tells you where to fix each issue, for example:

```text
License is required (1. Info -> License)
SVG icon is required (3. Files -> SVG Icon)
Changelog for version 1.0.0 must contain at least one item (4. Release -> Changelog)
```

The log uses the active 3ds Max theme and color-codes complete entries: green for `[OK]`, red for `[ERROR]`, yellow for `[WARNING]`, and blue for informational messages. It keeps the latest 30 entries visible and scrolls to the newest result automatically. The complete in-memory log is still used when deciding whether a build contains errors.

`Build MZP` uses the same status color. If there are issues, it will stay red and the package will not be created.

## 1. Info

### Package Name

The public name of your package.

Allowed characters:

```text
A-Z a-z 0-9 space - _
```

Avoid dots, slashes, `@`, non-English letters, and emoji. The package name is also used to generate a safe archive filename.

### Button Name

The text used for the generated 3ds Max macro button.

It uses the same character rules as `Package Name`.

### GUID

The GUID is the package identity.

Generate it once and keep it. The GUID is used to identify the package on maxpkg.dev and to verify uploaded archives. Changing it later means you are creating a different package identity.

If a GUID already exists, generating a new one requires extra confirmation.

Right-click the GUID field to open the custom context menu:

- `Copy`
- `Paste`

Pasting over an existing GUID shows a warning first.

### Description

A short description of your package.

This field is required and is written into the manifest. It is also shown by the optional installer window.

### Developer Name

Required.

Use the developer name you want users to see.

### License

Required.

You must choose one of:

- `Free`
- `Shareware`
- `Commercial`
- `Open source`
- `Trial`

The default value is empty on purpose, so you do not accidentally publish a package with the wrong license.

### Optional Links

These fields are optional, but useful:

- `License URL`
- `Documentation URL`
- `Homepage URL`
- `Support URL`

### Purchase URL

Use `Purchase URL` when your package has a paid license, donation page, sponsor page, or another external support link.

If you add a purchase link, choose how the button should be displayed on the website:

- `Buy`
- `Purchase`
- `Get license`
- `Donate`
- `Support`
- `Sponsor`

Pick the label that best matches the action users should take.

## 2. Setup

### Create 3ds Max Button

When enabled, the package creates a macro button during installation.

The generated macro is created for the current 3ds Max user profile, so it uses the correct local user macro and icon folders on the machine where the package is installed.

### Show In MaxPkg Toolbar

This saves toolbar metadata into the manifest.

If MaxPkg is loaded during installation, the installer tries to refresh the toolbar automatically.

### Standard MaxPkg Installer Hooks

The repository includes the standard MaxPkg `_install.ms` and `_uninstall.ms` files. Copy either file next to `maxpkg-packager.ms` when you want its installation or removal interface in your package. Leave it out when you do not need that interface.

The Setup tab shows each hook in green when its file is available and gray when it is not. Detected hooks are included automatically, so you do not need to add them to the Files List.

When a standard hook is ready, you may also choose a focused custom script:

- `Custom Install Script` runs at the end of package installation.
- `Custom Uninstall Script` runs before MaxPkg removes the package files.

Use these scripts only for project-specific actions that MaxPkg cannot infer, such as registering or removing callbacks. Each custom script must be a `.ms` file inside the project folder. The packager includes it automatically, writes its packaged location to the manifest, and applies Build Path Remap when necessary.

Keep custom scripts focused and non-interactive. A custom uninstall script must finish its cleanup before MaxPkg removes the package folder; short timer-based cleanup is supported, but it should not wait for additional user input.

Do not add a selected custom script to the Files List. If the same file is selected in Setup and is also present in the Files List, validation reports the conflict and blocks the build.

When MaxPkg Packager updates itself, it also downloads the latest copy of each hook that already exists in the project root. Missing hooks are not created automatically.

`_install.ms` provides a standalone installation window with the package icon, name, version, developer, current-version changelog, and an optional `Developer site` link. You can open it from the project folder to preview the interface. In preview mode, clicking `Install` does not install, change, or delete anything. Closing an actual extracted installer before confirmation removes only its verified `$temp\<GUID>` package folder.

`_uninstall.ms` provides a matching standalone removal window. During a real uninstall, it removes the verified `$temp\<GUID>` package folder, the package-generated macro files from the current 3ds Max user profile, and the installed SVG icon. When opened from a project folder, its button works only as a preview and cannot remove project files.

Use these files as the MaxPkg installation interface. Do not replace them with an older author installer or include the old installer as a fallback. If the project needs a small amount of additional setup or cleanup, move only those required actions into the matching custom script selected in Setup. The packaged script must run directly from its MaxPkg package folder after installation.

When adapting an existing project, inspect its old installer only to learn which files and setup steps the script requires. Add required runtime files to the Files List, configure macro buttons through the packager, and update fragile file paths to resolve relative to the running script. Keep the tool's features and user settings, but replace its old installation method with MaxPkg.

Only `_install.ms` and `_uninstall.ms` are detected and included automatically.

## 3. Files

### Output Folder

Where the final `.mzp` archive will be saved.

Default:

```text
<project-root>\dist
```

### SVG Icon

Required.

Choose a safe square `.svg` icon. A square icon is important for correct display in 3ds Max buttons, toolbars, and MaxPkg listings.

Use an SVG with a square canvas or viewBox, for example:

```text
viewBox="0 0 64 64"
```

Non-square icons may look stretched, cropped, or visually off-center.

The packager copies the selected icon into the project root as:

```text
maxpkg-icon.svg
```

Inside the final package, it is stored as:

```text
icons\icon.svg
```

During installation, the icon is copied to the current 3ds Max user icons folder and named with the package GUID.

### Files List

Use the file buttons to add your package files.

- `Add Files` lets you select multiple files at once.
- `Add Folder` adds files from a folder.
- `Remove` removes the selected file after confirmation.

The packager skips common internal and temporary files, such as `.git`, `.bak`, `.tmp`, `.log`, `.zip`, `.mzp`, packager settings, and build command files.

### Entry File

The entry file is the main file that runs when the generated macro button is clicked.

To set it:

1. Add the file to `Files List`.
2. Select it in the list.
3. Click `Use Selected`.

Runtime is detected automatically:

- `.py` runs with `python.ExecuteFile`.
- `.ms` and `.mse` run with `fileIn`.

### Compile entry file .ms to .mse

This option is enabled by default for `.ms` entry files.

It is disabled automatically for `.py` and `.mse`.

When enabled:

- your source `.ms` file is not modified;
- the temporary build copy is compiled to `.mse`;
- the package uses the generated `.mse` as the entry file.

### Build Path Remap

`Build Path Remap` is an advanced, collapsed section in `3. Files`.

Use it when your source project must keep files in one folder, but the final package needs those files in another folder.

Example:

```text
COMPILE -> /
```

This means files such as:

```text
COMPILE\uac.lnk
COMPILE\external_script.ms
```

will be copied into the package root as:

```text
uac.lnk
external_script.ms
```

Leave the target folder empty when you want to remap into the package root.

### Extra Macros

`Extra Macros` is an advanced, collapsed section in `3. Files`.

Use it when your package needs more than one 3ds Max macro button. The main macro button runs the `Entry File`; extra macros let you create additional buttons that run other `.ms`, `.mse`, or `.py` files from `Files List`.

To add an extra macro:

1. Add the script file to `Files List`.
2. Open `Extra Macros`.
3. Choose the script file from the dropdown.
4. Enter the button name.
5. Enable `Compile .ms to .mse` if needed.
6. Enable `Show in Quad Menu` if the command should also appear in the viewport right-click menu.
7. Click `Add`.

Extra macro button names may use only:

```text
A-Z a-z space _
```

Spaces are removed internally when the packager creates the technical `macroScript` name, so a button name like `Open Tools` becomes a safe macro identifier automatically.

If `Compile .ms to .mse` is enabled for an extra macro, the build uses the compiled `.mse` file for that macro. If the same file is also used as the main `Entry File`, the compile option must match in both places.

Extra macros respect `Build Path Remap`. For example, if `COMPILE\tool.ms` is remapped to the package root and used by an extra macro, the generated macro will run `tool.ms` or `tool.mse` from the final package location.

`Show in Quad Menu` supports both the classic 3ds Max menu system and the newer Quad Menu API used by recent 3ds Max versions. MaxPkg creates a small package-specific script in the current 3ds Max user startup folder, so selected commands are restored every time 3ds Max starts. Package uninstall removes both the Quad Menu entries and this startup script.

## 4. Release

### Version

Version is split into three dropdowns:

```text
major.minor.patch
```

Examples:

```text
1.0.0
1.0.1
2.3.0
```

The major dropdown supports `0..99`. Minor and patch support `0..9`.

### Channel

Choose one:

- `stable`
- `alpha`
- `beta`

The channel is saved separately as `releaseChannel`. It is not added to the version string.

### Release Date

Uses a date picker and saves the date in this format:

```text
YYYY-MM-DD
```

Release date is saved per version.

### Min 3ds Max

The minimum supported 3ds Max version.

The list starts at `2012` and ends at the current year plus one.

This setting is saved per version.

### Changelog

Every version has its own changelog.

For example:

- `1.0.0` can have its own entries.
- `1.0.1` can have different entries.

When you change the version dropdowns, the packager loads the changelog, release date, channel, and minimum 3ds Max version for that version.

At least one changelog item is required before building.

Changelog types:

- `Added`
- `Fixed`
- `Changed`
- `Removed`
- `Improved`

Changes are saved automatically after `Add`, `Edit/Save`, and `Remove`.

## Building

When the status is `Ready`, click:

```text
Build MZP
```

The final filename uses:

```text
slug@version@guid.mzp
```

Example:

```text
test-package@1.0.1@54d9b847-13a1-4747-b993-0d039a1c7ac3.mzp
```

The slug is created from `Package Name`.

If the log contains any `[ERROR]` entry, the `.mzp` file will not be created.

## What Goes Into The Package

The generated `.mzp` contains:

```text
manifest.ini
manifest.json
maxpkg-changelog.ini
mzp.run
mzp.run.ms
_install.ms         optional
_uninstall.ms       optional
<custom install script>    optional
<custom uninstall script>  optional
icons\icon.svg
<your package files>
```

`manifest.ini` and `manifest.json` contain the package metadata.

`mzp.run` is the native 3ds Max MZP command file.

`mzp.run.ms` runs during installation. It reads the manifest, creates the optional main macro button, creates any extra macro buttons, installs the icon, runs `_install.ms` if it exists, and notifies MaxPkg when possible. The standard hooks read the custom script locations from the manifest. `_uninstall.ms` is recorded in the manifest for package removal.

## Testing The Package

After building, test the `.mzp` before uploading it.

In 3ds Max:

1. Use `Scripting > Run Script...` and select the `.mzp`, or drag the `.mzp` into a viewport.
2. If you enabled the macro button, check that it appears in the `MaxPkg` category.
3. Click the generated button and make sure your entry file runs.
4. Check that the icon appears correctly.
5. If you included `_install.ms`, make sure the install window looks right.

## Publishing On maxpkg.dev

After you build and test your `.mzp`, you can upload it to MaxPkg.

1. Open [maxpkg.dev](https://maxpkg.dev).
2. Sign in, or create an account.
3. Open [maxpkg.dev/account](https://maxpkg.dev/account).
4. If you do not have a developer profile yet, click `Become a Developer`.
5. If you already have a developer profile, open the Developer Dashboard.
6. Go to [maxpkg.dev/dashboard/packages](https://maxpkg.dev/dashboard/packages).
7. Create a package and fill in the required information.
8. Open the package `Versions` tab.
9. Upload the `.mzp` file created by MaxPkg Packager.

The submitted file will be reviewed before it appears on the website.

## Updates

The packager checks for updates when it starts.

Update downloads run in the background. If the standard `.NET` download is unavailable, the packager automatically tries `curl.exe` when it is available on the system.

You can also open `About` and click:

```text
Check Updates
```

If an update is installed, the packager shows a notice with update information.

## Common Issues

### License is required

Go to `1. Info -> License` and choose a license.

### SVG icon is required

Go to `3. Files -> SVG Icon` and choose a valid square `.svg` file.

### SVG icon looks stretched or cropped

Use a square SVG canvas or viewBox. For example, `viewBox="0 0 64 64"` works well.

### Changelog must contain at least one item

Go to `4. Release -> Changelog` and add at least one item for the current version.

### Entry file must be included in package files

Go to `3. Files`, add the file to `Files List`, select it, and click `Use Selected`.

### Package name or button name has invalid characters

Use only:

```text
A-Z a-z 0-9 space - _
```

### Build MZP stays red

Click the status button at the top. The log will show what to fix and which tab contains the field.

## Minimal Working Package

For the smallest useful package:

1. Put `maxpkg-packager.ms` into your project root.
2. Run it in 3ds Max.
3. Fill `Package Name`, `Button Name`, `Description`, `Developer Name`, and `License`.
4. Generate a GUID.
5. Choose a valid square SVG icon.
6. Add your entry `.ms`, `.mse`, or `.py` file to `Files List`.
7. Select it and click `Use Selected`.
8. Add one changelog item.
9. Make sure the status says `Ready`.
10. Click `Build MZP`.

Then test the generated `.mzp` in 3ds Max before uploading it.
