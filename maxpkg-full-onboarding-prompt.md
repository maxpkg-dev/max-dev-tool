# MaxPkg Full Onboarding Prompt

Use this prompt with Codex or Claude Code when you want an AI coding agent to prepare an existing 3ds Max project for MaxPkg from start to finish. The agent should adapt the code, configure MaxPkg Packager, build and verify the package, prepare the marketplace content, and leave only the account-specific upload steps for you.

~~~text
Prepare this existing 3ds Max script/project for a complete release through MaxPkg.

Reference:
Use the MaxPkg Packager repository, its README, the adaptation prompt, and its standard hook files as the source of truth:
https://github.com/maxpkg-dev/max-dev-tool

Primary goal:
Deliver a release-ready MaxPkg project and a validated .mzp package. Complete the MaxPkg Packager configuration, prepare all marketplace text and visual guidance, and give me exact final upload instructions for maxpkg.dev. I should not need to investigate package metadata, rewrite descriptions, or determine what to upload myself.

Working rules:
- Read the complete project before editing anything.
- Follow the repository's coding rules and existing code style.
- Preserve the script's runtime behavior, settings, user data, licensing behavior, and important compatibility logic.
- Use MaxPkg as the installation system. Replace obsolete installation assumptions instead of keeping a parallel legacy installer.
- Do not commit, push, publish, or upload anything.
- Do not expose secrets, API keys, private URLs, customer data, or local credentials.
- Do not invent legal claims, license terms, URLs, supported 3ds Max versions, test results, or product capabilities.
- Ask only for information that cannot be safely determined from the project. Group unavoidable questions together and continue with every non-blocked task.

Phase 1: Audit the project
1. Read all relevant source files, existing installers, uninstallers, macros, startup scripts, callbacks, icons, documentation, version headers, and release notes.
2. Identify the real entry file, optional secondary entry files, generated macros, Quad Menu requirements, startup behavior, custom install work, and custom uninstall cleanup.
3. Find hard-coded paths and installation assumptions that will break when the package is extracted to $temp\<packageGuid>.
4. Identify files that belong in the package and files that must be excluded, such as source archives, old installers, build output, caches, tests, private notes, and credentials.
5. Summarize the migration risks before making broad behavioral changes.

Phase 2: Adapt the project to MaxPkg
1. Make project paths dynamic. Resolve files relative to the currently executing script with getFilenamePath (getThisScriptFileName()) or the appropriate equivalent.
2. Preserve existing runtime features while removing assumptions about a fixed source or installation folder.
3. Use the standard MaxPkg _install.ms and _uninstall.ms hooks when package lifecycle UI or cleanup is needed.
4. Move only genuinely project-specific work into custom install or uninstall scripts, such as registering callbacks, copying required external resources, or removing startup files and callbacks.
5. Make custom hooks safe, idempotent where practical, and silent when called by MaxPkg Runtime in silent mode.
6. Ensure uninstall removes package-owned callbacks, startup files, generated integration files, and other resources without deleting unrelated user data.

Phase 3: Prepare the project root
1. Place maxpkg-packager.ms in the project root if it is not already present.
2. Add the standard _install.ms and _uninstall.ms files when required by the current MaxPkg workflow.
3. Prepare a square SVG package icon. Reuse or carefully adapt an existing official project icon when possible. Do not invent a misleading brand identity.
4. Keep custom install and uninstall scripts separate from ordinary package files when the packager provides dedicated fields for them.
5. Remove obsolete package inputs only when they are clearly replaced and safe to remove. Do not delete author source files merely because they are not packaged.

Phase 4: Configure MaxPkg Packager completely
Fill the project's MaxPkg Packager settings and related INI data with values supported by evidence in the project.

Do not stop at recommending field values. Apply them to the project-local packager settings and versioned changelog files using the formats already implemented by MaxPkg Packager. If direct configuration is genuinely impossible, explain the blocker and provide the exact remaining field values in one compact table.

Info:
- Package Name
- Button Name
- Package GUID: preserve an existing valid GUID; generate one only when this is a genuinely new package
- Short Description
- Developer Name
- License
- License URL, Documentation URL, Homepage URL, Support URL, and Purchase URL when known
- Purchase button label that matches the purpose of the purchase URL

Setup:
- Create 3ds Max Button
- Show In MaxPkg Toolbar
- Standard install and uninstall hooks
- Custom install and uninstall scripts, when required

Files:
- Complete package file list
- Output folder
- Square SVG icon
- Entry file
- .ms to .mse compilation where appropriate
- Build Path Remap rules when source folders must be flattened or moved in the package
- Extra macros for additional .ms, .mse, or .py entry points
- Quad Menu options only where they are useful and supported

