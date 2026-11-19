/*

	MAXPKG PACKAGE UNINSTALLER

	Removes the package that this file belongs to. The work is done by _install.ms next to it (one installer for
	installing and removing, see that file): this file only asks it to remove the package.

	- With MaxPkg Manager (the MaxPkg global exists), it runs the package's Custom Uninstall Script; the Manager
	  removes the rest.
	- Without it, it opens the package's installer window on its Uninstall page.

	For work that is special to your tool, choose a Custom Uninstall Script in MaxPkg Packager instead of editing
	this file: it runs before the package files are removed.

*/

(
	local maxPkgHookEngine = (getFilenamePath (getSourceFileName())) + "_install.ms"
	if (doesFileExist maxPkgHookEngine) then (
		global MaxPkgHookRequest = "uninstall"
		fileIn maxPkgHookEngine
	) else (
		local maxPkgHookMessage = "This package cannot be removed here: its installer (_install.ms) is missing from its folder.\n\nInstall the package again, then remove it."
		if (MaxPkg != undefined) then throw maxPkgHookMessage else messageBox maxPkgHookMessage title: "MaxPkg"
	)
)
