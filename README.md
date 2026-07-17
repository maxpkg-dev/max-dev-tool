# MaxPkg Packager

`maxpkg-packager.ms` is a developer tool for building MaxPkg-compatible `.mzp` packages for Autodesk 3ds Max.

Place the script directly into your project folder, run it from 3ds Max, configure package metadata, add project files, select an entry file, and build a ready-to-upload `.mzp` archive.

The packager generates package metadata, changelog data, MZP command files, optional macro button installation code, and the final archive.

## Requirements

- Autodesk 3ds Max.
- A project to package, for example `.ms`, `.mse`, `.py`, SVG icon, and support files.
- `maxpkg-packager.ms`.
- Python support inside 3ds Max if your entry file is `.py`.

MaxPkg Toolbar is not required to build a package. If MaxPkg is already loaded when a package is installed, the generated installer script will try to call `MaxPkg.rebuildToolbar()`.

## Quick Start

1. Download the repository or archive that contains `maxpkg-packager.ms`.
2. Extract it into any temporary folder.
3. Copy `maxpkg-packager.ms` into the root folder of your own project.
4. Open 3ds Max.
5. Run `maxpkg-packager.ms` through `Scripting > Run Script...`, or drag the file into a viewport.
6. Fill in the fields in the `MaxPkg Packager` window.
7. Add your project files to `Files List`.
8. Select an `Entry File`.
9. Add at least one `Changelog` item for the current version.
10. Click `Validate`.
11. Click `Build MZP`.

The final `.mzp` file will be created in the output folder. By default this is the `dist` folder next to `maxpkg-packager.ms`.

## Project Folder Setup

The folder that contains `maxpkg-packager.ms` is treated as the package root.

Example:

```text
MyTool\
  maxpkg-packager.ms
  main.ms
  scripts\
    helpers.ms
  icons\
    source-icon.svg
```

In this example, `MyTool\` is the package root. All package paths written into the manifest are relative to this folder.

It is recommended to keep one copy of `maxpkg-packager.ms` inside each project that you package. This keeps settings, changelog data, icons, and sample install scripts isolated per project.

## Local Files Created By The Packager

After you run and configure the packager, these files may appear next to `maxpkg-packager.ms`:

- `maxpkg-packager.ini` - saved UI settings for the current project.
- `maxpkg-changelog.ini` - changelog entries grouped by version.
- `maxpkg-icon.svg` - selected SVG icon copied into the project root.
- `install.ms` - optional install hook, if you create the sample install script.
- `uninstall.ms` - optional uninstall hook, if you create the sample uninstall script.
- `dist\*.mzp` - generated package archives.

You do not need to manually add packager settings files to `Files List`. The sample `install.ms` and `uninstall.ms` files are added automatically when created.

## Packager Window

When you run the script again, the previous packager window is closed before a new one is opened. This prevents multiple copies of the same UI from staying open.

The main rollout is `Packager`. The second rollout is `About`, which contains script information, developer links, and update controls.

## Important Info

`Package Name` is the package display name.

Allowed characters:

```text
A-Z a-z 0-9 space - _
```

Characters such as `@`, `.`, `/`, `\`, non-English letters, and emoji are not allowed. The package name is used to generate a safe archive filename.

`Button Name` is the text used for the generated 3ds Max macro button. It uses the same character rules as `Package Name`.

`Package GUID` is the unique package identity.

- `Generate` creates a new GUID.
- If a GUID already exists, generating a new one requires typing `CHANGE` into a confirmation dialog.
- `Copy` copies the GUID to the clipboard.
- `Paste` pastes a GUID from the clipboard and warns you if it will replace an existing GUID.

The GUID is important because it identifies the package on the MaxPkg website and is used for archive verification. Do not change the GUID after publishing a package unless you intentionally want to create a new package identity.

`Description` is the package description. It is written into the manifest and shown by the sample install script.

## Package Metadata

`Version` is split into three dropdowns:

```text
major.minor.patch
```

Examples:

```text
1.0.0
1.0.1
2.3.0
```

`Channel` is the release channel:

- `stable`
- `alpha`
- `beta`

The channel is saved as `releaseChannel`. It is not appended to the version string.

`Release Date` is the release date. The current date is used by default.

`Min 3ds Max` is the minimum supported 3ds Max version. The list starts at `2012` and ends at the current year plus one.

`Create 3ds Max Macro Button` controls whether the package installer generates a macro button. When enabled, `mzp.run.ms` creates an `.mcr` file in the current 3ds Max `getDir #userMacros` folder and loads it with `fileIn`.

`Show In MaxPkg Toolbar` is metadata for MaxPkg Toolbar. It is saved into the manifest. If the global `MaxPkg` object is available during package installation, the installer calls `MaxPkg.rebuildToolbar()`.

## Info

`Developer Name` is required.

`License` can only be one of these values:

- `Free`
- `Shareware`
- `Commercial`
- `Open source`
- `Trial`

Optional URL fields:

- `License URL`
- `Homepage URL`
- `Documentation URL`
- `Support URL`

