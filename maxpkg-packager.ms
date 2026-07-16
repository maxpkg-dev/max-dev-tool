/*
[INFO]
NAME=MaxPkg Packager
VERSION=1.0.0
AUTHOR=Vasyl Lukianenko
DEV=https://3dground.net
SITE=https://maxpkg.dev
HELP=
UPDATE=https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/maxpkg-packager.ms

[ABOUT]
Drag this script into a 3ds Max viewport from a developer productfolder.=
It builds a universal MaxPkg-compatible .mzp package. =
The package does not install MaxPkg Toolbar or MaxPkg Runtime. =

[1.0.0]
* Initial release =

[FILES]

[SCRIPT]
*/

(
    local scriptPath = getFilenamePath (getThisScriptFilename())
    if (scriptPath == undefined) do scriptPath = (getDir #scripts) + "\\maxpkg-packager.ms"

    local rootDir = scriptPath
    local iniPath = rootDir + "maxpkg-packager.ini"
    local changelogIniPath = rootDir + "maxpkg-changelog.ini"

    local packageFiles = #()
    local changelogItems = #()
    local activeChangelogVersion = "1.0.0"
    local logItems = #()
    local isLoadingSettings = false
    global MaxPkgPackagerFloater
    global MaxPkgPackagerLogRollout
    global MaxPkgUpdateNoticeRollout
    local isLogDialogOpen = false
    local startupUpdateWorker = undefined
    local startupUpdateResult = undefined
    local pendingUpdateScriptFile = ""
    local pendingUpdateNoticeContent = ""

    local showLogWindow
    local refreshLogWindow
    local closeLogWindow
    local confirmGuidChange
    local isGuidChangeConfirmed = false

    fn trimString s tag:" " = (
        if (s == undefined) do return ""

        s = s as string
        return trimLeft (trimRight s tag) tag
    )

    fn lowerString s = (
        if (s == undefined) do return ""
        return toLower (s as string)
    )

    fn normalizePath p = (
        local result = p as string
        result = substituteString result "/" "\\"
        return result
    )

    fn ensureTrailingSlash p = (
        local result = normalizePath p

        if (result.count == 0) do return result
        if ((substring result result.count 1) == "\\") do return result

        return result + "\\"
    )

    fn boolToString v = (
        if (v) do return "true"
        return "false"
    )

    fn stringToBool s defaultValue:true = (
        local boolText = lowerString (trimString s)

        if (boolText == "") do return defaultValue
        return (boolText == "true" or boolText == "1" or boolText == "yes")
    )

    fn getDropDownText ddl = (
        if (ddl.selection < 1) do return ""
        return ddl.items[ddl.selection]
    )

    fn setDropDownText ddl itemText = (
        local index = findItem ddl.items itemText

        if (index > 0) then (
            ddl.selection = index
            return true
        )

        return false
    )

    fn addLog level logMessage = (
        append logItems ("[" + level + "] " + logMessage)
        try (refreshLogWindow()) catch()
        return true
    )

    fn clearLog = (
        logItems = #()
        return true
    )

    fn getLogText = (
        local result = ""

        for i in 1 to logItems.count do (
            result += logItems[i]
            if (i < logItems.count) do result += "\r\n"
        )

        return result
    )

    fn currentScriptFilePath = (
        local currentScriptFile = getThisScriptFileName()
        if (currentScriptFile == undefined or currentScriptFile == "") do currentScriptFile = getThisScriptFilename()
        return currentScriptFile
    )

    struct MaxPkgScriptInfoData (
        scriptTitle,
        versionString,
        authorTitle,
        developerUrl,
        siteUrl,
        helpUrl,
        updateUrl,
        descriptionContent,
        releases
    )

    struct MaxPkgUpdateResultData (
        isUpdated,
        currentVersionString,
        newVersionString,
        releaseNotesContent,
        messageContent,
        scriptFilePath
    )

    fn scriptInfoEntry scriptFilePath infoKey defaultContent:"" = (
        local entryContent = try (getINISetting scriptFilePath "INFO" infoKey) catch("")
        if (entryContent == undefined or entryContent == "") do return defaultContent
        return entryContent
    )

    fn readScriptInfo scriptFilePath releaseInfo:"" = (
        if (releaseInfo != "") do (
            local releaseItems = try (getINISetting scriptFilePath releaseInfo) catch(#())
            return releaseItems
        )

        local descriptionContent = ""
        local aboutItems = try (getINISetting scriptFilePath "ABOUT") catch(#())
        for aboutIndex in 1 to aboutItems.count do (
            descriptionContent += aboutItems[aboutIndex]
            if (aboutIndex < aboutItems.count) do descriptionContent += "\r\n"
        )

        local releaseItems = #()
        local iniSections = try (getINISetting scriptFilePath) catch(#())
        for iniSectionName in iniSections do (
            if (iniSectionName != "INFO" and iniSectionName != "ABOUT" and iniSectionName != "SCRIPT" and iniSectionName != "FILES") do (
                append releaseItems iniSectionName
            )
        )

        local scriptInfo = MaxPkgScriptInfoData()
        scriptInfo.scriptTitle = scriptInfoEntry scriptFilePath "NAME" defaultContent:"MaxPkg Packager"
        scriptInfo.versionString = scriptInfoEntry scriptFilePath "VERSION" defaultContent:"0.0.0"
        scriptInfo.authorTitle = scriptInfoEntry scriptFilePath "AUTHOR" defaultContent:""
        scriptInfo.developerUrl = scriptInfoEntry scriptFilePath "DEV" defaultContent:""
        scriptInfo.siteUrl = scriptInfoEntry scriptFilePath "SITE" defaultContent:""
        scriptInfo.helpUrl = scriptInfoEntry scriptFilePath "HELP" defaultContent:""
        scriptInfo.updateUrl = scriptInfoEntry scriptFilePath "UPDATE" defaultContent:""
        scriptInfo.descriptionContent = descriptionContent
        scriptInfo.releases = releaseItems

        return scriptInfo
    )

    fn versionNumberAt versionParts partIndex = (
        if (partIndex > versionParts.count) do return 0
        return try (versionParts[partIndex] as integer) catch(0)
    )

    fn compareVersionStrings candidateVersion currentVersion = (
        local candidateParts = filterString (candidateVersion as string) "."
        local currentParts = filterString (currentVersion as string) "."

        for versionPartIndex in 1 to 3 do (
            local candidateNumber = versionNumberAt candidateParts versionPartIndex
            local currentNumber = versionNumberAt currentParts versionPartIndex
            if (candidateNumber > currentNumber) do return 1
            if (candidateNumber < currentNumber) do return -1
        )

        return 0
    )

    fn downloadUpdateFile updateUrl targetFilePath = (
        if (updateUrl == undefined or updateUrl == "") do return false
        if (targetFilePath == undefined or targetFilePath == "") do return false

        try (deleteFile targetFilePath) catch()

        try (
            local servicePointManager = dotNetClass "System.Net.ServicePointManager"
            servicePointManager.SecurityProtocol = servicePointManager.SecurityProtocol.TLS12

            local webClient = dotNetObject "System.Net.WebClient"
            webClient.DownloadFile (updateUrl + "?time=" + (timestamp() as string)) targetFilePath
            return doesFileExist targetFilePath
        ) catch (
            return false
        )
    )

    fn applyDownloadedScriptUpdate downloadedFilePath currentScriptFile = (
        if (not (doesFileExist downloadedFilePath)) do return false
        if (not (doesFileExist currentScriptFile)) do return false

        local backupFilePath = currentScriptFile + ".bak"
        try (deleteFile backupFilePath) catch()

        if (not (copyFile currentScriptFile backupFilePath)) do return false

        try (
            setFileAttribute currentScriptFile #readOnly false
            deleteFile currentScriptFile
            if (not (renameFile downloadedFilePath currentScriptFile)) do (
                copyFile backupFilePath currentScriptFile
                return false
            )
        ) catch (
            try (copyFile backupFilePath currentScriptFile) catch()
            return false
        )

        try (deleteFile backupFilePath) catch()
        return true
    )

    fn releaseNotesForVersion scriptFilePath releaseVersionString = (
        local releaseItems = readScriptInfo scriptFilePath releaseInfo:releaseVersionString
        local releaseContent = ""

        for releaseIndex in 1 to releaseItems.count do (
            releaseContent += releaseItems[releaseIndex]
            if (releaseIndex < releaseItems.count) do releaseContent += "\r\n"
        )

        if (releaseContent == "") do releaseContent = "No changelog entries for this version."
        return releaseContent
    )

    fn releaseNotesForUpdate scriptFilePath currentVersionString newVersionString = (
        local scriptInfo = readScriptInfo scriptFilePath
        local releaseContent = ""

        for releaseSectionName in scriptInfo.releases do (
            local isAfterCurrent = (compareVersionStrings releaseSectionName currentVersionString) > 0
            local isNotAfterNew = (compareVersionStrings releaseSectionName newVersionString) <= 0

            if (isAfterCurrent and isNotAfterNew) do (
                if (releaseContent != "") do releaseContent += "\r\n\r\n"
                releaseContent += "[" + releaseSectionName + "]\r\n"
                releaseContent += releaseNotesForVersion scriptFilePath releaseSectionName
            )
        )

        if (releaseContent == "") do releaseContent = releaseNotesForVersion scriptFilePath newVersionString
        return releaseContent
    )

    fn newUpdateResultData = (
        local updateResult = MaxPkgUpdateResultData()
        updateResult.isUpdated = false
        updateResult.currentVersionString = ""
        updateResult.newVersionString = ""
        updateResult.releaseNotesContent = ""
        updateResult.messageContent = ""
        updateResult.scriptFilePath = currentScriptFilePath()
        return updateResult
    )

    fn checkAndDownloadScriptUpdate showMessages:false reloadAfterUpdate:false = (
        local updateResult = newUpdateResultData()
        local currentScriptFile = currentScriptFilePath()
        updateResult.scriptFilePath = currentScriptFile
        if (currentScriptFile == undefined or currentScriptFile == "") do return updateResult

        local currentInfo = readScriptInfo currentScriptFile
        updateResult.currentVersionString = currentInfo.versionString

        if (currentInfo.updateUrl == "") do (
            if (showMessages) do messageBox "Update URL is not configured." title:"MaxPkg Packager"
            updateResult.messageContent = "Update URL is not configured."
            return updateResult
        )

        local downloadedFilePath = currentScriptFile + ".update"
        if (not (downloadUpdateFile currentInfo.updateUrl downloadedFilePath)) do (
            if (showMessages) do messageBox "Could not download update." title:"MaxPkg Packager"
            updateResult.messageContent = "Could not download update."
            return updateResult
        )

        local downloadedInfo = readScriptInfo downloadedFilePath
        updateResult.newVersionString = downloadedInfo.versionString
        local compareResult = compareVersionStrings downloadedInfo.versionString currentInfo.versionString

        if (compareResult <= 0) do (
            try (deleteFile downloadedFilePath) catch()
            if (showMessages) do messageBox ("You already have the latest version: " + currentInfo.versionString) title:"MaxPkg Packager"
            updateResult.messageContent = "You already have the latest version: " + currentInfo.versionString
            return updateResult
        )

        updateResult.releaseNotesContent = releaseNotesForUpdate downloadedFilePath currentInfo.versionString downloadedInfo.versionString

        if (not (applyDownloadedScriptUpdate downloadedFilePath currentScriptFile)) do (
            try (deleteFile downloadedFilePath) catch()
            if (showMessages) do messageBox "Downloaded update, but could not replace current script." title:"MaxPkg Packager"
            updateResult.messageContent = "Downloaded update, but could not replace current script."
            return updateResult
        )

        updateResult.isUpdated = true
        updateResult.messageContent = "Script updated from " + currentInfo.versionString + " to " + downloadedInfo.versionString + "."
        print updateResult.messageContent

        if (reloadAfterUpdate) do try (fileIn currentScriptFile) catch()
        return updateResult
    )

    fn startsWith str prefix = (
        if (str == undefined or prefix == undefined) do return false
        if (str.count < prefix.count) do return false

        return (substring str 1 prefix.count) == prefix
    )

    fn endsWith str suffix = (
        if (str == undefined or suffix == undefined) do return false
        if (str.count < suffix.count) do return false

        return (substring str (str.count - suffix.count + 1) suffix.count) == suffix
    )

    fn hasLogErrors = (
        for logMessage in logItems do (
            if (startsWith logMessage "[ERROR]") do return true
        )

        return false
    )

    fn directoryExists dirPath = (
        if (dirPath == undefined) do return false
        if (dirPath == "") do return false

        return doesDirectoryExist dirPath
    )

    fn ensureDirectory dirPath = (
        local dir = ensureTrailingSlash dirPath

        if (directoryExists dir) do return true
        return makeDir dir all:true
    )

    fn deleteDirectory dirPath = (
        if (not (directoryExists dirPath)) do return true

        try (
            (dotNetClass "System.IO.Directory").Delete dirPath true
        ) catch (
            deleteFile ((ensureTrailingSlash dirPath) + "*.*")
        )

        return true
    )

    fn currentDateString = (
        try (
            return ((dotNetClass "System.DateTime").Now).ToString "yyyy-MM-dd"
        ) catch (
            return ""
        )
    )

    fn newGuidString = (
        return ((dotNetClass "System.Guid").NewGuid()).ToString()
    )

    fn currentMaxYearPlusOne = (
        try (
            return (((dotNetClass "System.DateTime").Now).Year + 1)
        ) catch (
            return 2027
        )
    )

    fn maxYearItems = (
        local result = #()
        local maxYear = currentMaxYearPlusOne()

        for yearItem in 2012 to maxYear do (
            append result (yearItem as string)
        )

        return result
    )

    fn versionNumberItems m: 99 = (
        local result = #()

        for numberItem in 0 to m do (
            append result (numberItem as string)
        )

        return result
    )

    fn parseVersionParts versionString = (
        local parts = filterString (trimString versionString) "."

        if (parts.count != 3) do return #("1", "0", "0")

        for i in 1 to 3 do (
            local partNumber = try (parts[i] as integer) catch(undefined)
            if (partNumber == undefined) do return #("1", "0", "0")
            if (partNumber < 0 or partNumber > 99) do return #("1", "0", "0")
            parts[i] = partNumber as string
        )

        return parts
    )

    fn buildVersionString ui = (
        local majorPart = getDropDownText ui.ddlVersionMajor
        local minorPart = getDropDownText ui.ddlVersionMinor
        local patchPart = getDropDownText ui.ddlVersionPatch

        if (majorPart == "") do majorPart = "1"
        if (minorPart == "") do minorPart = "0"
        if (patchPart == "") do patchPart = "0"

        return majorPart + "." + minorPart + "." + patchPart
    )

    fn selectedMinMaxYear ui = (
        local selectedYear = getDropDownText ui.ddlMinMax

        if (selectedYear == "") do return "2012"
        return selectedYear
    )

    fn selectedReleaseChannel ui = (
        local channel = getDropDownText ui.ddlReleaseChannel

        if (channel == "") do return "stable"
        return channel
    )

    fn copySvgIconToRoot sourceFilePath = (
        local sourceIconFile = normalizePath sourceFilePath
        local rootIconFile = normalizePath ((ensureTrailingSlash rootDir) + "maxpkg-icon.svg")

        if (sourceIconFile == "") do return ""
        if (not (doesFileExist sourceIconFile)) do return ""

        if ((lowerString sourceIconFile) != (lowerString rootIconFile)) do (
            if (doesFileExist rootIconFile) do deleteFile rootIconFile
            if (not (copyFile sourceIconFile rootIconFile)) do return ""
        )

        return rootIconFile
    )

    fn isValidGuid s = (
        local guidText = trimString s
        local dashPositions = #(9, 14, 19, 24)
        local hexChars = "0123456789abcdefABCDEF"

        if (guidText.count != 36) do return false

        for i in 1 to guidText.count do (
            local ch = substring guidText i 1
            local dashExpected = (findItem dashPositions i) > 0

            if (dashExpected) then (
                if (ch != "-") do return false
            ) else (
                if ((findString hexChars ch) == undefined) do return false
            )
        )

        return true
    )

    fn isSafeRelativePath relPath = (
        local rel = normalizePath relPath

        if (rel == "") do return false
        if ((findString rel ":") != undefined) do return false
        if (startsWith rel "\\") do return false
        if (startsWith rel "..\\") do return false
        if ((findString rel "\\..\\") != undefined) do return false
        if (rel == "..") do return false

        return true
    )

    fn relativePathFromRoot absPath = (
        local abs = normalizePath absPath
        local root = ensureTrailingSlash rootDir

        if (startsWith (lowerString abs) (lowerString root)) then (
            return substring abs (root.count + 1) (abs.count - root.count)
        )

        return (getFilenameFile abs) + (getFilenameType abs)
    )

    fn isExcludedPath absPath = (
        local p = lowerString (normalizePath absPath)
        local n = lowerString (filenameFromPath absPath)

        if ((findString p "\\.git\\") != undefined) do return true
        if ((findString p "\\.vscode\\") != undefined) do return true
        if (matchPattern n pattern:"*.bak" ignoreCase:true) do return true
        if (matchPattern n pattern:"*.tmp" ignoreCase:true) do return true
        if (matchPattern n pattern:"*.log" ignoreCase:true) do return true
        if (matchPattern n pattern:"*.zip" ignoreCase:true) do return true
        if (matchPattern n pattern:"*.mzp" ignoreCase:true) do return true
        if (n == "maxpkg-packager.ms") do return true
        if (n == "maxpkg-packager.ini") do return true
        if (n == "maxpkg-changelog.ini") do return true
        if (n == "maxpkg-button.mcr") do return true
        if (n == "mzp.run") do return true
        if (n == "mzp.run.ms") do return true

        return false
    )

    fn findPackageFileByRel relPath = (
        local rel = normalizePath relPath

        for item in packageFiles do (
            if (item[2] == rel) do return item
        )

        return undefined
    )

    fn addPackageFile absPath = (
        if (absPath == undefined) do return false
        if (not (doesFileExist absPath)) do return false
        if (isExcludedPath absPath) do return false

        local rel = normalizePath (relativePathFromRoot absPath)

        if (not (isSafeRelativePath rel)) do return false
        if ((findPackageFileByRel rel) != undefined) do return true

        append packageFiles #((normalizePath absPath), rel)
        return true
    )

    fn addFolderFiles folderPath = (
        local added = 0
        local dir = ensureTrailingSlash folderPath

        if (not (directoryExists dir)) do return 0

        try (
            local Directory = dotNetClass "System.IO.Directory"
            local SearchOption = dotNetClass "System.IO.SearchOption"
            local files = Directory.GetFiles dir "*" SearchOption.AllDirectories

            for filePath in files do (
                if (addPackageFile (filePath as string)) do added += 1
            )
        ) catch (
            local files = getFiles (dir + "**\\*.*")

            for filePath in files do (
                if (addPackageFile filePath) do added += 1
            )
        )

        return added
    )

    fn getPackageFileNames = (
        local result = #()

        for item in packageFiles do (
            append result item[2]
        )

        return result
    )

    fn readTextFile filePath = (
        local stream = openFile filePath mode:"rt"
        local content = ""

        if (stream == undefined) do return undefined

        while (not eof stream) do (
            content += readLine stream
            if (not eof stream) do content += "\n"
        )

        close stream
        return content
    )

    fn writeTextFile filePath content = (
        local stream = createFile filePath

        if (stream == undefined) do return false

        format "%" content to:stream
        close stream

        return true
    )

    fn escapeIniValue s = (
        local result = trimString s
        result = substituteString result "\r\n" "\\n"
        result = substituteString result "\n" "\\n"
        result = substituteString result "\r" "\\n"
        return result
    )

    fn unescapeIniValue s = (
        local result = s as string
        result = substituteString result "\\n" "\r\n"
        return result
    )

    fn escapeJson s = (
        local result = s as string
        result = substituteString result "\\" "\\\\"
        result = substituteString result "\"" "\\\""
        result = substituteString result "\r\n" "\\n"
        result = substituteString result "\n" "\\n"
        result = substituteString result "\r" "\\n"
        result = substituteString result "\t" "\\t"
        return result
    )

    fn isValidSafeSvg filePath = (
        if (filePath == undefined or filePath == "") do return false
        if (not (doesFileExist filePath)) do return false
        if ((lowerString (getFilenameType filePath)) != ".svg") do return false

        local content = readTextFile filePath
        if (content == undefined or content.count == 0) do return false

        for i in 1 to content.count do (
            local code = bit.charAsInt (substring content i 1)
            if (code == 0) do return false
        )

        local lowerContent = lowerString content

        if ((findString lowerContent "<svg") == undefined) do return false
        if ((findString lowerContent "<script") != undefined) do return false
        if ((findString lowerContent "javascript:") != undefined) do return false
        if ((findString lowerContent "onload=") != undefined) do return false
        if ((findString lowerContent "onclick=") != undefined) do return false
        if ((findString lowerContent "onerror=") != undefined) do return false
        if ((findString lowerContent "<foreignobject") != undefined) do return false

        return true
    )

    fn detectRootHook hookName = (
        local hook = lowerString hookName

        for item in packageFiles do (
            if ((lowerString item[2]) == hook) do return hookName
        )

        return ""
    )

    fn iniLine key settingValue = (
        return key + "=" + (escapeIniValue settingValue) + "\n"
    )

    fn iniSet key settingValue iniSection:"settings" = (
        setINISetting iniPath iniSection key (escapeIniValue settingValue)
        return true
    )

    fn iniGet key iniSection:"settings" = (
        return unescapeIniValue (getINISetting iniPath iniSection key)
    )

    fn iniGetBool key iniSection:"settings" defaultValue:true = (
        return stringToBool (getINISetting iniPath iniSection key) defaultValue:defaultValue
    )

    fn iniGetInt key iniSection:"settings" defaultValue:0 = (
        local settingValue = getINISetting iniPath iniSection key

        if (settingValue == "") do return defaultValue

        return settingValue as integer
    )

    fn iniSetRaw key settingValue iniSection:"settings" = (
        setINISetting iniPath iniSection key (settingValue as string)
        return true
    )

    fn changelogSectionFromVersion versionString = (
        local normalizedVersion = trimString versionString

        if (normalizedVersion == "") do normalizedVersion = "1.0.0"

        return "version_" + normalizedVersion
    )

    fn saveChangelogForVersion versionString = (
        local normalizedVersion = trimString versionString
        local changelogSectionName = changelogSectionFromVersion normalizedVersion

        if (normalizedVersion == "") do normalizedVersion = "1.0.0"

        try (delIniSetting changelogIniPath changelogSectionName) catch()

        setINISetting changelogIniPath changelogSectionName "version" normalizedVersion
        setINISetting changelogIniPath changelogSectionName "count" (changelogItems.count as string)

        for i in 1 to changelogItems.count do (
            setINISetting changelogIniPath changelogSectionName ((i as string) + "_type") (escapeIniValue changelogItems[i][1])
            setINISetting changelogIniPath changelogSectionName ((i as string) + "_text") (escapeIniValue changelogItems[i][2])
        )

        return true
    )

    fn saveCurrentChangelog = (
        return saveChangelogForVersion activeChangelogVersion
    )

    fn loadChangelogForVersion versionString = (
        local normalizedVersion = trimString versionString
        local changelogSectionName = changelogSectionFromVersion normalizedVersion
        local countString = getINISetting changelogIniPath changelogSectionName "count"
        local changelogCount = 0

        if (countString == "") do return false

        changelogCount = try (countString as integer) catch(0)
        changelogItems = #()

        for i in 1 to changelogCount do (
            local itemType = unescapeIniValue (getINISetting changelogIniPath changelogSectionName ((i as string) + "_type"))
            local itemContent = unescapeIniValue (getINISetting changelogIniPath changelogSectionName ((i as string) + "_text"))

            if (itemType != "" and itemContent != "") do (
                append changelogItems #(itemType, itemContent)
            )
        )

        return true
    )

    fn loadLegacyChangelogFromSettings = (
        local changelogCount = iniGetInt "count" iniSection:"changelog" defaultValue:0

        changelogItems = #()

        for i in 1 to changelogCount do (
            local itemType = iniGet ((i as string) + "_type") iniSection:"changelog"
            local itemContent = iniGet ((i as string) + "_text") iniSection:"changelog"

            if (itemType != "" and itemContent != "") do (
                append changelogItems #(itemType, itemContent)
            )
        )

        return changelogCount > 0
    )

    fn hasChangelogEntries = (
        for changelogItem in changelogItems do (
            if (changelogItem.count >= 2 and (trimString changelogItem[2]) != "") do return true
        )

        return false
    )

    fn saveSettings ui shouldLog:false = (
        if (isLoadingSettings) do return false

        iniSet "packageName" ui.edtName.text
        iniSet "buttonName" ui.edtButtonName.text
        iniSet "developerName" ui.edtDeveloperName.text
        iniSet "packageGuid" ui.edtGuid.text
        iniSet "description" ui.edtDescription.text
        iniSet "license" (getDropDownText ui.ddlLicense)
        iniSet "licenseUrl" ui.edtLicenseUrl.text
        iniSet "version" (buildVersionString ui)
        iniSet "releaseChannel" (selectedReleaseChannel ui)
        iniSet "releaseDate" ui.edtReleaseDate.text
        iniSet "min3dsMax" (selectedMinMaxYear ui)
        iniSet "max3dsMax" ((currentMaxYearPlusOne()) as string)
        iniSet "runtime" (getDropDownText ui.ddlRuntime)
        iniSet "entry" ui.edtEntry.text
        iniSet "svgIcon" ui.edtIcon.text
        iniSet "homepage" ui.edtHomepage.text
        iniSet "documentation" ui.edtDocumentation.text
        iniSet "support" ui.edtSupport.text
        iniSet "createMacroButton" (boolToString ui.chkCreateMacro.checked)
        iniSet "showInToolbar" (boolToString ui.chkShowToolbar.checked)
        iniSet "outputFolder" ui.edtOutput.text

        iniSetRaw "count" packageFiles.count iniSection:"files"

        for i in 1 to packageFiles.count do (
            iniSet ((i as string) + "_abs") packageFiles[i][1] iniSection:"files"
            iniSet ((i as string) + "_rel") packageFiles[i][2] iniSection:"files"
        )

        saveCurrentChangelog()

        if (shouldLog) do addLog "OK" "INI saved"

        return true
    )

    fn loadSettings ui = (
        if (not (doesFileExist iniPath)) do return false

        isLoadingSettings = true

        ui.edtName.text = iniGet "packageName"
        ui.edtButtonName.text = iniGet "buttonName"
        ui.edtDeveloperName.text = iniGet "developerName"
        ui.edtGuid.text = iniGet "packageGuid"
        ui.edtDescription.text = iniGet "description"
        setDropDownText ui.ddlLicense (iniGet "license")
        ui.edtLicenseUrl.text = iniGet "licenseUrl"

        local versionParts = parseVersionParts (iniGet "version")
        setDropDownText ui.ddlVersionMajor versionParts[1]
        setDropDownText ui.ddlVersionMinor versionParts[2]
        setDropDownText ui.ddlVersionPatch versionParts[3]
        if (not (setDropDownText ui.ddlReleaseChannel (iniGet "releaseChannel"))) do setDropDownText ui.ddlReleaseChannel "stable"

        ui.edtReleaseDate.text = iniGet "releaseDate"

        if (not (setDropDownText ui.ddlMinMax (iniGet "min3dsMax"))) do setDropDownText ui.ddlMinMax "2012"

        if (not (setDropDownText ui.ddlRuntime (iniGet "runtime"))) do setDropDownText ui.ddlRuntime "maxscript"
        ui.edtEntry.text = iniGet "entry"
        ui.edtIcon.text = iniGet "svgIcon"
        ui.edtHomepage.text = iniGet "homepage"
        ui.edtDocumentation.text = iniGet "documentation"
        ui.edtSupport.text = iniGet "support"
        ui.chkCreateMacro.checked = iniGetBool "createMacroButton" defaultValue:true
        ui.chkShowToolbar.checked = iniGetBool "showInToolbar" defaultValue:true
        ui.edtOutput.text = iniGet "outputFolder"

        packageFiles = #()

        local fileCount = iniGetInt "count" iniSection:"files" defaultValue:0

        for i in 1 to fileCount do (
            local abs = iniGet ((i as string) + "_abs") iniSection:"files"
            local rel = iniGet ((i as string) + "_rel") iniSection:"files"

            if (abs != "" and rel != "" and not (isExcludedPath abs)) do (
                append packageFiles #((normalizePath abs), (normalizePath rel))
            )
        )

        activeChangelogVersion = buildVersionString ui

        if (not (loadChangelogForVersion activeChangelogVersion)) do (
            if (loadLegacyChangelogFromSettings()) do saveCurrentChangelog()
        )

        --addLog "OK" "INI loaded"
        isLoadingSettings = false
        saveSettings ui
        return true
    )

    fn validateSettings ui = (
        local isValid = true
        local packageName = trimString ui.edtName.text
        local buttonName = trimString ui.edtButtonName.text
        local description = trimString ui.edtDescription.text
        local developerName = trimString ui.edtDeveloperName.text
        local guid = trimString ui.edtGuid.text
        local versionText = buildVersionString ui
        local releaseDate = trimString ui.edtReleaseDate.text
        local runtime = getDropDownText ui.ddlRuntime
        local entry = normalizePath (trimString ui.edtEntry.text)
        local iconFile = normalizePath (trimString ui.edtIcon.text)
        local minMax = (selectedMinMaxYear ui) as integer
        local maxMax = currentMaxYearPlusOne()
        local outputFolder = ensureTrailingSlash ui.edtOutput.text

        clearLog()

        if (packageName == "") do (addLog "ERROR" "Package name is required"; isValid = false)
        if (buttonName == "") do (addLog "ERROR" "Button name is required"; isValid = false)
        if (description == "") do (addLog "ERROR" "Description is required"; isValid = false)
        if (developerName == "") do (addLog "ERROR" "Developer name is required"; isValid = false)
        if (description.count > 500) do (addLog "ERROR" "Description must be 500 characters or less"; isValid = false)
        if (guid == "" or not (isValidGuid guid)) do (addLog "ERROR" "Package GUID must be a valid UUID"; isValid = false)
        if (versionText == "") do (addLog "ERROR" "Version is required"; isValid = false)
        if ((selectedReleaseChannel ui) == "") do (addLog "ERROR" "Release channel is required"; isValid = false)
        if (releaseDate == "") do (addLog "ERROR" "Release date is required"; isValid = false)
        if (not (hasChangelogEntries())) do (addLog "ERROR" ("Changelog for version " + versionText + " must contain at least one item"); isValid = false)
        if ((getDropDownText ui.ddlLicense) == "") do (addLog "ERROR" "License is required"; isValid = false)
        if (minMax == undefined or maxMax == undefined) do (addLog "ERROR" "Min and max 3ds Max versions must be numbers"; isValid = false)
        if (minMax != undefined and maxMax != undefined and minMax > maxMax) do (addLog "ERROR" "Min 3ds Max version must be <= max version"; isValid = false)
        if (runtime != "maxscript" and runtime != "python") do (addLog "ERROR" "Runtime must be maxscript or python"; isValid = false)

        if (entry == "") then (
            addLog "ERROR" "Entry file is required"
            isValid = false
        ) else (
            local entryItem = findPackageFileByRel entry

            if (entryItem == undefined) then (
                addLog "ERROR" "Entry file must be included in package files"
                isValid = false
            ) else (
                local ext = lowerString (getFilenameType entry)

                if (not (doesFileExist entryItem[1])) do (addLog "ERROR" "Entry file does not exist"; isValid = false)
                if (runtime == "maxscript" and ext != ".ms" and ext != ".mse") do (addLog "ERROR" "MaxScript runtime requires .ms or .mse entry file"; isValid = false)
                if (runtime == "python" and ext != ".py") do (addLog "ERROR" "Python runtime requires .py entry file"; isValid = false)
            )
        )

        if (iconFile != "") do (
            if (isValidSafeSvg iconFile) then (
                addLog "OK" "SVG icon validated"
            ) else (
                addLog "ERROR" "Selected icon is not a valid safe SVG file."
                isValid = false
            )
        )

        if (packageFiles.count == 0) do (addLog "ERROR" "At least one package file is required"; isValid = false)

        for item in packageFiles do (
            if (not (isSafeRelativePath item[2])) do (addLog "ERROR" ("Invalid relative path: " + item[2]); isValid = false)
            if (not (doesFileExist item[1])) do (addLog "ERROR" ("Missing file: " + item[2]); isValid = false)

            local rel = lowerString item[2]
            if (endsWith rel "\\install.ms") do (addLog "ERROR" "install.ms is only allowed in package root"; isValid = false)
            if (endsWith rel "\\uninstall.ms") do (addLog "ERROR" "uninstall.ms is only allowed in package root"; isValid = false)
        )

        if ((detectRootHook "install.ms") != "") do addLog "OK" "install.ms detected"
        if ((detectRootHook "uninstall.ms") != "") do addLog "OK" "uninstall.ms detected"

        if (outputFolder == "" or outputFolder == "\\") then (
            addLog "ERROR" "Output folder is required"
            isValid = false
        ) else if (not (ensureDirectory outputFolder)) then (
            addLog "ERROR" "Output folder does not exist and cannot be created"
            isValid = false
        )

        if (isValid) then addLog "OK" "Validation passed" else addLog "ERROR" "Validation failed"

        return isValid
    )

    fn buildManifestIni ui = (
        local ss = stringStream ""
        local iconPath = ""
        local scriptInfo = readScriptInfo (currentScriptFilePath())

        if ((trimString ui.edtIcon.text) != "") do iconPath = "icons/icon.svg"

        format "[package]\n" to:ss
        format "manifestVersion=1\n" to:ss
        format "%" (iniLine "packageGuid" ui.edtGuid.text) to:ss
        format "%" (iniLine "name" ui.edtName.text) to:ss
        format "%" (iniLine "buttonName" ui.edtButtonName.text) to:ss
        format "%" (iniLine "description" ui.edtDescription.text) to:ss
        format "%" (iniLine "version" (buildVersionString ui)) to:ss
        format "%" (iniLine "releaseChannel" (selectedReleaseChannel ui)) to:ss
        format "%" (iniLine "releaseDate" ui.edtReleaseDate.text) to:ss
        format "%" (iniLine "runtime" (getDropDownText ui.ddlRuntime)) to:ss
        format "%" (iniLine "entry" (normalizePath ui.edtEntry.text)) to:ss
        format "%" (iniLine "icon" iconPath) to:ss
        format "%" (iniLine "license" (getDropDownText ui.ddlLicense)) to:ss
        format "%" (iniLine "licenseUrl" ui.edtLicenseUrl.text) to:ss
        format "%" (iniLine "developerName" ui.edtDeveloperName.text) to:ss
        format "%" (iniLine "min3dsMax" (selectedMinMaxYear ui)) to:ss
        format "%" (iniLine "max3dsMax" ((currentMaxYearPlusOne()) as string)) to:ss
        format "%" (iniLine "homepage" ui.edtHomepage.text) to:ss
        format "%" (iniLine "documentation" ui.edtDocumentation.text) to:ss
        format "%" (iniLine "support" ui.edtSupport.text) to:ss
        format "%" (iniLine "createMacroButton" (boolToString ui.chkCreateMacro.checked)) to:ss
        format "%" (iniLine "showInToolbar" (boolToString ui.chkShowToolbar.checked)) to:ss
        format "%" (iniLine "installScript" (detectRootHook "install.ms")) to:ss
        format "%" (iniLine "uninstallScript" (detectRootHook "uninstall.ms")) to:ss
        format "%" (iniLine "packager" scriptInfo.scriptTitle) to:ss
        format "%" (iniLine "packagerVersion" scriptInfo.versionString) to:ss
        format "\n[changelog]\n" to:ss

        for i in 1 to changelogItems.count do (
            format "%" (iniLine ((i as string) + "_type") changelogItems[i][1]) to:ss
            format "%" (iniLine ((i as string) + "_text") changelogItems[i][2]) to:ss
        )

        return ss as string
    )

    fn buildManifestJson ui = (
        local ss = stringStream ""
        local iconPath = ""
        local scriptInfo = readScriptInfo (currentScriptFilePath())
        local minMax = (selectedMinMaxYear ui) as integer
        local maxMax = currentMaxYearPlusOne()

        if ((trimString ui.edtIcon.text) != "") do iconPath = "icons/icon.svg"

        format "{\n" to:ss
        format "  \"manifestVersion\": 1,\n" to:ss
        format "  \"packageGuid\": \"%\",\n" (escapeJson (trimString ui.edtGuid.text)) to:ss
        format "  \"name\": \"%\",\n" (escapeJson (trimString ui.edtName.text)) to:ss
        format "  \"buttonName\": \"%\",\n" (escapeJson (trimString ui.edtButtonName.text)) to:ss
        format "  \"description\": \"%\",\n" (escapeJson (trimString ui.edtDescription.text)) to:ss
        format "  \"version\": \"%\",\n" (escapeJson (buildVersionString ui)) to:ss
        format "  \"releaseChannel\": \"%\",\n" (escapeJson (selectedReleaseChannel ui)) to:ss
        format "  \"releaseDate\": \"%\",\n" (escapeJson (trimString ui.edtReleaseDate.text)) to:ss
        format "  \"runtime\": \"%\",\n" (escapeJson (getDropDownText ui.ddlRuntime)) to:ss
        format "  \"entry\": \"%\",\n" (escapeJson (normalizePath (trimString ui.edtEntry.text))) to:ss
        format "  \"icon\": \"%\",\n" (escapeJson iconPath) to:ss
        format "  \"license\": \"%\",\n" (escapeJson (getDropDownText ui.ddlLicense)) to:ss
        format "  \"licenseUrl\": \"%\",\n" (escapeJson (trimString ui.edtLicenseUrl.text)) to:ss
        format "  \"developerName\": \"%\",\n" (escapeJson (trimString ui.edtDeveloperName.text)) to:ss
        format "  \"min3dsMax\": %, \n" minMax to:ss
        format "  \"max3dsMax\": %, \n" maxMax to:ss
        format "  \"homepage\": \"%\",\n" (escapeJson (trimString ui.edtHomepage.text)) to:ss
        format "  \"documentation\": \"%\",\n" (escapeJson (trimString ui.edtDocumentation.text)) to:ss
        format "  \"support\": \"%\",\n" (escapeJson (trimString ui.edtSupport.text)) to:ss
        format "  \"createMacroButton\": %, \n" (boolToString ui.chkCreateMacro.checked) to:ss
        format "  \"showInToolbar\": %, \n" (boolToString ui.chkShowToolbar.checked) to:ss
        format "  \"installScript\": \"%\",\n" (escapeJson (detectRootHook "install.ms")) to:ss
        format "  \"uninstallScript\": \"%\",\n" (escapeJson (detectRootHook "uninstall.ms")) to:ss
        format "  \"packager\": \"%\",\n" (escapeJson scriptInfo.scriptTitle) to:ss
        format "  \"packagerVersion\": \"%\",\n" (escapeJson scriptInfo.versionString) to:ss
        format "  \"changelog\": [\n" to:ss

        for i in 1 to changelogItems.count do (
            format "    { \"type\": \"%\", \"text\": \"%\" }" (escapeJson changelogItems[i][1]) (escapeJson changelogItems[i][2]) to:ss
            if (i < changelogItems.count) do format "," to:ss
            format "\n" to:ss
        )

        format "  ]\n" to:ss
        format "}\n" to:ss

        return ss as string
    )

    fn buildSampleInstallScript = (
        local ss = stringStream ""

        format "(\n" to:ss
        format "    struct SampleDataSourcesData (\n" to:ss
        format "        scriptDir,\n" to:ss
        format "        manifestFilePath,\n" to:ss
        format "        settingsFilePath,\n" to:ss
        format "        changelogFilePath\n" to:ss
        format "    )\n\n" to:ss
        format "    struct SamplePackageInfoData (\n" to:ss
        format "        packageTitle,\n" to:ss
        format "        packageVersion,\n" to:ss
        format "        releaseChannel,\n" to:ss
        format "        releaseDate,\n" to:ss
        format "        packageLicense,\n" to:ss
        format "        developerTitle,\n" to:ss
        format "        minMaxVersion,\n" to:ss
        format "        maxMaxVersion,\n" to:ss
        format "        homepageLink,\n" to:ss
        format "        documentationLink,\n" to:ss
        format "        supportLink,\n" to:ss
        format "        packageDescription,\n" to:ss
        format "        changelogContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleEnsureSlash dirPath = (\n" to:ss
        format "        if (dirPath == undefined or dirPath == \"\") do return \"\"\n" to:ss
        format "        local normalizedDir = substituteString (dirPath as string) \"/\" \"\\\\\"\n" to:ss
        format "        if ((substring normalizedDir normalizedDir.count 1) == \"\\\\\") do return normalizedDir\n" to:ss
        format "        return normalizedDir + \"\\\\\"\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleDataSources = (\n" to:ss
        format "        local sourceFilePath = getSourceFileName()\n" to:ss
        format "        if (sourceFilePath == undefined or sourceFilePath == \"\") do sourceFilePath = getThisScriptFileName()\n" to:ss
        format "        local scriptDir = sampleEnsureSlash (getFilenamePath sourceFilePath)\n\n" to:ss
        format "        local sources = SampleDataSourcesData()\n" to:ss
        format "        sources.scriptDir = scriptDir\n" to:ss
        format "        sources.manifestFilePath = scriptDir + \"manifest.ini\"\n" to:ss
        format "        sources.settingsFilePath = scriptDir + \"maxpkg-packager.ini\"\n" to:ss
        format "        sources.changelogFilePath = scriptDir + \"maxpkg-changelog.ini\"\n\n" to:ss
        format "        return sources\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleUnescapeContent sourceContent = (\n" to:ss
        format "        local resultContent = sourceContent as string\n" to:ss
        format "        resultContent = substituteString resultContent \"\\\\n\" \"\\r\\n\"\n" to:ss
        format "        return resultContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleReadIniEntry sources packageKey settingsKey fallbackContent:\"\" = (\n" to:ss
        format "        local entryContent = getINISetting sources.manifestFilePath \"package\" packageKey\n" to:ss
        format "        if (entryContent == undefined or entryContent == \"\") do entryContent = getINISetting sources.settingsFilePath \"settings\" settingsKey\n" to:ss
        format "        if (entryContent == undefined or entryContent == \"\") do return fallbackContent\n" to:ss
        format "        return sampleUnescapeContent entryContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleReadChangelog sources packageVersion = (\n" to:ss
        format "        local changelogSectionName = \"version_\" + packageVersion\n" to:ss
        format "        local countContent = getINISetting sources.changelogFilePath changelogSectionName \"count\"\n" to:ss
        format "        local changelogCount = try (countContent as integer) catch(0)\n" to:ss
        format "        local changelogContent = \"\"\n\n" to:ss
        format "        for i in 1 to changelogCount do (\n" to:ss
        format "            local itemType = getINISetting sources.changelogFilePath changelogSectionName ((i as string) + \"_type\")\n" to:ss
        format "            local itemContent = getINISetting sources.changelogFilePath changelogSectionName ((i as string) + \"_text\")\n" to:ss
        format "            if (itemType != undefined and itemType != \"\" and itemContent != undefined and itemContent != \"\") do (\n" to:ss
        format "                changelogContent += \"- [\" + itemType + \"] \" + (sampleUnescapeContent itemContent) + \"\\r\\n\"\n" to:ss
        format "            )\n" to:ss
        format "        )\n\n" to:ss
        format "        if (changelogContent == \"\") do changelogContent = \"No changelog entries for this version.\"\n" to:ss
        format "        return changelogContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleReadPackageInfo sources = (\n" to:ss
        format "        local packageVersion = sampleReadIniEntry sources \"version\" \"version\" fallbackContent:\"1.0.0\"\n\n" to:ss
        format "        local packageInfo = SamplePackageInfoData()\n" to:ss
        format "        packageInfo.packageTitle = sampleReadIniEntry sources \"name\" \"packageName\" fallbackContent:\"Package\"\n" to:ss
        format "        packageInfo.packageVersion = packageVersion\n" to:ss
        format "        packageInfo.releaseChannel = sampleReadIniEntry sources \"releaseChannel\" \"releaseChannel\" fallbackContent:\"stable\"\n" to:ss
        format "        packageInfo.releaseDate = sampleReadIniEntry sources \"releaseDate\" \"releaseDate\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.packageLicense = sampleReadIniEntry sources \"license\" \"license\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.developerTitle = sampleReadIniEntry sources \"developerName\" \"developerName\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.minMaxVersion = sampleReadIniEntry sources \"min3dsMax\" \"min3dsMax\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.maxMaxVersion = sampleReadIniEntry sources \"max3dsMax\" \"max3dsMax\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.homepageLink = sampleReadIniEntry sources \"homepage\" \"homepage\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.documentationLink = sampleReadIniEntry sources \"documentation\" \"documentation\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.supportLink = sampleReadIniEntry sources \"support\" \"support\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.packageDescription = sampleReadIniEntry sources \"description\" \"description\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.changelogContent = sampleReadChangelog sources packageVersion\n\n" to:ss
        format "        return packageInfo\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleInfoLine labelText infoContent = (\n" to:ss
        format "        if (infoContent == undefined or infoContent == \"\") do return \"\"\n" to:ss
        format "        return labelText + infoContent + \"\\r\\n\"\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleInstallInfoContent packageInfo = (\n" to:ss
        format "        local infoContent = packageInfo.packageTitle + \" installed successfully.\\r\\n\\r\\n\"\n\n" to:ss
        format "        infoContent += sampleInfoLine \"Name: \" packageInfo.packageTitle\n" to:ss
        format "        infoContent += \"Version: \" + packageInfo.packageVersion + \" (\" + packageInfo.releaseChannel + \")\\r\\n\"\n" to:ss
        format "        infoContent += sampleInfoLine \"Release date: \" packageInfo.releaseDate\n" to:ss
        format "        if (packageInfo.minMaxVersion != \"\" or packageInfo.maxMaxVersion != \"\") do infoContent += \"3ds Max: \" + packageInfo.minMaxVersion + \" - \" + packageInfo.maxMaxVersion + \"\\r\\n\"\n" to:ss
        format "        infoContent += sampleInfoLine \"License: \" packageInfo.packageLicense\n" to:ss
        format "        infoContent += sampleInfoLine \"Developer: \" packageInfo.developerTitle\n" to:ss
        format "        infoContent += sampleInfoLine \"Homepage: \" packageInfo.homepageLink\n" to:ss
        format "        infoContent += sampleInfoLine \"Documentation: \" packageInfo.documentationLink\n" to:ss
        format "        infoContent += sampleInfoLine \"Support: \" packageInfo.supportLink\n" to:ss
        format "        infoContent += \"\\r\\nDescription:\\r\\n\" + packageInfo.packageDescription + \"\\r\\n\\r\\n\"\n" to:ss
        format "        infoContent += \"Latest changelog:\\r\\n\" + packageInfo.changelogContent\n\n" to:ss
        format "        return infoContent\n" to:ss
        format "    )\n\n" to:ss
        format "    local sources = sampleDataSources()\n" to:ss
        format "    local packageInfo = sampleReadPackageInfo sources\n" to:ss
        format "    local installInfoContent = sampleInstallInfoContent packageInfo\n\n" to:ss
        format "    try (destroyDialog MaxPkgSampleInstallRollout) catch()\n\n" to:ss
        format "    rollout MaxPkgSampleInstallRollout \"Install Complete\" width:430 height:315\n" to:ss
        format "    (\n" to:ss
        format "        dotNetControl dncInstallInfo \"System.Windows.Forms.TextBox\" width: 450 height:302 align:#left offset: [-13, -5] align:#left\n" to:ss
        format "        label lblInstallSpacer \"\" align:#left across:2 offset:[0, 4]\n" to:ss
        format "        button btnCloseInstallInfo \"Close\" width:80 height:24 align:#right offset:[0, 4]\n\n" to:ss
        format "        on MaxPkgSampleInstallRollout open do (\n" to:ss
        format "            local scrollBarsClass = dotNetClass \"System.Windows.Forms.ScrollBars\"\n" to:ss
        format "            dncInstallInfo.Multiline = true\n" to:ss
        format "            dncInstallInfo.ReadOnly = true\n" to:ss
        format "            dncInstallInfo.WordWrap = true\n" to:ss
        format "            dncInstallInfo.ScrollBars = scrollBarsClass.Vertical\n" to:ss
        format "            dncInstallInfo.Text = installInfoContent\n" to:ss
        format "        )\n\n" to:ss
        format "        on btnCloseInstallInfo pressed do destroyDialog MaxPkgSampleInstallRollout\n" to:ss
        format "    )\n\n" to:ss
        format "    createDialog MaxPkgSampleInstallRollout width:450 height:350 modal:false\n" to:ss
        format ")\n" to:ss

        return ss as string
    )

    fn buildSampleUninstallScript = (
        local ss = stringStream ""

        format "(\n" to:ss
        format "    struct SampleDataSourcesData (\n" to:ss
        format "        scriptDir,\n" to:ss
        format "        manifestFilePath,\n" to:ss
        format "        settingsFilePath,\n" to:ss
        format "        changelogFilePath\n" to:ss
        format "    )\n\n" to:ss
        format "    struct SamplePackageInfoData (\n" to:ss
        format "        packageTitle,\n" to:ss
        format "        packageVersion,\n" to:ss
        format "        releaseChannel,\n" to:ss
        format "        releaseDate,\n" to:ss
        format "        packageLicense,\n" to:ss
        format "        developerTitle,\n" to:ss
        format "        minMaxVersion,\n" to:ss
        format "        maxMaxVersion,\n" to:ss
        format "        homepageLink,\n" to:ss
        format "        documentationLink,\n" to:ss
        format "        supportLink,\n" to:ss
        format "        packageDescription,\n" to:ss
        format "        changelogContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleEnsureSlash dirPath = (\n" to:ss
        format "        if (dirPath == undefined or dirPath == \"\") do return \"\"\n" to:ss
        format "        local normalizedDir = substituteString (dirPath as string) \"/\" \"\\\\\"\n" to:ss
        format "        if ((substring normalizedDir normalizedDir.count 1) == \"\\\\\") do return normalizedDir\n" to:ss
        format "        return normalizedDir + \"\\\\\"\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleDataSources = (\n" to:ss
        format "        local sourceFilePath = getSourceFileName()\n" to:ss
        format "        if (sourceFilePath == undefined or sourceFilePath == \"\") do sourceFilePath = getThisScriptFileName()\n" to:ss
        format "        local scriptDir = sampleEnsureSlash (getFilenamePath sourceFilePath)\n\n" to:ss
        format "        local sources = SampleDataSourcesData()\n" to:ss
        format "        sources.scriptDir = scriptDir\n" to:ss
        format "        sources.manifestFilePath = scriptDir + \"manifest.ini\"\n" to:ss
        format "        sources.settingsFilePath = scriptDir + \"maxpkg-packager.ini\"\n" to:ss
        format "        sources.changelogFilePath = scriptDir + \"maxpkg-changelog.ini\"\n\n" to:ss
        format "        return sources\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleUnescapeContent sourceContent = (\n" to:ss
        format "        local resultContent = sourceContent as string\n" to:ss
        format "        resultContent = substituteString resultContent \"\\\\n\" \"\\r\\n\"\n" to:ss
        format "        return resultContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleReadIniEntry sources packageKey settingsKey fallbackContent:\"\" = (\n" to:ss
        format "        local entryContent = getINISetting sources.manifestFilePath \"package\" packageKey\n" to:ss
        format "        if (entryContent == undefined or entryContent == \"\") do entryContent = getINISetting sources.settingsFilePath \"settings\" settingsKey\n" to:ss
        format "        if (entryContent == undefined or entryContent == \"\") do return fallbackContent\n" to:ss
        format "        return sampleUnescapeContent entryContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleReadChangelog sources packageVersion = (\n" to:ss
        format "        local changelogSectionName = \"version_\" + packageVersion\n" to:ss
        format "        local countContent = getINISetting sources.changelogFilePath changelogSectionName \"count\"\n" to:ss
        format "        local changelogCount = try (countContent as integer) catch(0)\n" to:ss
        format "        local changelogContent = \"\"\n\n" to:ss
        format "        for i in 1 to changelogCount do (\n" to:ss
        format "            local itemType = getINISetting sources.changelogFilePath changelogSectionName ((i as string) + \"_type\")\n" to:ss
        format "            local itemContent = getINISetting sources.changelogFilePath changelogSectionName ((i as string) + \"_text\")\n" to:ss
        format "            if (itemType != undefined and itemType != \"\" and itemContent != undefined and itemContent != \"\") do (\n" to:ss
        format "                changelogContent += \"- [\" + itemType + \"] \" + (sampleUnescapeContent itemContent) + \"\\r\\n\"\n" to:ss
        format "            )\n" to:ss
        format "        )\n\n" to:ss
        format "        if (changelogContent == \"\") do changelogContent = \"No changelog entries for this version.\"\n" to:ss
        format "        return changelogContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleReadPackageInfo sources = (\n" to:ss
        format "        local packageVersion = sampleReadIniEntry sources \"version\" \"version\" fallbackContent:\"1.0.0\"\n\n" to:ss
        format "        local packageInfo = SamplePackageInfoData()\n" to:ss
        format "        packageInfo.packageTitle = sampleReadIniEntry sources \"name\" \"packageName\" fallbackContent:\"Package\"\n" to:ss
        format "        packageInfo.packageVersion = packageVersion\n" to:ss
        format "        packageInfo.releaseChannel = sampleReadIniEntry sources \"releaseChannel\" \"releaseChannel\" fallbackContent:\"stable\"\n" to:ss
        format "        packageInfo.releaseDate = sampleReadIniEntry sources \"releaseDate\" \"releaseDate\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.packageLicense = sampleReadIniEntry sources \"license\" \"license\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.developerTitle = sampleReadIniEntry sources \"developerName\" \"developerName\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.minMaxVersion = sampleReadIniEntry sources \"min3dsMax\" \"min3dsMax\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.maxMaxVersion = sampleReadIniEntry sources \"max3dsMax\" \"max3dsMax\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.homepageLink = sampleReadIniEntry sources \"homepage\" \"homepage\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.documentationLink = sampleReadIniEntry sources \"documentation\" \"documentation\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.supportLink = sampleReadIniEntry sources \"support\" \"support\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.packageDescription = sampleReadIniEntry sources \"description\" \"description\" fallbackContent:\"\"\n" to:ss
        format "        packageInfo.changelogContent = sampleReadChangelog sources packageVersion\n\n" to:ss
        format "        return packageInfo\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleInfoLine labelText infoContent = (\n" to:ss
        format "        if (infoContent == undefined or infoContent == \"\") do return \"\"\n" to:ss
        format "        return labelText + infoContent + \"\\r\\n\"\n" to:ss
        format "    )\n\n" to:ss
        format "    fn sampleUninstallInfoContent packageInfo = (\n" to:ss
        format "        local infoContent = packageInfo.packageTitle + \" has been completely removed.\"\n\n" to:ss
        format "        return infoContent\n" to:ss
        format "    )\n\n" to:ss
        format "    local sources = sampleDataSources()\n" to:ss
        format "    local packageInfo = sampleReadPackageInfo sources\n" to:ss
        format "    local uninstallInfoContent = sampleUninstallInfoContent packageInfo\n\n" to:ss
        format "    try (destroyDialog MaxPkgSampleUninstallRollout) catch()\n\n" to:ss
        format "    rollout MaxPkgSampleUninstallRollout \"Uninstall Complete\" width:430 height:315\n" to:ss
        format "    (\n" to:ss
        format "        dotNetControl dncUninstallInfo \"System.Windows.Forms.TextBox\" width: 450 height:302 align:#left offset: [-13, -5] align:#left\n" to:ss
        format "        label lblUninstallSpacer \"\" align:#left across:2 offset:[0, 4]\n" to:ss
        format "        button btnCloseUninstallInfo \"Close\" width:80 height:24 align:#right offset:[0, 4]\n\n" to:ss
        format "        on MaxPkgSampleUninstallRollout open do (\n" to:ss
        format "            local scrollBarsClass = dotNetClass \"System.Windows.Forms.ScrollBars\"\n" to:ss
        format "            dncUninstallInfo.Multiline = true\n" to:ss
        format "            dncUninstallInfo.ReadOnly = true\n" to:ss
        format "            dncUninstallInfo.WordWrap = true\n" to:ss
        format "            dncUninstallInfo.ScrollBars = scrollBarsClass.Vertical\n" to:ss
        format "            dncUninstallInfo.Text = uninstallInfoContent\n" to:ss
        format "        )\n\n" to:ss
        format "        on btnCloseUninstallInfo pressed do destroyDialog MaxPkgSampleUninstallRollout\n" to:ss
        format "    )\n\n" to:ss
        format "    createDialog MaxPkgSampleUninstallRollout width:450 height:350 modal:false\n" to:ss
        format ")\n" to:ss

        return ss as string
    )

    fn createSamplePackageScript scriptFileName sampleContent = (
        local sampleFilePath = normalizePath ((ensureTrailingSlash rootDir) + scriptFileName)

        if (doesFileExist sampleFilePath) do (
            messageBox (scriptFileName + " already exists.") title:"MaxPkg Packager"
            return false
        )

        if (not (writeTextFile sampleFilePath sampleContent)) do (
            messageBox ("Could not create " + scriptFileName + ".") title:"MaxPkg Packager"
            return false
        )

        addPackageFile sampleFilePath
        addLog "OK" (scriptFileName + " created")
        messageBox (scriptFileName + " created successfully.\n\nLocation:\n" + sampleFilePath) title:"MaxPkg Packager"
        return true
    )

    fn mzpQuotedString sourceContent = (
        local quotedContent = trimString sourceContent
        quotedContent = substituteString quotedContent "\"" "'"
        return "\"" + quotedContent + "\""
    )

    fn buildMzpRunScript ui = (
        local ss = stringStream ""
        local packageTitle = trimString ui.edtName.text
        local packageGuid = trimString ui.edtGuid.text
        local entryScriptFile = "mzp.run.ms"

        if (packageTitle == "") do packageTitle = packageGuid

        format "name %\n" (mzpQuotedString packageTitle) to:ss
        format "extract to %\n" (mzpQuotedString ("$temp\\" + packageGuid)) to:ss
        format "drop %\n" (mzpQuotedString entryScriptFile) to:ss
        format "run %\n" (mzpQuotedString entryScriptFile) to:ss

        return ss as string
    )

    fn buildMzpEntryScript = (
        local ss = stringStream ""

        format "(\n" to:ss
        format "    fn maxPkgEntryEnsureSlash folderPath = (\n" to:ss
        format "        if (folderPath == undefined or folderPath == \"\") do return \"\"\n" to:ss
        format "        if ((substring folderPath folderPath.count 1) == \"\\\\\") do return folderPath\n" to:ss
        format "        return folderPath + \"\\\\\"\n" to:ss
        format "    )\n\n" to:ss
        format "    fn maxPkgEntryMacroNameFromGuid packageGuid = (\n" to:ss
        format "        return \"MaxPkg_\" + (substituteString packageGuid \"-\" \"\")\n" to:ss
        format "    )\n\n" to:ss
        format "    fn maxPkgEntryStringLiteral sourceContent = (\n" to:ss
        format "        local literalContent = sourceContent as string\n" to:ss
        format "        literalContent = substituteString literalContent \"\\\\\" \"\\\\\\\\\"\n" to:ss
        format "        literalContent = substituteString literalContent \"\\\"\" \"\\\\\\\"\"\n" to:ss
        format "        return \"\\\"\" + literalContent + \"\\\"\"\n" to:ss
        format "    )\n\n" to:ss
        format "    fn maxPkgEntryForwardPathLiteral sourceFilePath = (\n" to:ss
        format "        local literalContent = sourceFilePath as string\n" to:ss
        format "        literalContent = substituteString literalContent \"\\\\\" \"/\"\n" to:ss
        format "        literalContent = substituteString literalContent \"\\\"\" \"\\\\\\\"\"\n" to:ss
        format "        return \"\\\"\" + literalContent + \"\\\"\"\n" to:ss
        format "    )\n\n" to:ss
        format "    fn maxPkgEntryWriteTextFile targetFilePath fileContent = (\n" to:ss
        format "        local fileStream = undefined\n\n" to:ss
        format "        try (\n" to:ss
        format "            fileStream = createFile targetFilePath\n" to:ss
        format "            if (fileStream == undefined) do return false\n" to:ss
        format "            format \"%\" fileContent to:fileStream\n" "%" to:ss
        format "            close fileStream\n" to:ss
        format "            return true\n" to:ss
        format "        ) catch (\n" to:ss
        format "            try (if (fileStream != undefined) do close fileStream) catch()\n" to:ss
        format "            return false\n" to:ss
        format "        )\n" to:ss
        format "    )\n\n" to:ss
        format "    fn maxPkgEntryInstallIcon entryFolder packageGuid = (\n" to:ss
        format "        local sourceIconFile = entryFolder + \"icons\\\\icon.svg\"\n" to:ss
        format "        local targetIconFile = (maxPkgEntryEnsureSlash (getDir #userIcons)) + packageGuid + \".svg\"\n\n" to:ss
        format "        if (not (doesFileExist sourceIconFile)) do return true\n\n" to:ss
        format "        try (\n" to:ss
        format "            if (doesFileExist targetIconFile) do deleteFile targetIconFile\n" to:ss
        format "            copyFile sourceIconFile targetIconFile\n" to:ss
        format "            return true\n" to:ss
        format "        ) catch (\n" to:ss
        format "            messageBox (\"Could not install package icon:\\n\" + targetIconFile + \"\\n\\n\" + getCurrentException()) title:\"MaxPkg\"\n" to:ss
        format "            return false\n" to:ss
        format "        )\n" to:ss
        format "    )\n\n" to:ss
        format "    fn maxPkgEntryBuildMacroScript entryFolder packageGuid = (\n" to:ss
        format "        local manifestFilePath = entryFolder + \"manifest.ini\"\n" to:ss
        format "        local packageButtonText = getINISetting manifestFilePath \"package\" \"buttonName\"\n" to:ss
        format "        local packageIcon = getINISetting manifestFilePath \"package\" \"icon\"\n" to:ss
        format "        local macroIconFilePath = (maxPkgEntryEnsureSlash (getDir #userIcons)) + packageGuid + \".svg\"\n" to:ss
        format "        local macroContent = \"\"\n\n" to:ss
        format "        if (packageButtonText == undefined or packageButtonText == \"\") do packageButtonText = packageGuid\n\n" to:ss
        format "        macroContent += \"macroScript \" + (maxPkgEntryMacroNameFromGuid packageGuid) + \"\\n\"\n" to:ss
        format "        macroContent += \"category:\\\"MaxPkg\\\"\\n\"\n" to:ss
        format "        macroContent += \"buttonText:\" + (maxPkgEntryStringLiteral packageButtonText) + \"\\n\"\n" to:ss
        format "        macroContent += \"tooltip:\" + (maxPkgEntryStringLiteral (\"Run \" + packageButtonText)) + \"\\n\"\n" to:ss
        format "        if (packageIcon != undefined and packageIcon != \"\") do macroContent += \"iconName:\" + (maxPkgEntryForwardPathLiteral macroIconFilePath) + \"\\n\"\n" to:ss
        format "        macroContent += \"(\\n\"\n" to:ss
        format "        macroContent += \"    on execute do\\n\"\n" to:ss
        format "        macroContent += \"    (\\n\"\n" to:ss
        format "        macroContent += \"        -- Generated by MaxPkg. https://maxpkg.dev\\n\"\n" to:ss
        format "        macroContent += \"        -- This file was created during package installation for the current 3ds Max profile.\\n\"\n" to:ss
        format "        macroContent += \"        -- Package GUID: \" + packageGuid + \"\\n\"\n" to:ss
        format "        macroContent += \"        try\\n\"\n" to:ss
        format "        macroContent += \"        (\\n\"\n" to:ss
        format "        macroContent += \"            local packageGuid = \" + (maxPkgEntryStringLiteral packageGuid) + \"\\n\"\n" to:ss
        format "        macroContent += \"            local packageDir = (getDir #temp) + \" + (maxPkgEntryStringLiteral \"\\\\\") + \" + packageGuid + \" + (maxPkgEntryStringLiteral \"\\\\\") + \"\\n\"\n" to:ss
        format "        macroContent += \"            local manifestIni = packageDir + \" + (maxPkgEntryStringLiteral \"manifest.ini\") + \"\\n\"\n" to:ss
        format "        macroContent += \"            if (not (doesFileExist manifestIni)) do throw (\" + (maxPkgEntryStringLiteral \"Package manifest was not found: \") + \" + manifestIni)\\n\"\n" to:ss
        format "        macroContent += \"            local runtime = getINISetting manifestIni \" + (maxPkgEntryStringLiteral \"package\") + \" \" + (maxPkgEntryStringLiteral \"runtime\") + \"\\n\"\n" to:ss
        format "        macroContent += \"            local entry = getINISetting manifestIni \" + (maxPkgEntryStringLiteral \"package\") + \" \" + (maxPkgEntryStringLiteral \"entry\") + \"\\n\"\n" to:ss
        format "        macroContent += \"            if (entry == undefined or entry == \" + (maxPkgEntryStringLiteral \"\") + \") do throw \" + (maxPkgEntryStringLiteral \"Package entry file is empty.\") + \"\\n\"\n" to:ss
        format "        macroContent += \"            local entryPath = packageDir + entry\\n\"\n" to:ss
        format "        macroContent += \"            if (not (doesFileExist entryPath)) do throw (\" + (maxPkgEntryStringLiteral \"Package entry file was not found: \") + \" + entryPath)\\n\"\n" to:ss
        format "        macroContent += \"            if (runtime == \" + (maxPkgEntryStringLiteral \"python\") + \") then\\n\"\n" to:ss
        format "        macroContent += \"            (\\n\"\n" to:ss
        format "        macroContent += \"                python.ExecuteFile entryPath\\n\"\n" to:ss
        format "        macroContent += \"            )\\n\"\n" to:ss
        format "        macroContent += \"            else\\n\"\n" to:ss
        format "        macroContent += \"            (\\n\"\n" to:ss
        format "        macroContent += \"                fileIn entryPath\\n\"\n" to:ss
        format "        macroContent += \"            )\\n\"\n" to:ss
        format "        macroContent += \"        )\\n\"\n" to:ss
        format "        macroContent += \"        catch\\n\"\n" to:ss
        format "        macroContent += \"        (\\n\"\n" to:ss
        format "        macroContent += \"            messageBox (\" + (maxPkgEntryStringLiteral \"Could not run MaxPkg package.\") + \" + getCurrentException()) title:\" + (maxPkgEntryStringLiteral \"MaxPkg\") + \"\\n\"\n" to:ss
        format "        macroContent += \"        )\\n\"\n" to:ss
        format "        macroContent += \"    )\\n\"\n" to:ss
        format "        macroContent += \")\\n\"\n\n" to:ss
        format "        return macroContent\n" to:ss
        format "    )\n\n" to:ss
        format "    fn maxPkgEntryInstallMacroButton entryFolder packageGuid = (\n" to:ss
        format "        local manifestFilePath = entryFolder + \"manifest.ini\"\n" to:ss
        format "        local createMacroButton = getINISetting manifestFilePath \"package\" \"createMacroButton\"\n" to:ss
        format "        local macroFilePath = (maxPkgEntryEnsureSlash (getDir #userMacros)) + \"maxpkg-\" + packageGuid + \".mcr\"\n" to:ss
        format "        local macroContent = \"\"\n\n" to:ss
        format "        if (createMacroButton == undefined) do createMacroButton = \"\"\n" to:ss
        format "        createMacroButton = toLower createMacroButton\n\n" to:ss
        format "        if (createMacroButton != \"true\") do return true\n\n" to:ss
        format "        maxPkgEntryInstallIcon entryFolder packageGuid\n" to:ss
        format "        macroContent = maxPkgEntryBuildMacroScript entryFolder packageGuid\n\n" to:ss
        format "        if (not (maxPkgEntryWriteTextFile macroFilePath macroContent)) do (\n" to:ss
        format "            messageBox (\"Could not create package macro button:\\n\" + macroFilePath) title:\"MaxPkg\"\n" to:ss
        format "            return false\n" to:ss
        format "        )\n\n" to:ss
        format "        try (\n" to:ss
        format "            fileIn macroFilePath\n" to:ss
        format "            return true\n" to:ss
        format "        ) catch (\n" to:ss
        format "            messageBox (\"Could not load package macro button:\\n\" + macroFilePath + \"\\n\\n\" + getCurrentException()) title:\"MaxPkg\"\n" to:ss
        format "            return false\n" to:ss
        format "        )\n" to:ss
        format "    )\n\n" to:ss
        format "    fn maxPkgEntryRunOptionalScript scriptFilePath = (\n" to:ss
        format "        if (scriptFilePath == undefined or scriptFilePath == \"\") do return false\n" to:ss
        format "        if (not (doesFileExist scriptFilePath)) do return true\n\n" to:ss
        format "        try (\n" to:ss
        format "            fileIn scriptFilePath\n" to:ss
        format "            return true\n" to:ss
        format "        ) catch (\n" to:ss
        format "            messageBox (\"Could not run package script:\\n\" + scriptFilePath + \"\\n\\n\" + getCurrentException()) title:\"MaxPkg\"\n" to:ss
        format "            return false\n" to:ss
        format "        )\n" to:ss
        format "    )\n\n" to:ss
        format "    local entryFolder = maxPkgEntryEnsureSlash (getFilenamePath (getSourceFileName()))\n" to:ss
        format "    local manifestFilePath = entryFolder + \"manifest.ini\"\n" to:ss
        format "    local packageGuid = getINISetting manifestFilePath \"package\" \"packageGuid\"\n\n" to:ss
        format "    if (packageGuid == undefined or packageGuid == \"\") then (\n" to:ss
        format "        messageBox (\"Package GUID was not found in manifest:\\n\" + manifestFilePath) title:\"MaxPkg\"\n" to:ss
        format "    ) else (\n" to:ss
        format "        maxPkgEntryInstallMacroButton entryFolder packageGuid\n" to:ss
        format "        maxPkgEntryRunOptionalScript (entryFolder + \"install.ms\")\n" to:ss
        format "    )\n" to:ss
        format ")\n" to:ss

        return ss as string
    )

    fn copyPackageFile absPath targetPath = (
        ensureDirectory (getFilenamePath targetPath)
        copyFile absPath targetPath
        return true
    )

    fn createMzpFromFolder sourceFolder outputFile = (
        if (doesFileExist outputFile) do deleteFile outputFile

        try (
            dotNet.loadAssembly "System.IO.Compression.FileSystem"
            local ZipFile = dotNetClass "System.IO.Compression.ZipFile"
            ZipFile.CreateFromDirectory sourceFolder outputFile
            return true
        ) catch (
            addLog "ERROR" ("Could not create MZP: " + getCurrentException())
            return false
        )
    )

    fn cleanupBuildFolder buildFolder = (
        if (buildFolder == undefined) do return false
        if (buildFolder == "") do return false
        if (not (directoryExists buildFolder)) do return true

        deleteDirectory buildFolder
        return true
    )

    fn buildPackage ui = (
        saveSettings ui

        if (not (validateSettings ui)) do return false

        local guid = trimString ui.edtGuid.text
        local outputFolder = ensureTrailingSlash ui.edtOutput.text
        local buildRoot = ensureTrailingSlash ((getDir #temp) + "\\maxpkg-packager-build-" + guid)
        local outputFile = outputFolder + guid + ".mzp"
        local isPackageBuilt = false

        try (
            deleteDirectory buildRoot
            ensureDirectory buildRoot

            writeTextFile (buildRoot + "manifest.ini") (buildManifestIni ui)
            addLog "OK" "manifest.ini generated"

            writeTextFile (buildRoot + "manifest.json") (buildManifestJson ui)
            addLog "OK" "manifest.json generated"

            saveCurrentChangelog()
            if (doesFileExist changelogIniPath) do (
                copyFile changelogIniPath (buildRoot + "maxpkg-changelog.ini")
                addLog "OK" "maxpkg-changelog.ini copied"
            )

            for item in packageFiles do (
                copyPackageFile item[1] (buildRoot + item[2])
            )

            addLog "OK" ((packageFiles.count as string) + " files copied")

            if ((trimString ui.edtIcon.text) != "") do (
                ensureDirectory (buildRoot + "icons")
                copyFile ui.edtIcon.text (buildRoot + "icons\\icon.svg")
                addLog "OK" "SVG icon copied"
            )

            writeTextFile (buildRoot + "mzp.run.ms") (buildMzpEntryScript())
            addLog "OK" "mzp.run.ms generated"

            writeTextFile (buildRoot + "mzp.run") (buildMzpRunScript ui)
            addLog "OK" "mzp.run generated"

            if (hasLogErrors()) then (
                addLog "ERROR" "MZP was not created because log contains errors"
            ) else (
                if (createMzpFromFolder buildRoot outputFile) do (
                    addLog "OK" ("MZP created: " + outputFile)
                    isPackageBuilt = true
                )
            )
        ) catch (
            addLog "ERROR" ("Build failed: " + getCurrentException())
            isPackageBuilt = false
        )

        cleanupBuildFolder buildRoot

        return isPackageBuilt
    )


    try (destroyDialog MaxPkgPackagerLogRollout) catch()
    try (destroyDialog MaxPkgUpdateNoticeRollout) catch()
    isLogDialogOpen = false

    try (closeRolloutFloater MaxPkgPackagerFloater) catch()

    rollout MaxPkgGuidChangeConfirmRollout "Confirm GUID Change" width:360 height:150
    (
        label lblGuidChangeWarning "Changing Package GUID creates a new package identity." align:#left
        label lblGuidChangeInstruction "Type CHANGE to generate a new GUID." align:#left offset: [0, 15]
        editText edtGuidChangePhrase "" align:#left

        button btnConfirmGuidChange "OK" width:80 height:24 enabled:false align:#left across:2 offset: [0, 15]
        button btnCancelGuidChange "Cancel" width:80 height:24 align:#right offset: [0, 15]

        on MaxPkgGuidChangeConfirmRollout open do (
            edtGuidChangePhrase.text = ""
            btnConfirmGuidChange.enabled = false
            setFocus edtGuidChangePhrase
        )

        on edtGuidChangePhrase changed fieldText do (
            btnConfirmGuidChange.enabled = ((toUpper fieldText) == "CHANGE")
        )

        on btnConfirmGuidChange pressed do (
            if ((toUpper edtGuidChangePhrase.text) == "CHANGE") do (
                isGuidChangeConfirmed = true
                destroyDialog MaxPkgGuidChangeConfirmRollout
            )
        )

        on btnCancelGuidChange pressed do (
            isGuidChangeConfirmed = false
            destroyDialog MaxPkgGuidChangeConfirmRollout
        )
    )

    fn confirmGuidChange = (
        isGuidChangeConfirmed = false
        try (destroyDialog MaxPkgGuidChangeConfirmRollout) catch()
        createDialog MaxPkgGuidChangeConfirmRollout width:380 height:128 modal:true
        return isGuidChangeConfirmed
    )

    rollout MaxPkgPackagerRollout "Packager" width:740 height:1070
    (
        group "Important Info" (
			label lblName "Package Name" align: #left across: 4
			editText edtName "" width:235 align: #left offset: [-75, 0]
			label lblButtonName "Button Name" align: #left
			editText edtButtonName ""  width: 235 align: #right

			label lblGuid "Package GUID"  align: #left across: 5 offset: [0, 4]
			editText edtGuid "" width:318 offset: [-39, 2] align: #left
			button btnGuidGenerate "Generate" width:70 offset: [150, 0] align: #left
			button btnGuidCopy "Copy"  width:55  offset: [85, 0] align: #left
			button btnGuidPaste "Paste" width:55 offset: [5, 0] align: #left

			label lblDescription "Description" align: #left across: 2
			editText edtDescription "" width:615 height:58 multiline:true align: #left offset: [-255, 0]
		)

        group "Package Metadata" (
			label lblVersion "Version" align: #left across: 10 offset: [0, 4]
			dropdownList ddlVersionMajor ""  width:52 items:(versionNumberItems()) selection:2 align: #left offset: [37, 0]
			label lblVersionDotA "." align: #left offset: [20, 5]
			dropdownList ddlVersionMinor "" width:52 items:(versionNumberItems m: 9) selection:1  align: #left offset: [-46, 0]
			label lblVersionDotB "." align: #left offset: [-63, 5]
			dropdownList ddlVersionPatch "" width:52 items:(versionNumberItems m: 9) selection:1 align: #left offset: [-129, 0]
			label lblReleaseChannel "Channel"  align: #left offset: [-110, 4]
			dropdownList ddlReleaseChannel "" width:95 items:#("stable","alpha","beta") selection:1 align: #left offset: [-122, 0]
			label lblReleaseDate "Release Date"  width:80 align: #left offset: [-60, 4]
			editText edtReleaseDate "" width:105 height:18 align: #left offset: [-53, 2]

			label lblMinMax "Min 3ds Max" align: #left across: 4 offset: [0, 4]
			dropdownList ddlMinMax "" width: 52 items:(maxYearItems()) selection:1 align: #left offset: [-71, 0]
			checkbox chkCreateMacro "Create 3ds Max Macro Button" checked:true  align: #left offset: [-39, 0]
			checkbox chkShowToolbar "Show In MaxPkg Toolbar"  checked:true align: #left offset: [-25, 0]
			
			label lblIcon "SVG Icon" align: #left across: 5
			editText edtIcon "" width: 348 align: #left offset: [-39, 0]
			button btnIconBrowse "Browse" width:80 align: #right offset: [110, 0]
			button btnIconClear "Clear"  width:80 align: #right offset: [55, 0]
			button btnIconPreview "Preview" width:80 align: #right 
		)

        group "Info"(
			label lblDeveloperName "Developer Name" across: 4 align: #left offset: [0, 4]
			editText edtDeveloperName "" width:235  align: #left offset: [-75, 4]
			label lblLicense "License" align: #left offset: [0, 4]
			dropdownList ddlLicense "" width: 100 items:#("Free","Shareware","Commercial","Open source","Trial") selection:1  align: #left offset: [-52, 0]

			label lblLicenseUrl "License URL" across: 4 align: #left
			editText edtLicenseUrl "" width:235  align: #left offset: [-75, 0]
			label lblHomepage "Homepage URL" align: #left
			editText edtHomepage "" width:235 align: #right

			label lblDocs "Documentation URL"  across: 4 align: #left
			editText edtDocumentation ""  width:235  align: #left offset: [-75, 0]
			label lblSupport "Support URL" align: #left
			editText edtSupport "" width:235 align: #right						
		)

        group "Files List" (
			label lblOutput "Output Folder" align: #left across: 3 offset: [0, 5]
			editText edtOutput "" width: 524 align: #left offset: [-135, 5]
			button btnOutputBrowse "Browse" width:80 align: #right offset: [0, 2]
			
			listBox lbFiles "" height:7
			
			button btnAddFile "[+] Add Files" width: 80 align: #left across: 6
			button btnAddFolder "Add Folder" width:80 align: #left offset: [-31, 0]
			button btnScanRoot "Scan Folder" width:80 align: #left offset: [-62, 0]			
			button btnCreateSampleInstall "Create sample install.ms" width:178 align:#left offset:[-93, 0]
            button btnCreateSampleUninstall "Create sample uninstall.ms" width:178 align:#left offset:[-27, 0]			
			button btnRemoveFile "[-] Remove" width:80 align: #right

         
		)
		
		group "Runtime" (
			label lblRuntime "Launch" align: #left across: 5 offset: [0, 4]
			dropdownList ddlRuntime "" width:120 items:#("maxscript", "python") selection:1 align: #left offset: [-37, 0]
			label lblEntry "Entry File" align: #left offset: [34, 4]
			editText edtEntry ""width: 250 align: #right offset: [53, 3]
			button btnEntryFromSelected "Use Selected" width: 80 align: #right	
		)

        group "Changelog" (
			listBox lbChangelog "" height:5
			
			dropdownList ddlChangeType "" width: 100 items:#("added","fixed","changed","removed","improved") selection:1 align: #left across: 5
			editText edtChangeText "" width: 347 align: #left offset: [-39, 0]
			button btnAddChange "Add" width:80 align: #right offset: [110, 0]
			button btnEditChange "Edit" width:80 align: #right offset: [55, 0]
			button btnRemoveChange "Remove" width:80 align: #right
		)

       
		button btnValidate "Validate" width: 120 height:28 align:#left across: 2 offset: [0, 15]
		button btnBuild "Build MZP" width: 120 height:28 align:#right offset: [0, 15]


        fn refreshFiles = (
            lbFiles.items = getPackageFileNames()
            refreshLogWindow()
            return true
        )

        fn refreshChangelog = (
            local items = #()

            for item in changelogItems do (
                append items (item[1] + ": " + item[2])
            )

            lbChangelog.items = items
            return true
        )

        fn refreshLog = (
            refreshLogWindow()
            return true
        )

        fn syncVersionState = (
            if (ddlVersionMajor.selection < 1) do setDropDownText ddlVersionMajor "1"
            if (ddlVersionMinor.selection < 1) do setDropDownText ddlVersionMinor "0"
            if (ddlVersionPatch.selection < 1) do setDropDownText ddlVersionPatch "0"
            return true
        )

        fn autoSaveSettings = (
            saveSettings MaxPkgPackagerRollout
            return true
        )

        fn switchChangelogVersion = (
            if (isLoadingSettings) do return false

            saveChangelogForVersion activeChangelogVersion
            activeChangelogVersion = buildVersionString MaxPkgPackagerRollout

            if (not (loadChangelogForVersion activeChangelogVersion)) do (
                changelogItems = #()
                saveCurrentChangelog()
            )

            refreshChangelog()
            saveSettings MaxPkgPackagerRollout
            return true
        )


        on MaxPkgPackagerRollout open do (
            isLoadingSettings = true
            edtOutput.text = rootDir + "dist"
            edtReleaseDate.text = currentDateString()
            isLoadingSettings = false

            if (doesFileExist iniPath) then (
                loadSettings MaxPkgPackagerRollout
            ) else (
                syncVersionState()
                saveSettings MaxPkgPackagerRollout
            )

            syncVersionState()
            activeChangelogVersion = buildVersionString MaxPkgPackagerRollout
            if (not (loadChangelogForVersion activeChangelogVersion)) do (
                changelogItems = #()
                saveCurrentChangelog()
            )

            refreshFiles()
            refreshChangelog()
            refreshLog()
        )

        on edtName changed fieldText do autoSaveSettings()
        on edtButtonName changed fieldText do autoSaveSettings()
        on edtDeveloperName changed fieldText do autoSaveSettings()
        on edtGuid changed fieldText do autoSaveSettings()
        on edtDescription changed fieldText do autoSaveSettings()
        on ddlLicense selected selectedIndex do autoSaveSettings()
        on edtLicenseUrl changed fieldText do autoSaveSettings()
        on ddlVersionMajor selected selectedIndex do switchChangelogVersion()
        on ddlVersionMinor selected selectedIndex do switchChangelogVersion()
        on ddlVersionPatch selected selectedIndex do switchChangelogVersion()
        on ddlReleaseChannel selected selectedIndex do autoSaveSettings()
        on edtReleaseDate changed fieldText do autoSaveSettings()
        on ddlMinMax selected selectedIndex do autoSaveSettings()
        on ddlRuntime selected selectedIndex do autoSaveSettings()
        on edtEntry changed fieldText do autoSaveSettings()
        on edtIcon changed fieldText do autoSaveSettings()
        on edtHomepage changed fieldText do autoSaveSettings()
        on edtDocumentation changed fieldText do autoSaveSettings()
        on edtSupport changed fieldText do autoSaveSettings()
        on chkCreateMacro changed isChecked do autoSaveSettings()
        on chkShowToolbar changed isChecked do autoSaveSettings()
        on edtOutput changed fieldText do autoSaveSettings()

        on btnGuidGenerate pressed do (
            if ((trimString edtGuid.text) == "") then (
                edtGuid.text = newGuidString()
            ) else (
                if (confirmGuidChange()) do (
                    edtGuid.text = newGuidString()
                )
            )

            autoSaveSettings()
        )

        on btnGuidCopy pressed do (
            setClipboardText edtGuid.text
        )

        on btnGuidPaste pressed do (
            edtGuid.text = getClipboardText()
            autoSaveSettings()
        )

        on btnEntryFromSelected pressed do (
            if (lbFiles.selection > 0) do (
                edtEntry.text = lbFiles.items[lbFiles.selection]
                autoSaveSettings()
            )
        )

        on btnIconBrowse pressed do (
            local filePath = getOpenFileName caption:"Select safe SVG icon" types:"SVG (*.svg)|*.svg|All Files (*.*)|*.*|"

            if (filePath != undefined) do (
                if (isValidSafeSvg filePath) then (
                    local rootIconFile = copySvgIconToRoot filePath

                    if (rootIconFile != "") then (
                        edtIcon.text = rootIconFile
                        addLog "OK" "SVG icon copied to root"
                        autoSaveSettings()
                    ) else (
                        messageBox "Could not copy SVG icon to root folder." title:"MaxPkg Packager"
                        addLog "ERROR" "Could not copy SVG icon to root folder."
                    )
                ) else (
                    messageBox "Selected icon is not a valid safe SVG file." title:"MaxPkg Packager"
                    addLog "ERROR" "Selected icon is not a valid safe SVG file."
                )

                refreshLog()
            )
        )

        on btnIconClear pressed do (
            edtIcon.text = ""
            autoSaveSettings()
        )

        on btnIconPreview pressed do (
            if (edtIcon.text != "" and doesFileExist edtIcon.text) do (
                shellLaunch edtIcon.text ""
            )
        )

        on btnOutputBrowse pressed do (
            local folder = getSavePath caption:"Select output folder" initialDir:rootDir
            if (folder != undefined) do (
                edtOutput.text = folder
                autoSaveSettings()
            )
        )

        on btnAddFile pressed do (
            local filePath = getOpenFileName caption:"Add package file" filename:(rootDir + "*.*") types:"Package Files (*.*)|*.*|"

            if (filePath != undefined) do (
                if (addPackageFile filePath) do (
                    addLog "OK" ("Added file: " + (relativePathFromRoot filePath))
                )

                refreshFiles()
                autoSaveSettings()
            )
        )

        on btnAddFolder pressed do (
            local folder = getSavePath caption:"Add package folder" initialDir:rootDir

            if (folder != undefined) do (
                local added = addFolderFiles folder
                addLog "OK" ((added as string) + " files added from folder")
                refreshFiles()
                autoSaveSettings()
            )
        )

        on btnScanRoot pressed do (
            packageFiles = #()

            local added = addFolderFiles rootDir
            addLog "OK" ((added as string) + " files scanned from product folder")
            refreshFiles()
            autoSaveSettings()
        )

        on btnCreateSampleInstall pressed do (
            if (createSamplePackageScript "install.ms" (buildSampleInstallScript())) do (
                refreshFiles()
                autoSaveSettings()
            )
        )

        on btnCreateSampleUninstall pressed do (
            if (createSamplePackageScript "uninstall.ms" (buildSampleUninstallScript())) do (
                refreshFiles()
                autoSaveSettings()
            )
        )

        on btnRemoveFile pressed do (
            if (lbFiles.selection > 0 and lbFiles.selection <= packageFiles.count) do (
                local selectedIndex = lbFiles.selection
                local selectedFileName = lbFiles.items[selectedIndex]
                local shouldRemoveFile = queryBox ("Remove this file from package list?\n\n" + selectedFileName) title:"MaxPkg Packager"

                if (shouldRemoveFile) do (
                    deleteItem packageFiles selectedIndex
                    refreshFiles()
                    autoSaveSettings()
                )
            )
        )

        on btnAddChange pressed do (
            local changeValue = trimString edtChangeText.text

            if (changeValue != "") do (
                append changelogItems #((getDropDownText ddlChangeType), changeValue)
                edtChangeText.text = ""
                refreshChangelog()
                saveCurrentChangelog()
                autoSaveSettings()
            )
        )

        on btnEditChange pressed do (
            if (lbChangelog.selection > 0) do (
                changelogItems[lbChangelog.selection] = #((getDropDownText ddlChangeType), (trimString edtChangeText.text))
                refreshChangelog()
                saveCurrentChangelog()
                autoSaveSettings()
            )
        )

        on btnRemoveChange pressed do (
            if (lbChangelog.selection > 0) do (
                deleteItem changelogItems lbChangelog.selection
                refreshChangelog()
                saveCurrentChangelog()
                autoSaveSettings()
            )
        )

        on lbChangelog selected index do (
            if (index > 0) do (
                local item = changelogItems[index]
                setDropDownText ddlChangeType item[1]
                edtChangeText.text = item[2]
            )
        )

        on btnValidate pressed do (
            saveSettings MaxPkgPackagerRollout
            validateSettings MaxPkgPackagerRollout
            showLogWindow()
        )        

        on btnBuild pressed do (
            local isSuccess = buildPackage MaxPkgPackagerRollout
            showLogWindow()	

			if (isSuccess and edtOutput.text != "" and doesDirectoryExist edtOutput.text) do (
				ShellLaunch edtOutput.text ""
			)			
        )

        on MaxPkgPackagerRollout close do (
            closeLogWindow()
        )
    )

    rollout MaxPkgPackagerLogRollout "Log" width:700 height:100
    (

		dotNetControl dncLogContent "System.Windows.Forms.TextBox" height:300 align:#left

		button btnClearLogWindow "Clear Log" width:80 height:24 align:#left across:2
		button btnCloseLogWindow "Close" width:80 height:24 align:#right


        on MaxPkgPackagerLogRollout open do (
            local scrollBarsClass = dotNetClass "System.Windows.Forms.ScrollBars"

            isLogDialogOpen = true
            dncLogContent.Multiline = true
            dncLogContent.ReadOnly = true
            dncLogContent.WordWrap = true
            dncLogContent.ScrollBars = scrollBarsClass.Vertical
            dncLogContent.Text = getLogText()
        )

        on MaxPkgPackagerLogRollout close do (
            isLogDialogOpen = false
        )

        on btnClearLogWindow pressed do (
            clearLog()
            refreshLogWindow()
        )

        on btnCloseLogWindow pressed do (
            closeLogWindow()
        )
    )

    fn refreshLogWindow = (
        local isRefreshed = true

        if (isLogDialogOpen) do (
            try (
                MaxPkgPackagerLogRollout.dncLogContent.Text = getLogText()
            ) catch (
                isLogDialogOpen = false
                isRefreshed = false
            )
        )

        return isRefreshed
    )

    fn showLogWindow = (
        if (isLogDialogOpen) do (
            if (not (refreshLogWindow())) do isLogDialogOpen = false
        )

        if (not isLogDialogOpen) do (
            try (
                createDialog MaxPkgPackagerLogRollout width:720 height:340
            ) catch (
                isLogDialogOpen = false
                return false
            )
        )

        refreshLogWindow()
        return true
    )

    fn closeLogWindow = (
        if (isLogDialogOpen) do (
            try (destroyDialog MaxPkgPackagerLogRollout) catch()
            isLogDialogOpen = false
        )

        return true
    )

    rollout MaxPkgUpdateNoticeRollout "MaxPkg Packager Updated" width:520 height:355
    (
        group "Update Installed" (
            label lblUpdateNoticeTitle "MaxPkg Packager has been updated." align:#left
            dotNetControl dncUpdateNoticeContent "System.Windows.Forms.TextBox" height:245 align:#left
        )

        button btnRestartUpdatedScript "Restart Packager" width:120 align:#left across:2
        button btnCloseUpdateNotice "Close" width:80 align:#right

        on MaxPkgUpdateNoticeRollout open do (
            local scrollBarsClass = dotNetClass "System.Windows.Forms.ScrollBars"
            dncUpdateNoticeContent.Multiline = true
            dncUpdateNoticeContent.ReadOnly = true
            dncUpdateNoticeContent.WordWrap = true
            dncUpdateNoticeContent.ScrollBars = scrollBarsClass.Vertical
            dncUpdateNoticeContent.Text = pendingUpdateNoticeContent
        )

        on btnRestartUpdatedScript pressed do (
            try (destroyDialog MaxPkgUpdateNoticeRollout) catch()
            try (fileIn pendingUpdateScriptFile) catch (
                messageBox "Update installed, but the script could not restart automatically." title:"MaxPkg Packager"
            )
        )

        on btnCloseUpdateNotice pressed do (
            destroyDialog MaxPkgUpdateNoticeRollout
        )
    )

    fn buildUpdateNoticeContent updateResult = (
        local noticeContent = "Update installed successfully.\r\n\r\n"
        noticeContent += "Previous version: " + updateResult.currentVersionString + "\r\n"
        noticeContent += "Installed version: " + updateResult.newVersionString + "\r\n\r\n"
        noticeContent += "Changelog:\r\n"
        noticeContent += updateResult.releaseNotesContent
        noticeContent += "\r\n\r\nClick Restart Packager to load the updated script."
        return noticeContent
    )

    fn showUpdateNoticeDialog updateResult = (
        if (updateResult == undefined) do return false
        if (not updateResult.isUpdated) do return false

        pendingUpdateScriptFile = updateResult.scriptFilePath
        pendingUpdateNoticeContent = buildUpdateNoticeContent updateResult

        try (destroyDialog MaxPkgUpdateNoticeRollout) catch()
        try (
            createDialog MaxPkgUpdateNoticeRollout width:540 height:380
        ) catch (
            messageBox pendingUpdateNoticeContent title:"MaxPkg Packager Updated"
            return false
        )

        return true
    )

    fn startupUpdateDoWork sender eventArgs = (
        startupUpdateResult = checkAndDownloadScriptUpdate showMessages:false reloadAfterUpdate:false
        local hasStartupUpdate = false
        if (startupUpdateResult != undefined) do hasStartupUpdate = startupUpdateResult.isUpdated
        eventArgs.Result = hasStartupUpdate
        return true
    )

    fn startupUpdateCompleted sender eventArgs = (
        if (eventArgs.Error != undefined) do return false
        if (eventArgs.Result == true) do showUpdateNoticeDialog startupUpdateResult
        return true
    )

    fn startStartupUpdateCheck = (
        try (
            startupUpdateWorker = dotNetObject "CSharpUtilities.SynchronizingBackgroundWorker"
            startupUpdateWorker.WorkerSupportsCancellation = true
            dotNet.addEventHandler startupUpdateWorker "DoWork" startupUpdateDoWork
            dotNet.addEventHandler startupUpdateWorker "RunWorkerCompleted" startupUpdateCompleted
            startupUpdateWorker.RunWorkerAsync()
            return true
        ) catch (
            return false
        )
    )

    rollout MaxPkgPackagerAboutRollout "About" width:740
    (
        local isUpdateCheckRunning = false
        local aboutUpdateWorker = undefined
        local aboutUpdateResult = undefined

        group "Script Info" (
            label lblAboutTitle "" align:#left
            label lblAboutVersion "" align:#left
            label lblAboutAuthor "" align:#left
            dotNetControl dncAboutDescription "System.Windows.Forms.TextBox" height:70 align:#left
        )

        group "Links" (
            label lblSiteCaption "Website:" align:#left across:2 width:80
            hyperlink hplAboutSite "" align:#left offset:[-250, 0] color: orange hoverColor:orange visitedColor: orange
            label lblDeveloperCaption "Developer:" align:#left across:2 width:80
            hyperlink hplAboutDeveloper "" align:#left offset:[-250, 0] color: orange hoverColor:orange visitedColor: orange
            label lblHelpCaption "Help:" align:#left across:2 width:80
            hyperlink hplAboutHelp "" align:#left offset:[-250, 0] color: orange hoverColor:orange visitedColor: orange
        )

        group "Update" (
            label lblAboutUpdateStatus "Update: not checked" align:#left
            button btnCheckAboutUpdate "Check Updates" width:120 align:#left
        )

        group "Paths" (
            label lblAboutRoot "" align:#left
            label lblAboutIni "" align:#left
        )

        fn updateLinkControl linkControl linkUrl emptyCaption:"Not configured" = (
            if (linkUrl == undefined or linkUrl == "") then (
                linkControl.caption = emptyCaption
                linkControl.address = ""
            ) else (
                linkControl.caption = linkUrl
                linkControl.address = linkUrl
            )

            return true
        )

        fn refreshAboutInfo = (
            local scriptInfo = readScriptInfo (currentScriptFilePath())

            lblAboutTitle.caption = scriptInfo.scriptTitle
            lblAboutVersion.caption = "Version: " + scriptInfo.versionString
            lblAboutAuthor.caption = "Author: " + scriptInfo.authorTitle
            lblAboutRoot.caption = "Root: " + rootDir
            lblAboutIni.caption = "INI: " + iniPath

            dncAboutDescription.Multiline = true
            dncAboutDescription.ReadOnly = true
            dncAboutDescription.WordWrap = true
            dncAboutDescription.BorderStyle = (dotNetClass "System.Windows.Forms.BorderStyle").FixedSingle
            dncAboutDescription.Text = scriptInfo.descriptionContent

            updateLinkControl hplAboutSite scriptInfo.siteUrl emptyCaption:"Not configured"
            updateLinkControl hplAboutDeveloper scriptInfo.developerUrl emptyCaption:"Not configured"
            updateLinkControl hplAboutHelp scriptInfo.helpUrl emptyCaption:"Not configured"

            try (MaxPkgPackagerFloater.title = scriptInfo.scriptTitle + " v" + scriptInfo.versionString) catch()
            return true
        )

        fn aboutUpdateDoWork sender eventArgs = (
            aboutUpdateResult = checkAndDownloadScriptUpdate showMessages:false reloadAfterUpdate:false
            local hasAboutUpdate = false
            if (aboutUpdateResult != undefined) do hasAboutUpdate = aboutUpdateResult.isUpdated
            eventArgs.Result = hasAboutUpdate
            return true
        )

        fn aboutUpdateCompleted sender eventArgs = (
            isUpdateCheckRunning = false
            if (eventArgs.Error != undefined) then (
                lblAboutUpdateStatus.caption = "Update: check failed"
            ) else if (eventArgs.Result == true) then (
                lblAboutUpdateStatus.caption = "Update: installed"
                showUpdateNoticeDialog aboutUpdateResult
            ) else (
                local scriptInfo = readScriptInfo (currentScriptFilePath())
                lblAboutUpdateStatus.caption = "Update: current version " + scriptInfo.versionString
            )
            return true
        )

        fn runBackgroundUpdateCheck = (
            if (isUpdateCheckRunning) do return false

            isUpdateCheckRunning = true
            lblAboutUpdateStatus.caption = "Update: checking..."

            try (
                aboutUpdateWorker = dotNetObject "CSharpUtilities.SynchronizingBackgroundWorker"
                aboutUpdateWorker.WorkerSupportsCancellation = true

                dotNet.addEventHandler aboutUpdateWorker "DoWork" aboutUpdateDoWork
                dotNet.addEventHandler aboutUpdateWorker "RunWorkerCompleted" aboutUpdateCompleted
                aboutUpdateWorker.RunWorkerAsync()
            ) catch (
                isUpdateCheckRunning = false
                lblAboutUpdateStatus.caption = "Update: check failed"
                return false
            )

            return true
        )

        on MaxPkgPackagerAboutRollout open do (
            refreshAboutInfo()
        )

        on btnCheckAboutUpdate pressed do (
            runBackgroundUpdateCheck()
        )
    )

    MaxPkgPackagerFloater = newRolloutFloater "MaxPkg Packager" 760 805
    addRollout MaxPkgPackagerRollout MaxPkgPackagerFloater rolledUp:false
    addRollout MaxPkgPackagerAboutRollout MaxPkgPackagerFloater rolledUp:true
    startStartupUpdateCheck()
)
