(
    fn writeFixtureFile filePath fileContent = (
        local fileStream = createFile filePath
        if (fileStream == undefined) do return false
        format "%" fileContent to: fileStream
        close fileStream
        return true
    )

    fn responseIsSuccessful responseContent = (
        local quoteContent = bit.intAsChar 34
        return (findString responseContent (quoteContent + "ok" + quoteContent + ":true")) != undefined
    )

    fn requireSuccess operationName responseContent = (
        if (not (responseIsSuccessful responseContent)) do throw (operationName + " failed: " + responseContent)
        return true
    )

    fn deleteFixtureFolder fixtureFolder = (
        local pathClass = dotNetClass "System.IO.Path"
        local directoryClass = dotNetClass "System.IO.Directory"
        local tempRoot = pathClass.GetFullPath (getDir #temp)
        local normalizedFixtureFolder = pathClass.GetFullPath fixtureFolder
        local isInsideTemp = normalizedFixtureFolder.count > tempRoot.count and (substring normalizedFixtureFolder 1 tempRoot.count) == tempRoot
        if (not isInsideTemp) do return false
        if (directoryClass.Exists normalizedFixtureFolder) do directoryClass.Delete normalizedFixtureFolder true
        return not (directoryClass.Exists normalizedFixtureFolder)
    )

    local testScriptFile = getThisScriptFilename()
    local testFolder = getFilenamePath testScriptFile
    local pathClass = dotNetClass "System.IO.Path"
    local slashContent = bit.intAsChar 92
    local projectFolder = (pathClass.GetFullPath (pathClass.Combine testFolder "..")) + slashContent
    local fixtureFolder = (pathClass.Combine (getDir #temp) "maxpkg-api-smoke-fixture") + slashContent
    local packagerSourceFile = projectFolder + "maxpkg-packager.ms"
    local packagerFixtureFile = fixtureFolder + "maxpkg-packager.ms"
    local entryFixtureFile = fixtureFolder + "entry.ms"
    local iconFixtureFile = fixtureFolder + "fixture-icon.svg"
    local outputFolder = fixtureFolder + "dist"
    local isSuccessful = false
    local currentStage = "setup"
    local failureMessage = ""

    try (
        currentStage = "cleanupFixture"
        if (not (deleteFixtureFolder fixtureFolder)) do throw "Could not clean the fixture folder."
        currentStage = "makeFixture"
        makeDir fixtureFolder all: true
        currentStage = "copyPackager"
        copyFile packagerSourceFile packagerFixtureFile
        currentStage = "writeEntry"
        writeFixtureFile entryFixtureFile "(global MaxPkgApiSmokeEntry = true)\r\n"
        currentStage = "writeIcon"
        writeFixtureFile iconFixtureFile "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><rect width='64' height='64' fill='#4caf50'/></svg>"

        currentStage = "fileIn"
        fileIn packagerFixtureFile
        currentStage = "loaded"
        if (MaxPkgPackerApi == undefined) do throw "MaxPkgPackerApi was not created."

        currentStage = "ping"
        requireSuccess "ping" (MaxPkgPackerApi.ping())
        currentStage = "schema"
        requireSuccess "schema" (MaxPkgPackerApi.getSchema())
        currentStage = "addFile"
        requireSuccess "addFile" (MaxPkgPackerApi.addFile entryFixtureFile)
        currentStage = "setOptions"
        requireSuccess "setOptions" (MaxPkgPackerApi.setOptions #(
            #("packageName", "API Smoke"),
            #("buttonName", "API Smoke"),
            #("packageGuid", "12345678-1234-1234-1234-123456789abc"),
            #("description", "MaxPkg API smoke fixture"),
            #("developerName", "MaxPkg"),
            #("license", "Free"),
            #("createMacroButton", true),
            #("showInToolbar", true),
            #("outputFolder", outputFolder),
            #("svgIconFile", iconFixtureFile),
            #("entryFile", "entry.ms"),
            #("compileEntry", false),
            #("version", "1.2.3"),
            #("releaseChannel", "stable"),
            #("releaseDate", "2026-08-26"),
            #("min3dsMax", "2022")
        ))
        requireSuccess "addChangelog" (MaxPkgPackerApi.addChangelog "Added" "API smoke coverage")
        requireSuccess "addBuildPathRule" (MaxPkgPackerApi.addBuildPathRule "source" "")
        requireSuccess "updateBuildPathRule" (MaxPkgPackerApi.updateBuildPathRule 1 "source" "runtime")
        requireSuccess "addExtraMacro" (MaxPkgPackerApi.addExtraMacro "entry.ms" "API Extra" compileScript: false showInQuadMenu: true)
        requireSuccess "updateExtraMacro" (MaxPkgPackerApi.updateExtraMacro 1 "entry.ms" "API Extra Updated" compileScript: false showInQuadMenu: false)
        requireSuccess "validate" (MaxPkgPackerApi.validate())
        requireSuccess "build" (MaxPkgPackerApi.build())
        requireSuccess "reload" (MaxPkgPackerApi.reload())
        requireSuccess "getState" (MaxPkgPackerApi.getState())

        local guardedRemoval = MaxPkgPackerApi.removeFile "entry.ms"
        if (responseIsSuccessful guardedRemoval) do throw "removeFile should require force for an entry/extra macro file."

        requireSuccess "removeExtraMacro" (MaxPkgPackerApi.removeExtraMacro 1)
        requireSuccess "removeBuildPathRule" (MaxPkgPackerApi.removeBuildPathRule 1)
        requireSuccess "updateChangelog" (MaxPkgPackerApi.updateChangelog 1 "Improved" "API smoke coverage updated")
        requireSuccess "removeChangelog" (MaxPkgPackerApi.removeChangelog 1)
        requireSuccess "removeFile" (MaxPkgPackerApi.removeFile "entry.ms" force: true)
        isSuccessful = true
        format "MAXPKG_API_SMOKE_OK\n"
    ) catch (
        failureMessage = getCurrentException()
        format "MAXPKG_API_SMOKE_FAILED at %: %\n" currentStage failureMessage
    )

    try (closeRolloutFloater MaxPkgPackerNewFloater) catch()
    try (destroyDialog MaxPkgPackerNewLogRollout) catch()
    MaxPkgPackerApi = undefined
    try (deleteFixtureFolder fixtureFolder) catch()
    if (not isSuccessful) do throw ("MaxPkg API smoke test failed at " + currentStage + ": " + failureMessage)
    "MAXPKG_API_SMOKE_OK"
)
