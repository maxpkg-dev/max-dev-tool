"""Building the .mzp archive. Produces the same package layout as the MaxScript packager (manifest 1)."""

import json
import os
import shutil
import tempfile
import zipfile

from . import hooks, store
from .inifile import escape_value
from .project import HOOK_FILES, clamp_min_max, compiled_path, max_year_plus_one, norm
from .validate import ERROR, OK, WARNING, validate

MANIFEST_VERSION = "1"
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


class BuildResult(object):
    def __init__(self):
        self.ok = False
        self.output_file = ""
        self.size = 0
        self.members = []
        self.issues = []  # validation issues
        self.messages = []  # [(level, text)]


def _crlf(text):
    return text.replace("\r\n", "\n").replace("\n", "\r\n")


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(_crlf(text).encode("utf-8"))


def _template(name):
    with open(os.path.join(TEMPLATE_DIR, name), "rb") as handle:
        return handle.read().decode("utf-8")


def _flag(value):
    return "true" if value else "false"


def manifest_values(project, packager_title, packager_version):
    """Ordered (key, value) pairs of the [package] section; the JSON manifest uses the same data."""
    release = project.release()

    def custom(source):
        source = norm(source).strip()
        return project.build_path(project.relative_to_root(source)) if source else ""

    return [
        ("manifestVersion", MANIFEST_VERSION),
        ("packageGuid", project.guid.strip()),
        ("name", project.package_name.strip()),
        ("buttonName", project.button_name.strip()),
        ("description", project.description.strip()),
        ("version", project.version),
        ("releaseChannel", release.channel),
        ("releaseDate", release.date.strip()),
        ("entry", project.manifest_entry()),
        ("compileEntry", project.effective_compile_entry),
        ("icon", "icons/icon.svg" if project.svg_icon.strip() else ""),
        ("license", project.license),
        ("licenseUrl", project.license_url.strip()),
        ("developerName", project.developer.strip()),
        ("min3dsMax", int(clamp_min_max(release.min_max))),
        ("max3dsMax", max_year_plus_one()),
        ("homepage", project.homepage.strip()),
        ("documentation", project.documentation.strip()),
        ("purchase", project.purchase.strip()),
        ("purchaseButtonLabel", project.purchase_label),
        ("createMacroButton", project.create_button),
        ("showInToolbar", project.show_toolbar),
        ("installScript", HOOK_FILES[0]),  # Every package has the install and uninstall windows (core/hooks.py)
        ("uninstallScript", HOOK_FILES[1]),
        ("customInstallScript", custom(project.custom_install)),
        ("customUninstallScript", custom(project.custom_uninstall)),
        ("packager", packager_title),
        ("packagerVersion", packager_version),
    ]


def manifest_ini(project, packager_title, packager_version):
    lines = ["[package]"]
    for key, value in manifest_values(project, packager_title, packager_version):
        if isinstance(value, bool):
            value = _flag(value)
        lines.append("{}={}".format(key, escape_value(str(value))))
    lines += ["", "[extraMacros]", "count={}".format(len(project.macros))]
    for index, macro in enumerate(project.macros, 1):
        lines += [
            "{}_file={}".format(index, project.macro_output(macro)),
            "{}_button={}".format(index, escape_value(macro.button)),
            "{}_macro={}".format(index, macro.identifier),
            "{}_compile={}".format(index, _flag(macro.compile)),
            "{}_quad={}".format(index, _flag(macro.quad)),
            "{}_quadId={}".format(index, project.macro_quad_id(macro)),
        ]
    changelog = project.release().changelog
    lines += ["", "[changelog]", "count={}".format(len(changelog))]
    for index, (kind, body) in enumerate(changelog, 1):
        lines += ["{}_type={}".format(index, escape_value(kind)), "{}_text={}".format(index, escape_value(body))]
    return "\n".join(lines) + "\n"


def manifest_json(project, packager_title, packager_version):
    data = dict((key, value) for key, value in manifest_values(project, packager_title, packager_version))
    data["extraMacros"] = [{"file": project.macro_output(m), "buttonName": m.button, "macroName": m.identifier,
                            "compile": m.compile, "showInQuadMenu": m.quad, "quadMenuId": project.macro_quad_id(m)}
                           for m in project.macros]
    data["changelog"] = [{"type": kind, "text": body} for kind, body in project.release().changelog]
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def mzp_run(project):
    name = project.package_name.strip().replace('"', "'") or project.guid.strip()
    guid = project.guid.strip()
    return 'name "{}"\nextract to "$temp\\{}"\ndrop "mzp.run.ms"\nrun "mzp.run.ms"\n'.format(name, guid)


def pymxs_compile(path):
    """Compile a staged .ms into .mse next to it with 3ds Max's encryptScript. Needs a running 3ds Max."""
    from pymxs import runtime as rt  # Imported late so the core stays usable outside Max.
    rt.encryptScript(path)
    return os.path.isfile(compiled_path(path))