These fields are useful for the website, the manifest, and the sample install window.

## Files List

`Output Folder` is where the final `.mzp` file is saved. By default it is:

```text
<project-root>\dist
```

`SVG Icon` is the package icon.

When you choose an SVG file through `Browse`, the packager copies it into the project root as:

```text
maxpkg-icon.svg
```

Inside the final `.mzp`, the icon is stored as:

```text
icons\icon.svg
```

During package installation, `mzp.run.ms` copies this icon into the current 3ds Max user icons folder:

```text
getDir #userIcons
```

The installed icon filename is:

```text
<packageGuid>.svg
```

That full path is written into the generated macro button.

File list buttons:

- `Add Files` - adds one file. The file dialog opens in the project root.
- `Add Folder` - adds files from a selected folder.
- `Scan Folder` - scans the project root and adds package files.
- `Remove` - removes the selected file from the package list after confirmation.
- `Sample install.ms` - creates a sample `install.ms` if it does not exist.
- `Sample uninstall.ms` - creates a sample `uninstall.ms` if it does not exist.

If a file is removed from `Files List` and that file was selected as `Entry File`, the `Entry File` field is cleared automatically.

The packager automatically excludes internal and temporary files such as:

- `.git`
- `.vscode`
- `.bak`
- `.tmp`
- `.log`
- `.zip`
- `.mzp`
- `maxpkg-packager.ms`
- `maxpkg-packager.ini`
- `maxpkg-changelog.ini`
- `mzp.run`
- `mzp.run.ms`

## Entry

`Entry File` is the main file launched by the generated macro button.

The entry file must be included in `Files List`. Select the file in the list, then click `Use Selected`.

Supported entry extensions:

- `.ms`
- `.mse`
- `.py`

There is no runtime dropdown. Runtime is detected from the entry file extension:

- `.py` runs through `python.ExecuteFile`.
- `.ms` and `.mse` run through `fileIn`.

`Compile entry file .ms to .mse` is enabled only when the entry file is `.ms`.

When this option is enabled:

- the source `.ms` file in your project is not modified;
- the `.ms` file is copied into the temporary build folder;
- the copy is compiled to `.mse`;
- the temporary `.ms` copy is removed;
- the manifest entry points to the generated `.mse`;
- the package contains the compiled `.mse` for the entry file.

## Changelog

Changelog entries are stored per version.

For example:

- version `1.0.0` has its own changelog list;
- version `1.0.1` has a separate changelog list.

When you change the version dropdowns, the packager loads the changelog for that selected version.

At least one changelog item is required for the current version. If the current version has no changelog entries, `Build MZP` will not create an archive.

Changelog types:

- `added`
- `fixed`
- `changed`
- `removed`
- `improved`

Buttons:

- `Add` - adds a new changelog item.
- `Edit` - replaces the selected changelog item.
- `Remove` - removes the selected changelog item.

Changelog data is saved automatically after `Add`, `Edit`, and `Remove`.

## Log

The log is shown in a separate window.

The log window opens for important actions such as `Validate` and `Build MZP`. Regular actions such as `Add Files` or `Scan Folder` should not open it by themselves.

If the log contains an `[ERROR]` entry, the `.mzp` file will not be created.

The log window has two buttons:

- `Clear Log`
- `Close`

## Build Workflow

Click `Validate` before building.

Validation checks that:

- `Package Name` is filled;
- `Button Name` is filled;
- `Package Name` and `Button Name` use only allowed characters;
- `Description` is filled;
- `Developer Name` is filled;
- `Package GUID` is valid;
- version, channel, and release date are filled;
- the current version has at least one changelog item;
- `Entry File` is selected;
- `Entry File` is included in `Files List`;
- the entry file exists on disk;
- the entry file extension is supported;
- the selected SVG icon is safe and valid;
- the package has at least one file;
- relative package paths are safe;
- `install.ms` and `uninstall.ms` are only in the package root;
- output folder exists or can be created.

After validation succeeds, click `Build MZP`.

The final archive filename format is:

```text
slug@version@guid.mzp
```

Example:

```text
test-package@1.0.1@54d9b847-13a1-4747-b993-0d039a1c7ac3.mzp
```

The `slug` is generated from `Package Name`:

- converted to lowercase;
- spaces and hyphens are collapsed into one `-`;
- only `a-z`, `0-9`, `-`, and `_` are kept;
- if the result is empty, `package` is used.

## What Goes Into The MZP

During build, the packager creates a temporary build folder and writes:

```text
manifest.ini
manifest.json
maxpkg-changelog.ini
mzp.run
mzp.run.ms
install.ms          optional
uninstall.ms        optional
icons\icon.svg      optional
<your package files>
```

After the `.mzp` archive is created, the temporary build folder is removed.

`mzp.run` is a native MZP command file. It contains commands like:

```text
name "<Package Name>"
extract to "$temp\<packageGuid>"
drop "mzp.run.ms"
run "mzp.run.ms"
```

3ds Max extracts the package to:

