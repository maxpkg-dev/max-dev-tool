"""MaxPkg Packager: a Python + Qt tool for 3ds Max. Importing this package is passive: it creates no windows and touches no scene.

Identity and links live here once; the title bar, About, Settings and Donate buttons read them.
"""

__version__ = "2.0.2"
TOOL_NAME = "MaxPkgPackager"  # Identifier: names the %LOCALAPPDATA% folder, log and launcher file.
DISPLAY_NAME = "MaxPkg Packager"  # Human-readable title (added to the template: title bars, dialogs, messages).
SUBTITLE = "Build clean MaxPkg .mzp packages for 3ds Max"
DEVELOPER = "Vasyl Lukianenko"  # Public name; About leaves out empty values (never invent them).
LINKS = (("maxpkg.dev", "https://maxpkg.dev"), ("GitHub", "https://github.com/maxpkg-dev/max-dev-tool"))  # (label, https URL) pairs shown in About.
DONATE_URL = ""  # Only a destination the owner gave; "" hides every Donate button.
UPDATE_URL = "https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/release/update.json"  # Made by maxpkg-src/tools/release.py
