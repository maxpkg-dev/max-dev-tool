struct MaxPkgQuadMenuManagerData (
        packageFolder = getFilenamePath (getSourceFileName()),
        manifestFilePath = "",
        packageGuid = "",
        callbackId = undefined,
        quadItems = #(),

        fn ensureTrailingSlash folderPath = (
            if (folderPath == undefined or folderPath == "") do return ""
            if ((substring folderPath folderPath.count 1) == "\\") do return folderPath
            return folderPath + "\\"
        ),

        fn startsWith sourceContent prefixContent = (
            if (sourceContent == undefined or prefixContent == undefined) do return false
            local sourceString = sourceContent as string
            local prefixString = prefixContent as string
            if (sourceString.count < prefixString.count) do return false
            return (substring sourceString 1 prefixString.count) == prefixString
        ),

        fn loadPackageData = (
            packageFolder = ensureTrailingSlash packageFolder
            manifestFilePath = packageFolder + "manifest.ini"
            quadItems = #()
            if (not (doesFileExist manifestFilePath)) do return false

            packageGuid = getINISetting manifestFilePath "package" "packageGuid"
            if (packageGuid == undefined or packageGuid == "") do return false
            callbackId = ("MaxPkgQuad_" + (substituteString packageGuid "-" "")) as name

            local macroCount = try ((getINISetting manifestFilePath "extraMacros" "count") as integer) catch(0)
            for macroIndex in 1 to macroCount do (
                local indexPrefix = macroIndex as string
                local showInQuadMenu = toLower (getINISetting manifestFilePath "extraMacros" (indexPrefix + "_quad"))
                if (showInQuadMenu == "true") do (
                    local buttonTitle = getINISetting manifestFilePath "extraMacros" (indexPrefix + "_button")
                    local macroSuffix = getINISetting manifestFilePath "extraMacros" (indexPrefix + "_macro")
                    local quadMenuId = getINISetting manifestFilePath "extraMacros" (indexPrefix + "_quadId")
                    if (buttonTitle != "" and macroSuffix != "" and quadMenuId != "") do (
                        local macroScriptTitle = "MaxPkg_" + (substituteString packageGuid "-" "") + "_" + macroSuffix
                        append quadItems #(buttonTitle, macroScriptTitle, quadMenuId)
                    )
                )
            )
            return true
        ),

        fn legacyQuadMenu = (
            try (
                return (menuMan.getViewportRightClickMenu #nonePressed).getMenu 1
            ) catch (
                return undefined
            )
        ),

        fn legacyItemPosition quadMenu buttonTitle = (
            if (quadMenu == undefined) do return 0
            for itemIndex in 1 to quadMenu.numItems() do (
                local menuItem = quadMenu.getItem itemIndex
                if (menuItem != undefined and menuItem.getTitle() == buttonTitle) do return itemIndex
            )
            return 0
        ),

        fn removeLegacyItem quadMenu buttonTitle = (
            local itemPosition = legacyItemPosition quadMenu buttonTitle
            if (itemPosition > 0) do quadMenu.removeItemByPosition itemPosition
            return true
        ),

        fn installLegacy = (
            local quadMenu = legacyQuadMenu()
            if (quadMenu == undefined) do return false
            local insertPosition = legacyItemPosition quadMenu "Select &Similar"
            if (insertPosition < 1) do insertPosition = quadMenu.numItems()
            local installedItemCount = 0

            for quadItem in quadItems do (
                removeLegacyItem quadMenu quadItem[1]
                local actionItem = menuMan.createActionItem quadItem[2] "MaxPkg"
                if (actionItem != undefined) do (
                    insertPosition += 1
                    quadMenu.addItem actionItem insertPosition
                    installedItemCount += 1
                )
            )
            menuMan.updateMenuBar()
            return installedItemCount == quadItems.count
        ),

        fn uninstallLegacy = (
            local quadMenu = legacyQuadMenu()
            if (quadMenu == undefined) do return false
            for quadItem in quadItems do removeLegacyItem quadMenu quadItem[1]
            menuMan.updateMenuBar()
            return true
        ),

        fn findModernItem searchContent matchTitle: false = (
            local searchString = toLower (searchContent as string)
            local quadMenuManager = maxops.getICUiQuadMenuMgr()
            for quadContext in quadMenuManager.contexts do (
                for quadMenu in quadContext.quadMenus do (
                    for subMenu in quadMenu.menus do (
                        for menuItem in subMenu.menuItems do (
                            local itemContent = if matchTitle then (try (menuItem.title as string) catch("")) else (try (menuItem.id as string) catch(""))
                            if ((toLower itemContent) == searchString) do return #(subMenu, menuItem)
                        )
                    )
                )
            )
            return undefined
        ),

        fn removeModernItem quadMenuId = (
            local foundItem = findModernItem quadMenuId
            if (foundItem != undefined) do foundItem[1].DeleteItem foundItem[2].id
            return true
        ),

        fn installModern = (
            local insertTarget = findModernItem "Select &Similar" matchTitle: true
            if (insertTarget == undefined) do return false

            for quadItem in quadItems do (
                removeModernItem quadItem[3]
                insertTarget[1].CreateAction quadItem[3] 647394 (quadItem[2] + "`MaxPkg") title: quadItem[1] beforeId: insertTarget[2].id
            )
            return true
        ),

        fn uninstallModern = (
            for quadItem in quadItems do removeModernItem quadItem[3]
            return true
        ),

        fn stringLiteral sourceContent = (
            local literalContent = sourceContent as string
            literalContent = substituteString literalContent "\\" "\\\\"
            literalContent = substituteString literalContent "\"" "\\\""
            return "\"" + literalContent + "\""
        ),

        fn registerModernCallback = (
            if (callbackId == undefined) do return false
            try (callbacks.removeScripts id: callbackId) catch()
            local callbackContent = "(MaxPkgQuadMenuManagerData packageFolder: " + (stringLiteral packageFolder) + ").installModern()"
            try (
                callbacks.addScript #cuiRegisterQuadMenus callbackContent id: callbackId
                return true
            ) catch (
                return false
            )
        ),

        fn install = (
            if (not (loadPackageData())) do return false
            if (quadItems.count == 0) do return true
            if (menuMan != undefined) do return installLegacy()
            registerModernCallback()
            return installModern()
        ),

        fn uninstall = (
            if (not (loadPackageData())) do return false
            if (callbackId != undefined) do try (callbacks.removeScripts id: callbackId) catch()
            if (quadItems.count == 0) do return true
            if (menuMan != undefined) do return uninstallLegacy()
            return uninstallModern()
        ),

        on create do (
            packageFolder = ensureTrailingSlash packageFolder
            loadPackageData()
        )
)

