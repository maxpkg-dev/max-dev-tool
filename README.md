# MaxPkg Packager

`maxpkg-packager.ms` helps 3ds Max developers build clean MaxPkg-compatible `.mzp` packages.

Put the packager into the root folder of your script project, run it in 3ds Max, fill in the package information, add your files, choose the entry file, and build the final `.mzp` archive.

The script keeps its settings next to your project, so every package can have its own metadata, changelog, icon, and build output.

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

1. Download or copy `maxpkg-packager.ms`.
2. Put it into the root folder of your own project.
3. Open 3ds Max.
4. Run `maxpkg-packager.ms` from `Scripting > Run Script...`, or drag it into a viewport.
5. Fill the required fields in the packager window.
6. Add your package files.
7. Select an entry file and click `Use Selected`.
8. Add at least one changelog item for the current version.
9. Fix anything shown by the `Has Issues` status.
10. Click `Build MZP`.

The package will be created in the output folder. By default, that is:

```text
<project-root>\dist
```

## Project Folder

The folder that contains `maxpkg-packager.ms` is treated as the package root.

Example:

```text
MyTool\
  maxpkg-packager.ms
  main.ms
  helpers\
    ui.ms
  data\
    presets.json
```

Keep one copy of `maxpkg-packager.ms` inside each project you package. This keeps the project settings, changelog, icon, and optional install scripts nicely separated.

## Files Created By The Packager

The packager may create these files next to `maxpkg-packager.ms`:

- `maxpkg-packager.ini` - saved project settings.
- `maxpkg-changelog.ini` - changelog entries, grouped by version.
- `maxpkg-icon.svg` - the selected icon copied into the project root.
- `install.ms` - optional install hook if you create the sample.
- `uninstall.ms` - optional uninstall hook if you create the sample.
- `dist\*.mzp` - built package archives.

You do not need to add `maxpkg-packager.ini` or `maxpkg-changelog.ini` manually. The packager handles its own internal files.

## Interface Overview

The packager uses four tabs:

- `1. Info` - package identity, description, developer, and license.
- `2. Setup` - macro button, toolbar metadata, and sample install scripts.
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

This field is required and is written into the manifest. It is also shown by the sample install window.

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

## 2. Setup

### Create 3ds Max Button

When enabled, the package creates a macro button during installation.

The generated macro is created for the current 3ds Max user profile, so it uses the correct local user macro and icon folders on the machine where the package is installed.

### Show In MaxPkg Toolbar

This saves toolbar metadata into the manifest.

If MaxPkg is loaded during installation, the installer tries to refresh the toolbar automatically.

### Sample install.ms

Creates a sample `install.ms` in the project root if it does not already exist.

The sample install script shows an `Install Complete` window with useful package information from the manifest, including version, release date, description, and the latest changelog.

You can keep the sample as-is or replace it with your own install code.

### Sample uninstall.ms

Creates a sample `uninstall.ms` in the project root if it does not already exist.

The sample uninstall script only shows a simple message that the package has been removed. You can replace it with your own uninstall code if needed.

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
install.ms          optional
uninstall.ms        optional
icons\icon.svg
<your package files>
```

`manifest.ini` and `manifest.json` contain the package metadata.

`mzp.run` is the native 3ds Max MZP command file.

`mzp.run.ms` runs during installation. It reads the manifest, creates the optional macro button, installs the icon, runs `install.ms` if it exists, and refreshes MaxPkg toolbar when possible.

## Testing The Package

After building, test the `.mzp` before uploading it.

In 3ds Max:

1. Use `Scripting > Run Script...` and select the `.mzp`, or drag the `.mzp` into a viewport.
2. If you enabled the macro button, check that it appears in the `MaxPkg` category.
3. Click the generated button and make sure your entry file runs.
4. Check that the icon appears correctly.
5. If you created `install.ms`, make sure the install message looks right.

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
