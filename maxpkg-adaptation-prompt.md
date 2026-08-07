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
- Do not call the author's installer or uninstaller with `fileIn`, `include`, `execute`, shell commands, or any other mechanism.
- Do not add a standalone fallback installation mode.
- Do not add `MaxPkg == undefined` branches that run the author's installation logic.
- Do not include obsolete author installer launchers in the package.
- Do not duplicate work already performed by `mzp.run.ms`, including MaxPkg notification, package icon installation, and generated macro creation.

Migration process:
1. Read the complete project before editing.
2. Identify the runtime entry file, supporting scripts, icons, resources, settings, macros, startup files, and the original install/uninstall scripts.
3. Inspect the original installer only to understand which files and setup steps the tool previously required. Never use it as part of the final installation flow.
4. Classify every original installer action:
   - Package file deployment: add the required files to the MaxPkg Files List and preserve their relative layout.
   - Macro or toolbar creation: configure the main button and extra macros through MaxPkg Packager.
   - Icon installation: use the package SVG icon and MaxPkg-generated macro handling.
   - Runtime initialization: move essential initialization into the runtime entry code or a focused helper loaded by the entry code.
   - User settings: initialize them lazily in an appropriate writable 3ds Max user folder. Preserve existing settings during updates.
   - Obsolete installation-only work: remove it.
5. Make the packaged runtime fully usable immediately after the standard MaxPkg installation completes.

Paths and package layout:
- MaxPkg extracts a package into `$temp\<packageGuid>`. Treat that folder as the package runtime root.
- Review all author scripts for hardcoded paths, assumptions about the original source folder, and fragile relative file access.
- Resolve files relative to the script that owns them, for example:

  local scriptDir = getFilenamePath (getThisScriptFileName())
  local helperFilePath = scriptDir + "helpers\\tool-helper.ms"

- If `getThisScriptFileName()` is unreliable in a specific execution context, use the safest context-appropriate equivalent, such as `getSourceFileName()`.
- Use `getDir` locations only for data that genuinely belongs in a 3ds Max user folder, such as settings or user-generated data.
- Do not hardcode a package GUID, a user name, a 3ds Max version, `$temp` subfolder, drive letter, or machine-specific absolute path.
- Preserve relative subfolders unless a MaxPkg Build Path Remap is intentionally configured.
- Make sure paths still work after `.ms` files are compiled to `.mse` and after Build Path Remap is applied.

Runtime requirements:
- Preserve the author's actual tool behavior, not the author's installation method.
- The selected entry file must launch the tool directly from the installed MaxPkg package without first running the old installer.
- Required resources must be included in the package and resolved dynamically.
- Optional files must remain optional and must not produce errors when absent.
- Do not delete or overwrite existing user settings during installation or update.
- Do not introduce destructive uninstall behavior copied from the author's uninstaller.
- Use the MaxPkg Packager for the main macro, extra macros, button labels, SVG icon, changelog, version metadata, and Build Path Remap.
- The package SVG icon must be square.

Validation:
- Confirm that no code path can launch the author's installer or uninstaller.
- Confirm that author installer files are not included in the final Files List or archive.
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
