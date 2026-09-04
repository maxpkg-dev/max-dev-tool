# Recommended MaxScript Coding Rules

These rules provide a practical baseline for writing maintainable and predictable MaxScript code. They can be used by developers and shared with AI coding agents such as Codex or Claude Code.

They are recommendations for general MaxScript projects, not only for MaxPkg packages. Existing project conventions take priority when they are stricter.

## Core Principles

- Read the existing project before changing its architecture or naming style.
- Prefer clear, explicit code over compact code with hidden behavior.
- Keep changes focused on the requested feature.
- Preserve existing runtime behavior unless a behavioral change is intentional.
- Do not silently remove compatibility logic, user settings, callbacks, startup integration, or cleanup behavior.
- Validate assumptions in the supported 3ds Max versions whenever possible.

## Safe Identifiers

MaxScript identifiers are case-insensitive. A user-defined identifier can collide with a built-in symbol, rollout clause, property, type, or context-sensitive keyword even when the capitalization is different.

Do not introduce these ambiguous identifiers for local variables, global variables, function parameters, loop variables, struct fields, rollout locals, or control aliases:

- `path`
- `text`
- `name`
- `section`
- `icon`
- `ok`
- `value`

This list is a minimum, not a complete list of every MaxScript symbol. Avoid any short generic identifier that already has a system meaning or makes the code difficult to search.

Use descriptive alternatives:

| Avoid | Prefer |
| --- | --- |
| `path` | `filePath`, `folderPath`, `sourcePath` |
| `text` | `textContent`, `messageContent`, `descriptionContent` |
| `name` | `packageName`, `displayName`, `fileName` |
| `section` | `iniSection`, `sectionName` |
| `icon` | `iconFilePath`, `iconBitmap` |
| `ok` | `isSuccess`, `isConfirmed`, `isValid` |
| `value` | `currentValue`, `settingValue`, `resultValue` |

Avoid:

~~~maxscript
local ok = 15
local path = getDir #temp
fn saveValue value = (...)
~~~

Prefer:

~~~maxscript
local retryCount = 15
local tempFolderPath = getDir #temp
fn saveSetting settingValue = (...)
~~~

Additional naming rules:

- Name booleans as questions or states: `isReady`, `hasErrors`, `shouldCompile`.
- Use meaningful collection names: `packageFiles`, `validationErrors`.
- Do not create identifiers that differ only by capitalization.
- Do not give a struct type and a function or variable nearly identical names. Use an explicit suffix such as `Data`, `State`, or `Result` for data structures.
- Short variables such as `i` are acceptable for small numeric loops. Use descriptive names when the loop body is not trivial.

## Functions And Returns

- Use an explicit `return` when a function produces a result.
- Do not rely on the last expression as an implicit return value.
- Return `true` or `false` explicitly from functions that report success.
- Use early guard returns when they make a function easier to read.
- Keep functions focused on one responsibility.
- Avoid long argument lists. Group related inputs in a small data struct.
- Do not hide required state in unrelated globals when it can be passed as an argument.

Example:

~~~maxscript
fn isExistingFile filePath = (
	if (filePath == undefined or filePath == "") do return false
	if (not doesFileExist filePath) do return false
	return true
)
~~~

## Scope And State

- Declare temporary variables with `local`.
- Keep globals limited to state that genuinely must be shared, such as manager instances or rollout references.
- Prefix project globals consistently to reduce collisions with other installed scripts.
- Do not create a global merely to avoid passing an argument.
- Keep UI state separate from processing state.
- Do not mutate saved UI settings to control one temporary operation. Use a local runtime flag.
- Initialize state explicitly instead of depending on an earlier script execution.

## Named Arguments

For function keyword arguments, rollout options, and UI control parameters:

- Write exactly one space after `:`.
- Do not put a space before `:`.
- Use `argumentName: argumentValue`.

Example:

~~~maxscript
dotNetControl dncTabs "System.Windows.Forms.TabControl" width: 260 height: 20 align: #left across: 2 offset: [-10, 0]
local versionParts = parseVersionParts versionContent defaultContent: "1.0.0"
~~~

## Strings

- Never use `format` for string concatenation.
- Use `+` to combine strings.
- Convert non-string data explicitly when needed.
- Use `format` only for intentional formatted output to a stream or the Listener.
- Be especially careful when generating MaxScript source code as strings. Escaping must be obvious and testable.
- Keep user-facing content separate from generated source code when practical.

Example:

