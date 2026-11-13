/*
[INFO]
NAME=MaxPkg Packager
VERSION=2.0.1
AUTHOR=Vasyl Lukianenko
DEV=https://3dground.net
SITE=https://maxpkg.dev
HELP=https://github.com/maxpkg-dev/max-dev-tool
UPDATE=https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/maxpkg-packager.ms
UPDATE_INFO=https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/release/update.json
MANIFEST_VERSION=1

[ABOUT]
Copy this one file into the root folder of your script project and run it in 3ds Max 2022 or newer. =
It builds a MaxPkg-compatible .mzp package for maxpkg.dev. =
Everything it keeps for your project is in the max-package folder next to it. =

[2.0.0]
+ Added: Complete rewrite in Python and Qt: a compact window, a colour log, a quick changelog editor=
+ Added: Safe automatic updates: verified download, one-step switch, automatic rollback to the previous version=
+ Added: MaxPkgPackerApi for AI agents, with or without the window=
+ Added: Installer MaxPkgPackager.mzp: drag it into 3ds Max, choose your project, and it puts this file there=
* Changed: All project files now live in the max-package folder; the files of version 1.x move there automatically=
* Changed: This file is a small launcher; the packager itself lives in your user profile and updates there=
* Changed: Needs 3ds Max 2022 or newer; in older 3ds Max it offers to keep version 1.2.1=

[2.0.1]
* Changed: Every package now includes the MaxPkg install and uninstall windows; they come with the packager=
* Changed: The Setup tab keeps only your own custom scripts: nothing to add or download=

[SCRIPT]
*/

