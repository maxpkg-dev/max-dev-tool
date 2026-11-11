"""Checks of the window code that need no window and no 3ds Max (Qt for Python is only imported, never started)."""

import ast
import glob
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.join(os.path.dirname(HERE), "maxpkg-src", "python")
sys.path.insert(0, PACKAGE)


def _classes():
    """{class name: (base expressions, assigned self attributes with line numbers, file)} of every ui module."""
    found = {}
    for path in glob.glob(os.path.join(PACKAGE, "maxpkgpackager", "ui", "*.py")):
        with open(path, encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name):
                    bases.append(base.value.id + "." + base.attr)
                elif isinstance(base, ast.Name):
                    bases.append(base.id)
            assigned = []
            for inner in ast.walk(node):
                if isinstance(inner, ast.Assign):
                    for target in inner.targets:
                        if (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                                and target.value.id == "self"):
                            assigned.append((target.attr, inner.lineno))
            found[node.name] = (bases, assigned, os.path.basename(path))
    return found


class QtNamesTests(unittest.TestCase):
    """`self.font = ...` in a widget hid QWidget.font(): Qt code calling widget.font() then crashed ("'QFont' object
    is not callable") at any interface size other than 100 %. No attribute of a widget may take the name of a method
    of its Qt class."""

    def test_no_attribute_hides_a_qt_method(self):
        try:
            from maxpkgpackager.qt_compat import QtCore, QtGui, QtWidgets
        except ImportError:
            self.skipTest("Qt for Python is not available in this Python")
        modules = {"QtWidgets": QtWidgets, "QtCore": QtCore, "QtGui": QtGui}
        classes = _classes()

        def qt_bases(name, seen=()):
            bases, _assigned, _file = classes.get(name, ([], [], ""))
            result = []
            for base in bases:
                module, _dot, attribute = base.rpartition(".")
                module = module.split(".")[-1]
                if module in modules and hasattr(modules[module], attribute):
                    result.append(getattr(modules[module], attribute))
                elif attribute in classes and attribute not in seen:
                    result.extend(qt_bases(attribute, seen + (name,)))
            return result

        problems = []
        for name, (_bases, assigned, file_name) in classes.items():
            for qt_class in qt_bases(name):
                for attribute, line in assigned:
                    if callable(getattr(qt_class, attribute, None)):
                        problems.append("{}:{} {}.{} hides {}.{}()".format(file_name, line, name, attribute,
                                                                         qt_class.__name__, attribute))
        self.assertEqual(sorted(set(problems)), [])


class MaskedPopupTests(unittest.TestCase):
    """A popup shaped by a window mask (a bubble with an arrow) lost the outer half of its outline to the mask: the red
    error bubble had no edge on the right, at the bottom and along its arrow. Such a popup paints itself through
    controls.paint_bubble, which keeps the outline inside the shape on the whole perimeter."""

    def test_masked_bubbles_outline_the_whole_shape(self):
        problems = []
        for path in glob.glob(os.path.join(PACKAGE, "maxpkgpackager", "ui", "*.py")):
            with open(path, encoding="utf-8") as handle:
                source = handle.read()
            for chunk in source.split("\nclass ")[1:]:
                name = chunk.split("(", 1)[0].split(":", 1)[0].strip()
                if "self.setMask(" in chunk and "def paintEvent" in chunk:
                    paint = chunk.split("def paintEvent", 1)[1].split("\n    def ", 1)[0]
                    outlines = any(call in paint for call in ("drawPath(", "strokePath(", "QPen("))
                    if outlines and "paint_bubble(" not in paint:  # A window that only shades itself is fine
                        problems.append("{}: {} paints a masked shape without paint_bubble".format(
                            os.path.basename(path), name))
        self.assertEqual(problems, [])

    def test_bubbles_keep_the_light_system_shadow(self):
        """The error bubble and the help balloon have Windows' own small popup shadow, like Qt's tooltips (asked for:
        light, small, not heavy). NoDropShadowWindowHint takes it away, and a Qt.ToolTip window only gets it when its
        class inherits one named QTipLabel (checked in Max 2022 / Qt 5.15 and Max 2027 / Qt 6.8)."""
        with open(os.path.join(PACKAGE, "maxpkgpackager", "ui", "controls.py"), encoding="utf-8") as handle:
            source = handle.read()
        chunks = {chunk.split("(", 1)[0].split(":", 1)[0].strip(): chunk for chunk in source.split("\nclass ")[1:]}
        for name in ("ErrorTip", "Balloon"):
            self.assertNotIn("Qt.NoDropShadowWindowHint", chunks[name], name)
        self.assertTrue(chunks["ErrorTip"].startswith("ErrorTip(QTipLabel"))
        self.assertIn("QTipLabel", chunks)


if __name__ == "__main__":
    unittest.main()
