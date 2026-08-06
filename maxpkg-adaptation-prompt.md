# MaxPkg Adaptation Prompt

Use this prompt when you want Codex to adapt an existing 3ds Max script or project for MaxPkg packaging while preserving the original installation behavior.

```text
Adapt this 3ds Max script/project for MaxPkg packaging without breaking the original installation logic.

Reference:
Use the MaxPkg Packager project as the compatibility reference:
https://github.com/maxpkg-dev/max-dev-tool

Goal:
The script must work in two installation modes:

1. MaxPkg mode:
   If MaxPkg Runtime is available during installation, the package should install cleanly as a MaxPkg package.
   MaxPkg should be notified after installation, so it can scan the package, rebuild its toolbar, and update the manager UI.

2. Standalone/original mode:
   If MaxPkg Runtime is not available, the script must continue to install exactly as the original author intended.
   Do not remove, bypass, or rewrite the original install behavior unless it is strictly required for compatibility.

Rules:
- Read the project first before editing.
- Identify the original entry file, install script, uninstall script, macroscript files, icons, and any user folders used by the script.
- Preserve the original install/uninstall behavior.
- Add MaxPkg compatibility as a wrapper or additional path, not as a replacement for the author's logic.
- Do not assume MaxPkg exists.
- Always guard MaxPkg calls:

  try (
      if (MaxPkg != undefined and isProperty MaxPkg #packageInstalled) do (
          MaxPkg.packageInstalled packageGuid
      )
  ) catch()

- If the original installer creates macros, toolbar buttons, icons, user files, startup scripts, or copies files into 3ds Max folders, keep that behavior for standalone mode.
- If MaxPkg mode handles part of the installation, make sure the original fallback still works when MaxPkg is missing.
- MaxPkg packages are extracted into a temporary package folder, usually `$temp\<packageGuid>`. This can break scripts that assume they are running from the original source folder or from a fixed install folder.
- Review author scripts for fragile path logic, hardcoded project paths, and relative file access.
- When a script needs to load files next to itself, prefer dynamic script-local paths, for example: local scriptDir = getFilenamePath (getThisScriptFileName())

- If `getThisScriptFileName()` is not reliable in a specific context, use the safest equivalent for that context, such as `getSourceFileName()` inside loaded installer scripts.
- Update path handling only where needed for package compatibility. Do not rewrite unrelated author logic.
- Do not hardcode user-specific paths.
- Use getDir paths where appropriate, such as #userMacros, #userIcons, #userStartupScripts, #scripts, #temp.
- Keep package files relative to the project root where possible.
- Do not generate destructive uninstall behavior unless the original project already had it.
- Do not delete user settings during update/install unless the original script explicitly does so.
- If a file is optional, do not show errors when it is missing.
- If changing macroScript generation, make sure icon paths are valid for the current 3ds Max profile.
- SVG icons should be copied to getDir #userIcons when needed.
- Make the final package installable by MaxPkg, but also runnable without MaxPkg.

Expected output:
- Explain what the original installer does.
- Explain what changes were made for MaxPkg compatibility.
- List any files that were added or changed.
- Mention any assumptions.
- Do not commit or push changes.
```