-- MaxPkg Packager launcher: the only file a project needs. Keep it in the root folder of the project you package.
-- It starts the packager installed in your user profile (installing it on the first run), or the source next to it
-- in the packager's own repository. An offline copy (update.json and its maxpkg-packager-app-*.zip next to this
-- file, as in the installer MaxPkgPackager.mzp) installs without the internet when it is newer than the installed one.
-- Set the global MaxPkgPackagerHeadless = true before running this file to load only MaxPkgPackerApi, without the
-- window. The installer sets MaxPkgPackagerSetup = true: the packager then asks which project gets this file.
-- In 3ds Max older than 2022 it offers version 1.2.1 instead (release/maxpkg-packager-1.x.ms, which stays on 1.x).
(
    local projectFolder = getFilenamePath (getThisScriptFileName())
    local updateInfoUrl = "https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/release/update.json"
    local headless = (globalVars.isGlobal #MaxPkgPackagerHeadless) and (MaxPkgPackagerHeadless == true)
    local setup = (globalVars.isGlobal #MaxPkgPackagerSetup) and (MaxPkgPackagerSetup == true)
    local setupSource = if setup then (substituteString (getThisScriptFileName()) "\\" "/") else ""

    local legacyUrl = "https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/release/maxpkg-packager-1.x.ms"
    local installerUrl = "https://github.com/maxpkg-dev/max-dev-tool/releases/latest/download/MaxPkgPackager.mzp"

    -- Puts version 1.2.1 at scriptFile. That copy updates only to itself, so it stays on 1.x. True when it is there.
    fn placeLegacyPackager scriptFile legacyUrl = (
        local downloadedFile = (getDir #temp) + "\\maxpkg-packager-1.x.ms"
        local backupFile = (getDir #temp) + "\\maxpkg-packager-replaced.ms"
        local isDownloaded = false
        try (deleteFile downloadedFile) catch()
        try (
            local servicePointManager = dotNetClass "System.Net.ServicePointManager"
            servicePointManager.SecurityProtocol = servicePointManager.SecurityProtocol.TLS12
            local webClient = dotNetObject "System.Net.WebClient"
            webClient.DownloadFile (legacyUrl + "?time=" + (timestamp() as string)) downloadedFile
            webClient.Dispose()
            isDownloaded = (doesFileExist downloadedFile) and ((getFileSize downloadedFile) > 10000)
        ) catch (
            isDownloaded = false
        )
        if (not isDownloaded) do return false
        local hadScriptFile = doesFileExist scriptFile
        if hadScriptFile do (
            try (deleteFile backupFile) catch()
            if (not (copyFile scriptFile backupFile)) do return false
            setFileAttribute scriptFile #readOnly false
            deleteFile scriptFile
        )
        if (copyFile downloadedFile scriptFile) do return true
        if hadScriptFile do copyFile backupFile scriptFile
        return false
    )

    -- 3ds Max 2022 or newer: the packager is Python 3 + Qt for Python. Older versions are offered 1.2.1 instead.
    local maxRelease = (maxVersion())[1]
    if maxRelease < 24000 then (
        local tooOld = "MaxPkg Packager 2 needs 3ds Max 2022 or newer. This is 3ds Max " + ((1998 + maxRelease / 1000) as string) + "."
        if headless then (
            print (tooOld + " Version 1.2.1 for this 3ds Max: " + legacyUrl)
        ) else (
            local legacyQuestion = tooOld + "\n\nVersion 1.2.1 works in this 3ds Max. Put it in place of this file and start it?\nIt stays on version 1.x and does not update to version 2."
            -- The installer (.mzp) has asked already and sets MaxPkgPackagerLegacyAccepted.
            local legacyAccepted = (globalVars.isGlobal #MaxPkgPackagerLegacyAccepted) and (MaxPkgPackagerLegacyAccepted == true)
            if (legacyAccepted or (queryBox legacyQuestion title:"MaxPkg Packager")) do (
                local scriptFile = getThisScriptFileName()
                if (placeLegacyPackager scriptFile legacyUrl) then (
                    fileIn scriptFile
                ) else (
                    messageBox ("Version 1.2.1 could not be put in place. Check the internet connection, or download it yourself and put it in place of this file:\n" + legacyUrl) title:"MaxPkg Packager"
                )
            )
        )
    ) else (
        -- Version 1.x updates itself to this file and runs it: its old window closes, the new one opens.
        if (globalVars.isGlobal #MaxPkgPackerNewFloater) do try (closeRolloutFloater MaxPkgPackerNewFloater) catch()

        local pythonLines = #(
            "import os, re, sys, json, shutil, tempfile, zipfile, time, urllib.request",
            "PROJECT = '" + (substituteString projectFolder "\\" "/") + "'",
            "UPDATE_URL = '" + updateInfoUrl + "'",
            "HOME = os.path.join(os.environ.get('LOCALAPPDATA') or os.path.expanduser('~'), 'MaxPkgPackager', 'app')",
            "def boot_of(state):",
            "    path = os.path.join(HOME, state['dir'], 'python', 'bootstrap.py')",
            "    return path if os.path.isfile(path) else ''",
            "def read_state():",
            "    try:",
            "        with open(os.path.join(HOME, 'current.json'), encoding='utf-8') as handle:",
            "            return json.load(handle)",
            "    except Exception:",
            "        return None",
            "def fetch(url, destination):",
            "    if url.lower().startswith('http'):",
            "        url += ('&' if '?' in url else '?') + 't=' + str(int(time.time()))",
            "    request = urllib.request.Request(url, headers={'User-Agent': 'MaxPkgPackager'})",
            "    with urllib.request.urlopen(request, timeout=60) as response, open(destination, 'wb') as handle:",
            "        shutil.copyfileobj(response, handle)",
            "def offline_copy():",
            "    try:",
            "        with open(os.path.join(PROJECT, 'update.json'), encoding='utf-8') as handle:",
            "            data = json.load(handle)",
            "        name = os.path.basename(data['payload']['url'])",
            "        payload_file = os.path.join(PROJECT, name)",
            "        if name.startswith('maxpkg-packager-app-') and name.endswith('.zip') and os.path.isfile(payload_file):",
            "            return data, payload_file",
            "    except Exception:",
            "        pass",
            "    return None",
            "def version_of(text):",
            "    return tuple(int(part) for part in re.findall('[0-9]+', str(text))[:3])",
            "def wants_offline(copy, state):",
            "    if not copy:",
            "        return False",
            "    if not state:",
            "        return True",
            "    data = copy[0]",
            "    if version_of(data['version']) != version_of(state.get('version', '')):",
            "        return version_of(data['version']) > version_of(state.get('version', ''))",
            "    return data['payload']['sha256'] != state.get('sha256', '')",
            "def first_install(copy=None):",
            "    work = tempfile.mkdtemp(prefix='maxpkg-first-')",
            "    try:",
            "        if copy:",
            "            data, payload_file = copy",
            "        else:",
            "            info_file = os.path.join(work, 'update.json')",
            "            fetch(UPDATE_URL, info_file)",
            "            with open(info_file, encoding='utf-8') as handle:",
            "                data = json.load(handle)",
            "            payload_file = os.path.join(work, 'payload.zip')",
            "            fetch(data['payload']['url'], payload_file)",
            "        code = os.path.join(work, 'code')",
            "        with zipfile.ZipFile(payload_file) as archive:",
            "            for member in archive.namelist():",
            "                if '..' not in member and (member.startswith('python/maxpkgpackager/core/') or member == 'python/maxpkgpackager/__init__.py'):",
            "                    archive.extract(member, code)",
            "        sys.path.insert(0, os.path.join(code, 'python'))",
            "        from maxpkgpackager.core import updater",
            "        info = updater.UpdateInfo(str(data['version']), data['payload']['url'], data['payload']['sha256'])",
            "        updater.install_payload(HOME, info, payload_file)",
            "    finally:",
            "        sys.path = [item for item in sys.path if not item.startswith(work)]",
            "        for name in [n for n in sys.modules if n == 'maxpkgpackager' or n.startswith('maxpkgpackager.')]:",
            "            del sys.modules[name]",
            "        shutil.rmtree(work, ignore_errors=True)",
            "def run():",
            "    source = os.path.join(PROJECT, 'maxpkg-src', 'python')",
            "    boot = ''",
            "    if os.path.isfile(os.path.join(source, 'maxpkgpackager', '__init__.py')) and os.path.isfile(os.path.join(source, 'bootstrap.py')):",
            "        boot = os.path.join(source, 'bootstrap.py')",
            "    if not boot:",
            "        state = read_state()",
            "        boot = boot_of(state) if state else ''",
            "        copy = offline_copy()",
            "        if wants_offline(copy, state if boot else None):",
            "            first_install(copy)",
            "            state = read_state()",
            "            boot = boot_of(state) if state else ''",
            "        if not boot:",
            "            first_install()",
            "            state = read_state()",
            "            boot = boot_of(state) if state else ''",
            "    if not boot:",
            "        raise RuntimeError('MaxPkg Packager is not installed')",
            "    os.environ['MAXPKG_PACKAGER_PROJECT'] = PROJECT",
            "    os.environ['MAXPKG_PACKAGER_HEADLESS'] = '" + (if headless then "1" else "") + "'",
            "    os.environ['MAXPKG_PACKAGER_SETUP'] = '" + setupSource + "'",
            "    with open(boot, encoding='utf-8') as handle:",
            "        source_code = handle.read()",
            "    exec(compile(source_code, boot, 'exec'), {'__file__': boot, '__name__': '__maxpkg_bootstrap__'})",
            "run()"
        )

        local pythonSource = stringStream ""
        for pythonLine in pythonLines do format "%\n" pythonLine to:pythonSource

        try (
            python.Execute (pythonSource as string)
            -- The automation API for agents and scripts: MaxPkgPackerApi.ping(), .setOption, .build() ...
            global MaxPkgPackerApi = python.import "maxpkgpackager_api"
        ) catch (
            local failure = getCurrentException()
            if headless then (
                print ("MaxPkg Packager could not start: " + failure + " Installer: " + installerUrl)
            ) else (
                messageBox ("MaxPkg Packager could not start.\n\nThe first launch on a computer installs the packager from the internet once: check the connection and run this file again.\n\nIf the problem stays, download the installer again and drag it into a viewport:\n" + installerUrl + "\nYour projects and their settings (the max-package folder) are kept.\n\n" + failure) title:"MaxPkg Packager"
            )
        )
    )
)
