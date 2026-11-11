"""Self-update that cannot leave the tool half-updated.

Layout under the app home (%LOCALAPPDATA%\\MaxPkgPackager\\app):

    current.json      {"version": "2.0.2", "dir": "v2.0.2", "sha256": "<payload>", "previous": "2.0.1",
                       "previousDir": "v2.0.1"}
    v2.0.1\\ v2.0.2\\  one complete, verified copy of python\\ and assets\\ per version

An update is downloaded, checked against its SHA-256, unpacked into a staging folder, compiled as a syntax check
and only then moved into place with one rename; current.json switches with one atomic replace. The running tool
keeps using its own folder, the new version starts at the next launch, and the previous version stays on disk so a
failed start can roll back. Nothing outside the app home is touched except an optional launcher/hook refresh, which
uses the same verify-then-replace rule and keeps a .bak copy.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

KEEP_VERSIONS = 2  # current + previous


class UpdateError(Exception):
    pass


class UpdateInfo(object):
    def __init__(self, version, url, sha256, launcher=None, notes=None, hooks=None):
        self.version = version
        self.url = url
        self.sha256 = (sha256 or "").lower()
        self.launcher = launcher or {}  # {"url": ..., "sha256": ...} or {}
        self.notes = list(notes or [])
        self.hooks = hooks or {}  # {"_install.ms": {"url": ..., "sha256": ...}}


def parse_version(text):
    parts = re.findall(r"\d+", text or "")
    return tuple(int(part) for part in parts[:3]) + (0,) * (3 - len(parts[:3]))


def is_newer(candidate, current):
    return parse_version(candidate) > parse_version(current)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


# ---- state -----------------------------------------------------------------------------------------------------
def current_path(home):
    return os.path.join(home, "current.json")


def read_current(home):
    try:
        with open(current_path(home), "r", encoding="utf-8") as handle:
            state = json.load(handle)
        return state if isinstance(state, dict) and state.get("dir") else None
    except (OSError, ValueError):
        return None


def _write_current(home, state):
    os.makedirs(home, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=".current-", suffix=".tmp", dir=home)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2)
        os.replace(temporary, current_path(home))
    except BaseException:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


def current_root(home):
    """Folder of the active version, or None when nothing valid is installed."""
    state = read_current(home)
    if state:
        root = os.path.join(home, state["dir"])
        if os.path.isfile(os.path.join(root, "python", "bootstrap.py")):
            return root
    return None


def rollback(home):
    """Make the previous version current again. True when it was switched."""
    state = read_current(home)
    if not state or not state.get("previousDir"):
        return False
    if not os.path.isfile(os.path.join(home, state["previousDir"], "python", "bootstrap.py")):
        return False
    _write_current(home, {"version": state.get("previous", ""), "dir": state["previousDir"], "previous": "",
                          "previousDir": ""})
    return True


# ---- install ---------------------------------------------------------------------------------------------------
def _safe_extract(archive, folder):
    base = os.path.realpath(folder)
    for member in archive.infolist():
        target = os.path.realpath(os.path.join(folder, member.filename))
        if target != base and not target.startswith(base + os.sep):
            raise UpdateError("Unsafe path in update: {}".format(member.filename))
    archive.extractall(folder)


def _check_payload(folder, version):
    boot = os.path.join(folder, "python", "bootstrap.py")
    init = os.path.join(folder, "python", "maxpkgpackager", "__init__.py")
    if not os.path.isfile(boot) or not os.path.isfile(init):
        raise UpdateError("Update is incomplete: bootstrap or package is missing")
    with open(init, "r", encoding="utf-8") as handle:
        match = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", handle.read(), re.M)
    if not match or match.group(1) != version:
        raise UpdateError("Update version does not match its manifest")
    for current, _directories, names in os.walk(os.path.join(folder, "python")):
        for name in names:
            if name.endswith(".py"):
                path = os.path.join(current, name)
                with open(path, "r", encoding="utf-8") as handle:
                    try:
                        compile(handle.read(), path, "exec")  # Syntax check only; nothing is imported or run.
                    except SyntaxError as error:
                        raise UpdateError("Update has a syntax error in {}: {}".format(name, error))


def install_payload(home, info, zip_path):
    """Verify, unpack and activate a downloaded payload. Any failure leaves the current version untouched."""
    if sha256_file(zip_path) != info.sha256:
        raise UpdateError("Downloaded update does not match its checksum")
    os.makedirs(home, exist_ok=True)
    staging = tempfile.mkdtemp(prefix=".staging-", dir=home)
    try:
        try:
            with zipfile.ZipFile(zip_path) as archive:
                _safe_extract(archive, staging)
        except zipfile.BadZipFile as error:
            raise UpdateError("Update archive is damaged: {}".format(error))
        _check_payload(staging, info.version)
        target_name = "v" + info.version
        target = os.path.join(home, target_name)
        if os.path.isdir(target):
            os.rename(target, target + ".old-{}".format(int(time.time())))
        os.replace(staging, target)
        state = read_current(home) or {}
        previous = state if state.get("dir") and state.get("dir") != target_name else {}
        _write_current(home, {"version": info.version, "dir": target_name, "sha256": info.sha256,
                              "previous": previous.get("version", ""), "previousDir": previous.get("dir", "")})
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    prune(home)


def prune(home):
    state = read_current(home) or {}
    keep = {state.get("dir"), state.get("previousDir")}
    for name in os.listdir(home):
        path = os.path.join(home, name)
        if os.path.isdir(path) and name not in keep and (name.startswith("v") or name.startswith(".staging-")):
            shutil.rmtree(path, ignore_errors=True)


# ---- network ---------------------------------------------------------------------------------------------------
def _request(url, timeout):
    if url.lower().startswith("http"):  # Defeat caches of the raw-file host; file:// URLs take no query.
        url += ("&" if "?" in url else "?") + "t=" + str(int(time.time()))
    request = urllib.request.Request(url,
                                     headers={"User-Agent": "MaxPkgPackager", "Cache-Control": "no-cache"})
    return urllib.request.urlopen(request, timeout=timeout)


def download(url, destination, timeout=30):
    """Download to `destination` (via a .part file). Falls back to curl.exe when urllib cannot connect."""
    part = destination + ".part"
    try:
        with _request(url, timeout) as response, open(part, "wb") as handle:
            shutil.copyfileobj(response, handle)
    except Exception as first_error:
        curl = shutil.which("curl.exe") or shutil.which("curl")
        if not curl:
            raise UpdateError("Download failed: {}".format(first_error))
        flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
        done = subprocess.run([curl, "-fsSL", "--max-time", str(timeout * 4), "-o", part, url],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=flags)
        if done.returncode != 0 or not os.path.isfile(part):
            raise UpdateError("Download failed: {}".format(first_error))
    if not os.path.isfile(part) or os.path.getsize(part) == 0:
        raise UpdateError("Downloaded file is empty")
    os.replace(part, destination)
    return destination


def fetch_manifest(update_url, timeout=15):
    """The published update.json as a dict. Raises UpdateError when it cannot be read."""
    try:
        with _request(update_url, timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise UpdateError("No update has been published yet.")
        raise UpdateError("The update server answered with an error ({}).".format(error.code))
    except urllib.error.URLError as error:
        raise UpdateError("Could not reach the update server: {}".format(error.reason))
    except Exception as error:
        raise UpdateError("Could not check for updates: {}".format(error))
    if not isinstance(data, dict):
        raise UpdateError("Update information is invalid")
    return data


def fetch_info(update_url, current_version, timeout=15, data=None):
    """UpdateInfo when a newer version is published, else None. Raises UpdateError when the check itself fails."""
    data = data if data is not None else fetch_manifest(update_url, timeout)
    try:
        payload = data["payload"]
        info = UpdateInfo(str(data["version"]), payload["url"], payload["sha256"], data.get("launcher"),
                          data.get("notes"), data.get("hooks"))
    except (KeyError, ValueError, TypeError) as error:
        raise UpdateError("Update information is invalid: {}".format(error))
    return info if is_newer(info.version, current_version) else None


def download_and_install(home, info, timeout=60):
    temp = tempfile.mkdtemp(prefix="maxpkg-update-")
    try:
        archive = download(info.url, os.path.join(temp, "payload.zip"), timeout)
        install_payload(home, info, archive)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def replace_file(url, sha256, target, timeout=30):
    """Replace one tracked file (launcher or hook) after verifying the download. The backup copy is kept in a
    temporary folder, never next to the target, and restored if the replacement fails."""
    temp = tempfile.mkdtemp(prefix="maxpkg-file-")
    try:
        downloaded = download(url, os.path.join(temp, "file"), timeout)
        if sha256 and sha256_file(downloaded) != sha256.lower():
            raise UpdateError("Downloaded file does not match its checksum")
        backup = os.path.join(temp, "backup")
        if os.path.isfile(target):
            shutil.copyfile(target, backup)
        try:
            shutil.copyfile(downloaded, target)
        except OSError:
            if os.path.isfile(backup):
                shutil.copyfile(backup, target)
            raise
    finally:
        shutil.rmtree(temp, ignore_errors=True)