```text
getDir #temp\<packageGuid>\
```

Then it runs `mzp.run.ms`.

## What mzp.run.ms Does

`mzp.run.ms` runs during package installation.

It:

1. Reads `manifest.ini`.
2. Reads `packageGuid`.
3. If `Create 3ds Max Macro Button` is enabled, creates an `.mcr` file in `getDir #userMacros`.
4. If an SVG icon exists, copies it to `getDir #userIcons` as `<packageGuid>.svg`.
5. Loads the generated macro button with `fileIn`.
6. Runs root `install.ms` if it exists.
7. Calls `MaxPkg.rebuildToolbar()` if the global `MaxPkg` object is available.

When the generated macro button is clicked, it:

- reads `manifest.ini`;
- reads the `entry` value;
- builds the entry path inside `$temp\<packageGuid>`;
- runs `.py` through `python.ExecuteFile`;
- runs `.ms` and `.mse` through `fileIn`.

## install.ms And uninstall.ms

`install.ms` is not created automatically during every build. The user decides whether the package needs an install hook.

To create a sample install script, click:

```text
Sample install.ms
```

If the file does not exist, the packager creates `install.ms`, adds it to `Files List`, and shows the path to the created file.

The sample `install.ms` shows an `Install Complete` window with information from the manifest:

- name;
- version;
- channel;
- release date;
- supported 3ds Max versions;
- license;
- developer;
- homepage, documentation, and support links;
- description;
- latest changelog.

To create a sample uninstall script, click:

```text
Sample uninstall.ms
```

The sample `uninstall.ms` shows a simple uninstall window:

```text
<Package Name> has been completely removed.
```

Important: putting `uninstall.ms` into the package does not mean 3ds Max runs it automatically. It is a hook for MaxPkg, website, or runtime uninstall logic.

## Manifest

The packager always creates two manifest files:

```text
manifest.ini
manifest.json
```

They contain package metadata:

- `packageGuid`
- `name`
- `buttonName`
- `description`
- `version`
- `releaseChannel`
- `releaseDate`
- `entry`
- `compileEntry`
- `icon`
- `license`
- `licenseUrl`
- `developerName`
- `min3dsMax`
- `max3dsMax`
- `homepage`
- `documentation`
- `support`
- `createMacroButton`
- `showInToolbar`
- `installScript`
- `uninstallScript`
- `packager`
- `packagerVersion`
- `changelog`

The archive filename is useful as a fast index, but the manifest inside the archive is the source of truth. Even if a filename looks valid, the website should open the MZP, read the manifest, and verify `packageGuid`, `version`, and other metadata.

## Publishing On maxpkg.dev

After you build and test your `.mzp` file, you can upload it to the MaxPkg website.

1. Open [maxpkg.dev](https://maxpkg.dev).
2. Sign in to your account, or create a new account if you do not have one yet.
3. Open [maxpkg.dev/account](https://maxpkg.dev/account).
4. If you do not have a developer profile yet, click the blue `Become a Developer` button and create one.
5. If your developer profile already exists, open the Developer Dashboard.
6. Go to [maxpkg.dev/dashboard/packages](https://maxpkg.dev/dashboard/packages).
7. Create a new Package.
8. Fill in the required package information on the website.
9. Open the package `Versions` tab.
10. Upload the `.mzp` file generated by MaxPkg Packager.

After upload, the MaxPkg administration team will review the submitted file. If the package passes review, it will be published on the website.

## Packager Updates

When the packager starts, it checks update information from the script's own `[INFO]` block.

You can also open `About` and click `Check Updates`.

If an update is found and applied, the packager shows a notice window with update information and offers to restart the script.

## Common Errors

`Changelog for version ... must contain at least one item`

Add at least one changelog item for the current version.

`Entry file must be included in package files`

The selected `Entry File` is not in `Files List`. Add the file and click `Use Selected`.

`Entry file must be .ms, .mse, or .py`

The selected entry file has an unsupported extension.

`Developer name is required`

Fill `Developer Name` in the `Info` group.

`Package name allows only A-Z, a-z, 0-9, space, hyphen, and underscore`

The package name contains a forbidden character. Remove dots, `@`, slashes, non-English letters, or other unsupported characters.

`Button name allows only A-Z, a-z, 0-9, space, hyphen, and underscore`

The button name contains a forbidden character.

`MZP was not created because log contains errors`

The log contains at least one `[ERROR]`. Fix the error, validate again, and rebuild.

## Minimal Working Package

For the simplest package:

1. Put `maxpkg-packager.ms` into your project root.
2. Run it in 3ds Max.
3. Fill `Package Name`, `Button Name`, `Description`, and `Developer Name`.
4. Generate a GUID.
5. Add an entry `.ms`, `.mse`, or `.py` file to `Files List`.
6. Select that entry file with `Use Selected`.
7. Add one changelog item.
8. Click `Validate`.
9. Click `Build MZP`.

After that, test the final `.mzp` through `Scripting > Run Script...` or by dragging it into a 3ds Max viewport.
