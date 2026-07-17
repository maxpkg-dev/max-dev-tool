/*
[INFO]
NAME=MaxPkg Packager
VERSION=1.0.1
AUTHOR=Vasyl Lukianenko
DEV=https://3dground.net
SITE=https://maxpkg.dev
HELP=https://maxpkg.dev
UPDATE=https://raw.githubusercontent.com/maxpkg-dev/max-dev-tool/main/maxpkg-packager.ms
MANIFEST_VERSION=1

[ABOUT]
Drag this script into a 3ds Max viewport from a developer productfolder.=
It builds a universal MaxPkg-compatible .mzp package. =
The package does not install MaxPkg Toolbar or MaxPkg Runtime. =

[1.0.0]
* Initial release =

[1.0.1]
* Compact UI functional wiring=

[SCRIPT]
*/

(
    local scriptFilePath = getThisScriptFilename()
    local scriptDir = ""
    local iniFilePath = ""
    local settingsIniFilePath = ""
    local changelogIniFilePath = ""
    local currentTabId = "info"
    local activeContentRollout = undefined
    local isSwitchingTab = false
    local isLoadingSettings = false
    local packageFiles = #()
    local changelogItems = #()
    local activeChangelogVersion = "1.0.0"
    local logItems = #()
    local isGuidChangeConfirmed = false
    local isLogDialogOpen = false
    local startupUpdateWorker = undefined
    local startupUpdateResult = undefined
    local pendingUpdateScriptFile = ""
    local pendingUpdateNoticeContent = ""
    local isSyncingBuildButtonStatus = false

    global MaxPkgPackerNewFloater
    global MaxPkgPackerNewLogRollout
    global MaxPkgPackerNewUpdateNoticeRollout
    global MaxPkgPackerNewTabsRollout
    global MaxPkgPackerNewInfoRollout
    global MaxPkgPackerNewSetupRollout
    global MaxPkgPackerNewFilesRollout
    global MaxPkgPackerNewReleaseRollout
    global MaxPkgPackerNewActionsRollout
    global MaxPkgPackerNewAboutRollout

    local switchTab
    local refreshLogWindow
    local showLogWindow
    local closeLogWindow

    if (scriptFilePath == undefined or scriptFilePath == "") do scriptFilePath = getThisScriptFileName()
    scriptDir = getFilenamePath scriptFilePath
    if (scriptDir == undefined or scriptDir == "") do scriptDir = (getDir #scripts) + "\\"
    iniFilePath = scriptDir + "maxpkg-packager.ini"
    settingsIniFilePath = scriptDir + "maxpkg-packager.ini"
    changelogIniFilePath = scriptDir + "maxpkg-changelog.ini"

    struct MaxPkgPackerNewStateData (
        packageTitle = "",
        buttonTitle = "",
        packageGuid = "",
        descriptionContent = "",
        developerTitle = "",
        licenseType = "",
        licenseUrl = "",
        documentationUrl = "",
        homepageUrl = "",
        supportUrl = "",
        createButton = true,
        showToolbar = true,
        outputFolder = "",
        svgIconFile = "",
        entryFile = "",
        compileEntry = true,
        versionMajor = "1",
        versionMinor = "0",
        versionPatch = "0",
        releaseChannel = "stable",
        releaseDate = "",
        minMaxVersion = "2012"
    )

    local packageState = MaxPkgPackerNewStateData()

    struct MaxPkgPackerNewScriptInfoData (
        scriptTitle,
        versionString,
        authorTitle,
        developerUrl,
        siteUrl,
        helpUrl,
        updateUrl,
        descriptionContent,
        releases,
        manifestVersion
    )

    struct MaxPkgPackerNewUpdateResultData (
        isUpdated,
        currentVersionString,
        newVersionString,
        releaseNotesContent,
        messageContent,
        scriptFilePath
    )

    fn normalizeTabId requestedTabId = (
        local tabId = toLower (requestedTabId as string)

        case tabId of (
            "info": return "info"
            "setup": return "setup"
            "files": return "files"
            "release": return "release"
            default: return "info"
        )
    )

    fn iniSet settingKey settingContent = (
        setINISetting iniFilePath "ui" settingKey (settingContent as string)
        return true
    )

    fn iniGet settingKey defaultContent: "" = (
        local settingContent = getINISetting iniFilePath "ui" settingKey

        if (settingContent == undefined or settingContent == "") do return defaultContent
        return settingContent
    )

    fn selectedTabId = (
        return normalizeTabId (iniGet "lastTab" defaultContent: "info")
    )

    fn setupTextBoxControl textBoxControl isMultiline: false isReadOnly: false = (
        local borderStyleClass = dotNetClass "System.Windows.Forms.BorderStyle"
        local scrollBarsClass = dotNetClass "System.Windows.Forms.ScrollBars"

        textBoxControl.Multiline = isMultiline
        textBoxControl.ReadOnly = isReadOnly
        textBoxControl.WordWrap = true
        textBoxControl.BorderStyle = borderStyleClass.FixedSingle

        if (isMultiline) then (
            textBoxControl.AcceptsReturn = true
            textBoxControl.AcceptsTab = true
            textBoxControl.ScrollBars = scrollBarsClass.Vertical
        ) else (
            textBoxControl.AcceptsReturn = false
            textBoxControl.AcceptsTab = false
            textBoxControl.ScrollBars = scrollBarsClass.None
        )

        return true
    )

    fn trimString sourceContent tag: " " = (
        if (sourceContent == undefined) do return ""
        sourceContent = sourceContent as string
        return trimLeft (trimRight sourceContent tag) tag
    )

    fn fieldColorFromRgb redAmount greenAmount blueAmount = (
        local colorClass = dotNetClass "System.Drawing.Color"
        return colorClass.FromArgb redAmount greenAmount blueAmount
    )

    fn setValidationColor textBoxControl statusType = (
        local colorClass = dotNetClass "System.Drawing.Color"
        local colorRef = colorClass.White

        case statusType of (
            #valid: colorRef = fieldColorFromRgb 246 255 246
            #invalid: colorRef = fieldColorFromRgb 255 246 246
            default: colorRef = colorClass.White
        )

        try (textBoxControl.BackColor = colorRef) catch()
        return true
    )

    fn validationStatusFromBool statusFlag = (
        if (statusFlag) do return #valid
        return #invalid
    )

    fn optionalTextStatus sourceContent = (
        if ((trimString sourceContent) != "") do return #valid
        return #neutral
    )

    fn lowerString sourceContent = (
        if (sourceContent == undefined) do return ""
        return toLower (sourceContent as string)
    )

    fn normalizePath filePath = (
        local normalizedFilePath = filePath as string
        normalizedFilePath = substituteString normalizedFilePath "/" "\\"
        return normalizedFilePath
    )

    fn ensureTrailingSlash folderPath = (
        local normalizedFolderPath = normalizePath folderPath

        if (normalizedFolderPath.count == 0) do return normalizedFolderPath
        if ((substring normalizedFolderPath normalizedFolderPath.count 1) == "\\") do return normalizedFolderPath
        return normalizedFolderPath + "\\"
    )

    fn boolToString isEnabled = (
        if (isEnabled) do return "true"
        return "false"
    )

    fn stringToBool sourceContent defaultContent: true = (
        local boolContent = lowerString (trimString sourceContent)

        if (boolContent == "") do return defaultContent
        return (boolContent == "true" or boolContent == "1" or boolContent == "yes")
    )

    fn getDropDownText dropdownControl = (
        if (dropdownControl.selection < 1) do return ""
        return dropdownControl.items[dropdownControl.selection]
    )

    fn setDropDownText dropdownControl itemContent = (
        local itemIndex = findItem dropdownControl.items itemContent

        if (itemIndex > 0) then (
            dropdownControl.selection = itemIndex
            return true
        )

        return false
    )

    fn addLog logLevel logMessage = (
        append logItems ("[" + logLevel + "] " + logMessage)
        try (refreshLogWindow()) catch()
        return true
    )

    fn clearLog = (
        logItems = #()
        return true
    )

    fn getLogText = (
        local logContent = ""

        for logIndex in 1 to logItems.count do (
            logContent += logItems[logIndex]
            if (logIndex < logItems.count) do logContent += "\r\n"
        )

        return logContent
    )

    fn startsWith sourceContent prefixContent = (
        if (sourceContent == undefined or prefixContent == undefined) do return false
        if (sourceContent.count < prefixContent.count) do return false
        return (substring sourceContent 1 prefixContent.count) == prefixContent
    )

    fn endsWith sourceContent suffixContent = (
        if (sourceContent == undefined or suffixContent == undefined) do return false
        if (sourceContent.count < suffixContent.count) do return false
        return (substring sourceContent (sourceContent.count - suffixContent.count + 1) suffixContent.count) == suffixContent
    )

    fn hasLogErrors = (
        for logMessage in logItems do (
            if (startsWith logMessage "[ERROR]") do return true
        )

        return false
    )

    fn directoryExists folderPath = (
        if (folderPath == undefined or folderPath == "") do return false
        return doesDirectoryExist folderPath
    )

    fn ensureDirectory folderPath = (
        local normalizedFolderPath = ensureTrailingSlash folderPath

        if (directoryExists normalizedFolderPath) do return true
        return makeDir normalizedFolderPath all: true
    )

    fn deleteDirectory folderPath = (
        if (not (directoryExists folderPath)) do return true

        try (
            (dotNetClass "System.IO.Directory").Delete folderPath true
        ) catch (
            deleteFile ((ensureTrailingSlash folderPath) + "*.*")
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

    fn parseSqlDate dateContent = (
        local dateString = trimString dateContent
        local dateTimeClass = dotNetClass "System.DateTime"
        local dateParts = filterString dateString "-"

        if (dateString == "") do return dateTimeClass.Now
        if (dateParts.count != 3) do return dateTimeClass.Now

        try (
            local yearNumber = dateParts[1] as integer
            local monthNumber = dateParts[2] as integer
            local dayNumber = dateParts[3] as integer

            return dotNetObject "System.DateTime" yearNumber monthNumber dayNumber
        ) catch (
            return dateTimeClass.Now
        )

        return dateTimeClass.Now
    )

    fn setupDatePickerControl datePickerControl = (
        local dateTimePickerFormatClass = dotNetClass "System.Windows.Forms.DateTimePickerFormat"

        datePickerControl.Format = dateTimePickerFormatClass.Custom
        datePickerControl.CustomFormat = "yyyy-MM-dd"
        datePickerControl.Value = parseSqlDate packageState.releaseDate
        packageState.releaseDate = datePickerControl.Value.ToString "yyyy-MM-dd"
        return true
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
        local yearItems = #()
        local maxYear = currentMaxYearPlusOne()

        for yearNumber in 2012 to maxYear do (
            append yearItems (yearNumber as string)
        )

        return yearItems
    )

    fn versionNumberItems m: 99 = (
        local versionItems = #()

        for numberItem in 0 to m do (
            append versionItems (numberItem as string)
        )

        return versionItems
    )

    fn parseVersionParts versionString = (
        local versionParts = filterString (trimString versionString) "."

        if (versionParts.count != 3) do return #("1", "0", "0")

        for versionIndex in 1 to 3 do (
            local partNumber = try (versionParts[versionIndex] as integer) catch(undefined)
            if (partNumber == undefined) do return #("1", "0", "0")
            if (partNumber < 0 or partNumber > 99) do return #("1", "0", "0")
            versionParts[versionIndex] = partNumber as string
        )

        return versionParts
    )

    fn buildVersionStringFromState = (
        local majorPart = packageState.versionMajor
        local minorPart = packageState.versionMinor
        local patchPart = packageState.versionPatch

        if (majorPart == "") do majorPart = "1"
        if (minorPart == "") do minorPart = "0"
        if (patchPart == "") do patchPart = "0"

        return majorPart + "." + minorPart + "." + patchPart
    )

    fn settingsSet settingKey settingContent settingsSection: "settings" = (
        setINISetting settingsIniFilePath settingsSection settingKey (trimString settingContent)
        return true
    )

    fn settingsGet settingKey settingsSection: "settings" defaultContent: "" = (
        local settingContent = getINISetting settingsIniFilePath settingsSection settingKey

        if (settingContent == undefined or settingContent == "") do return defaultContent
        return settingContent
    )

    fn settingsGetBool settingKey settingsSection: "settings" defaultContent: true = (
        return stringToBool (getINISetting settingsIniFilePath settingsSection settingKey) defaultContent: defaultContent
    )

    fn settingsGetInt settingKey settingsSection: "settings" defaultContent: 0 = (
        local settingContent = getINISetting settingsIniFilePath settingsSection settingKey

        if (settingContent == undefined or settingContent == "") do return defaultContent
        return try (settingContent as integer) catch(defaultContent)
    )

    fn escapeIniValue sourceContent = (
        local resultContent = trimString sourceContent
        resultContent = substituteString resultContent "\r\n" "\\n"
        resultContent = substituteString resultContent "\n" "\\n"
        resultContent = substituteString resultContent "\r" "\\n"
        return resultContent
    )

    fn unescapeIniValue sourceContent = (
        local resultContent = sourceContent as string
        resultContent = substituteString resultContent "\\n" "\r\n"
        return resultContent
    )

    fn settingsSetEscaped settingKey settingContent settingsSection: "settings" = (
        setINISetting settingsIniFilePath settingsSection settingKey (escapeIniValue settingContent)
        return true
    )

    fn settingsGetEscaped settingKey settingsSection: "settings" defaultContent: "" = (
        local settingContent = getINISetting settingsIniFilePath settingsSection settingKey

        if (settingContent == undefined or settingContent == "") do return defaultContent
        return unescapeIniValue settingContent
    )

    fn escapeJson sourceContent = (
        local resultContent = sourceContent as string
        resultContent = substituteString resultContent "\\" "\\\\"
        resultContent = substituteString resultContent "\"" "\\\""
        resultContent = substituteString resultContent "\r\n" "\\n"
        resultContent = substituteString resultContent "\n" "\\n"
        resultContent = substituteString resultContent "\r" "\\n"
        resultContent = substituteString resultContent "\t" "\\t"
        return resultContent
    )

    fn readScriptInfoEntry infoKey defaultContent: "" = (
        local entryContent = try (getINISetting scriptFilePath "INFO" infoKey) catch("")
        if (entryContent == undefined or entryContent == "") do return defaultContent
        return entryContent
    )

    fn currentScriptFilePath = (
        local currentScriptFile = getThisScriptFileName()
        if (currentScriptFile == undefined or currentScriptFile == "") do currentScriptFile = getThisScriptFilename()
        return currentScriptFile
    )

    fn scriptInfoEntry sourceScriptFile infoKey defaultContent: "" = (
        local entryContent = try (getINISetting sourceScriptFile "INFO" infoKey) catch("")
        if (entryContent == undefined or entryContent == "") do return defaultContent
        return entryContent
    )

    fn readScriptInfo sourceScriptFile releaseInfo: "" = (
        if (releaseInfo != "") do (
            local releaseItems = try (getINISetting sourceScriptFile releaseInfo) catch(#())
            return releaseItems
        )

        local descriptionContent = ""
        local aboutItems = try (getINISetting sourceScriptFile "ABOUT") catch(#())
        for aboutIndex in 1 to aboutItems.count do (
            descriptionContent += aboutItems[aboutIndex]
            if (aboutIndex < aboutItems.count) do descriptionContent += "\r\n"
        )

        local releaseItems = #()
        local iniSections = try (getINISetting sourceScriptFile) catch(#())
        for iniSectionName in iniSections do (
            if (iniSectionName != "INFO" and iniSectionName != "ABOUT" and iniSectionName != "SCRIPT" and iniSectionName != "FILES") do (
                append releaseItems iniSectionName
            )
        )

        local scriptInfo = MaxPkgPackerNewScriptInfoData()
        scriptInfo.scriptTitle = scriptInfoEntry sourceScriptFile "NAME" defaultContent: "MaxPkg Packer New UI"
        scriptInfo.versionString = scriptInfoEntry sourceScriptFile "VERSION" defaultContent: "0.0.0"
        scriptInfo.authorTitle = scriptInfoEntry sourceScriptFile "AUTHOR" defaultContent: ""
        scriptInfo.developerUrl = scriptInfoEntry sourceScriptFile "DEV" defaultContent: ""
        scriptInfo.siteUrl = scriptInfoEntry sourceScriptFile "SITE" defaultContent: ""
        scriptInfo.helpUrl = scriptInfoEntry sourceScriptFile "HELP" defaultContent: ""
        scriptInfo.updateUrl = scriptInfoEntry sourceScriptFile "UPDATE" defaultContent: ""
        scriptInfo.manifestVersion = scriptInfoEntry sourceScriptFile "MANIFEST_VERSION" defaultContent: "1"
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

    fn releaseNotesForVersion sourceScriptFile releaseVersionString = (
        local releaseItems = readScriptInfo sourceScriptFile releaseInfo: releaseVersionString
        local releaseContent = ""

        for releaseIndex in 1 to releaseItems.count do (
            releaseContent += releaseItems[releaseIndex]
            if (releaseIndex < releaseItems.count) do releaseContent += "\r\n"
        )

        if (releaseContent == "") do releaseContent = "No changelog entries for this version."
        return releaseContent
    )

    fn releaseNotesForUpdate sourceScriptFile currentVersionString newVersionString = (
        local scriptInfo = readScriptInfo sourceScriptFile
        local releaseContent = ""

        for releaseSectionName in scriptInfo.releases do (
            local isAfterCurrent = (compareVersionStrings releaseSectionName currentVersionString) > 0
            local isNotAfterNew = (compareVersionStrings releaseSectionName newVersionString) <= 0

            if (isAfterCurrent and isNotAfterNew) do (
                if (releaseContent != "") do releaseContent += "\r\n\r\n"
                releaseContent += "[" + releaseSectionName + "]\r\n"
                releaseContent += releaseNotesForVersion sourceScriptFile releaseSectionName
            )
        )

        if (releaseContent == "") do releaseContent = releaseNotesForVersion sourceScriptFile newVersionString
        return releaseContent
    )

    fn newUpdateResultData = (
        local updateResult = MaxPkgPackerNewUpdateResultData()
        updateResult.isUpdated = false
        updateResult.currentVersionString = ""
        updateResult.newVersionString = ""
        updateResult.releaseNotesContent = ""
        updateResult.messageContent = ""
        updateResult.scriptFilePath = currentScriptFilePath()
        return updateResult
    )

    fn checkAndDownloadScriptUpdate showMessages: false reloadAfterUpdate: false = (
        local updateResult = newUpdateResultData()
        local currentScriptFile = currentScriptFilePath()
        updateResult.scriptFilePath = currentScriptFile
        if (currentScriptFile == undefined or currentScriptFile == "") do return updateResult

        local currentInfo = readScriptInfo currentScriptFile
        updateResult.currentVersionString = currentInfo.versionString

        if (currentInfo.updateUrl == "") do (
            if (showMessages) do messageBox "Update URL is not configured." title: "MaxPkg Packer"
            updateResult.messageContent = "Update URL is not configured."
            return updateResult
        )

        local downloadedFilePath = currentScriptFile + ".update"
        if (not (downloadUpdateFile currentInfo.updateUrl downloadedFilePath)) do (
            if (showMessages) do messageBox "Could not download update." title: "MaxPkg Packer"
            updateResult.messageContent = "Could not download update."
            return updateResult
        )

        local downloadedInfo = readScriptInfo downloadedFilePath
        updateResult.newVersionString = downloadedInfo.versionString
        local compareResult = compareVersionStrings downloadedInfo.versionString currentInfo.versionString

        if (compareResult <= 0) do (
            try (deleteFile downloadedFilePath) catch()
            if (showMessages) do messageBox ("You already have the latest version: " + currentInfo.versionString) title: "MaxPkg Packer"
            updateResult.messageContent = "You already have the latest version: " + currentInfo.versionString
            return updateResult
        )

        updateResult.releaseNotesContent = releaseNotesForUpdate downloadedFilePath currentInfo.versionString downloadedInfo.versionString

        if (not (applyDownloadedScriptUpdate downloadedFilePath currentScriptFile)) do (
            try (deleteFile downloadedFilePath) catch()
            if (showMessages) do messageBox "Downloaded update, but could not replace current script." title: "MaxPkg Packer"
            updateResult.messageContent = "Downloaded update, but could not replace current script."
            return updateResult
        )

        updateResult.isUpdated = true
        updateResult.messageContent = "Script updated from " + currentInfo.versionString + " to " + downloadedInfo.versionString + "."
        print updateResult.messageContent

        if (reloadAfterUpdate) do try (fileIn currentScriptFile) catch()
        return updateResult
    )

    fn readTextFile filePath = (
        local fileStream = openFile filePath mode: "rt"
        local fileContent = ""

        if (fileStream == undefined) do return undefined

        while (not eof fileStream) do (
            fileContent += readLine fileStream
            if (not eof fileStream) do fileContent += "\n"
        )

        close fileStream
        return fileContent
    )

    fn writeTextFile filePath fileContent = (
        local fileStream = createFile filePath

        if (fileStream == undefined) do return false
        format "%" fileContent to: fileStream
        close fileStream
        return true
    )

    fn isSafePackageDisplayText sourceContent = (
        local allowedChars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 -_"
        local sourceString = sourceContent as string

        for charIndex in 1 to sourceString.count do (
            local charContent = substring sourceString charIndex 1
            if ((findString allowedChars charContent) == undefined) do return false
        )

        return true
    )

    fn packageSlugFromName sourceContent = (
        local sourceString = lowerString (trimString (sourceContent as string))
        local allowedChars = "abcdefghijklmnopqrstuvwxyz0123456789_"
        local slugContent = ""
        local previousWasDash = false

        for charIndex in 1 to sourceString.count do (
            local charContent = substring sourceString charIndex 1

            if (charContent == " " or charContent == "-") then (
                if (not previousWasDash and slugContent != "") do (
                    slugContent += "-"
                    previousWasDash = true
                )
            ) else if ((findString allowedChars charContent) != undefined) then (
                slugContent += charContent
                previousWasDash = false
            )
        )

        while (slugContent.count > 0 and (substring slugContent slugContent.count 1) == "-") do (
            slugContent = substring slugContent 1 (slugContent.count - 1)
        )

        if (slugContent == "") do slugContent = "package"
        return slugContent
    )

    fn outputMzpFileName = (
        return (packageSlugFromName packageState.packageTitle) + "@" + (buildVersionStringFromState()) + "@" + (trimString packageState.packageGuid) + ".mzp"
    )

    fn isValidGuid sourceContent = (
        local guidContent = trimString sourceContent
        local dashPositions = #(9, 14, 19, 24)
        local hexChars = "0123456789abcdefABCDEF"

        if (guidContent.count != 36) do return false

        for charIndex in 1 to guidContent.count do (
            local charContent = substring guidContent charIndex 1
            local dashExpected = (findItem dashPositions charIndex) > 0

            if (dashExpected) then (
                if (charContent != "-") do return false
            ) else (
                if ((findString hexChars charContent) == undefined) do return false
            )
        )

        return true
    )

    fn isSafeRelativePath relativeFilePath = (
        local relativePackagePath = normalizePath relativeFilePath

        if (relativePackagePath == "") do return false
        if ((findString relativePackagePath ":") != undefined) do return false
        if (startsWith relativePackagePath "\\") do return false
        if (startsWith relativePackagePath "..\\") do return false
        if ((findString relativePackagePath "\\..\\") != undefined) do return false
        if (relativePackagePath == "..") do return false
        return true
    )

    fn relativePathFromRoot absFilePath = (
        local normalizedAbsFilePath = normalizePath absFilePath
        local rootFolderPath = ensureTrailingSlash scriptDir

        if (startsWith (lowerString normalizedAbsFilePath) (lowerString rootFolderPath)) then (
            return substring normalizedAbsFilePath (rootFolderPath.count + 1) (normalizedAbsFilePath.count - rootFolderPath.count)
        )

        return (getFilenameFile normalizedAbsFilePath) + (getFilenameType normalizedAbsFilePath)
    )

    fn isExcludedPath absFilePath = (
        local lowerFilePath = lowerString (normalizePath absFilePath)
        local lowerFileName = lowerString (filenameFromPath absFilePath)

        if ((findString lowerFilePath "\\.git\\") != undefined) do return true
        if ((findString lowerFilePath "\\.vscode\\") != undefined) do return true
        if (matchPattern lowerFileName pattern: "*.bak" ignoreCase: true) do return true
        if (matchPattern lowerFileName pattern: "*.tmp" ignoreCase: true) do return true
        if (matchPattern lowerFileName pattern: "*.log" ignoreCase: true) do return true
        if (matchPattern lowerFileName pattern: "*.zip" ignoreCase: true) do return true
        if (matchPattern lowerFileName pattern: "*.mzp" ignoreCase: true) do return true
        if (lowerFileName == "maxpkg-packager.ms") do return true
        if (lowerFileName == "maxpkg-packager.ini") do return true
        if (lowerFileName == "maxpkg-changelog.ini") do return true
        if (lowerFileName == "maxpkg-button.mcr") do return true
        if (lowerFileName == "mzp.run") do return true
        if (lowerFileName == "mzp.run.ms") do return true
        return false
    )

    fn findPackageFileByRel relativeFilePath = (
        local normalizedRelativePath = normalizePath relativeFilePath

        for packageItem in packageFiles do (
            if (packageItem[2] == normalizedRelativePath) do return packageItem
        )

        return undefined
    )

    fn addPackageFile absFilePath = (
        if (absFilePath == undefined) do return false
        if (not (doesFileExist absFilePath)) do return false
        if (isExcludedPath absFilePath) do return false

        local relativeFilePath = normalizePath (relativePathFromRoot absFilePath)

        if (not (isSafeRelativePath relativeFilePath)) do return false
        if ((findPackageFileByRel relativeFilePath) != undefined) do return true

        append packageFiles #((normalizePath absFilePath), relativeFilePath)
        return true
    )

    fn addFolderFiles folderPath = (
        local addedCount = 0
        local folderRoot = ensureTrailingSlash folderPath

        if (not (directoryExists folderRoot)) do return 0

        try (
            local directoryClass = dotNetClass "System.IO.Directory"
            local searchOptionClass = dotNetClass "System.IO.SearchOption"
            local folderFiles = directoryClass.GetFiles folderRoot "*" searchOptionClass.AllDirectories

            for filePath in folderFiles do (
                if (addPackageFile (filePath as string)) do addedCount += 1
            )
        ) catch (
            local folderFiles = getFiles (folderRoot + "**\\*.*")

            for filePath in folderFiles do (
                if (addPackageFile filePath) do addedCount += 1
            )
        )

        return addedCount
    )

    fn selectPackageFiles = (
        local openDialog = dotNetObject "System.Windows.Forms.OpenFileDialog"
        local dialogResultClass = dotNetClass "System.Windows.Forms.DialogResult"
        local selectedFiles = #()

        openDialog.Title = "Add package files"
        openDialog.InitialDirectory = scriptDir
        openDialog.Filter = "Package Files (*.*)|*.*"
        openDialog.Multiselect = true
        openDialog.CheckFileExists = true
        openDialog.CheckPathExists = true

        if (openDialog.ShowDialog() == dialogResultClass.OK) do (
            for filePath in openDialog.FileNames do (
                append selectedFiles (filePath as string)
            )
        )

        return selectedFiles
    )

    fn getPackageFileNames = (
        local fileItems = #()

        for packageItem in packageFiles do (
            append fileItems packageItem[2]
        )

        return fileItems
    )

    fn isValidSafeSvg filePath = (
        if (filePath == undefined or filePath == "") do return false
        if (not (doesFileExist filePath)) do return false
        if ((lowerString (getFilenameType filePath)) != ".svg") do return false

        local fileContent = readTextFile filePath
        if (fileContent == undefined or fileContent.count == 0) do return false

        for charIndex in 1 to fileContent.count do (
            local charCode = bit.charAsInt (substring fileContent charIndex 1)
            if (charCode == 0) do return false
        )

        local lowerContent = lowerString fileContent

        if ((findString lowerContent "<svg") == undefined) do return false
        if ((findString lowerContent "<script") != undefined) do return false
        if ((findString lowerContent "javascript:") != undefined) do return false
        if ((findString lowerContent "onload=") != undefined) do return false
        if ((findString lowerContent "onclick=") != undefined) do return false
        if ((findString lowerContent "onerror=") != undefined) do return false
        if ((findString lowerContent "<foreignobject") != undefined) do return false
        return true
    )

    fn copySvgIconToRoot sourceFilePath = (
        local sourceIconFilePath = normalizePath sourceFilePath
        local targetIconFilePath = normalizePath ((ensureTrailingSlash scriptDir) + "maxpkg-icon.svg")

        if (sourceIconFilePath == "") do return ""
        if (not (doesFileExist sourceIconFilePath)) do return ""

        if ((lowerString sourceIconFilePath) != (lowerString targetIconFilePath)) do (
            if (doesFileExist targetIconFilePath) do deleteFile targetIconFilePath
            if (not (copyFile sourceIconFilePath targetIconFilePath)) do return ""
        )

        return targetIconFilePath
    )

    fn detectRootHook hookFileName = (
        local hookContent = lowerString hookFileName

        for packageItem in packageFiles do (
            if ((lowerString packageItem[2]) == hookContent) do return hookFileName
        )

        return ""
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
        packageState.releaseDate = (parseSqlDate packageState.releaseDate).ToString "yyyy-MM-dd"

        try (delIniSetting changelogIniFilePath changelogSectionName) catch()
        setINISetting changelogIniFilePath changelogSectionName "version" normalizedVersion
        setINISetting changelogIniFilePath changelogSectionName "releaseDate" packageState.releaseDate
        setINISetting changelogIniFilePath changelogSectionName "releaseChannel" packageState.releaseChannel
        setINISetting changelogIniFilePath changelogSectionName "min3dsMax" packageState.minMaxVersion
        setINISetting changelogIniFilePath changelogSectionName "count" (changelogItems.count as string)

        for changelogIndex in 1 to changelogItems.count do (
            setINISetting changelogIniFilePath changelogSectionName ((changelogIndex as string) + "_type") (escapeIniValue changelogItems[changelogIndex][1])
            setINISetting changelogIniFilePath changelogSectionName ((changelogIndex as string) + "_text") (escapeIniValue changelogItems[changelogIndex][2])
        )

        return true
    )

    fn saveCurrentChangelog = (
        return saveChangelogForVersion activeChangelogVersion
    )

    fn loadChangelogForVersion versionString = (
        local normalizedVersion = trimString versionString
        local changelogSectionName = changelogSectionFromVersion normalizedVersion
        local releaseDateContent = getINISetting changelogIniFilePath changelogSectionName "releaseDate"
        local releaseChannelContent = getINISetting changelogIniFilePath changelogSectionName "releaseChannel"
        local minMaxContent = getINISetting changelogIniFilePath changelogSectionName "min3dsMax"
        local countContent = getINISetting changelogIniFilePath changelogSectionName "count"
        local changelogCount = 0

        if (releaseDateContent == undefined or releaseDateContent == "") then (
            packageState.releaseDate = currentDateString()
        ) else (
            packageState.releaseDate = (parseSqlDate releaseDateContent).ToString "yyyy-MM-dd"
        )

        if (releaseChannelContent == undefined or releaseChannelContent == "") then (
            packageState.releaseChannel = "stable"
        ) else (
            packageState.releaseChannel = lowerString releaseChannelContent
            if (packageState.releaseChannel != "stable" and packageState.releaseChannel != "alpha" and packageState.releaseChannel != "beta") do packageState.releaseChannel = "stable"
        )

        if (minMaxContent == undefined or minMaxContent == "") then (
            packageState.minMaxVersion = "2012"
        ) else (
            packageState.minMaxVersion = minMaxContent
            if ((findItem (maxYearItems()) packageState.minMaxVersion) < 1) do packageState.minMaxVersion = "2012"
        )

        if (countContent == "") do return false

        changelogCount = try (countContent as integer) catch(0)
        changelogItems = #()

        for changelogIndex in 1 to changelogCount do (
            local itemType = unescapeIniValue (getINISetting changelogIniFilePath changelogSectionName ((changelogIndex as string) + "_type"))
            local itemContent = unescapeIniValue (getINISetting changelogIniFilePath changelogSectionName ((changelogIndex as string) + "_text"))

            if (itemType != "" and itemContent != "") do (
                append changelogItems #(itemType, itemContent)
            )
        )

        return true
    )

    fn hasChangelogEntries = (
        for changelogItem in changelogItems do (
            if (changelogItem.count >= 2 and (trimString changelogItem[2]) != "") do return true
        )

        return false
    )

    fn isValidPackageTitleForState = (
        local packageTitle = trimString packageState.packageTitle
        if (packageTitle == "") do return false
        return isSafePackageDisplayText packageTitle
    )

    fn isValidButtonTitleForState = (
        local buttonTitle = trimString packageState.buttonTitle
        if (buttonTitle == "") do return false
        return isSafePackageDisplayText buttonTitle
    )

    fn isValidDescriptionForState = (
        local descriptionContent = trimString packageState.descriptionContent
        if (descriptionContent == "") do return false
        if (descriptionContent.count > 500) do return false
        return true
    )

    fn isValidDeveloperTitleForState = (
        return (trimString packageState.developerTitle) != ""
    )

    fn isValidLicenseTypeForState = (
        local licenseContent = trimString packageState.licenseType

        if (licenseContent == "Free") do return true
        if (licenseContent == "Shareware") do return true
        if (licenseContent == "Commercial") do return true
        if (licenseContent == "Open source") do return true
        if (licenseContent == "Trial") do return true
        return false
    )

    fn isValidReleaseDateForState = (
        return (trimString packageState.releaseDate) != ""
    )

    fn isValidOutputFolderForState = (
        local outputFolderPath = ensureTrailingSlash packageState.outputFolder
        if (outputFolderPath == "" or outputFolderPath == "\\") do return false
        return true
    )

    fn isValidEntryFileForState = (
        local entryFilePath = normalizePath (trimString packageState.entryFile)

        if (entryFilePath == "") do return false

        local entryItem = findPackageFileByRel entryFilePath
        if (entryItem == undefined) do return false
        if (not (doesFileExist entryItem[1])) do return false

        local entryExt = lowerString (getFilenameType entryFilePath)
        if (entryExt != ".ms" and entryExt != ".mse" and entryExt != ".py") do return false
        if (packageState.compileEntry and entryExt != ".ms") do return false

        return true
    )

    fn svgIconStatusForState = (
        local svgIconFilePath = normalizePath (trimString packageState.svgIconFile)

        if (svgIconFilePath == "") do return #invalid
        if (isValidSafeSvg svgIconFilePath) do return #valid
        return #invalid
    )

    fn refreshValidationColors = (
        try (setValidationColor MaxPkgPackerNewInfoRollout.dncPackageName (validationStatusFromBool (isValidPackageTitleForState()))) catch()
        try (setValidationColor MaxPkgPackerNewInfoRollout.dncButtonName (validationStatusFromBool (isValidButtonTitleForState()))) catch()
        try (setValidationColor MaxPkgPackerNewInfoRollout.dncGuid (validationStatusFromBool (isValidGuid packageState.packageGuid))) catch()
        try (setValidationColor MaxPkgPackerNewInfoRollout.dncDescription (validationStatusFromBool (isValidDescriptionForState()))) catch()
        try (setValidationColor MaxPkgPackerNewInfoRollout.dncDeveloperName (validationStatusFromBool (isValidDeveloperTitleForState()))) catch()

        try (setValidationColor MaxPkgPackerNewFilesRollout.dncOutputFolder (validationStatusFromBool (isValidOutputFolderForState()))) catch()
        try (setValidationColor MaxPkgPackerNewFilesRollout.dncEntryFile (validationStatusFromBool (isValidEntryFileForState()))) catch()
        try (setValidationColor MaxPkgPackerNewFilesRollout.dncSvgIcon (svgIconStatusForState())) catch()

        try (
            local changelogStatusType = if (hasChangelogEntries()) then #neutral else #invalid
            setValidationColor MaxPkgPackerNewReleaseRollout.dncChangeContent changelogStatusType
        ) catch()
        return true
    )

    fn hasValidationIssues = (
        if (not (isValidPackageTitleForState())) do return true
        if (not (isValidButtonTitleForState())) do return true
        if (not (isValidGuid packageState.packageGuid)) do return true
        if (not (isValidDescriptionForState())) do return true
        if (not (isValidDeveloperTitleForState())) do return true
        if (not (isValidLicenseTypeForState())) do return true
        if (not (isValidReleaseDateForState())) do return true
        if (packageState.releaseChannel != "stable" and packageState.releaseChannel != "alpha" and packageState.releaseChannel != "beta") do return true
        if (not (isValidEntryFileForState())) do return true
        if ((svgIconStatusForState()) == #invalid) do return true
        if (not (hasChangelogEntries())) do return true
        if (packageFiles.count == 0) do return true
        if (not (isValidOutputFolderForState())) do return true

        for packageItem in packageFiles do (
            if (not (isSafeRelativePath packageItem[2])) do return true
            if (not (doesFileExist packageItem[1])) do return true

            local relativeLowerPath = lowerString packageItem[2]
            if (endsWith relativeLowerPath "\\install.ms") do return true
            if (endsWith relativeLowerPath "\\uninstall.ms") do return true
        )

        return false
    )

    fn stopValidationStatusTimer = (
        try (
            MaxPkgPackerNewTabsRollout.tmrValidationStatus.active = false
        ) catch()

        return true
    )

    fn setBuildButtonStatusColor statusColor = (
        try (
            isSyncingBuildButtonStatus = true
            MaxPkgPackerNewActionsRollout.btnBuild.checked = false
            MaxPkgPackerNewActionsRollout.btnBuild.highlightColor = statusColor
            MaxPkgPackerNewActionsRollout.btnBuild.checked = true
            isSyncingBuildButtonStatus = false
        ) catch (
            isSyncingBuildButtonStatus = false
        )

        return true
    )

    fn refreshValidationStatusButton = (
        local statusHasIssues = hasValidationIssues()
        local issueColor = color 125 36 36
        local readyColor = color 52 168 83

        stopValidationStatusTimer()

        try (
            MaxPkgPackerNewTabsRollout.btnValidationStatus.checked = true

            if (statusHasIssues) then (
                MaxPkgPackerNewTabsRollout.btnValidationStatus.caption = "Has Issues"
                MaxPkgPackerNewTabsRollout.btnValidationStatus.highlightColor = issueColor
                setBuildButtonStatusColor issueColor
            ) else (
                MaxPkgPackerNewTabsRollout.btnValidationStatus.caption = "Ready"
                MaxPkgPackerNewTabsRollout.btnValidationStatus.highlightColor = readyColor
                setBuildButtonStatusColor readyColor
            )
        ) catch()

        return true
    )

    fn scheduleValidationStatusUpdate = (
        try (
            stopValidationStatusTimer()
            MaxPkgPackerNewTabsRollout.tmrValidationStatus.active = true
        ) catch()

        return true
    )

    fn canCompileEntryFileFromState = (
        local entryExt = lowerString (getFilenameType (normalizePath (trimString packageState.entryFile)))
        return entryExt == ".ms"
    )

    fn shouldCompileEntryFileFromState = (
        if (not (canCompileEntryFileFromState())) do return false
        return packageState.compileEntry
    )

    fn syncCompileEntryState = (
        if (canCompileEntryFileFromState()) do return true
        packageState.compileEntry = false
        return false
    )

    fn compiledEntryPath entryFilePath = (
        local normalizedEntryFile = normalizePath entryFilePath
        local entryFolderPath = getFilenamePath normalizedEntryFile
        local entryBaseFile = getFilenameFile normalizedEntryFile

        return entryFolderPath + entryBaseFile + ".mse"
    )

    fn manifestEntryPathFromState = (
        local entryFilePath = normalizePath (trimString packageState.entryFile)

        if (shouldCompileEntryFileFromState()) do return compiledEntryPath entryFilePath
        return entryFilePath
    )

    fn syncEntryFileWithPackageList = (
        local currentEntryFile = normalizePath (trimString packageState.entryFile)

        if (currentEntryFile == "") do return true

        if ((findPackageFileByRel currentEntryFile) == undefined) do (
            packageState.entryFile = ""
            packageState.compileEntry = false
            return false
        )

        return true
    )

    fn refreshFilesView = (
        syncCompileEntryState()
        try (MaxPkgPackerNewFilesRollout.lbFiles.items = getPackageFileNames()) catch()
        try (MaxPkgPackerNewFilesRollout.dncEntryFile.Text = packageState.entryFile) catch()
        try (
            MaxPkgPackerNewFilesRollout.chkCompileEntry.enabled = canCompileEntryFileFromState()
            MaxPkgPackerNewFilesRollout.chkCompileEntry.checked = packageState.compileEntry and canCompileEntryFileFromState()
        ) catch()
        refreshValidationColors()
        return true
    )

    fn refreshChangelogView = (
        local changelogListItems = #()

        for changelogItem in changelogItems do (
            append changelogListItems ((lowerString changelogItem[1]) + ": " + changelogItem[2])
        )

        try (MaxPkgPackerNewReleaseRollout.lbChangelog.items = changelogListItems) catch()
        return true
    )

    fn refreshReleaseDateView = (
        local previousLoadingState = isLoadingSettings

        try (
            isLoadingSettings = true
            MaxPkgPackerNewReleaseRollout.dncReleaseDate.Value = parseSqlDate packageState.releaseDate
        ) catch()

        isLoadingSettings = previousLoadingState
        return true
    )

    fn refreshReleaseChannelView = (
        local previousLoadingState = isLoadingSettings

        try (
            isLoadingSettings = true
            if (not (setDropDownText MaxPkgPackerNewReleaseRollout.ddlChannel packageState.releaseChannel)) do setDropDownText MaxPkgPackerNewReleaseRollout.ddlChannel "stable"
        ) catch()

        isLoadingSettings = previousLoadingState
        return true
    )

    fn refreshMinMaxView = (
        local previousLoadingState = isLoadingSettings

        try (
            isLoadingSettings = true
            MaxPkgPackerNewReleaseRollout.ddlMinMax.items = maxYearItems()
            if (not (setDropDownText MaxPkgPackerNewReleaseRollout.ddlMinMax packageState.minMaxVersion)) do setDropDownText MaxPkgPackerNewReleaseRollout.ddlMinMax "2012"
        ) catch()

        isLoadingSettings = previousLoadingState
        return true
    )

    fn savePackageSettings = (
        if (isLoadingSettings) do return false

        settingsSetEscaped "packageName" packageState.packageTitle
        settingsSetEscaped "buttonName" packageState.buttonTitle
        settingsSetEscaped "packageGuid" packageState.packageGuid
        settingsSetEscaped "description" packageState.descriptionContent
        settingsSetEscaped "developerName" packageState.developerTitle
        settingsSetEscaped "license" packageState.licenseType
        settingsSetEscaped "licenseUrl" packageState.licenseUrl
        settingsSetEscaped "documentation" packageState.documentationUrl
        settingsSetEscaped "homepage" packageState.homepageUrl
        settingsSetEscaped "support" packageState.supportUrl
        settingsSetEscaped "createMacroButton" (boolToString packageState.createButton)
        settingsSetEscaped "showInToolbar" (boolToString packageState.showToolbar)
        settingsSetEscaped "outputFolder" packageState.outputFolder
        settingsSetEscaped "svgIcon" packageState.svgIconFile
        settingsSetEscaped "entry" packageState.entryFile
        syncCompileEntryState()
        settingsSetEscaped "compileEntry" (boolToString packageState.compileEntry)
        settingsSetEscaped "version" (buildVersionStringFromState())
        settingsSetEscaped "releaseChannel" packageState.releaseChannel
        settingsSetEscaped "releaseDate" packageState.releaseDate
        settingsSetEscaped "min3dsMax" packageState.minMaxVersion
        settingsSetEscaped "max3dsMax" ((currentMaxYearPlusOne()) as string)

        setINISetting settingsIniFilePath "files" "count" (packageFiles.count as string)
        for fileIndex in 1 to packageFiles.count do (
            settingsSetEscaped ((fileIndex as string) + "_abs") packageFiles[fileIndex][1] settingsSection: "files"
            settingsSetEscaped ((fileIndex as string) + "_rel") packageFiles[fileIndex][2] settingsSection: "files"
        )

        saveCurrentChangelog()
        refreshValidationColors()
        scheduleValidationStatusUpdate()
        return true
    )

    fn loadPackageSettings = (
        isLoadingSettings = true

        packageState.outputFolder = scriptDir + "dist"
        packageState.releaseDate = currentDateString()

        if (doesFileExist settingsIniFilePath) do (
            packageState.packageTitle = settingsGetEscaped "packageName"
            packageState.buttonTitle = settingsGetEscaped "buttonName"
            packageState.packageGuid = settingsGetEscaped "packageGuid"
            packageState.descriptionContent = settingsGetEscaped "description"
            packageState.developerTitle = settingsGetEscaped "developerName"
            packageState.licenseType = settingsGetEscaped "license"
            packageState.licenseUrl = settingsGetEscaped "licenseUrl"
            packageState.documentationUrl = settingsGetEscaped "documentation"
            packageState.homepageUrl = settingsGetEscaped "homepage"
            packageState.supportUrl = settingsGetEscaped "support"
            packageState.createButton = settingsGetBool "createMacroButton" defaultContent: true
            packageState.showToolbar = settingsGetBool "showInToolbar" defaultContent: true
            packageState.outputFolder = settingsGetEscaped "outputFolder" defaultContent: (scriptDir + "dist")
            packageState.svgIconFile = settingsGetEscaped "svgIcon"
            packageState.entryFile = settingsGetEscaped "entry"
            packageState.compileEntry = settingsGetBool "compileEntry" defaultContent: true
            packageState.releaseChannel = settingsGetEscaped "releaseChannel" defaultContent: "stable"
            packageState.releaseDate = settingsGetEscaped "releaseDate" defaultContent: (currentDateString())
            packageState.minMaxVersion = settingsGetEscaped "min3dsMax" defaultContent: "2012"

            local versionParts = parseVersionParts (settingsGetEscaped "version" defaultContent: "1.0.0")
            packageState.versionMajor = versionParts[1]
            packageState.versionMinor = versionParts[2]
            packageState.versionPatch = versionParts[3]

            packageFiles = #()
            local fileCount = settingsGetInt "count" settingsSection: "files" defaultContent: 0
            for fileIndex in 1 to fileCount do (
                local absFilePath = settingsGetEscaped ((fileIndex as string) + "_abs") settingsSection: "files"
                local relativeFilePath = settingsGetEscaped ((fileIndex as string) + "_rel") settingsSection: "files"

                if (absFilePath != "" and relativeFilePath != "" and not (isExcludedPath absFilePath)) do (
                    append packageFiles #((normalizePath absFilePath), (normalizePath relativeFilePath))
                )
            )
        )

        activeChangelogVersion = buildVersionStringFromState()
        if (not (loadChangelogForVersion activeChangelogVersion)) do changelogItems = #()
        syncEntryFileWithPackageList()
        syncCompileEntryState()
        packageState.releaseDate = (parseSqlDate packageState.releaseDate).ToString "yyyy-MM-dd"

        isLoadingSettings = false
        savePackageSettings()
        return true
    )

    fn switchChangelogVersion = (
        if (isLoadingSettings) do return false

        saveChangelogForVersion activeChangelogVersion
        activeChangelogVersion = buildVersionStringFromState()

        if (not (loadChangelogForVersion activeChangelogVersion)) do (
            changelogItems = #()
            saveCurrentChangelog()
        )

        refreshChangelogView()
        refreshReleaseDateView()
        refreshReleaseChannelView()
        refreshMinMaxView()
        savePackageSettings()
        return true
    )

    fn addValidationError errorContent uiPlace = (
        addLog "ERROR" (errorContent + " (" + uiPlace + ")")
        return true
    )

    fn validatePackageSettings = (
        local isValid = true
        local packageTitle = trimString packageState.packageTitle
        local buttonTitle = trimString packageState.buttonTitle
        local descriptionContent = trimString packageState.descriptionContent
        local developerTitle = trimString packageState.developerTitle
        local guidContent = trimString packageState.packageGuid
        local versionContent = buildVersionStringFromState()
        local releaseDateContent = trimString packageState.releaseDate
        local entryFilePath = normalizePath (trimString packageState.entryFile)
        local isEntryCompileEnabled = shouldCompileEntryFileFromState()
        local svgIconFilePath = normalizePath (trimString packageState.svgIconFile)
        local minMax = try (packageState.minMaxVersion as integer) catch(undefined)
        local maxMax = currentMaxYearPlusOne()
        local outputFolderPath = ensureTrailingSlash packageState.outputFolder

        clearLog()

        if (packageTitle == "") do (addValidationError "Package name is required" "1. Info -> Package Name"; isValid = false)
        if (buttonTitle == "") do (addValidationError "Button name is required" "1. Info -> Button Name"; isValid = false)
        if (packageTitle != "" and not (isSafePackageDisplayText packageTitle)) do (addValidationError "Package name allows only A-Z, a-z, 0-9, space, hyphen, and underscore" "1. Info -> Package Name"; isValid = false)
        if (buttonTitle != "" and not (isSafePackageDisplayText buttonTitle)) do (addValidationError "Button name allows only A-Z, a-z, 0-9, space, hyphen, and underscore" "1. Info -> Button Name"; isValid = false)
        if (descriptionContent == "") do (addValidationError "Description is required" "1. Info -> Description"; isValid = false)
        if (developerTitle == "") do (addValidationError "Developer name is required" "1. Info -> Developer Name"; isValid = false)
        if (descriptionContent.count > 500) do (addValidationError "Description must be 500 characters or less" "1. Info -> Description"; isValid = false)
        if (guidContent == "" or not (isValidGuid guidContent)) do (addValidationError "Package GUID must be a valid UUID" "1. Info -> GUID"; isValid = false)
        if (versionContent == "") do (addValidationError "Version is required" "4. Release -> Version"; isValid = false)
        if (packageState.releaseChannel == "") do (addValidationError "Release channel is required" "4. Release -> Channel"; isValid = false)
        if (releaseDateContent == "") do (addValidationError "Release date is required" "4. Release -> Release Date"; isValid = false)
        if (not (hasChangelogEntries())) do (addValidationError ("Changelog for version " + versionContent + " must contain at least one item") "4. Release -> Changelog"; isValid = false)
        if (not (isValidLicenseTypeForState())) do (addValidationError "License is required" "1. Info -> License"; isValid = false)
        if (minMax == undefined or maxMax == undefined) do (addValidationError "Min and max 3ds Max versions must be numbers" "4. Release -> Min 3ds Max"; isValid = false)
        if (minMax != undefined and maxMax != undefined and minMax > maxMax) do (addValidationError "Min 3ds Max version must be <= max version" "4. Release -> Min 3ds Max"; isValid = false)

        if (entryFilePath == "") then (
            addValidationError "Entry file is required" "3. Files -> Entry File"
            isValid = false
        ) else (
            local entryItem = findPackageFileByRel entryFilePath

            if (entryItem == undefined) then (
                addValidationError "Entry file must be included in package files" "3. Files -> Entry File"
                isValid = false
            ) else (
                local entryExt = lowerString (getFilenameType entryFilePath)

                if (not (doesFileExist entryItem[1])) do (addValidationError "Entry file does not exist" "3. Files -> Entry File"; isValid = false)
                if (entryExt != ".ms" and entryExt != ".mse" and entryExt != ".py") do (addValidationError "Entry file must be .ms, .mse, or .py" "3. Files -> Entry File"; isValid = false)
                if (isEntryCompileEnabled and entryExt != ".ms") do (addValidationError "Entry compile requires .ms entry file" "3. Files -> Compile Entry"; isValid = false)
            )
        )

        if (svgIconFilePath == "") then (
            addValidationError "SVG icon is required" "3. Files -> SVG Icon"
            isValid = false
        ) else (
            if (isValidSafeSvg svgIconFilePath) then (
                addLog "OK" "SVG icon validated"
            ) else (
                addValidationError "Selected icon is not a valid safe SVG file." "3. Files -> SVG Icon"
                isValid = false
            )
        )

        if (packageFiles.count == 0) do (addValidationError "At least one package file is required" "3. Files -> Files"; isValid = false)

        for packageItem in packageFiles do (
            if (not (isSafeRelativePath packageItem[2])) do (addValidationError ("Invalid relative path: " + packageItem[2]) "3. Files -> Files"; isValid = false)
            if (not (doesFileExist packageItem[1])) do (addValidationError ("Missing file: " + packageItem[2]) "3. Files -> Files"; isValid = false)

            local relativeLowerPath = lowerString packageItem[2]
            if (endsWith relativeLowerPath "\\install.ms") do (addValidationError "install.ms is only allowed in package root" "3. Files -> Files"; isValid = false)
            if (endsWith relativeLowerPath "\\uninstall.ms") do (addValidationError "uninstall.ms is only allowed in package root" "3. Files -> Files"; isValid = false)
        )

        if ((detectRootHook "install.ms") != "") do addLog "OK" "install.ms detected"
        if ((detectRootHook "uninstall.ms") != "") do addLog "OK" "uninstall.ms detected"

        if (outputFolderPath == "" or outputFolderPath == "\\") then (
            addValidationError "Output folder is required" "3. Files -> Output Folder"
            isValid = false
        ) else if (not (ensureDirectory outputFolderPath)) then (
            addValidationError "Output folder does not exist and cannot be created" "3. Files -> Output Folder"
            isValid = false
        )

        if (isValid) then addLog "OK" "Validation passed" else addLog "ERROR" "Validation failed"
        refreshValidationColors()
        return isValid
    )

    fn iniLine settingKey settingContent = (
        return settingKey + "=" + (escapeIniValue settingContent) + "\n"
    )

    fn buildManifestIni = (
        local stringStreamContent = stringStream ""
        local iconPathContent = ""
        local manifestVersion = readScriptInfoEntry "MANIFEST_VERSION" defaultContent: "1"
        local packagerTitle = readScriptInfoEntry "NAME" defaultContent: "MaxPkg Packer"
        local packagerVersion = readScriptInfoEntry "VERSION" defaultContent: "0.1.0"

        if ((trimString packageState.svgIconFile) != "") do iconPathContent = "icons/icon.svg"

        format "[package]\n" to: stringStreamContent
        format "%" (iniLine "manifestVersion" manifestVersion) to: stringStreamContent
        format "%" (iniLine "packageGuid" packageState.packageGuid) to: stringStreamContent
        format "%" (iniLine "name" packageState.packageTitle) to: stringStreamContent
        format "%" (iniLine "buttonName" packageState.buttonTitle) to: stringStreamContent
        format "%" (iniLine "description" packageState.descriptionContent) to: stringStreamContent
        format "%" (iniLine "version" (buildVersionStringFromState())) to: stringStreamContent
        format "%" (iniLine "releaseChannel" packageState.releaseChannel) to: stringStreamContent
        format "%" (iniLine "releaseDate" packageState.releaseDate) to: stringStreamContent
        format "%" (iniLine "entry" (manifestEntryPathFromState())) to: stringStreamContent
        format "%" (iniLine "compileEntry" (boolToString (shouldCompileEntryFileFromState()))) to: stringStreamContent
        format "%" (iniLine "icon" iconPathContent) to: stringStreamContent
        format "%" (iniLine "license" packageState.licenseType) to: stringStreamContent
        format "%" (iniLine "licenseUrl" packageState.licenseUrl) to: stringStreamContent
        format "%" (iniLine "developerName" packageState.developerTitle) to: stringStreamContent
        format "%" (iniLine "min3dsMax" packageState.minMaxVersion) to: stringStreamContent
        format "%" (iniLine "max3dsMax" ((currentMaxYearPlusOne()) as string)) to: stringStreamContent
        format "%" (iniLine "homepage" packageState.homepageUrl) to: stringStreamContent
        format "%" (iniLine "documentation" packageState.documentationUrl) to: stringStreamContent
        format "%" (iniLine "support" packageState.supportUrl) to: stringStreamContent
        format "%" (iniLine "createMacroButton" (boolToString packageState.createButton)) to: stringStreamContent
        format "%" (iniLine "showInToolbar" (boolToString packageState.showToolbar)) to: stringStreamContent
        format "%" (iniLine "installScript" (detectRootHook "install.ms")) to: stringStreamContent
        format "%" (iniLine "uninstallScript" (detectRootHook "uninstall.ms")) to: stringStreamContent
        format "%" (iniLine "packager" packagerTitle) to: stringStreamContent
        format "%" (iniLine "packagerVersion" packagerVersion) to: stringStreamContent
        format "\n[changelog]\n" to: stringStreamContent

        for changelogIndex in 1 to changelogItems.count do (
            format "%" (iniLine ((changelogIndex as string) + "_type") changelogItems[changelogIndex][1]) to: stringStreamContent
            format "%" (iniLine ((changelogIndex as string) + "_text") changelogItems[changelogIndex][2]) to: stringStreamContent
        )

        return stringStreamContent as string
    )

    fn buildManifestJson = (
        local stringStreamContent = stringStream ""
        local iconPathContent = ""
        local manifestVersion = readScriptInfoEntry "MANIFEST_VERSION" defaultContent: "1"
        local packagerTitle = readScriptInfoEntry "NAME" defaultContent: "MaxPkg Packer"
        local packagerVersion = readScriptInfoEntry "VERSION" defaultContent: "0.1.0"
        local minMax = try (packageState.minMaxVersion as integer) catch(2012)
        local maxMax = currentMaxYearPlusOne()

        if ((trimString packageState.svgIconFile) != "") do iconPathContent = "icons/icon.svg"

        format "{\n" to: stringStreamContent
        format "  \"manifestVersion\": \"%\",\n" (escapeJson manifestVersion) to: stringStreamContent
        format "  \"packageGuid\": \"%\",\n" (escapeJson (trimString packageState.packageGuid)) to: stringStreamContent
        format "  \"name\": \"%\",\n" (escapeJson (trimString packageState.packageTitle)) to: stringStreamContent
        format "  \"buttonName\": \"%\",\n" (escapeJson (trimString packageState.buttonTitle)) to: stringStreamContent
        format "  \"description\": \"%\",\n" (escapeJson (trimString packageState.descriptionContent)) to: stringStreamContent
        format "  \"version\": \"%\",\n" (escapeJson (buildVersionStringFromState())) to: stringStreamContent
        format "  \"releaseChannel\": \"%\",\n" (escapeJson packageState.releaseChannel) to: stringStreamContent
        format "  \"releaseDate\": \"%\",\n" (escapeJson (trimString packageState.releaseDate)) to: stringStreamContent
        format "  \"entry\": \"%\",\n" (escapeJson (manifestEntryPathFromState())) to: stringStreamContent
        format "  \"compileEntry\": %, \n" (boolToString (shouldCompileEntryFileFromState())) to: stringStreamContent
        format "  \"icon\": \"%\",\n" (escapeJson iconPathContent) to: stringStreamContent
        format "  \"license\": \"%\",\n" (escapeJson packageState.licenseType) to: stringStreamContent
        format "  \"licenseUrl\": \"%\",\n" (escapeJson (trimString packageState.licenseUrl)) to: stringStreamContent
        format "  \"developerName\": \"%\",\n" (escapeJson (trimString packageState.developerTitle)) to: stringStreamContent
        format "  \"min3dsMax\": %, \n" minMax to: stringStreamContent
        format "  \"max3dsMax\": %, \n" maxMax to: stringStreamContent
        format "  \"homepage\": \"%\",\n" (escapeJson (trimString packageState.homepageUrl)) to: stringStreamContent
        format "  \"documentation\": \"%\",\n" (escapeJson (trimString packageState.documentationUrl)) to: stringStreamContent
        format "  \"support\": \"%\",\n" (escapeJson (trimString packageState.supportUrl)) to: stringStreamContent
        format "  \"createMacroButton\": %, \n" (boolToString packageState.createButton) to: stringStreamContent
        format "  \"showInToolbar\": %, \n" (boolToString packageState.showToolbar) to: stringStreamContent
        format "  \"installScript\": \"%\",\n" (escapeJson (detectRootHook "install.ms")) to: stringStreamContent
        format "  \"uninstallScript\": \"%\",\n" (escapeJson (detectRootHook "uninstall.ms")) to: stringStreamContent
        format "  \"packager\": \"%\",\n" (escapeJson packagerTitle) to: stringStreamContent
        format "  \"packagerVersion\": \"%\",\n" (escapeJson packagerVersion) to: stringStreamContent
        format "  \"changelog\": [\n" to: stringStreamContent

        for changelogIndex in 1 to changelogItems.count do (
            format "    { \"type\": \"%\", \"text\": \"%\" }" (escapeJson changelogItems[changelogIndex][1]) (escapeJson changelogItems[changelogIndex][2]) to: stringStreamContent
            if (changelogIndex < changelogItems.count) do format "," to: stringStreamContent
            format "\n" to: stringStreamContent
        )

        format "  ]\n" to: stringStreamContent
        format "}\n" to: stringStreamContent
        return stringStreamContent as string
    )

    fn maxScriptStringLiteral sourceContent = (
        local literalContent = sourceContent as string
        literalContent = substituteString literalContent "\\" "\\\\"
        literalContent = substituteString literalContent "\"" "\\\""
        literalContent = substituteString literalContent "\r\n" "\\n"
        literalContent = substituteString literalContent "\n" "\\n"
        return "\"" + literalContent + "\""
    )

    fn maxScriptForwardPathLiteral sourceFilePath = (
        local literalContent = sourceFilePath as string
        literalContent = substituteString literalContent "\\" "/"
        literalContent = substituteString literalContent "\"" "\\\""
        return "\"" + literalContent + "\""
    )

    fn mzpQuotedString sourceContent = (
        local quotedContent = trimString sourceContent
        quotedContent = substituteString quotedContent "\"" "'"
        return "\"" + quotedContent + "\""
    )

    fn buildMzpRunScript = (
        local packageTitle = trimString packageState.packageTitle
        local packageGuid = trimString packageState.packageGuid
        local entryScriptFile = "mzp.run.ms"
        local mzpContent = ""

        if (packageTitle == "") do packageTitle = packageGuid

        mzpContent += "name " + (mzpQuotedString packageTitle) + "\n"
        mzpContent += "extract to " + (mzpQuotedString ("$temp\\" + packageGuid)) + "\n"
        mzpContent += "drop " + (mzpQuotedString entryScriptFile) + "\n"
        mzpContent += "run " + (mzpQuotedString entryScriptFile) + "\n"
        return mzpContent
    )

    fn buildMzpEntryScript = (
        local scriptContent = ""

        scriptContent += "(\n"
        scriptContent += "    fn maxPkgEntryEnsureSlash folderPath = (\n"
        scriptContent += "        if (folderPath == undefined or folderPath == \"\") do return \"\"\n"
        scriptContent += "        if ((substring folderPath folderPath.count 1) == \"\\\\\") do return folderPath\n"
        scriptContent += "        return folderPath + \"\\\\\"\n"
        scriptContent += "    )\n\n"
        scriptContent += "    fn maxPkgEntryStringLiteral sourceContent = (\n"
        scriptContent += "        local literalContent = sourceContent as string\n"
        scriptContent += "        literalContent = substituteString literalContent \"\\\\\" \"\\\\\\\\\"\n"
        scriptContent += "        literalContent = substituteString literalContent \"\\\"\" \"\\\\\\\"\"\n"
        scriptContent += "        return \"\\\"\" + literalContent + \"\\\"\"\n"
        scriptContent += "    )\n\n"
        scriptContent += "    fn maxPkgEntryForwardPathLiteral sourceFilePath = (\n"
        scriptContent += "        local literalContent = sourceFilePath as string\n"
        scriptContent += "        literalContent = substituteString literalContent \"\\\\\" \"/\"\n"
        scriptContent += "        literalContent = substituteString literalContent \"\\\"\" \"\\\\\\\"\"\n"
        scriptContent += "        return \"\\\"\" + literalContent + \"\\\"\"\n"
        scriptContent += "    )\n\n"
        scriptContent += "    fn maxPkgEntryWriteTextFile targetFilePath fileContent = (\n"
        scriptContent += "        local fileStream = undefined\n"
        scriptContent += "        try (\n"
        scriptContent += "            fileStream = createFile targetFilePath\n"
        scriptContent += "            if (fileStream == undefined) do return false\n"
        scriptContent += "            format \"%\" fileContent to: fileStream\n"
        scriptContent += "            close fileStream\n"
        scriptContent += "            return true\n"
        scriptContent += "        ) catch (\n"
        scriptContent += "            try (if (fileStream != undefined) do close fileStream) catch()\n"
        scriptContent += "            return false\n"
        scriptContent += "        )\n"
        scriptContent += "    )\n\n"
        scriptContent += "    fn maxPkgEntryMacroNameFromGuid packageGuid = (\n"
        scriptContent += "        return \"MaxPkg_\" + (substituteString packageGuid \"-\" \"\")\n"
        scriptContent += "    )\n\n"
        scriptContent += "    fn maxPkgEntryInstallIcon entryFolder packageGuid = (\n"
        scriptContent += "        local sourceIconFile = entryFolder + \"icons\\\\icon.svg\"\n"
        scriptContent += "        local targetIconFile = (maxPkgEntryEnsureSlash (getDir #userIcons)) + packageGuid + \".svg\"\n"
        scriptContent += "        if (not (doesFileExist sourceIconFile)) do return true\n"
        scriptContent += "        try (\n"
        scriptContent += "            if (doesFileExist targetIconFile) do deleteFile targetIconFile\n"
        scriptContent += "            copyFile sourceIconFile targetIconFile\n"
        scriptContent += "            return true\n"
        scriptContent += "        ) catch (\n"
        scriptContent += "            messageBox (\"Could not install package icon:\\n\" + targetIconFile + \"\\n\\n\" + getCurrentException()) title: \"MaxPkg\"\n"
        scriptContent += "            return false\n"
        scriptContent += "        )\n"
        scriptContent += "    )\n\n"
        scriptContent += "    fn maxPkgEntryBuildMacroScript entryFolder packageGuid = (\n"
        scriptContent += "        local manifestFilePath = entryFolder + \"manifest.ini\"\n"
        scriptContent += "        local packageButtonText = getINISetting manifestFilePath \"package\" \"buttonName\"\n"
        scriptContent += "        local packageIcon = getINISetting manifestFilePath \"package\" \"icon\"\n"
        scriptContent += "        local macroIconFilePath = (maxPkgEntryEnsureSlash (getDir #userIcons)) + packageGuid + \".svg\"\n"
        scriptContent += "        local macroContent = \"\"\n"
        scriptContent += "        if (packageButtonText == undefined or packageButtonText == \"\") do packageButtonText = packageGuid\n"
        scriptContent += "        macroContent += \"macroScript \" + (maxPkgEntryMacroNameFromGuid packageGuid) + \"\\n\"\n"
        scriptContent += "        macroContent += \"category: \\\"MaxPkg\\\"\\n\"\n"
        scriptContent += "        macroContent += \"buttonText: \" + (maxPkgEntryStringLiteral packageButtonText) + \"\\n\"\n"
        scriptContent += "        macroContent += \"tooltip: \" + (maxPkgEntryStringLiteral (\"Run \" + packageButtonText)) + \"\\n\"\n"
        scriptContent += "        if (packageIcon != undefined and packageIcon != \"\") do macroContent += \"iconName: \" + (maxPkgEntryForwardPathLiteral macroIconFilePath) + \"\\n\"\n"
        scriptContent += "        macroContent += \"(\\n\"\n"
        scriptContent += "        macroContent += \"    on execute do\\n\"\n"
        scriptContent += "        macroContent += \"    (\\n\"\n"
        scriptContent += "        macroContent += \"        -- Generated by MaxPkg. https://maxpkg.dev\\n\"\n"
        scriptContent += "        macroContent += \"        -- This file was created during package installation for the current 3ds Max profile.\\n\"\n"
        scriptContent += "        macroContent += \"        -- Package GUID: \" + packageGuid + \"\\n\"\n"
        scriptContent += "        macroContent += \"        try\\n\"\n"
        scriptContent += "        macroContent += \"        (\\n\"\n"
        scriptContent += "        macroContent += \"            local packageGuid = \" + (maxPkgEntryStringLiteral packageGuid) + \"\\n\"\n"
        scriptContent += "        macroContent += \"            local packageDir = (getDir #temp) + \" + (maxPkgEntryStringLiteral \"\\\\\") + \" + packageGuid + \" + (maxPkgEntryStringLiteral \"\\\\\") + \"\\n\"\n"
        scriptContent += "        macroContent += \"            local manifestIni = packageDir + \" + (maxPkgEntryStringLiteral \"manifest.ini\") + \"\\n\"\n"
        scriptContent += "        macroContent += \"            if (not (doesFileExist manifestIni)) do throw (\" + (maxPkgEntryStringLiteral \"Package manifest was not found: \") + \" + manifestIni)\\n\"\n"
        scriptContent += "        macroContent += \"            local entry = getINISetting manifestIni \" + (maxPkgEntryStringLiteral \"package\") + \" \" + (maxPkgEntryStringLiteral \"entry\") + \"\\n\"\n"
        scriptContent += "        macroContent += \"            if (entry == undefined or entry == \" + (maxPkgEntryStringLiteral \"\") + \") do throw \" + (maxPkgEntryStringLiteral \"Package entry file is empty.\") + \"\\n\"\n"
        scriptContent += "        macroContent += \"            local entryPath = packageDir + entry\\n\"\n"
        scriptContent += "        macroContent += \"            local entryExt = toLower (getFilenameType entryPath)\\n\"\n"
        scriptContent += "        macroContent += \"            if (not (doesFileExist entryPath)) do throw (\" + (maxPkgEntryStringLiteral \"Package entry file was not found: \") + \" + entryPath)\\n\"\n"
        scriptContent += "        macroContent += \"            if (entryExt == \" + (maxPkgEntryStringLiteral \".py\") + \") then python.ExecuteFile entryPath else if (entryExt == \" + (maxPkgEntryStringLiteral \".ms\") + \" or entryExt == \" + (maxPkgEntryStringLiteral \".mse\") + \") then fileIn entryPath else throw (\" + (maxPkgEntryStringLiteral \"Unsupported package entry file type: \") + \" + entryExt)\\n\"\n"
        scriptContent += "        macroContent += \"        )\\n\"\n"
        scriptContent += "        macroContent += \"        catch\\n\"\n"
        scriptContent += "        macroContent += \"        (\\n\"\n"
        scriptContent += "        macroContent += \"            messageBox (\" + (maxPkgEntryStringLiteral \"Could not run MaxPkg package.\\n\") + \" + getCurrentException()) title: \" + (maxPkgEntryStringLiteral \"MaxPkg\") + \"\\n\"\n"
        scriptContent += "        macroContent += \"        )\\n\"\n"
        scriptContent += "        macroContent += \"    )\\n\"\n"
        scriptContent += "        macroContent += \")\\n\"\n"
        scriptContent += "        return macroContent\n"
        scriptContent += "    )\n\n"
        scriptContent += "    fn maxPkgEntryInstallMacroButton entryFolder packageGuid = (\n"
        scriptContent += "        local manifestFilePath = entryFolder + \"manifest.ini\"\n"
        scriptContent += "        local createMacroButton = getINISetting manifestFilePath \"package\" \"createMacroButton\"\n"
        scriptContent += "        local macroFilePath = (maxPkgEntryEnsureSlash (getDir #userMacros)) + \"maxpkg-\" + packageGuid + \".mcr\"\n"
        scriptContent += "        local macroContent = \"\"\n"
        scriptContent += "        if (createMacroButton == undefined) do createMacroButton = \"\"\n"
        scriptContent += "        createMacroButton = toLower createMacroButton\n"
        scriptContent += "        if (createMacroButton != \"true\") do return true\n"
        scriptContent += "        maxPkgEntryInstallIcon entryFolder packageGuid\n"
        scriptContent += "        macroContent = maxPkgEntryBuildMacroScript entryFolder packageGuid\n"
        scriptContent += "        if (not (maxPkgEntryWriteTextFile macroFilePath macroContent)) do (\n"
        scriptContent += "            messageBox (\"Could not create package macro button:\\n\" + macroFilePath) title: \"MaxPkg\"\n"
        scriptContent += "            return false\n"
        scriptContent += "        )\n"
        scriptContent += "        try (fileIn macroFilePath; return true) catch (messageBox (\"Could not load package macro button:\\n\" + macroFilePath + \"\\n\\n\" + getCurrentException()) title: \"MaxPkg\"; return false)\n"
        scriptContent += "    )\n\n"
        scriptContent += "    fn maxPkgEntryRunOptionalScript scriptFilePath = (\n"
        scriptContent += "        if (scriptFilePath == undefined or scriptFilePath == \"\") do return false\n"
        scriptContent += "        if (not (doesFileExist scriptFilePath)) do return true\n"
        scriptContent += "        try (fileIn scriptFilePath; return true) catch (messageBox (\"Could not run package script:\\n\" + scriptFilePath + \"\\n\\n\" + getCurrentException()) title: \"MaxPkg\"; return false)\n"
        scriptContent += "    )\n\n"
        scriptContent += "    local entryFolder = maxPkgEntryEnsureSlash (getFilenamePath (getSourceFileName()))\n"
        scriptContent += "    local manifestFilePath = entryFolder + \"manifest.ini\"\n"
        scriptContent += "    local packageGuid = getINISetting manifestFilePath \"package\" \"packageGuid\"\n"
        scriptContent += "    if (packageGuid == undefined or packageGuid == \"\") then (\n"
        scriptContent += "        messageBox (\"Package GUID was not found in manifest:\\n\" + manifestFilePath) title: \"MaxPkg\"\n"
        scriptContent += "    ) else (\n"
        scriptContent += "        maxPkgEntryInstallMacroButton entryFolder packageGuid\n"
        scriptContent += "        maxPkgEntryRunOptionalScript (entryFolder + \"install.ms\")\n"
        scriptContent += "        try (if (MaxPkg != undefined) do MaxPkg.newInstallation packageGuid) catch()\n"
        scriptContent += "    )\n"
        scriptContent += ")\n"

        return scriptContent
    )

    fn buildSampleInstallScript = (
        local sampleContent = ""

        sampleContent += "(\n"
        sampleContent += "    local scriptDir = getFilenamePath (getSourceFileName())\n"
        sampleContent += "    local manifestFilePath = scriptDir + \"manifest.ini\"\n"
        sampleContent += "    local changelogFilePath = scriptDir + \"maxpkg-changelog.ini\"\n"
        sampleContent += "    local packageTitle = getINISetting manifestFilePath \"package\" \"name\"\n"
        sampleContent += "    local packageVersion = getINISetting manifestFilePath \"package\" \"version\"\n"
        sampleContent += "    local releaseDate = getINISetting manifestFilePath \"package\" \"releaseDate\"\n"
        sampleContent += "    local packageDescription = getINISetting manifestFilePath \"package\" \"description\"\n"
        sampleContent += "    local changelogContent = \"\"\n"
        sampleContent += "    if (packageTitle == undefined or packageTitle == \"\") do packageTitle = \"Package\"\n"
        sampleContent += "    if (packageVersion == undefined or packageVersion == \"\") do packageVersion = \"1.0.0\"\n"
        sampleContent += "    if (releaseDate == undefined) do releaseDate = \"\"\n"
        sampleContent += "    if (packageDescription == undefined) do packageDescription = \"\"\n"
        sampleContent += "    packageDescription = substituteString packageDescription \"\\\\n\" \"\\r\\n\"\n"
        sampleContent += "    local changelogSectionName = \"version_\" + packageVersion\n"
        sampleContent += "    local changelogCount = try ((getINISetting changelogFilePath changelogSectionName \"count\") as integer) catch(0)\n"
        sampleContent += "    for changelogIndex in 1 to changelogCount do (\n"
        sampleContent += "        local itemType = getINISetting changelogFilePath changelogSectionName ((changelogIndex as string) + \"_type\")\n"
        sampleContent += "        local itemContent = getINISetting changelogFilePath changelogSectionName ((changelogIndex as string) + \"_text\")\n"
        sampleContent += "        if (itemType != undefined and itemType != \"\" and itemContent != undefined and itemContent != \"\") do changelogContent += \"- [\" + itemType + \"] \" + (substituteString itemContent \"\\\\n\" \"\\r\\n\") + \"\\r\\n\"\n"
        sampleContent += "    )\n"
        sampleContent += "    if (changelogContent == \"\") do changelogContent = \"No changelog entries for this version.\"\n"
        sampleContent += "    local infoContent = \"Installed successfully\\r\\n\\r\\nName: \" + packageTitle + \"\\r\\nVersion: \" + packageVersion + \"\\r\\nRelease Date: \" + releaseDate + \"\\r\\n\\r\\nDescription:\\r\\n\" + packageDescription + \"\\r\\n\\r\\nLatest changelog:\\r\\n\" + changelogContent\n"
        sampleContent += "    try (destroyDialog MaxPkgSampleInstallRollout) catch()\n"
        sampleContent += "    rollout MaxPkgSampleInstallRollout \"Install Complete\" width: 450 height: 350 (\n"
        sampleContent += "        dotNetControl dncInstallInfo \"System.Windows.Forms.TextBox\" height: 260 align: #left\n"
        sampleContent += "        button btnCloseInstallInfo \"Close\" width: 80 height: 24 align: #right offset: [0, 4]\n"
        sampleContent += "        on MaxPkgSampleInstallRollout open do (\n"
        sampleContent += "            local scrollBarsClass = dotNetClass \"System.Windows.Forms.ScrollBars\"\n"
        sampleContent += "            dncInstallInfo.Multiline = true\n"
        sampleContent += "            dncInstallInfo.ReadOnly = true\n"
        sampleContent += "            dncInstallInfo.WordWrap = true\n"
        sampleContent += "            dncInstallInfo.ScrollBars = scrollBarsClass.Vertical\n"
        sampleContent += "            dncInstallInfo.Text = infoContent\n"
        sampleContent += "        )\n"
        sampleContent += "        on btnCloseInstallInfo pressed do destroyDialog MaxPkgSampleInstallRollout\n"
        sampleContent += "    )\n"
        sampleContent += "    createDialog MaxPkgSampleInstallRollout width: 450 height: 350 modal: false style: #(#style_titlebar, #style_sysmenu, #style_toolwindow)\n"
        sampleContent += ")\n"
        return sampleContent
    )

    fn buildSampleUninstallScript = (
        local sampleContent = ""

        sampleContent += "(\n"
        sampleContent += "    local scriptDir = getFilenamePath (getSourceFileName())\n"
        sampleContent += "    local manifestFilePath = scriptDir + \"manifest.ini\"\n"
        sampleContent += "    local packageTitle = getINISetting manifestFilePath \"package\" \"name\"\n"
        sampleContent += "    if (packageTitle == undefined or packageTitle == \"\") do packageTitle = \"Package\"\n"
        sampleContent += "    messageBox (packageTitle + \" has been completely removed.\") title: \"Uninstall Complete\"\n"
        sampleContent += ")\n"
        return sampleContent
    )

    fn createSamplePackageScript scriptFileName sampleContent = (
        local sampleFilePath = normalizePath ((ensureTrailingSlash scriptDir) + scriptFileName)

        if (doesFileExist sampleFilePath) do (
            messageBox (scriptFileName + " already exists.") title: "MaxPkg Packer"
            return false
        )

        if (not (writeTextFile sampleFilePath sampleContent)) do (
            messageBox ("Could not create " + scriptFileName + ".") title: "MaxPkg Packer"
            return false
        )

        addPackageFile sampleFilePath
        messageBox (scriptFileName + " created successfully.\n\nLocation:\n" + sampleFilePath) title: "MaxPkg Packer"
        return true
    )

    fn copyPackageFile absFilePath targetFilePath = (
        ensureDirectory (getFilenamePath targetFilePath)
        copyFile absFilePath targetFilePath
        return true
    )

    fn compilePackageEntryFile sourceFilePath stagingSourceFilePath = (
        local targetFilePath = compiledEntryPath stagingSourceFilePath

        ensureDirectory (getFilenamePath stagingSourceFilePath)

        try (
            if (doesFileExist stagingSourceFilePath) do deleteFile stagingSourceFilePath
            if (doesFileExist targetFilePath) do deleteFile targetFilePath
            copyFile sourceFilePath stagingSourceFilePath
            encryptScript stagingSourceFilePath
            deleteFile stagingSourceFilePath

            if (doesFileExist targetFilePath) do return true

            addLog "ERROR" ("Compiled entry was not created: " + targetFilePath)
            return false
        ) catch (
            addLog "ERROR" ("Could not compile entry file: " + getCurrentException())
            return false
        )
    )

    fn createMzpFromFolder sourceFolder outputFile = (
        if (doesFileExist outputFile) do deleteFile outputFile

        try (
            dotNet.loadAssembly "System.IO.Compression.FileSystem"
            local zipFileClass = dotNetClass "System.IO.Compression.ZipFile"
            zipFileClass.CreateFromDirectory sourceFolder outputFile
            return true
        ) catch (
            addLog "ERROR" ("Could not create MZP: " + getCurrentException())
            return false
        )
    )

    fn cleanupBuildFolder buildFolder = (
        if (buildFolder == undefined or buildFolder == "") do return false
        if (not (directoryExists buildFolder)) do return true
        deleteDirectory buildFolder
        return true
    )

    fn buildPackage = (
        savePackageSettings()

        if (not (validatePackageSettings())) do return false

        local packageGuid = trimString packageState.packageGuid
        local outputFolderPath = ensureTrailingSlash packageState.outputFolder
        local buildRoot = ensureTrailingSlash ((getDir #temp) + "\\maxpkg-packager-build-" + packageGuid)
        local outputFilePath = outputFolderPath + outputMzpFileName()
        local sourceEntryFilePath = normalizePath (trimString packageState.entryFile)
        local isEntryCompileEnabled = shouldCompileEntryFileFromState()
        local isPackageBuilt = false

        try (
            deleteDirectory buildRoot
            ensureDirectory buildRoot

            writeTextFile (buildRoot + "manifest.ini") (buildManifestIni())
            addLog "OK" "manifest.ini generated"

            writeTextFile (buildRoot + "manifest.json") (buildManifestJson())
            addLog "OK" "manifest.json generated"

            saveCurrentChangelog()
            if (doesFileExist changelogIniFilePath) do (
                copyFile changelogIniFilePath (buildRoot + "maxpkg-changelog.ini")
                addLog "OK" "maxpkg-changelog.ini copied"
            )

            for packageItem in packageFiles do (
                local packageRelativePath = normalizePath packageItem[2]

                if (isEntryCompileEnabled and (lowerString packageRelativePath) == (lowerString sourceEntryFilePath)) then (
                    compilePackageEntryFile packageItem[1] (buildRoot + sourceEntryFilePath)
                ) else (
                    copyPackageFile packageItem[1] (buildRoot + packageRelativePath)
                )
            )

            addLog "OK" ((packageFiles.count as string) + " files copied")

            if ((trimString packageState.svgIconFile) != "") do (
                ensureDirectory (buildRoot + "icons")
                copyFile packageState.svgIconFile (buildRoot + "icons\\icon.svg")
                addLog "OK" "SVG icon copied"
            )

            writeTextFile (buildRoot + "mzp.run.ms") (buildMzpEntryScript())
            addLog "OK" "mzp.run.ms generated"

            writeTextFile (buildRoot + "mzp.run") (buildMzpRunScript())
            addLog "OK" "mzp.run generated"

            if (hasLogErrors()) then (
                addLog "ERROR" "MZP was not created because log contains errors"
            ) else (
                if (createMzpFromFolder buildRoot outputFilePath) do (
                    addLog "OK" ("MZP created: " + outputFilePath)
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

    fn contentRolloutForTabId tabId = (
        case (normalizeTabId tabId) of (
            "info": return MaxPkgPackerNewInfoRollout
            "setup": return MaxPkgPackerNewSetupRollout
            "files": return MaxPkgPackerNewFilesRollout
            "release": return MaxPkgPackerNewReleaseRollout
            default: return MaxPkgPackerNewInfoRollout
        )
    )

    rollout MaxPkgPackerNewGuidConfirmRollout "Confirm GUID Change" width: 360 height: 150
    (
        label lblGuidChangeWarning "Changing Package GUID creates a new package identity." align: #left
        label lblGuidChangeInstruction "Type CHANGE to generate a new GUID." align: #left offset: [0, 15]
        dotNetControl dncGuidChangePhrase "System.Windows.Forms.TextBox" height: 22 align: #left

        button btnConfirmGuidChange "OK" width: 80 height: 23 enabled: false align: #left across: 2 offset: [0, 15]
        button btnCancelGuidChange "Cancel" width: 80 height: 23 align: #right offset: [0, 15]

        on MaxPkgPackerNewGuidConfirmRollout open do (
            setupTextBoxControl dncGuidChangePhrase
            dncGuidChangePhrase.Text = ""
            btnConfirmGuidChange.enabled = false
            dncGuidChangePhrase.Focus()
        )

        on dncGuidChangePhrase TextChanged sender eventArgs do (
            btnConfirmGuidChange.enabled = ((toUpper dncGuidChangePhrase.Text) == "CHANGE")
        )

        on btnConfirmGuidChange pressed do (
            if ((toUpper dncGuidChangePhrase.Text) == "CHANGE") do (
                isGuidChangeConfirmed = true
                destroyDialog MaxPkgPackerNewGuidConfirmRollout
            )
        )

        on btnCancelGuidChange pressed do (
            isGuidChangeConfirmed = false
            destroyDialog MaxPkgPackerNewGuidConfirmRollout
        )
    )

    fn confirmGuidChange = (
        isGuidChangeConfirmed = false
        try (destroyDialog MaxPkgPackerNewGuidConfirmRollout) catch()
        createDialog MaxPkgPackerNewGuidConfirmRollout width: 380 height: 128 modal: true
        return isGuidChangeConfirmed
    )

    rollout MaxPkgPackerNewTabsRollout "Tabs" width: 380 category: 1
    (
        local isTabsLoading = false

        dotNetControl dncTabs "System.Windows.Forms.TabControl" width: 260 height: 30 align: #left across: 2 offset: [-10, 0]
        checkbutton btnValidationStatus "Has Issues" width: 95 height: 23 align: #right checked: true highlightColor: (color 125 36 36)  offset: [0, 3]
        timer tmrValidationStatus interval: 700 active: false

        fn tabIndexFromId tabId = (
            case (normalizeTabId tabId) of (
                "info": return 0
                "setup": return 1
                "files": return 2
                "release": return 3
                default: return 0
            )
        )

        fn tabIdFromIndex tabIndex = (
            case tabIndex of (
                0: return "info"
                1: return "setup"
                2: return "files"
                3: return "release"
                default: return "info"
            )
        )

        fn addTabPage tabCaption tabId = (
            local tabPage = dotNetObject "System.Windows.Forms.TabPage"

            tabPage.Text = tabCaption
            tabPage.Tag = tabId
            dncTabs.TabPages.Add tabPage
            return true
        )

        fn setupTabsControl = (
            local tabSizeModeClass = dotNetClass "System.Windows.Forms.TabSizeMode"
            local tabItemSize = dotNetObject "System.Drawing.Size" 64 24

            dncTabs.SizeMode = tabSizeModeClass.Fixed
            dncTabs.ItemSize = tabItemSize
            return true
        )

        fn selectTabById tabId = (
            local tabIndex = tabIndexFromId tabId

            if (dncTabs.SelectedIndex != tabIndex) do dncTabs.SelectedIndex = tabIndex
            return true
        )

        on MaxPkgPackerNewTabsRollout open do (
            isTabsLoading = true
            setupTabsControl()
            dncTabs.TabPages.Clear()
            addTabPage "1. Info" "info"
            addTabPage "2. Setup" "setup"
            addTabPage "3. Files" "files"
            addTabPage "4. Release" "release"
            selectTabById currentTabId
            isTabsLoading = false
            scheduleValidationStatusUpdate()
        )

        on dncTabs SelectedIndexChanged sender eventArgs do (
            if (not isTabsLoading and not isSwitchingTab) do (
                switchTab (tabIdFromIndex dncTabs.SelectedIndex)
            )
        )

        on btnValidationStatus changed isChecked do (
            btnValidationStatus.checked = true
            validatePackageSettings()
            refreshValidationStatusButton()
            showLogWindow()
        )

        on tmrValidationStatus tick do (
            stopValidationStatusTimer()
            refreshValidationStatusButton()
        )
    )

	rollout MaxPkgPackerNewInfoRollout "Info" width: 380 category: 2
    (
        local guidContextMenu
        local guidCopyMenuItem
        local guidPasteMenuItem
        local guidTextBoxControl
        local previousPackageTitle = ""
        local previousButtonTitle = ""
        local isRevertingSafeContent = false

        fn copyGuidToClipboard guidTextBox = (
            local guidContent = guidTextBox.Text
            local clipboardClass = dotNetClass "System.Windows.Forms.Clipboard"

            if (guidContent == undefined) do guidContent = ""
            clipboardClass.SetText (guidContent as string)
            return true
        )

        fn pasteGuidFromClipboard guidTextBox = (
            local clipboardClass = dotNetClass "System.Windows.Forms.Clipboard"

            if (clipboardClass.ContainsText()) do (
                local pastedGuidContent = trimString (clipboardClass.GetText())
                local currentGuidContent = trimString guidTextBox.Text
                local shouldPasteGuid = true

                if (currentGuidContent != "" and pastedGuidContent != currentGuidContent) do (
                    shouldPasteGuid = queryBox ("Replace current Package GUID?\n\nCurrent GUID:\n" + currentGuidContent + "\n\nNew GUID:\n" + pastedGuidContent + "\n\nPackage GUID is important. It is linked to the MaxPkg website and used to verify package archives. If you replace it, existing archives may no longer be accepted.") title: "MaxPkg Packer"
                )

                if (shouldPasteGuid) do (
                    guidTextBox.Text = pastedGuidContent
                    packageState.packageGuid = pastedGuidContent
                    savePackageSettings()
                )
            )

            return true
        )

        fn onGuidCopyMenuItemClick sender eventArgs = (
            copyGuidToClipboard guidTextBoxControl
            return true
        )

        fn onGuidPasteMenuItemClick sender eventArgs = (
            pasteGuidFromClipboard guidTextBoxControl
            return true
        )

        fn setupGuidContextMenu guidTextBox = (
            guidTextBoxControl = guidTextBox
            guidContextMenu = dotNetObject "System.Windows.Forms.ContextMenuStrip"
            guidCopyMenuItem = dotNetObject "System.Windows.Forms.ToolStripMenuItem" "Copy"
            guidPasteMenuItem = dotNetObject "System.Windows.Forms.ToolStripMenuItem" "Paste"

            dotNet.addEventHandler guidCopyMenuItem "Click" onGuidCopyMenuItemClick
            dotNet.addEventHandler guidPasteMenuItem "Click" onGuidPasteMenuItemClick
            guidContextMenu.Items.Add guidCopyMenuItem
            guidContextMenu.Items.Add guidPasteMenuItem
            guidTextBox.ContextMenuStrip = guidContextMenu
            return true
        )

        fn syncSafeDisplayText textBoxControl fieldLabel previousContent = (
            local incomingContent = textBoxControl.Text

            if (isSafePackageDisplayText incomingContent) do return incomingContent

            messageBox (fieldLabel + " allows only A-Z, a-z, 0-9, space, hyphen, and underscore.") title: "MaxPkg Packer"
            isRevertingSafeContent = true
            textBoxControl.Text = previousContent
            isRevertingSafeContent = false
            return previousContent
        )

        group "Important Info" (
            label lblPackageName "Package Name" align: #left
            dotNetControl dncPackageName "System.Windows.Forms.TextBox" height: 22 align: #left

            label lblButtonName "Button Name" align: #left
            dotNetControl dncButtonName "System.Windows.Forms.TextBox" height: 22 align: #left

			label lblDescription "Description" align: #left
            dotNetControl dncDescription "System.Windows.Forms.TextBox" height: 58 align: #left

			label lblLicense "License" align: #left
            dropdownList ddlLicense "" items: #("", "Free","Shareware","Commercial","Open source","Trial") selection: 1 align: #left
		)

		group "GUID" (
            dotNetControl dncGuid "System.Windows.Forms.TextBox" readOnly: true height: 22 align: #left width: 232 across: 2
            button btnGenerateGuid "Generate" width: 120 height: 23 align: #right offset: [0, -1]
		)

		group "Developer Name" (
            dotNetControl dncDeveloperName "System.Windows.Forms.TextBox" height: 22 align: #left
        )

        group "Additional" (
            label lblLicenseUrl "License URL" align: #left
            dotNetControl dncLicenseUrl "System.Windows.Forms.TextBox" height: 22 align: #left

            label lblDocumentationUrl "Documentation URL" align: #left
            dotNetControl dncDocumentationUrl "System.Windows.Forms.TextBox" height: 22 align: #left

            label lblHomepageUrl "Homepage URL" align: #left
            dotNetControl dncHomepageUrl "System.Windows.Forms.TextBox" height: 22 align: #left

            label lblSupportUrl "Support URL" align: #left
            dotNetControl dncSupportUrl "System.Windows.Forms.TextBox" height: 22 align: #left
        )

        on MaxPkgPackerNewInfoRollout open do (
            setupTextBoxControl dncPackageName
            setupTextBoxControl dncButtonName
            setupTextBoxControl dncGuid isReadOnly: true
            setupTextBoxControl dncDescription isMultiline: true
            setupTextBoxControl dncDeveloperName
            setupTextBoxControl dncLicenseUrl
            setupTextBoxControl dncDocumentationUrl
            setupTextBoxControl dncHomepageUrl
            setupTextBoxControl dncSupportUrl
            setupGuidContextMenu dncGuid

            isLoadingSettings = true
            dncPackageName.Text = packageState.packageTitle
            dncButtonName.Text = packageState.buttonTitle
            dncGuid.Text = packageState.packageGuid
            dncDescription.Text = packageState.descriptionContent
            dncDeveloperName.Text = packageState.developerTitle
            if (not (setDropDownText ddlLicense packageState.licenseType)) do (
                ddlLicense.selection = 1
                packageState.licenseType = ""
            )
            dncLicenseUrl.Text = packageState.licenseUrl
            dncDocumentationUrl.Text = packageState.documentationUrl
            dncHomepageUrl.Text = packageState.homepageUrl
            dncSupportUrl.Text = packageState.supportUrl
            previousPackageTitle = packageState.packageTitle
            previousButtonTitle = packageState.buttonTitle
            isLoadingSettings = false
            refreshValidationColors()
        )

        on dncPackageName TextChanged sender eventArgs do (
            if (not isLoadingSettings and not isRevertingSafeContent) do (
                previousPackageTitle = syncSafeDisplayText dncPackageName "Package Name" previousPackageTitle
                packageState.packageTitle = dncPackageName.Text
                savePackageSettings()
            )
        )

        on dncButtonName TextChanged sender eventArgs do (
            if (not isLoadingSettings and not isRevertingSafeContent) do (
                previousButtonTitle = syncSafeDisplayText dncButtonName "Button Name" previousButtonTitle
                packageState.buttonTitle = dncButtonName.Text
                savePackageSettings()
            )
        )

        on dncGuid TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.packageGuid = dncGuid.Text
                savePackageSettings()
            )
        )

        on dncDescription TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.descriptionContent = dncDescription.Text
                savePackageSettings()
            )
        )

        on dncDescription keyPress sender eventArgs do (
            if (eventArgs.keyChar == "\r") do (
                dncDescription.text += "\r\n"
                dncDescription.SelectionStart = dncDescription.text.count
            )
        )

        on dncDeveloperName TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.developerTitle = dncDeveloperName.Text
                savePackageSettings()
            )
        )

        on ddlLicense selected selectedIndex do (
            if (not isLoadingSettings) do (
                packageState.licenseType = getDropDownText ddlLicense
                savePackageSettings()
            )
        )

        on dncLicenseUrl TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.licenseUrl = dncLicenseUrl.Text
                savePackageSettings()
            )
        )

        on dncDocumentationUrl TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.documentationUrl = dncDocumentationUrl.Text
                savePackageSettings()
            )
        )

        on dncHomepageUrl TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.homepageUrl = dncHomepageUrl.Text
                savePackageSettings()
            )
        )

        on dncSupportUrl TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.supportUrl = dncSupportUrl.Text
                savePackageSettings()
            )
        )

        on btnGenerateGuid pressed do (
            if ((trimString dncGuid.Text) == "") then (
                dncGuid.Text = newGuidString()
            ) else (
                if (confirmGuidChange()) do dncGuid.Text = newGuidString()
            )

            packageState.packageGuid = dncGuid.Text
            savePackageSettings()
        )
    )

    rollout MaxPkgPackerNewSetupRollout "Setup" width: 380 category: 2
    (
        group "Interface" (
            checkbox chkCreateButton "Create 3ds Max Button" checked: true align: #left
            checkbox chkShowToolbar "Show In MaxPkg Toolbar" checked: true align: #left
        )

        group "Install And Uninstall" (
            label lblInstallHintA "Sample scripts are optional." align: #left
            label lblInstallHintB "You can replace them with custom code later." align: #left
            button btnCreateInstall "Create install.ms" width: 120 height: 23 align: #left across: 2
            button btnCreateUninstall "Create uninstall.ms" width: 120 height: 23 align: #right
        )

        on MaxPkgPackerNewSetupRollout open do (
            isLoadingSettings = true
            chkCreateButton.checked = packageState.createButton
            chkShowToolbar.checked = packageState.showToolbar
            isLoadingSettings = false
        )

        on chkCreateButton changed isChecked do (
            if (not isLoadingSettings) do (
                packageState.createButton = isChecked
                savePackageSettings()
            )
        )

        on chkShowToolbar changed isChecked do (
            if (not isLoadingSettings) do (
                packageState.showToolbar = isChecked
                savePackageSettings()
            )
        )

        on btnCreateInstall pressed do (
            if (createSamplePackageScript "install.ms" (buildSampleInstallScript())) do (
                refreshFilesView()
                savePackageSettings()
            )
        )

        on btnCreateUninstall pressed do (
            if (createSamplePackageScript "uninstall.ms" (buildSampleUninstallScript())) do (
                refreshFilesView()
                savePackageSettings()
            )
        )
    )

    rollout MaxPkgPackerNewFilesRollout "Files" width: 380 category: 2
    (
        group "Output Folder" (
            dotNetControl dncOutputFolder "System.Windows.Forms.TextBox" width: 313 height: 22 align: #left across: 2
            button btnBrowseOutput "..." width: 40 height: 23 align: #right offset: [0, -1]
		)

		group "SVG Icon" (
            dotNetControl dncSvgIcon "System.Windows.Forms.TextBox" height: 22 width: 313 align: #left across: 2
            button btnBrowseIcon "..." width: 40 height: 23 align: #right offset: [0, -1]

			button btnClearIcon "Clear" width: 82 height: 23 align: #left across: 2
            button btnPreviewIcon "Preview" width: 82 height: 23 align: #left offset: [-91, 0]
		)

		group "Files List" (
            listBox lbFiles "" height: 7 align: #left

            button btnAddFiles "[+] Add Files" width: 82 height: 23 align: #left across: 3
			button btnRemoveFile "[-] Remove" width: 82 height: 23 align: #left offset: [-31, 0]
            button btnAddFolder "Add Folder" width: 82 height: 23 align: #right
        )

        group "Entry File" (
            dotNetControl dncEntryFile "System.Windows.Forms.TextBox" readOnly: true height: 22 width: 232 align: #left across: 2
            button btnUseSelected "Use Selected" width: 120 height: 23 align: #right offset: [0, -1]

			checkbox chkCompileEntry "Compile entry file .ms to .mse" checked: true align: #left
		)

        on MaxPkgPackerNewFilesRollout open do (
            setupTextBoxControl dncOutputFolder
            setupTextBoxControl dncSvgIcon
            setupTextBoxControl dncEntryFile isReadOnly: true

            isLoadingSettings = true
            dncOutputFolder.Text = packageState.outputFolder
            dncSvgIcon.Text = packageState.svgIconFile
            dncEntryFile.Text = packageState.entryFile
            lbFiles.items = getPackageFileNames()
            syncCompileEntryState()
            chkCompileEntry.enabled = canCompileEntryFileFromState()
            chkCompileEntry.checked = packageState.compileEntry and canCompileEntryFileFromState()
            isLoadingSettings = false
            refreshValidationColors()
        )

        on dncOutputFolder TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.outputFolder = dncOutputFolder.Text
                savePackageSettings()
            )
        )

        on dncSvgIcon TextChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.svgIconFile = dncSvgIcon.Text
                savePackageSettings()
            )
        )

        on chkCompileEntry changed isChecked do (
            if (not isLoadingSettings) do (
                packageState.compileEntry = isChecked and canCompileEntryFileFromState()
                chkCompileEntry.checked = packageState.compileEntry
                savePackageSettings()
            )
        )

        on btnBrowseOutput pressed do (
            local folderPath = getSavePath caption: "Select output folder" initialDir: scriptDir
            if (folderPath != undefined) do (
                packageState.outputFolder = folderPath
                dncOutputFolder.Text = folderPath
                savePackageSettings()
            )
        )

        on btnBrowseIcon pressed do (
            local filePath = getOpenFileName caption: "Select safe SVG icon" filename: (scriptDir + "*.svg") types: "SVG (*.svg)|*.svg|All Files (*.*)|*.*|"

            if (filePath != undefined) do (
                if (isValidSafeSvg filePath) then (
                    local rootIconFilePath = copySvgIconToRoot filePath

                    if (rootIconFilePath != "") then (
                        packageState.svgIconFile = rootIconFilePath
                        dncSvgIcon.Text = rootIconFilePath
                        savePackageSettings()
                    ) else (
                        messageBox "Could not copy SVG icon to root folder." title: "MaxPkg Packer"
                    )
                ) else (
                    messageBox "Selected icon is not a valid safe SVG file." title: "MaxPkg Packer"
                )
            )
        )

        on btnClearIcon pressed do (
            packageState.svgIconFile = ""
            dncSvgIcon.Text = ""
            savePackageSettings()
        )

        on btnPreviewIcon pressed do (
            if (packageState.svgIconFile != "" and doesFileExist packageState.svgIconFile) do (
                shellLaunch packageState.svgIconFile ""
            )
        )

        on btnAddFiles pressed do (
            local selectedFiles = selectPackageFiles()

            if (selectedFiles.count > 0) do (
                for filePath in selectedFiles do (
                    addPackageFile filePath
                )
                refreshFilesView()
                savePackageSettings()
            )
        )

        on btnAddFolder pressed do (
            local folderPath = getSavePath caption: "Add package folder" initialDir: scriptDir

            if (folderPath != undefined) do (
                addFolderFiles folderPath
                refreshFilesView()
                savePackageSettings()
            )
        )

        on btnRemoveFile pressed do (
            if (lbFiles.selection > 0 and lbFiles.selection <= packageFiles.count) do (
                local selectedFileIndex = lbFiles.selection
                local selectedFileTitle = lbFiles.items[selectedFileIndex]
                local shouldRemoveFile = queryBox ("Remove this file from package list?\n\n" + selectedFileTitle) title: "MaxPkg Packer"

                if (shouldRemoveFile) do (
                    deleteItem packageFiles selectedFileIndex
                    syncEntryFileWithPackageList()
                    refreshFilesView()
                    savePackageSettings()
                )
            )
        )

        on btnUseSelected pressed do (
            if (lbFiles.selection > 0 and lbFiles.selection <= lbFiles.items.count) do (
                packageState.entryFile = lbFiles.items[lbFiles.selection]
                packageState.compileEntry = canCompileEntryFileFromState()
                syncCompileEntryState()
                dncEntryFile.Text = packageState.entryFile
                chkCompileEntry.enabled = canCompileEntryFileFromState()
                chkCompileEntry.checked = packageState.compileEntry
                savePackageSettings()
            )
        )
    )

    rollout MaxPkgPackerNewReleaseRollout "Release" width: 380 category: 2
    (
        group "Version" (
            dropdownList ddlVersionMajor "" width: 45 items: (versionNumberItems()) selection: 2 align: #left across: 6
            label lblVersionDotA "." align: #left offset: [-12, 5]
            dropdownList ddlVersionMinor "" width: 45 items: (versionNumberItems m: 9) selection: 1 align: #left offset: [-65, 0]
            label lblVersionDotB "." align: #left offset: [-77, 5]
            dropdownList ddlVersionPatch "" width: 45 items: (versionNumberItems m: 9) selection: 1 align: #left offset: [-130, 0]

			dropdownList ddlChannel "" width: 75 items: #("stable","alpha","beta") selection: 1 align: #left  offset: [-128, 0]
		)

		group "Misc." (
            label lblMinMax "Min 3ds Max" align: #left across: 2
			label lblReleaseDate "Release Date" align: #left
            dropdownList ddlMinMax "" width: 75 items: #("2012","2013","2014","2015","2016","2017","2018","2019","2020","2021","2022","2023","2024","2025","2026","2027") selection: 1 align: #left across: 2
            dotNetControl dncReleaseDate "System.Windows.Forms.DateTimePicker" height: 22 align: #left
        )

        group "Changelog" (
            listBox lbChangelog "" height: 6 align: #left
            dropdownList ddlChangeType "" width: 75 items: #("Added","Fixed","Changed","Removed","Improved") selection: 1 align: #left across: 2
            dotNetControl dncChangeContent "System.Windows.Forms.TextBox" width: 278 height: 22 align: #right
            button btnAddChange "[+] Add" width: 82 height: 23 align: #left across: 3 offset: [0, 10]
			button btnRemoveChange "[-] Remove" width: 82 height: 23 align: #left offset: [-31, 10]
            button btnEditChange "Edit/Save" width: 82 height: 23 align: #right offset: [0, 10]

        )

        on MaxPkgPackerNewReleaseRollout open do (
            isLoadingSettings = true
            setupDatePickerControl dncReleaseDate
            setupTextBoxControl dncChangeContent
            ddlMinMax.items = maxYearItems()
            setDropDownText ddlVersionMajor packageState.versionMajor
            setDropDownText ddlVersionMinor packageState.versionMinor
            setDropDownText ddlVersionPatch packageState.versionPatch
            setDropDownText ddlChannel packageState.releaseChannel
            if (not (setDropDownText ddlMinMax packageState.minMaxVersion)) do setDropDownText ddlMinMax "2012"
            dncReleaseDate.Value = parseSqlDate packageState.releaseDate
            packageState.releaseDate = dncReleaseDate.Value.ToString "yyyy-MM-dd"
            refreshChangelogView()
            isLoadingSettings = false
            refreshValidationColors()
        )

        on ddlVersionMajor selected selectedIndex do (
            if (not isLoadingSettings) do (
                packageState.versionMajor = getDropDownText ddlVersionMajor
                switchChangelogVersion()
            )
        )

        on ddlVersionMinor selected selectedIndex do (
            if (not isLoadingSettings) do (
                packageState.versionMinor = getDropDownText ddlVersionMinor
                switchChangelogVersion()
            )
        )

        on ddlVersionPatch selected selectedIndex do (
            if (not isLoadingSettings) do (
                packageState.versionPatch = getDropDownText ddlVersionPatch
                switchChangelogVersion()
            )
        )

        on ddlChannel selected selectedIndex do (
            if (not isLoadingSettings) do (
                packageState.releaseChannel = getDropDownText ddlChannel
                saveChangelogForVersion activeChangelogVersion
                savePackageSettings()
            )
        )

        on ddlMinMax selected selectedIndex do (
            if (not isLoadingSettings) do (
                packageState.minMaxVersion = getDropDownText ddlMinMax
                saveChangelogForVersion activeChangelogVersion
                savePackageSettings()
            )
        )

        on dncReleaseDate ValueChanged sender eventArgs do (
            if (not isLoadingSettings) do (
                packageState.releaseDate = dncReleaseDate.Value.ToString "yyyy-MM-dd"
                saveChangelogForVersion activeChangelogVersion
                savePackageSettings()
            )
        )

        on dncChangeContent TextChanged sender eventArgs do (
            refreshValidationColors()
        )

        on btnAddChange pressed do (
            local changeContent = trimString dncChangeContent.Text

            if (changeContent != "") do (
                append changelogItems #((getDropDownText ddlChangeType), changeContent)
                dncChangeContent.Text = ""
                refreshChangelogView()
                saveCurrentChangelog()
                savePackageSettings()
            )
        )

        on btnEditChange pressed do (
            if (lbChangelog.selection > 0 and lbChangelog.selection <= changelogItems.count) do (
                local changeContent = trimString dncChangeContent.Text

                if (changeContent != "") do (
                    changelogItems[lbChangelog.selection] = #((getDropDownText ddlChangeType), changeContent)
                    refreshChangelogView()
                    saveCurrentChangelog()
                    savePackageSettings()
                )
            )
        )

        on btnRemoveChange pressed do (
            if (lbChangelog.selection > 0 and lbChangelog.selection <= changelogItems.count) do (
                deleteItem changelogItems lbChangelog.selection
                refreshChangelogView()
                saveCurrentChangelog()
                savePackageSettings()
            )
        )

        on lbChangelog selected selectedIndex do (
            if (selectedIndex > 0 and selectedIndex <= changelogItems.count) do (
                local changelogItem = changelogItems[selectedIndex]
                setDropDownText ddlChangeType changelogItem[1]
                dncChangeContent.Text = changelogItem[2]
            )
        )
    )

    rollout MaxPkgPackerNewActionsRollout "Actions" width: 380 category: 3
    (
        checkbutton btnBuild "Build MZP" width: 380 height: 32 align: #center checked: true highlightColor: (color 52 168 83)

        on MaxPkgPackerNewActionsRollout open do (
            refreshValidationStatusButton()
        )

        on btnBuild changed isChecked do (
            if (not isSyncingBuildButtonStatus) do (
                btnBuild.checked = true
                local isPackageBuilt = buildPackage()
                showLogWindow()

                if (isPackageBuilt and packageState.outputFolder != "" and doesDirectoryExist packageState.outputFolder) do (
                    shellLaunch packageState.outputFolder ""
                )
            )
        )
    )

    rollout MaxPkgPackerNewLogRollout "Log" width: 700 height: 100
    (
        dotNetControl dncLogContent "System.Windows.Forms.TextBox" height: 300 align: #left

        button btnClearLogWindow "Clear Log" width: 80 height: 23 align: #left across: 2
        button btnCloseLogWindow "Close" width: 80 height: 23 align: #right

        on MaxPkgPackerNewLogRollout open do (
            isLogDialogOpen = true
            setupTextBoxControl dncLogContent isMultiline: true isReadOnly: true
            dncLogContent.Text = getLogText()
        )

        on MaxPkgPackerNewLogRollout close do (
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
                MaxPkgPackerNewLogRollout.dncLogContent.Text = getLogText()
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
                createDialog MaxPkgPackerNewLogRollout width: 600 height: 340
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
            try (destroyDialog MaxPkgPackerNewLogRollout) catch()
            isLogDialogOpen = false
        )

        return true
    )

    rollout MaxPkgPackerNewUpdateNoticeRollout "MaxPkg Packer Updated" width: 380 height: 330
    (
        group "Update Installed" (
            label lblUpdateNoticeTitle "MaxPkg Packer has been updated." align: #left
            dotNetControl dncUpdateNoticeContent "System.Windows.Forms.TextBox" height: 220 align: #left
        )

        button btnRestartUpdatedScript "Restart" width: 120 height: 23 align: #left across: 2
        button btnCloseUpdateNotice "Close" width: 80 height: 23 align: #right

        on MaxPkgPackerNewUpdateNoticeRollout open do (
            setupTextBoxControl dncUpdateNoticeContent isMultiline: true isReadOnly: true
            dncUpdateNoticeContent.Text = pendingUpdateNoticeContent
        )

        on btnRestartUpdatedScript pressed do (
            try (destroyDialog MaxPkgPackerNewUpdateNoticeRollout) catch()
            try (fileIn pendingUpdateScriptFile) catch (
                messageBox "Update installed, but the script could not restart automatically." title: "MaxPkg Packer"
            )
        )

        on btnCloseUpdateNotice pressed do (
            destroyDialog MaxPkgPackerNewUpdateNoticeRollout
        )
    )

    fn buildUpdateNoticeContent updateResult = (
        local noticeContent = "Update installed successfully.\r\n\r\n"
        noticeContent += "Previous version: " + updateResult.currentVersionString + "\r\n"
        noticeContent += "Installed version: " + updateResult.newVersionString + "\r\n\r\n"
        noticeContent += "Changelog:\r\n"
        noticeContent += updateResult.releaseNotesContent
        noticeContent += "\r\n\r\nClick Restart to load the updated script."
        return noticeContent
    )

    fn showUpdateNoticeDialog updateResult = (
        if (updateResult == undefined) do return false
        if (not updateResult.isUpdated) do return false

        pendingUpdateScriptFile = updateResult.scriptFilePath
        pendingUpdateNoticeContent = buildUpdateNoticeContent updateResult

        try (destroyDialog MaxPkgPackerNewUpdateNoticeRollout) catch()
        try (
            createDialog MaxPkgPackerNewUpdateNoticeRollout width: 400 height: 355
        ) catch (
            messageBox pendingUpdateNoticeContent title: "MaxPkg Packer Updated"
            return false
        )

        return true
    )

    fn startupUpdateDoWork sender eventArgs = (
        startupUpdateResult = checkAndDownloadScriptUpdate showMessages: false reloadAfterUpdate: false
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

    rollout MaxPkgPackerNewAboutRollout "About" width: 380 category: 4
    (
        local isUpdateCheckRunning = false
        local aboutUpdateWorker = undefined
        local aboutUpdateResult = undefined

        group "Script Info" (
            label lblAboutTitle "" align: #left
            label lblAboutVersion "" align: #left
            label lblAboutAuthor "" align: #left
            dotNetControl dncAboutDescription "System.Windows.Forms.TextBox" height: 70 align: #left
        )

        group "Links" (
            label lblSiteCaption "Website:" align: #left across: 2
            hyperlink hplAboutSite "" align: #left color: orange hoverColor: orange visitedColor: orange offset: [-120, 0]
            label lblDeveloperCaption "Developer:" align: #left across: 2
            hyperlink hplAboutDeveloper "" align: #left color: orange hoverColor: orange visitedColor: orange offset: [-120, 0]
            label lblHelpCaption "Help:" align: #left across: 2
            hyperlink hplAboutHelp "" align: #left color: orange hoverColor: orange visitedColor: orange offset: [-120, 0]
        )

        group "Update" (
            label lblAboutUpdateStatus "Update: not checked" align: #left
            button btnCheckAboutUpdate "Check Updates" width: 120 height: 23 align: #left
        )

        group "Paths" (
            label lblAboutRoot "" align: #left
            label lblAboutIni "" align: #left
        )

        fn updateLinkControl linkControl linkUrl emptyCaption: "Not configured" = (
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
            lblAboutRoot.caption = "Root: " + scriptDir
            lblAboutIni.caption = "INI: " + iniFilePath

            setupTextBoxControl dncAboutDescription isMultiline: true isReadOnly: true
            dncAboutDescription.Text = scriptInfo.descriptionContent

            updateLinkControl hplAboutSite scriptInfo.siteUrl emptyCaption: "Not configured"
            updateLinkControl hplAboutDeveloper scriptInfo.developerUrl emptyCaption: "Not configured"
            updateLinkControl hplAboutHelp scriptInfo.helpUrl emptyCaption: "Not configured"

            try (MaxPkgPackerNewFloater.title = scriptInfo.scriptTitle + " v" + scriptInfo.versionString) catch()
            return true
        )

        fn aboutUpdateDoWork sender eventArgs = (
            aboutUpdateResult = checkAndDownloadScriptUpdate showMessages: false reloadAfterUpdate: false
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

        on MaxPkgPackerNewAboutRollout open do (
            refreshAboutInfo()
        )

        on btnCheckAboutUpdate pressed do (
            runBackgroundUpdateCheck()
        )
    )

    fn addContentRollout tabId = (
        activeContentRollout = contentRolloutForTabId tabId
        addRollout activeContentRollout MaxPkgPackerNewFloater rolledUp: false border: false
        return true
    )

    fn removeContentRollout = (
        if (activeContentRollout != undefined) do (
            try (removeRollout activeContentRollout MaxPkgPackerNewFloater) catch()
            activeContentRollout = undefined
        )

        return true
    )

    fn switchTab requestedTabId shouldSave: true = (
        local tabId = normalizeTabId requestedTabId

        if (MaxPkgPackerNewFloater == undefined) do return false

        isSwitchingTab = true
        removeContentRollout()
        currentTabId = tabId
        addContentRollout currentTabId
        if (shouldSave) do iniSet "lastTab" currentTabId
        try (MaxPkgPackerNewTabsRollout.selectTabById currentTabId) catch()
        isSwitchingTab = false

        return true
    )

    try (destroyDialog MaxPkgPackerNewLogRollout) catch()
    try (destroyDialog MaxPkgPackerNewUpdateNoticeRollout) catch()
    isLogDialogOpen = false
    try (closeRolloutFloater MaxPkgPackerNewFloater) catch()

    loadPackageSettings()
    currentTabId = selectedTabId()
    MaxPkgPackerNewFloater = newRolloutFloater "MaxPkg Packer New UI" 400 680

    addRollout MaxPkgPackerNewTabsRollout MaxPkgPackerNewFloater rolledUp: false border: false
    addContentRollout currentTabId
    addRollout MaxPkgPackerNewActionsRollout MaxPkgPackerNewFloater rolledUp: false border: false
    addRollout MaxPkgPackerNewAboutRollout MaxPkgPackerNewFloater rolledUp: true
    scheduleValidationStatusUpdate()
    startStartupUpdateCheck()
)
