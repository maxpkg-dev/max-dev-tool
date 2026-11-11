# MaxPkg Adaptation Prompt

Use this prompt when you want Codex to adapt an existing 3ds Max script or project to the standard MaxPkg installation flow.

```text
Adapt this existing 3ds Max script/project for installation and distribution through MaxPkg.

Reference:
Use the MaxPkg Packager project, its documentation, and its standard installer files as the compatibility reference:
https://github.com/maxpkg-dev/max-dev-tool

Goal:
Replace the author's installation flow with the standard MaxPkg installation flow. Preserve the tool's runtime behavior, features, settings, and user data, but do not preserve, execute, chain, or package the author's installer or uninstaller.

Installation policy:
- MaxPkg is the only supported installation system for the adapted package.
- Use the standard MaxPkg `_install.ms` and `_uninstall.ms` files without replacing their implementation with the author's installer code.
- Do not call the author's complete installer or uninstaller with `fileIn`, `include`, `execute`, shell commands, or any other mechanism.
- Do not add a standalone fallback installation mode.
- Do not add `MaxPkg == undefined` branches that run the author's installation logic.
- Do not include obsolete author installer launchers in the package.
- Do not duplicate work already performed by `mzp.run.ms`, including MaxPkg notification, package icon installation, and generated macro creation.

Migration process:
1. Read the complete project before editing.
2. Identify the runtime entry file, supporting scripts, icons, resources, settings, macros, startup files, and the original install/uninstall scripts.
3. Inspect the original installer only to understand which files and setup steps the tool previously required. Never use the complete legacy installer as part of the final installation flow.
4. Classify every original installer action:
   - Package file deployment: add the required files to the MaxPkg Files List and preserve their relative layout.
   - Macro or toolbar creation: configure the main button and extra macros through MaxPkg Packager.
   - Icon installation: use the package SVG icon and MaxPkg-generated macro handling.
   - Runtime initialization: move essential initialization into the runtime entry code or a focused helper loaded by the entry code.
   - Package-owned settings: initialize them lazily inside the installed package runtime root. An INI next to the installed entry file is valid and recommended when it belongs only to that package. Preserve existing settings during updates.
   - Shared or durable user data: use a separate writable 3ds Max user folder only when the data is deliberately shared, user-authored, or expected to survive package removal.
   - Essential custom setup or cleanup: extract only the focused actions that MaxPkg cannot perform automatically into small `.ms` scripts, then select them as `Custom Install Script` or `Custom Uninstall Script` in Setup. Examples include registering or removing callbacks.
   - Obsolete installation-only work: remove it.
5. Make the packaged runtime fully usable immediately after the standard MaxPkg installation completes.

Paths and package layout:
- MaxPkg extracts a package into `$temp\<packageGuid>`. Treat that folder as the package runtime root.
- Review all author scripts for hardcoded paths, assumptions about the original source folder, and fragile relative file access.
- Resolve files relative to the script that owns them, for example:

  local scriptDir = getFilenamePath (getThisScriptFileName())
  local helperFilePath = scriptDir + "helpers\\tool-helper.ms"

- If `getThisScriptFileName()` is unreliable in a specific execution context, use the safest context-appropriate equivalent, such as `getSourceFileName()`.
- Use the installed entry script as the path anchor for package-owned INI files and resources. It is valid to create and update an INI beside the installed entry file when that setting belongs to the package.
- Use `getDir` locations only for data that deliberately belongs outside the package runtime root, such as shared data or user-authored content that must survive package removal.
- Do not hardcode a package GUID, a user name, a 3ds Max version, `$temp` subfolder, drive letter, or machine-specific absolute path.
- Preserve relative subfolders unless a MaxPkg Build Path Remap is intentionally configured.
- Make sure paths still work after `.ms` files are compiled to `.mse` and after Build Path Remap is applied.

Runtime requirements:
- Preserve the author's actual tool behavior, not the author's installation method.
- The selected entry file must launch the tool directly from the installed MaxPkg package without first running the old installer.
- Required resources must be included in the package and resolved dynamically.
- Keep package-owned resources and mutable settings inside `$temp\<packageGuid>` so uninstall can remove the complete package by deleting its verified runtime root instead of searching for files scattered through the system.
- Optional files must remain optional and must not produce errors when absent.
- Do not delete or overwrite existing user settings during installation or update.
- Do not introduce destructive uninstall behavior copied from the author's uninstaller.
- Use the MaxPkg Packager for the main macro, extra macros, button labels, SVG icon, changelog, version metadata, and Build Path Remap.
- Keep custom install and uninstall scripts inside the project root. Do not add them to the Files List; the packager includes them automatically and records their packaged paths in the manifest.
- The package SVG icon must be square.

Validation:
- Confirm that no code path can launch the author's complete installer or uninstaller.
- Confirm that obsolete author installer files are not included in the final Files List or archive.
- Confirm that each selected custom script contains only the required additional actions and runs correctly from the installed `$temp\<packageGuid>` folder.
- Confirm that the entry file and every generated macro work from `$temp\<packageGuid>`.
- Confirm that required resources use dynamic paths.
- Confirm that a clean MaxPkg installation works without any previous installation of the tool.
- Confirm that updating the package preserves user settings.
- Build and test the MZP in 3ds Max before considering the adaptation complete.

Expected output:
- Explain what the original installer used to do.
- Explain how each required action is now handled by MaxPkg or by the adapted runtime code.
- List all files added, changed, excluded, or replaced.
- Identify any original installer behavior that was intentionally removed.
- Report the validation and test results.
- Mention assumptions or remaining risks.
- Do not commit or push changes.
```
