@echo off
rem Release MaxPkg Packager. Double-click it (or run it in a terminal):
rem   1. runs the tests,
rem   2. builds release\ and the installer release\MaxPkgPackager.mzp,
rem   3. shows what would be committed and asks; only after "y" it commits, pushes main and creates the GitHub
rem      release with the installer (needs git and gh, the GitHub command line, signed in).
rem Before: raise the version in maxpkg-src\python\maxpkgpackager\__init__.py and VERSION in maxpkg-packager.ms, and add
rem the version's notes to maxpkg-packager.ms (see .codex\how-to-release.md).
setlocal
cd /d "%~dp0"

set "PY="
for %%V in (2027 2026 2025 2024 2023) do (
    if not defined PY if exist "C:\Program Files\Autodesk\3ds Max %%V\Python\python.exe" set "PY=C:\Program Files\Autodesk\3ds Max %%V\Python\python.exe"
)
if not defined PY if exist "C:\Program Files\Autodesk\3ds Max 2022\Python37\python.exe" set "PY=C:\Program Files\Autodesk\3ds Max 2022\Python37\python.exe"
if not defined PY set "PY=python"
echo Python: %PY%

echo.
echo == Tests ==
"%PY%" -I -m unittest discover -s tests -p "test_*.py"
if errorlevel 1 goto stopped

echo.
echo == Build and publish ==
"%PY%" -I maxpkg-src\tools\release.py --publish
if errorlevel 1 goto stopped
goto done

:stopped
echo.
echo Release stopped: see the messages above.

:done
echo.
pause
