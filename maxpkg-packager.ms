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
        local value = lowerString (trimString s)

        if (value == "") do return defaultValue
        return (value == "true" or value == "1" or value == "yes")
    )

    fn getDropDownText ddl = (
        if (ddl.selection < 1) do return ""
        return ddl.items[ddl.selection]
    )

    fn setDropDownText ddl value = (
        local index = findItem ddl.items value
        if (index > 0) do ddl.selection = index
        return true
    )

    fn addLog level text = (
        append logItems ("[" + level + "] " + text)
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

    fn isValidGuid s = (
        local value = trimString s
        local dashPositions = #(9, 14, 19, 24)
        local hexChars = "0123456789abcdefABCDEF"

        if (value.count != 36) do return false

        for i in 1 to value.count do (
            local ch = substring value i 1
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
        local path = lowerString (normalizePath absPath)
        local name = lowerString (filenameFromPath absPath)

        if ((findString path "\\.git\\") != undefined) do return true
        if ((findString path "\\.vscode\\") != undefined) do return true
        if (matchPattern name pattern:"*.bak" ignoreCase:true) do return true
        if (matchPattern name pattern:"*.tmp" ignoreCase:true) do return true
        if (matchPattern name pattern:"*.log" ignoreCase:true) do return true
        if (matchPattern name pattern:"*.zip" ignoreCase:true) do return true
        if (matchPattern name pattern:"*.mzp" ignoreCase:true) do return true
        if (name == "maxpkg-packager.ms") do return true
        if (name == "maxpkg-packager.ini") do return true

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

    fn readTextFile path = (
        local stream = openFile path mode:"rt"
        local text = ""

        if (stream == undefined) do return undefined

        while (not eof stream) do (
            text += readLine stream
            if (not eof stream) do text += "\n"
        )

        close stream
        return text
    )

    fn writeTextFile path text = (
        local stream = createFile path

        if (stream == undefined) do return false

        format "%" text to:stream
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

    fn isValidSafeSvg path = (
        if (path == undefined or path == "") do return false
        if (not (doesFileExist path)) do return false
        if ((lowerString (getFilenameType path)) != ".svg") do return false

        local text = readTextFile path
        if (text == undefined or text.count == 0) do return false

        for i in 1 to text.count do (
            local code = bit.charAsInt (substring text i 1)
            if (code == 0) do return false
        )

        local value = lowerString text

        if ((findString value "<svg") == undefined) do return false
        if ((findString value "<script") != undefined) do return false
        if ((findString value "javascript:") != undefined) do return false
        if ((findString value "onload=") != undefined) do return false
        if ((findString value "onclick=") != undefined) do return false
        if ((findString value "onerror=") != undefined) do return false
        if ((findString value "<foreignobject") != undefined) do return false

        return true
    )

    fn detectRootHook hookName = (
        local hook = lowerString hookName

        for item in packageFiles do (
            if ((lowerString item[2]) == hook) do return hookName
        )

        return ""
    )

    fn iniLine key value = (
        return key + "=" + (escapeIniValue value) + "\n"
    )

    fn iniSet key value section:"settings" = (
        setINISetting iniPath section key (escapeIniValue value)
        return true
    )

    fn iniGet key section:"settings" = (
        return unescapeIniValue (getINISetting iniPath section key)
    )

    fn iniGetBool key section:"settings" defaultValue:true = (
        return stringToBool (getINISetting iniPath section key) defaultValue:defaultValue
    )

    fn iniGetInt key section:"settings" defaultValue:0 = (
        local value = getINISetting iniPath section key

        if (value == "") do return defaultValue

        return value as integer
    )

    fn iniSetRaw key value section:"settings" = (
        setINISetting iniPath section key (value as string)
        return true
    )

    fn saveSettings ui = (
        iniSet "packageName" ui.edtName.text
        iniSet "buttonName" ui.edtButtonName.text
        iniSet "developerName" ui.edtDeveloperName.text
        iniSet "developerSlug" ui.edtDeveloperSlug.text
        iniSet "packageGuid" ui.edtGuid.text
        iniSet "description" ui.edtDescription.text
        iniSet "license" (getDropDownText ui.ddlLicense)
        iniSet "licenseUrl" ui.edtLicenseUrl.text
        iniSet "version" ui.edtVersion.text
        iniSet "releaseDate" ui.edtReleaseDate.text
        iniSet "min3dsMax" ui.edtMinMax.text
        iniSet "max3dsMax" ui.edtMaxMax.text
        iniSet "runtime" (getDropDownText ui.ddlRuntime)
        iniSet "entry" ui.edtEntry.text
        iniSet "svgIcon" ui.edtIcon.text
        iniSet "homepage" ui.edtHomepage.text
        iniSet "documentation" ui.edtDocumentation.text
        iniSet "support" ui.edtSupport.text
        iniSet "createMacroButton" (boolToString ui.chkCreateMacro.checked)
        iniSet "showInToolbar" (boolToString ui.chkShowToolbar.checked)
        iniSet "outputFolder" ui.edtOutput.text

        iniSetRaw "count" packageFiles.count section:"files"

        for i in 1 to packageFiles.count do (
            iniSet ((i as string) + "_abs") packageFiles[i][1] section:"files"
            iniSet ((i as string) + "_rel") packageFiles[i][2] section:"files"
        )

        iniSetRaw "count" changelogItems.count section:"changelog"

        for i in 1 to changelogItems.count do (
            iniSet ((i as string) + "_type") changelogItems[i][1] section:"changelog"
            iniSet ((i as string) + "_text") changelogItems[i][2] section:"changelog"
        )

        addLog "OK" "INI saved"

        return true
    )

    fn loadSettings ui = (
        if (not (doesFileExist iniPath)) do return false

        ui.edtName.text = iniGet "packageName"
        ui.edtButtonName.text = iniGet "buttonName"
        ui.edtDeveloperName.text = iniGet "developerName"
        ui.edtDeveloperSlug.text = iniGet "developerSlug"
        ui.edtGuid.text = iniGet "packageGuid"
        ui.edtDescription.text = iniGet "description"
        setDropDownText ui.ddlLicense (iniGet "license")
        ui.edtLicenseUrl.text = iniGet "licenseUrl"
        ui.edtVersion.text = iniGet "version"
        ui.edtReleaseDate.text = iniGet "releaseDate"
        ui.edtMinMax.text = iniGet "min3dsMax"
        ui.edtMaxMax.text = iniGet "max3dsMax"
        setDropDownText ui.ddlRuntime (iniGet "runtime")
        ui.edtEntry.text = iniGet "entry"
        ui.edtIcon.text = iniGet "svgIcon"
        ui.edtHomepage.text = iniGet "homepage"
        ui.edtDocumentation.text = iniGet "documentation"
        ui.edtSupport.text = iniGet "support"
        ui.chkCreateMacro.checked = iniGetBool "createMacroButton" defaultValue:true
        ui.chkShowToolbar.checked = iniGetBool "showInToolbar" defaultValue:true
        ui.edtOutput.text = iniGet "outputFolder"

        packageFiles = #()

        local fileCount = iniGetInt "count" section:"files" defaultValue:0

        for i in 1 to fileCount do (
            local abs = iniGet ((i as string) + "_abs") section:"files"
            local rel = iniGet ((i as string) + "_rel") section:"files"

            if (abs != "" and rel != "") do (
                append packageFiles #((normalizePath abs), (normalizePath rel))
            )
        )

        changelogItems = #()

        local changelogCount = iniGetInt "count" section:"changelog" defaultValue:0

        for i in 1 to changelogCount do (
            local itemType = iniGet ((i as string) + "_type") section:"changelog"
            local itemText = iniGet ((i as string) + "_text") section:"changelog"

            if (itemType != "" and itemText != "") do (
                append changelogItems #(itemType, itemText)
            )
        )

        addLog "OK" "INI loaded"
        return true
    )

    fn validateSettings ui = (
        local ok = true
        local packageName = trimString ui.edtName.text
        local buttonName = trimString ui.edtButtonName.text
        local description = trimString ui.edtDescription.text
        local guid = trimString ui.edtGuid.text
        local versionText = trimString ui.edtVersion.text
        local releaseDate = trimString ui.edtReleaseDate.text
        local runtime = getDropDownText ui.ddlRuntime
        local entry = normalizePath (trimString ui.edtEntry.text)
        local icon = normalizePath (trimString ui.edtIcon.text)
        local minMax = ui.edtMinMax.text as integer
        local maxMax = ui.edtMaxMax.text as integer
        local outputFolder = ensureTrailingSlash ui.edtOutput.text

        clearLog()

        if (packageName == "") do (addLog "ERROR" "Package name is required"; ok = false)
        if (buttonName == "") do (addLog "ERROR" "Button name is required"; ok = false)
        if (description == "") do (addLog "ERROR" "Description is required"; ok = false)
        if (description.count > 500) do (addLog "ERROR" "Description must be 500 characters or less"; ok = false)
        if (guid == "" or not (isValidGuid guid)) do (addLog "ERROR" "Package GUID must be a valid UUID"; ok = false)
        if (versionText == "") do (addLog "ERROR" "Version is required"; ok = false)
        if (releaseDate == "") do (addLog "ERROR" "Release date is required"; ok = false)
        if ((getDropDownText ui.ddlLicense) == "") do (addLog "ERROR" "License is required"; ok = false)
        if (minMax == undefined or maxMax == undefined) do (addLog "ERROR" "Min and max 3ds Max versions must be numbers"; ok = false)
        if (minMax != undefined and maxMax != undefined and minMax > maxMax) do (addLog "ERROR" "Min 3ds Max version must be <= max version"; ok = false)
        if (runtime != "maxscript" and runtime != "python") do (addLog "ERROR" "Runtime must be maxscript or python"; ok = false)

        if (entry == "") then (
            addLog "ERROR" "Entry file is required"
            ok = false
        ) else (
            local entryItem = findPackageFileByRel entry

            if (entryItem == undefined) then (
                addLog "ERROR" "Entry file must be included in package files"
                ok = false
            ) else (
                local ext = lowerString (getFilenameType entry)

                if (not (doesFileExist entryItem[1])) do (addLog "ERROR" "Entry file does not exist"; ok = false)
                if (runtime == "maxscript" and ext != ".ms" and ext != ".mse") do (addLog "ERROR" "MaxScript runtime requires .ms or .mse entry file"; ok = false)
                if (runtime == "python" and ext != ".py") do (addLog "ERROR" "Python runtime requires .py entry file"; ok = false)
            )
        )

        if (icon != "") do (
            if (isValidSafeSvg icon) then (
                addLog "OK" "SVG icon validated"
            ) else (
                addLog "ERROR" "Selected icon is not a valid safe SVG file."
                ok = false
            )
        )

        if (packageFiles.count == 0) do (addLog "ERROR" "At least one package file is required"; ok = false)

        for item in packageFiles do (
            if (not (isSafeRelativePath item[2])) do (addLog "ERROR" ("Invalid relative path: " + item[2]); ok = false)
            if (not (doesFileExist item[1])) do (addLog "ERROR" ("Missing file: " + item[2]); ok = false)

            local rel = lowerString item[2]
            if (endsWith rel "\\install.ms") do (addLog "ERROR" "install.ms is only allowed in package root"; ok = false)
            if (endsWith rel "\\uninstall.ms") do (addLog "ERROR" "uninstall.ms is only allowed in package root"; ok = false)
        )

        if ((detectRootHook "install.ms") != "") do addLog "OK" "install.ms detected"
        if ((detectRootHook "uninstall.ms") != "") do addLog "OK" "uninstall.ms detected"

        if (outputFolder == "" or outputFolder == "\\") then (
            addLog "ERROR" "Output folder is required"
            ok = false
        ) else if (not (ensureDirectory outputFolder)) then (
            addLog "ERROR" "Output folder does not exist and cannot be created"
            ok = false
        )

        if (ok) then addLog "OK" "Validation passed" else addLog "ERROR" "Validation failed"

        return ok
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
        format "%" (iniLine "version" ui.edtVersion.text) to:ss
        format "%" (iniLine "releaseDate" ui.edtReleaseDate.text) to:ss
        format "%" (iniLine "runtime" (getDropDownText ui.ddlRuntime)) to:ss
        format "%" (iniLine "entry" (normalizePath ui.edtEntry.text)) to:ss
        format "%" (iniLine "icon" iconPath) to:ss
        format "%" (iniLine "license" (getDropDownText ui.ddlLicense)) to:ss
        format "%" (iniLine "licenseUrl" ui.edtLicenseUrl.text) to:ss
        format "%" (iniLine "developerName" ui.edtDeveloperName.text) to:ss
        format "%" (iniLine "developerSlug" ui.edtDeveloperSlug.text) to:ss
        format "%" (iniLine "min3dsMax" ui.edtMinMax.text) to:ss
        format "%" (iniLine "max3dsMax" ui.edtMaxMax.text) to:ss
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
        local minMax = ui.edtMinMax.text as integer
        local maxMax = ui.edtMaxMax.text as integer

        if ((trimString ui.edtIcon.text) != "") do iconPath = "icons/icon.svg"

        format "{\n" to:ss
        format "  \"manifestVersion\": 1,\n" to:ss
        format "  \"packageGuid\": \"%\",\n" (escapeJson (trimString ui.edtGuid.text)) to:ss
        format "  \"name\": \"%\",\n" (escapeJson (trimString ui.edtName.text)) to:ss
        format "  \"buttonName\": \"%\",\n" (escapeJson (trimString ui.edtButtonName.text)) to:ss
        format "  \"description\": \"%\",\n" (escapeJson (trimString ui.edtDescription.text)) to:ss
        format "  \"version\": \"%\",\n" (escapeJson (trimString ui.edtVersion.text)) to:ss
        format "  \"releaseDate\": \"%\",\n" (escapeJson (trimString ui.edtReleaseDate.text)) to:ss
        format "  \"runtime\": \"%\",\n" (escapeJson (getDropDownText ui.ddlRuntime)) to:ss
        format "  \"entry\": \"%\",\n" (escapeJson (normalizePath (trimString ui.edtEntry.text))) to:ss
        format "  \"icon\": \"%\",\n" (escapeJson iconPath) to:ss
        format "  \"license\": \"%\",\n" (escapeJson (getDropDownText ui.ddlLicense)) to:ss
        format "  \"licenseUrl\": \"%\",\n" (escapeJson (trimString ui.edtLicenseUrl.text)) to:ss
        format "  \"developerName\": \"%\",\n" (escapeJson (trimString ui.edtDeveloperName.text)) to:ss
        format "  \"developerSlug\": \"%\",\n" (escapeJson (trimString ui.edtDeveloperSlug.text)) to:ss
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


    try (destroyDialog MaxPkgPackagerRollout) catch()

    rollout MaxPkgPackagerRollout "MaxPkg Packager" width:720 height:820
    (
        label lblName "Package Name" pos:[12,12] width:120
        editText edtName "" pos:[145,10] width:220 height:18
        label lblButtonName "Button Name" pos:[380,12] width:100
        editText edtButtonName "" pos:[490,10] width:210 height:18

        label lblDeveloperName "Developer Name" pos:[12,40] width:120
        editText edtDeveloperName "" pos:[145,38] width:220 height:18
        label lblDeveloperSlug "Developer Slug" pos:[380,40] width:100
        editText edtDeveloperSlug "" pos:[490,38] width:210 height:18

        label lblGuid "Package GUID" pos:[12,68] width:120
        editText edtGuid "" pos:[145,66] width:330 height:18
        button btnGuidGenerate "Generate" pos:[485,64] width:70 height:22
        button btnGuidCopy "Copy" pos:[560,64] width:55 height:22
        button btnGuidPaste "Paste" pos:[620,64] width:55 height:22

        label lblDescription "Description" pos:[12,98] width:120
        editText edtDescription "" pos:[145,96] width:555 height:60 multiline:true

        label lblLicense "License" pos:[12,168] width:120
        dropdownList ddlLicense "" pos:[145,164] width:160 items:#("Free","Shareware","Commercial","Open Source","MIT","GPL","Custom") selection:1
        label lblLicenseUrl "License URL" pos:[320,168] width:80
        editText edtLicenseUrl "" pos:[405,166] width:295 height:18

        label lblVersion "Version" pos:[12,196] width:120
        editText edtVersion "1.0.0" pos:[145,194] width:100 height:18
        label lblReleaseDate "Release Date" pos:[260,196] width:85
        editText edtReleaseDate "" pos:[350,194] width:110 height:18
        label lblMinMax "Min 3ds Max" pos:[475,196] width:80
        editText edtMinMax "2012" pos:[560,194] width:55 height:18
        label lblMaxMax "Max" pos:[625,196] width:30
        editText edtMaxMax "2027" pos:[660,194] width:40 height:18

        label lblRuntime "Runtime" pos:[12,224] width:120
        dropdownList ddlRuntime "" pos:[145,220] width:120 items:#("maxscript","python") selection:1
        label lblEntry "Entry File" pos:[280,224] width:70
        editText edtEntry "" pos:[355,222] width:255 height:18
        button btnEntryFromSelected "Use Selected" pos:[620,220] width:80 height:22

        label lblIcon "SVG Icon" pos:[12,252] width:120
        editText edtIcon "" pos:[145,250] width:380 height:18
        button btnIconBrowse "Browse" pos:[535,248] width:55 height:22
        button btnIconClear "Clear" pos:[595,248] width:50 height:22
        button btnIconPreview "Preview" pos:[650,248] width:50 height:22

        label lblHomepage "Homepage URL" pos:[12,280] width:120
        editText edtHomepage "" pos:[145,278] width:220 height:18
        label lblDocs "Documentation URL" pos:[380,280] width:110
        editText edtDocumentation "" pos:[500,278] width:200 height:18

        label lblSupport "Support URL" pos:[12,308] width:120
        editText edtSupport "" pos:[145,306] width:220 height:18
        checkbox chkCreateMacro "Create 3ds Max Macro Button" pos:[380,306] width:185 checked:true
        checkbox chkShowToolbar "Show In MaxPkg Toolbar" pos:[570,306] width:145 checked:true

        label lblOutput "Output Folder" pos:[12,336] width:120
        editText edtOutput "" pos:[145,334] width:480 height:18
        button btnOutputBrowse "Browse" pos:[635,332] width:65 height:22

        groupBox grpFiles "Files List" pos:[10,365] width:345 height:205
        listBox lbFiles "" pos:[20,388] width:325 height:9
        button btnAddFile "Add Files" pos:[20,530] width:70 height:24
        button btnAddFolder "Add Folder" pos:[95,530] width:75 height:24
        button btnScanRoot "Scan Folder" pos:[175,530] width:80 height:24
        button btnRemoveFile "Remove" pos:[260,530] width:45 height:24
        button btnClearFiles "Clear" pos:[310,530] width:45 height:24

        groupBox grpChangelog "Changelog" pos:[365,365] width:345 height:205
        listBox lbChangelog "" pos:[375,388] width:325 height:7
        dropdownList ddlChangeType "" pos:[375,505] width:100 items:#("added","fixed","changed","removed","improved","security") selection:1
        editText edtChangeText "" pos:[480,507] width:220 height:18
        button btnAddChange "Add" pos:[375,530] width:60 height:24
        button btnEditChange "Edit" pos:[440,530] width:60 height:24
        button btnRemoveChange "Remove" pos:[505,530] width:70 height:24

        editText edtLog "" pos:[10,580] width:700 height:165 multiline:true readOnly:true

        button btnLoadIni "Load INI" pos:[10,760] width:80 height:28
        button btnSaveIni "Save INI" pos:[95,760] width:80 height:28
        button btnValidate "Validate" pos:[180,760] width:80 height:28
        button btnPreviewManifest "Preview Manifest" pos:[265,760] width:105 height:28
        button btnBuild "Build MZP" pos:[375,760] width:95 height:28
        button btnOpenOutput "Open Output Folder" pos:[475,760] width:120 height:28
        button btnClose "Close" pos:[630,760] width:70 height:28


        fn refreshFiles = (
            lbFiles.items = getPackageFileNames()
            edtLog.text = getLogText()
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
            edtLog.text = getLogText()
            return true
        )


        on MaxPkgPackagerRollout open do (
            edtOutput.text = rootDir + "dist"
            edtReleaseDate.text = currentDateString()

            if (doesFileExist iniPath) do loadSettings MaxPkgPackagerRollout

            refreshFiles()
            refreshChangelog()
            refreshLog()
        )

        on btnGuidGenerate pressed do (
            if ((trimString edtGuid.text) == "") then (
                edtGuid.text = newGuidString()
            ) else (
                if (queryBox "Package GUID already exists. Generate a new technical identity?" title:"MaxPkg Packager") do (
                    edtGuid.text = newGuidString()
                )
            )
        )

        on btnGuidCopy pressed do (
            setClipboardText edtGuid.text
        )

        on btnGuidPaste pressed do (
            edtGuid.text = getClipboardText()
        )

        on btnEntryFromSelected pressed do (
            if (lbFiles.selection > 0) do (
                edtEntry.text = lbFiles.items[lbFiles.selection]
            )
        )

        on btnIconBrowse pressed do (
            local path = getOpenFileName caption:"Select safe SVG icon" types:"SVG (*.svg)|*.svg|All Files (*.*)|*.*|"

            if (path != undefined) do (
                if (isValidSafeSvg path) then (
                    edtIcon.text = path
                    addLog "OK" "SVG icon validated"
                ) else (
                    messageBox "Selected icon is not a valid safe SVG file." title:"MaxPkg Packager"
                    addLog "ERROR" "Selected icon is not a valid safe SVG file."
                )

                refreshLog()
            )
        )

        on btnIconClear pressed do (
            edtIcon.text = ""
        )

        on btnIconPreview pressed do (
            if (edtIcon.text != "" and doesFileExist edtIcon.text) do (
                shellLaunch edtIcon.text ""
            )
        )

        on btnOutputBrowse pressed do (
            local folder = getSavePath caption:"Select output folder" initialDir:rootDir
            if (folder != undefined) do edtOutput.text = folder
        )

        on btnAddFile pressed do (
            local path = getOpenFileName caption:"Add package file" types:"Package Files (*.*)|*.*|"

            if (path != undefined) do (
                if (addPackageFile path) do (
                    addLog "OK" ("Added file: " + (relativePathFromRoot path))
                )

                refreshFiles()
            )
        )

        on btnAddFolder pressed do (
            local folder = getSavePath caption:"Add package folder" initialDir:rootDir

            if (folder != undefined) do (
                local added = addFolderFiles folder
                addLog "OK" ((added as string) + " files added from folder")
                refreshFiles()
            )
        )

        on btnScanRoot pressed do (
            packageFiles = #()

            local added = addFolderFiles rootDir
            addLog "OK" ((added as string) + " files scanned from product folder")
            refreshFiles()
        )

        on btnRemoveFile pressed do (
            if (lbFiles.selection > 0 and lbFiles.selection <= packageFiles.count) do (
                deleteItem packageFiles lbFiles.selection
            )

            refreshFiles()
        )

        on btnClearFiles pressed do (
            if (queryBox "Clear package files list?" title:"MaxPkg Packager") do (
                packageFiles = #()
                refreshFiles()
            )
        )

        on btnAddChange pressed do (
            local text = trimString edtChangeText.text

            if (text != "") do (
                append changelogItems #((getDropDownText ddlChangeType), text)
                edtChangeText.text = ""
                refreshChangelog()
            )
        )

        on btnEditChange pressed do (
            if (lbChangelog.selection > 0) do (
                changelogItems[lbChangelog.selection] = #((getDropDownText ddlChangeType), (trimString edtChangeText.text))
                refreshChangelog()
            )
        )

        on btnRemoveChange pressed do (
            if (lbChangelog.selection > 0) do (
                deleteItem changelogItems lbChangelog.selection
                refreshChangelog()
            )
        )

        on lbChangelog selected index do (
            if (index > 0) do (
                local item = changelogItems[index]
                setDropDownText ddlChangeType item[1]
                edtChangeText.text = item[2]
            )
        )

        on btnLoadIni pressed do (
            loadSettings MaxPkgPackagerRollout
            refreshFiles()
            refreshChangelog()
            refreshLog()
        )

        on btnSaveIni pressed do (
            saveSettings MaxPkgPackagerRollout
            refreshLog()
        )

        on btnValidate pressed do (
            saveSettings MaxPkgPackagerRollout
            validateSettings MaxPkgPackagerRollout
            refreshLog()
        )

        on btnPreviewManifest pressed do (
            if (validateSettings MaxPkgPackagerRollout) do (
                messageBox (buildManifestIni MaxPkgPackagerRollout) title:"manifest.ini preview"
            )

            refreshLog()
        )

        on btnBuild pressed do (
            buildPackage MaxPkgPackagerRollout
            refreshLog()
        )

        on btnOpenOutput pressed do (
            if (edtOutput.text != "") do shellLaunch edtOutput.text ""
        )

        on btnClose pressed do (
            destroyDialog MaxPkgPackagerRollout
        )
    )

    createDialog MaxPkgPackagerRollout style:#(#style_titlebar, #style_sysmenu, #style_minimizebox, #style_resizing)
)
