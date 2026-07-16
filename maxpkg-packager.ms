(
    /*
        MaxPkg Packager for Autodesk 3ds Max
        ------------------------------------------------------------

        Drag this script into a 3ds Max viewport from a developer product
        folder. It builds a universal MaxPkg-compatible .mzp package.

        The package does not install MaxPkg Toolbar or MaxPkg Runtime.
    */


    local PACKAGER_VERSION = "1.0.0"
    local PACKAGER_NAME = "maxpkg-packager"

    local scriptPath = getThisScriptFilename()
    if (scriptPath == undefined) do scriptPath = (getDir #scripts) + "\\maxpkg-packager.ms"

    local rootDir = getFilenamePath scriptPath
    local iniPath = rootDir + "maxpkg-packager.ini"

    local packageFiles = #()
    local changelogItems = #()
    local logItems = #()
    local isLoadingSettings = false
    global MaxPkgPackagerFloater
    global MaxPkgPackagerLogRollout
    local isLogDialogOpen = false

    local showLogWindow
    local refreshLogWindow
    local closeLogWindow

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
        try (showLogWindow()) catch()
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

    fn macroNameFromGuid guid = (
        return "MaxPkg_" + (substituteString guid "-" "")
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

        iniSetRaw "count" changelogItems.count iniSection:"changelog"

        for i in 1 to changelogItems.count do (
            iniSet ((i as string) + "_type") changelogItems[i][1] iniSection:"changelog"
            iniSet ((i as string) + "_text") changelogItems[i][2] iniSection:"changelog"
        )

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

            if (abs != "" and rel != "") do (
                append packageFiles #((normalizePath abs), (normalizePath rel))
            )
        )

        changelogItems = #()

        local changelogCount = iniGetInt "count" iniSection:"changelog" defaultValue:0

        for i in 1 to changelogCount do (
            local itemType = iniGet ((i as string) + "_type") iniSection:"changelog"
            local itemText = iniGet ((i as string) + "_text") iniSection:"changelog"

            if (itemType != "" and itemText != "") do (
                append changelogItems #(itemType, itemText)
            )
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
        if (description.count > 500) do (addLog "ERROR" "Description must be 500 characters or less"; isValid = false)
        if (guid == "" or not (isValidGuid guid)) do (addLog "ERROR" "Package GUID must be a valid UUID"; isValid = false)
        if (versionText == "") do (addLog "ERROR" "Version is required"; isValid = false)
        if ((selectedReleaseChannel ui) == "") do (addLog "ERROR" "Release channel is required"; isValid = false)
        if (releaseDate == "") do (addLog "ERROR" "Release date is required"; isValid = false)
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
        format "%" (iniLine "packager" PACKAGER_NAME) to:ss
        format "%" (iniLine "packagerVersion" PACKAGER_VERSION) to:ss
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
        format "  \"packager\": \"%\",\n" PACKAGER_NAME to:ss
        format "  \"packagerVersion\": \"%\",\n" PACKAGER_VERSION to:ss
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

    fn buildMacroScript ui = (
        local ss = stringStream ""
        local guid = trimString ui.edtGuid.text
        local buttonText = substituteString (trimString ui.edtButtonName.text) "\"" "\\\""

        format "macroScript %\n" (macroNameFromGuid guid) to:ss
        format "category:\"MaxPkg\"\n" to:ss
        format "buttonText:\"%\"\n" buttonText to:ss
        format "tooltip:\"Run %\"\n" buttonText to:ss
        format "(\n" to:ss
        format "    on execute do\n" to:ss
        format "    (\n" to:ss
        format "        try\n" to:ss
        format "        (\n" to:ss
        format "            local packageDir = (getDir #temp) + \"\\\\maxpkg\\\\packages\\\\%\\\\\"\n" guid to:ss
        format "            local manifestIni = packageDir + \"manifest.ini\"\n" to:ss
        format "            local runtime = getINISetting manifestIni \"package\" \"runtime\"\n" to:ss
        format "            local entry = getINISetting manifestIni \"package\" \"entry\"\n" to:ss
        format "            local entryPath = packageDir + entry\n" to:ss
        format "\n" to:ss
        format "            if (runtime == \"python\") then\n" to:ss
        format "            (\n" to:ss
        format "                python.ExecuteFile entryPath\n" to:ss
        format "            )\n" to:ss
        format "            else\n" to:ss
        format "            (\n" to:ss
        format "                fileIn entryPath\n" to:ss
        format "            )\n" to:ss
        format "        )\n" to:ss
        format "        catch\n" to:ss
        format "        (\n" to:ss
        format "            messageBox (\"Could not run MaxPkg package.\\\\n\\\\n\" + getCurrentException()) title:\"MaxPkg\"\n" to:ss
        format "        )\n" to:ss
        format "    )\n" to:ss
        format ")\n" to:ss

        return ss as string
    )

    fn buildMzpRunScript = (
        local ss = stringStream ""

        format "(\n" to:ss
        format "    fn mpEnsureSlash p = (\n" to:ss
        format "        if ((substring p p.count 1) == \"\\\\\") then return p\n" to:ss
        format "        return p + \"\\\\\"\n" to:ss
        format "    )\n\n" to:ss
        format "    fn mpDirExists p = (\n" to:ss
        format "        try (return (dotNetClass \"System.IO.Directory\").Exists p) catch (return doesFileExist p)\n" to:ss
        format "    )\n\n" to:ss
        format "    fn mpEnsureDir p = (\n" to:ss
        format "        if (mpDirExists p) then return true\n" to:ss
        format "        return makeDir p all:true\n" to:ss
        format "    )\n\n" to:ss
        format "    fn mpDeleteDir p = (\n" to:ss
        format "        if (mpDirExists p) do (\n" to:ss
        format "            try ((dotNetClass \"System.IO.Directory\").Delete p true) catch()\n" to:ss
        format "        )\n" to:ss
        format "        return true\n" to:ss
        format "    )\n\n" to:ss
        format "    fn mpMoveDir source target = (\n" to:ss
        format "        try ((dotNetClass \"System.IO.Directory\").Move source target) catch (renameFile source target)\n" to:ss
        format "        return true\n" to:ss
        format "    )\n\n" to:ss
        format "    fn mpCopyDir source target = (\n" to:ss
        format "        local src = mpEnsureSlash source\n" to:ss
        format "        local dst = mpEnsureSlash target\n" to:ss
        format "        local files = (dotNetClass \"System.IO.Directory\").GetFiles src \"*\" (dotNetClass \"System.IO.SearchOption\").AllDirectories\n\n" to:ss
        format "        mpEnsureDir dst\n\n" to:ss
        format "        for filePath in files do (\n" to:ss
        format "            local sourcePath = filePath as string\n" to:ss
        format "            local rel = substring sourcePath (src.count + 1) (sourcePath.count - src.count)\n" to:ss
        format "            local targetPath = dst + rel\n\n" to:ss
        format "            mpEnsureDir (getFilenamePath targetPath)\n" to:ss
        format "            copyFile sourcePath targetPath\n" to:ss
        format "        )\n\n" to:ss
        format "        return true\n" to:ss
        format "    )\n\n" to:ss
        format "    try (\n" to:ss
        format "        local sourceDir = mpEnsureSlash (getFilenamePath (getSourceFileName()))\n" to:ss
        format "        local manifestIni = sourceDir + \"manifest.ini\"\n" to:ss
        format "        local packageGuid = getINISetting manifestIni \"package\" \"packageGuid\"\n" to:ss
        format "        local createMacroButton = toLower (getINISetting manifestIni \"package\" \"createMacroButton\")\n" to:ss
        format "        local installScript = getINISetting manifestIni \"package\" \"installScript\"\n\n" to:ss
        format "        if (packageGuid == undefined or packageGuid == \"\") do throw \"manifest.ini is missing packageGuid.\"\n\n" to:ss
        format "        local packageRoot = mpEnsureSlash ((getDir #temp) + \"\\\\maxpkg\\\\packages\\\\\" + packageGuid)\n" to:ss
        format "        local backupRoot = packageRoot + \".backup\"\n\n" to:ss
        format "        if (mpDirExists backupRoot) do mpDeleteDir backupRoot\n" to:ss
        format "        if (mpDirExists packageRoot) do mpMoveDir packageRoot backupRoot\n\n" to:ss
        format "        try (\n" to:ss
        format "            mpCopyDir sourceDir packageRoot\n\n" to:ss
        format "            if (doesFileExist (packageRoot + \"mzp.run\")) do deleteFile (packageRoot + \"mzp.run\")\n\n" to:ss
        format "            if (createMacroButton == \"true\") do (\n" to:ss
        format "                local mcrSource = packageRoot + \"maxpkg-button.mcr\"\n\n" to:ss
        format "                if (doesFileExist mcrSource) do (\n" to:ss
        format "                    local mcrTarget = (mpEnsureSlash (getDir #userMacros)) + \"maxpkg-\" + packageGuid + \".mcr\"\n" to:ss
        format "                    copyFile mcrSource mcrTarget\n" to:ss
        format "                    fileIn mcrTarget\n" to:ss
        format "                )\n" to:ss
        format "            )\n\n" to:ss
        format "            if (installScript != undefined and installScript != \"\") do (\n" to:ss
        format "                local installPath = packageRoot + installScript\n" to:ss
        format "                if (doesFileExist installPath) do fileIn installPath\n" to:ss
        format "            )\n\n" to:ss
        format "            if (mpDirExists backupRoot) do mpDeleteDir backupRoot\n\n" to:ss
        format "            try (if (MaxPkg != undefined) do MaxPkg.rebuildToolbar()) catch()\n" to:ss
        format "            try (if (MaxPkgToolbar != undefined) do MaxPkgToolbar.refresh()) catch()\n\n" to:ss
        format "            messageBox (\"MaxPkg package installed.\\\\n\\\\n\" + packageGuid) title:\"MaxPkg\"\n" to:ss
        format "        ) catch (\n" to:ss
        format "            if (mpDirExists packageRoot) do mpDeleteDir packageRoot\n" to:ss
        format "            if (mpDirExists backupRoot) do mpMoveDir backupRoot packageRoot\n" to:ss
        format "            throw getCurrentException()\n" to:ss
        format "        )\n" to:ss
        format "    ) catch (\n" to:ss
        format "        messageBox (\"MaxPkg package install failed.\\\\n\\\\n\" + getCurrentException()) title:\"MaxPkg\"\n" to:ss
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

    fn buildPackage ui = (
        saveSettings ui

        if (not (validateSettings ui)) do return false

        local guid = trimString ui.edtGuid.text
        local outputFolder = ensureTrailingSlash ui.edtOutput.text
        local buildRoot = ensureTrailingSlash ((getDir #temp) + "\\maxpkg-packager-build-" + guid)
        local outputFile = outputFolder + guid + ".mzp"

        deleteDirectory buildRoot
        ensureDirectory buildRoot

        writeTextFile (buildRoot + "manifest.ini") (buildManifestIni ui)
        addLog "OK" "manifest.ini generated"

        writeTextFile (buildRoot + "manifest.json") (buildManifestJson ui)
        addLog "OK" "manifest.json generated"

        writeTextFile (buildRoot + "mzp.run") (buildMzpRunScript())
        addLog "OK" "mzp.run generated"

        if (ui.chkCreateMacro.checked) do (
            writeTextFile (buildRoot + "maxpkg-button.mcr") (buildMacroScript ui)
            addLog "OK" "maxpkg-button.mcr generated"
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

        if (createMzpFromFolder buildRoot outputFile) then (
            addLog "OK" ("MZP created: " + outputFile)
            return true
        )

        return false
    )


    try (destroyDialog MaxPkgPackagerLogRollout) catch()
    isLogDialogOpen = false

    try (closeRolloutFloater MaxPkgPackagerFloater) catch()

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
			dropdownList ddlLicense "" width: 100 items:#("Free","Shareware","Commercial","Open Source","MIT","GPL","Custom") selection:1  align: #left offset: [-52, 0]

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
			
			button btnAddFile "Add Files" width: 80 align: #left across: 5
			button btnAddFolder "Add Folder" width:80 align: #left offset: [-55, 0]
			button btnScanRoot "Scan Folder" width:80 align: #left offset: [-110, 0]
			button btnRemoveFile "Remove" width:80 align: #right offset: [55, 0]
			button btnClearFiles "Clear" width:80 align: #right 				
		)
		
		group "Runtime" (
			label lblRuntime "Launch" align: #left across: 5 offset: [0, 4]
			dropdownList ddlRuntime "" width:120 items:#("maxscript", "python") selection:1 align: #left offset: [-37, 0]
			label lblEntry "Entry File" align: #left offset: [34, 4]
			editText edtEntry ""width: 250 align: #right offset: [53, 0]
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
        on ddlVersionMajor selected selectedIndex do autoSaveSettings()
        on ddlVersionMinor selected selectedIndex do autoSaveSettings()
        on ddlVersionPatch selected selectedIndex do autoSaveSettings()
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
                if (queryBox "Package GUID already exists. Generate a new technical identity?" title:"MaxPkg Packager") do (
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
                    edtIcon.text = filePath
                    addLog "OK" "SVG icon validated"
                    autoSaveSettings()
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
            local filePath = getOpenFileName caption:"Add package file" types:"Package Files (*.*)|*.*|"

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

        on btnRemoveFile pressed do (
            if (lbFiles.selection > 0 and lbFiles.selection <= packageFiles.count) do (
                deleteItem packageFiles lbFiles.selection
            )

            refreshFiles()
            autoSaveSettings()
        )

        on btnClearFiles pressed do (
            if (queryBox "Clear package files list?" title:"MaxPkg Packager") do (
                packageFiles = #()
                refreshFiles()
                autoSaveSettings()
            )
        )

        on btnAddChange pressed do (
            local changeValue = trimString edtChangeText.text

            if (changeValue != "") do (
                append changelogItems #((getDropDownText ddlChangeType), changeValue)
                edtChangeText.text = ""
                refreshChangelog()
                autoSaveSettings()
            )
        )

        on btnEditChange pressed do (
            if (lbChangelog.selection > 0) do (
                changelogItems[lbChangelog.selection] = #((getDropDownText ddlChangeType), (trimString edtChangeText.text))
                refreshChangelog()
                autoSaveSettings()
            )
        )

        on btnRemoveChange pressed do (
            if (lbChangelog.selection > 0) do (
                deleteItem changelogItems lbChangelog.selection
                refreshChangelog()
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
            refreshLog()
        )        

        on btnBuild pressed do (
            buildPackage MaxPkgPackagerRollout
            refreshLog()
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

    rollout MaxPkgPackagerAboutRollout "About" width:740
    (
        label lblAboutTitle "MaxPkg Packager for Autodesk 3ds Max" align:#left
        label lblAboutVersion "" align:#left
        label lblAboutWebsite "MaxPkg: https://maxpkg.dev" align:#left
        label lblAboutDeveloper "Developer: Vasyl Lukianenko (https://3dground.net)" align:#left
        label lblAboutPurpose "Builds a universal MaxPkg-compatible .mzp package from the current product folder." align:#left
        label lblAboutRoot "" align:#left
        label lblAboutIni "" align:#left

        on MaxPkgPackagerAboutRollout open do (
            lblAboutVersion.text = "Version: " + PACKAGER_VERSION
            lblAboutRoot.text = "Root: " + rootDir
            lblAboutIni.text = "INI: " + iniPath
        )
    )

    MaxPkgPackagerFloater = newRolloutFloater "MaxPkg Packager" 760 900
    addRollout MaxPkgPackagerRollout MaxPkgPackagerFloater rolledUp:false
    addRollout MaxPkgPackagerAboutRollout MaxPkgPackagerFloater rolledUp:true
)