Release:
- Semantic version
- Release channel
- Release date in YYYY-MM-DD format
- Minimum supported 3ds Max version based on real compatibility evidence
- At least one clear changelog item for the current version

Do not leave required values as placeholders. If a required fact cannot be established, ask me for that specific fact and explain why it cannot be inferred safely.

Phase 5: Validate and build
1. Run or reproduce the packer's validation checks.
2. Resolve missing files, duplicate custom hooks, invalid paths, invalid metadata, missing changelog entries, unsupported entry files, remap conflicts, macro conflicts, and required icon or license issues.
3. Build the final .mzp with MaxPkg Packager.
4. Inspect the archive contents and generated manifests.
5. Confirm the archive filename, package GUID, version, entry file, hooks, changelog, icon, macros, and path remaps match the configured release.
6. Do not report the package as ready while validation errors remain.

Phase 6: Test the package
When 3ds Max is available, test the actual .mzp in a suitable 3ds Max environment:
- installation completes;
- the main script launches;
- generated toolbar macros launch the correct files;
- the package icon renders correctly;
- optional custom install work completes;
- Quad Menu entries appear after any required restart;
- uninstall runs silently when requested by MaxPkg Runtime and removes package-owned integrations;
- reinstall or update preserves user settings where expected.

If 3ds Max or UI automation is unavailable, complete every static and archive-level check possible. Do not claim that runtime testing passed. State the exact untested steps and provide the shortest manual verification checklist.

Phase 7: Prepare the marketplace listing
Create maxpkg-marketplace-listing.md in the project root. It must contain ready-to-use content, not planning notes:
- Package name
- Recommended marketplace category
- One-sentence summary
- Short description
- Full description in clean Markdown
- Feature list
- Requirements and compatibility
- License information
- Developer name
- Homepage, documentation, support, license, and purchase links that actually exist
- Current version, release channel, and release date
- Current-version changelog
- Suggested search tags or keywords
- Cover image recommendation
- Screenshot checklist
- Suggested screenshot titles and captions
- Final .mzp filename and full local path
- Package GUID

Full description requirements:
- Explain what the script does, who it is for, and the practical problem it solves.
- Describe the primary workflow and important features in plain English.
- Include requirements, compatibility, and any meaningful limitations.
- Avoid unsupported marketing claims, filler, internal implementation details, and duplicated short-description text.
- Keep the tone clear, human, and useful to a 3ds Max user.

Category selection:
- If browser access is available, inspect the current category choices in the Create Package form on maxpkg.dev and select the best real category.
- If the live choices cannot be inspected, provide the strongest category recommendation and clearly mark it for confirmation instead of inventing a category.

Visual assets:
- Ensure the package icon is a square SVG and remains legible at small sizes.
- Recommend or prepare a marketplace cover image that represents the actual tool.
- Use real screenshots of the script UI, workflow, or result. Do not use unrelated stock images.
- Treat the first screenshot as the strongest cover-style product view.
- Give every screenshot a concise title and useful caption.
- Remove private paths, license keys, email addresses, customer data, and unrelated desktop clutter from screenshots.
- If screenshots cannot be captured automatically, provide an exact shot list describing what screen to open, what state to show, and what each caption should say.

Phase 8: Give exact upload instructions
At the end, give me a short numbered checklist using the content and files you prepared:
1. Open https://maxpkg.dev and sign in or register.
2. Open https://maxpkg.dev/account.
3. If no developer profile exists, click Become a Developer and complete it.
4. Open https://maxpkg.dev/dashboard/packages.
5. Create a package and fill its fields from maxpkg-marketplace-listing.md.
6. Use the recommended category after confirming it exists in the form.
7. Add the package icon, cover image, and screenshots with the prepared titles and captions.
8. Open the package's Versions tab.
9. Upload the exact final .mzp file identified in the listing document.
10. Review the package preview, verify the GUID and version, and submit it for administration review.
11. Explain that the package is published after administration approves the submitted file.

Final response format:
1. What was adapted.
2. MaxPkg configuration completed.
3. Validation and build result.
4. Runtime tests performed and any remaining manual checks.
5. Exact path to the final .mzp.
6. Exact path to maxpkg-marketplace-listing.md.
7. Any facts I still need to confirm.
8. The numbered maxpkg.dev upload checklist.

Completion standard:
The task is complete only when the project is adapted, MaxPkg Packager is configured, validation passes, the .mzp exists, available tests are complete, marketplace content is ready to paste, visual requirements are covered, and only account-specific actions on maxpkg.dev remain for me.
~~~