~~~maxscript
local packageFolderPath = (getDir #temp) + "\\" + packageGuid + "\\"
local errorMessage = "Package file was not found:\n" + missingFilePath
~~~

## Files And Paths

- Build paths dynamically from the executing script or a documented 3ds Max directory.
- Use `getFilenamePath (getThisScriptFileName())` when project files must be resolved relative to the current script.
- Do not hard-code developer machine paths.
- Normalize paths only at clear boundaries.
- Check that a required file exists before opening, executing, copying, or deleting it.
- Distinguish source paths, package-relative paths, output paths, and installed paths in variable names.
- Keep path separators correct for the API receiving the path.
- Treat archive extraction directories as dynamic.
- For an installed MaxPkg package, derive the runtime root from the executing entry script, for example `getFilenamePath (getThisScriptFileName())`.
- Keep package-owned helpers, resources, and mutable settings inside that runtime root so they share one ownership and uninstall boundary.
- Use a separate 3ds Max user-data folder only for shared or user-authored data that is intentionally expected to survive package removal.
- Clean up temporary files and build folders when ownership is clear.

## Structures And Data

Use a `struct` when several related values describe one logical object.

Good uses include package metadata, validation results, file mappings, build options, UI state, and operation results.

- Give the struct a meaningful type name.
- Prefer named struct arguments at construction sites.
- Keep data structs focused on data.
- Avoid parallel arrays and undocumented numeric indexes.
- Do not turn a temporary data container into a large manager without a clear reason.
- Use explicit suffixes such as `Data`, `State`, and `Result`.

Example:

~~~maxscript
struct PackageFileData (
	sourceFilePath,
	relativeFilePath,
	shouldCompile
)

local packageFile = PackageFileData \
	sourceFilePath: selectedFilePath \
	relativeFilePath: selectedRelativePath \
	shouldCompile: false
~~~

## Loops And Collections

- Use `for i in 1 to itemCount do (...)` for numeric ranges.
- Do not use the assignment-style form `for i = 1 to itemCount do (...)`.
- Check collection bounds before indexing.
- Prefer named fields over expressions such as `item[1]`, `item[2]`, and `item[3]`.
- Do not modify a collection while iterating over it unless the behavior is deliberate and safe.
- When deleting selected items, process indexes in descending order.

## Error Handling

- Use `try/catch` only when the fallback behavior is understood.
- Do not use empty catches around required operations.
- Preserve the original error message when reporting a failure.
- Stop the current operation when continuing could create incomplete output or delete the wrong files.
- Optional integrations may fail without stopping the main feature, but the failure should be logged when useful.
- Keep the code inside `catch` compatible with MaxScript syntax.
- Rethrow with `throw()` when required; do not pass unsupported arguments to `throw`.
- Avoid broad exception handling around large blocks when smaller failure boundaries are available.

## Logging And Validation

- Use clear messages that identify the failed operation and relevant field or file.
- Distinguish errors, warnings, and successful operations.
- Do not report success before all required work is complete.
- Validate required metadata before building or publishing output.
- If any validation error exists, prevent the destructive or release operation.
- Point users to the relevant UI area when reporting a validation problem.
- Avoid opening intrusive log windows for routine successful actions.

## INI, JSON, And Structured Data

- Use standard INI functions such as `getINISetting`, `setINISetting`, and `delINISetting`.
- An INI beside the installed entry file is valid and recommended when it is an intentional package-owned setting. Build its path from the executing script rather than from a developer path or unrelated system folder.
- Save a UI setting when it changes if the project uses automatic persistence.
- Provide safe defaults for missing or invalid settings.
- Use a JSON serializer or a project JSON builder instead of manual JSON concatenation.
- Escape strings correctly.
- Keep field names consistent across settings, manifests, generated files, and runtime readers.
- Preserve backward compatibility when reading older settings when practical.

## UI

- Follow the existing UI structure and visual conventions.
- Prefer rollout layout with `group`, `across`, `align`, and `offset`.
- Avoid `pos:` unless the layout cannot be expressed reliably without it.
- Keep related controls in clearly named groups or rollouts.
- Use consistent control heights and spacing.
- Do not overlap controls or depend on one machine's font metrics.
- Show confirmation before replacing important identifiers or deleting user-selected data.
- Keep destructive actions visually and behaviorally distinct.
- Provide clear empty, disabled, loading, success, warning, and error states.

For .NET text input controls inside 3ds Max:

- Set `enableAccelerators = false` while the user is editing.
- Restore `enableAccelerators = true` on blur, rollout close, and dialog close.
- Preserve `Tab` and `Shift+Tab` navigation between controls.
- Configure multiline controls explicitly with `Multiline`, `AcceptsReturn`, `WordWrap`, and appropriate scroll bars.
- Do not bind the same .NET event repeatedly every time a rollout opens.

## Generated Code And Package Scripts

- Treat generated MaxScript as production code.
- Keep generated lines readable and syntactically complete.
- Validate quoting, newlines, and path separators in the final generated file.
- Do not leave template concatenation fragments inside generated code.
- Resolve installed package files from their runtime location, not from the author's source folder.
- Keep installed package code, private resources, and package-owned settings under the same verified `$temp\<packageGuid>` runtime root. This lets uninstall remove the complete package by deleting one owned folder instead of searching for scattered leftovers.
- Generate version-specific paths only at installation time when they depend on the current 3ds Max profile.
- Make optional hooks optional and required hooks explicit.
- Never delete a folder unless its resolved location has been validated as package-owned.

## Comments And Formatting

- Write comments that explain why a non-obvious block exists.
- Do not narrate self-explanatory assignments.
- Use block comments for substantial examples or replaceable template sections.
- Keep indentation consistent with the surrounding file.
- Keep one space after named-argument colons.
- Avoid unrelated whitespace and metadata churn.
- Prefer ASCII unless the file intentionally uses another character set.

## Verification Checklist

Before finishing a change:

1. Search for obsolete control names, settings keys, generated filenames, and hard-coded paths.
2. Search for forbidden ambiguous identifiers.
3. Check every new function for explicit returns where a result is expected.
4. Verify that required files exist before they are used.
5. Verify generated scripts and manifests as final files, not only as string-building source.
6. Run syntax checks or load the script in supported 3ds Max versions when available.
7. Test both success and failure paths.
8. Confirm that settings survive restart when persistence is expected.
9. Confirm that uninstall and cleanup affect only package-owned files.
10. Run `git diff --check` and review the final diff.
11. Do not claim a runtime test passed when it was not run.

## Instructions For AI Coding Agents

When using these rules with Codex, Claude Code, or another coding agent:

- Ask the agent to read this file before editing MaxScript.
- Ask it to preserve the project's existing behavior and style.
- Require it to inspect generated scripts, manifests, and archives.
- Require it to report tests that were actually run.
- Do not let it silently substitute guessed metadata, legal information, URLs, or compatibility claims.
- Do not let it commit or push unless you explicitly request that action.