def build(project, packager_title="MaxPkg Packager", packager_version="0", log=None, compile_script=None):
    """Validate and build the archive. Returns BuildResult; never leaves a half-written output file."""
    result = BuildResult()

    def say(level, text):
        result.messages.append((level, text))
        if log:
            log(level, text)

    result.issues = validate(project)
    for issue in result.issues:
        say(issue.level, issue.message + (" ({})".format(issue.where()) if issue.where() else ""))
    if any(issue.level == ERROR for issue in result.issues):
        say(ERROR, "Validation failed")
        return result
    say(OK, "Validation passed")

    try:
        store.save(project)
    except OSError as error:
        say(ERROR, "Could not save project files: {}".format(error))
        return result

    compile_script = compile_script or pymxs_compile
    stage = tempfile.mkdtemp(prefix="maxpkg-packager-build-")
    try:
        _stage_files(project, stage, packager_title, packager_version, say, compile_script)
        if any(level == ERROR for level, _text in result.messages):
            say(ERROR, "MZP was not created because the log contains errors")
            return result
        output_dir = os.path.abspath(project.output_folder)
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, project.output_name())
        _zip_stage(stage, output_file)
        result.members = verify_archive(output_file, project)
        result.output_file = output_file
        result.size = os.path.getsize(output_file)
        result.ok = True
        say(OK, "MZP created: {}".format(output_file))
    except Exception as error:  # Report any failure through the log; the stage is removed below.
        say(ERROR, "Build failed: {}".format(error))
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return result


def _stage_files(project, stage, title, version, say, compile_script):
    _write_text(os.path.join(stage, "manifest.ini"), manifest_ini(project, title, version))
    say(OK, "manifest.ini generated")
    _write_text(os.path.join(stage, "manifest.json"), manifest_json(project, title, version))
    say(OK, "manifest.json generated")
    changelog = store.changelog_path(project.root)
    if os.path.isfile(changelog):
        shutil.copyfile(changelog, os.path.join(stage, "maxpkg-changelog.ini"))
        say(OK, "maxpkg-changelog.ini copied")

    entry = norm(project.entry).lower()
    for absolute, relative in project.files:
        target = os.path.join(stage, project.build_path(relative))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(absolute, target)
        if (project.effective_compile_entry and relative.lower() == entry) or project.macro_uses_compile(relative):
            if compile_script(target):
                os.remove(target)
            else:
                say(ERROR, "Could not compile {}".format(relative))
    say(OK, "{} files copied".format(len(project.files)))

    for name in HOOK_FILES:  # The packager's own files; the project's copy only when this packager has lost its own
        hook = hooks.shipped(name) or project.hook_path(name)
        if hook:
            shutil.copyfile(hook, os.path.join(stage, name))
            say(OK, "{} copied".format(name))
        else:
            say(ERROR, "{} is missing: install MaxPkg Packager again".format(name))
    for source in (project.custom_install, project.custom_uninstall):
        source = norm(source).strip()
        if source:
            target = os.path.join(stage, project.build_path(project.relative_to_root(source)))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target)
            say(OK, "Custom script copied: {}".format(project.relative_to_root(source)))

    if project.svg_icon.strip():
        os.makedirs(os.path.join(stage, "icons"), exist_ok=True)
        shutil.copyfile(project.svg_icon, os.path.join(stage, "icons", "icon.svg"))
        say(OK, "SVG icon copied")
    _write_text(os.path.join(stage, "mzp.run.ms"), _template("mzp.run.ms"))
    say(OK, "mzp.run.ms generated")
    if project.uses_quad():
        _write_text(os.path.join(stage, "maxpkg-quad.ms"), _template("maxpkg-quad.ms"))
        say(OK, "maxpkg-quad.ms generated")
    _write_text(os.path.join(stage, "mzp.run"), mzp_run(project))
    say(OK, "mzp.run generated")


def _zip_stage(stage, output_file):
    """Write to a temporary file first and replace the output only when the archive is complete."""
    handle, temporary = tempfile.mkstemp(prefix=".mzp-", suffix=".tmp", dir=os.path.dirname(output_file))
    os.close(handle)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
            for current, directories, names in os.walk(stage):
                directories.sort()
                for name in sorted(names):
                    full = os.path.join(current, name)
                    archive.write(full, os.path.relpath(full, stage).replace("\\", "/"))
        os.replace(temporary, output_file)
    except BaseException:
        try:
            os.remove(temporary)
        except OSError:
            pass
        raise


def verify_archive(path, project):
    """Re-open the finished archive: integrity, required members, manifest/entry/version consistency.

    Returns the member names. Raises ValueError with the reason when something is wrong.
    """
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError("Archive member is corrupt: {}".format(bad))
        names = archive.namelist()
        lowered = [name.lower() for name in names]
        if len(set(lowered)) != len(lowered):
            raise ValueError("Archive has case-conflicting paths")
        for name in names:
            if name.startswith("/") or ".." in name.split("/") or ":" in name:
                raise ValueError("Unsafe archive path: {}".format(name))
        for required in ("manifest.ini", "manifest.json", "mzp.run", "mzp.run.ms") + HOOK_FILES:
            if required not in names:
                raise ValueError("Archive is missing {}".format(required))
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        entry = manifest.get("entry", "").replace("\\", "/")
        if entry not in names:
            raise ValueError("Entry file is not in the archive: {}".format(entry))
        if manifest.get("version") != project.version or manifest.get("packageGuid") != project.guid.strip():
            raise ValueError("Manifest does not match the project")
        if manifest.get("icon") and manifest["icon"] not in names:
            raise ValueError("Icon is not in the archive")
    return names
