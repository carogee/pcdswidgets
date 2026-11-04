"""
Helper for using designer to layout widgets.
"""

import os
import warnings
from pathlib import Path
from string import Template
from typing import Any, ClassVar, Protocol

from pydm.utilities.iconfont import IconFont
from pydm.widgets.base import PyDMPrimitiveWidget
from pydm.widgets.designer_settings import update_property_for_widget
from pydm.widgets.embedded_display import PyDMEmbeddedDisplay
from pydm.widgets.qtplugin_extensions import RulesExtension
from pydm.widgets.related_display_button import PyDMRelatedDisplayButton
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QAction,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import pcdswidgets

from .designer_options import DesignerOptions
from .icon_options import IconOptions

MODULE_ROOT = Path(pcdswidgets.__file__).parent.resolve()  # type: ignore
ICON_AREA = MODULE_ROOT / "icons"

ifont = IconFont()


class _UiForm(Protocol):
    def setupUi(self, Form): ...

    def retranslateUi(self, Form): ...


class DesignerWidget(QWidget, PyDMPrimitiveWidget):  # type: ignore
    """Helper class for converting pydm displays for embedding to standalone widgets."""

    # Loaded from uic
    ui_form: ClassVar[type[_UiForm]]
    # Used to generate _qt_designer_
    designer_options: ClassVar[DesignerOptions]
    # Tells PyDM to include in designer
    _qt_designer_: ClassVar[dict[str, Any]]
    # Special handling for icon variants
    _icon_option: ClassVar[QIcon | IconOptions | str | None]
    # Macro name to widget names that include that macro
    _macro_to_widget: ClassVar[dict[str, list[str]]]
    # Widget name to required macros: all must be non-empty before updating
    _widget_to_macro: ClassVar[dict[str, list[str]]]
    # Widget name to per-property template to fill
    _widget_to_pre_template: ClassVar[dict[str, list[tuple[str, str | list[str]]]]]
    # Current values for each macro
    _macro_values: dict[str, str]
    # Enum/choice properties to expose as dropdowns in the Core Settings editor.
    # Maps a Qt property name to an ordered {display label: value} mapping.
    editable_choice_properties: ClassVar[dict[str, dict[str, int]]] = {}
    # Map some Qt property name to an arbitrary str
    editable_str_properties: ClassVar[dict[str, str]] = {}

    def __init_subclass__(cls):
        super().__init_subclass__()
        # Create _qt_designer_ for pydm if designer_options is present
        if hasattr(cls, "designer_options"):
            cls._qt_designer_ = {
                "group": cls.designer_options.group,
                "is_container": cls.designer_options.is_container,
            }
            cls._icon_option = cls.designer_options.icon

        # Include a quick editor for macro vals
        new_ext = [MacroEditExtension, RulesExtension]
        try:
            cls._qt_designer_["extensions"].extend(new_ext)
        except (AttributeError, KeyError):
            try:
                cls._qt_designer_["extensions"] = new_ext
            except AttributeError:
                ...

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ui_form.setupUi(self, self)  # type: ignore
        self.update_relative_paths()

    def retranslateUi(self, *args, **kwargs):
        """Required function for setupUi to work in __init__"""
        self.ui_form.retranslateUi(self, *args, **kwargs)  # type: ignore

    @classmethod
    def get_designer_icon(cls) -> QIcon | None:  # type: ignore
        """
        Return the correct QIcon for PyDM's designer hooks.

        If we return None, PyDM will use the default icon.
        """
        try:
            icon = cls._icon_option
        except AttributeError:
            return None
        match icon:
            case QIcon():
                return icon
            case IconOptions.NONE:
                return None
            case IconOptions():
                return ifont.icon(str(icon))
            case str():
                return QIcon(get_icon_path(icon))
            case _:
                return None

    def update_relative_paths(self):
        """
        Special handling for PyDMRelatedDisplay and PyDMEmbeddedDisplay.

        Relative filepaths are nearly non-functional when used in pcdswidgets,
        because they are relative to the filepath of the ui file (Display)
        they are placed in, not relative to the package data here.

        To opt in to a path relative to the package data here, the user
        should express it in the following form:

        pcdswidgets/tests/builder/test.ui

        When we see a relative filepath that starts with "pcdswidgets",
        we will update it to be the absolute path to that resource to avoid
        these sorts of issues. This allows us to make widgets that refer to each other
        or to ui file resources shipped with the module.

        For example, if pcdswidgets is installed at
        /some/path/python/lib/site-packages/pcdswidgets
        and we pick a relative path pcdswidgets/tests/builder/test.ui
        then we will replace it with the absolute path
        /some/path/python/lib/site-packages/pcdswidgets/tests/builder/test.ui
        """
        # ui-file loaded objects are attributes of the class
        for obj in self.__dict__.values():
            if isinstance(obj, PyDMEmbeddedDisplay):
                fname = obj.readFilename()
                new_filename = fix_pcdswidgets_filename(fname)
                if fname != new_filename:
                    obj.setFilename(new_filename)
            elif isinstance(obj, PyDMRelatedDisplayButton):
                filenames = obj.readFilenames()
                updated_one = False
                for idx, fname in enumerate(filenames):
                    new_filename = fix_pcdswidgets_filename(fname)
                    if fname != new_filename:
                        filenames[idx] = new_filename
                        updated_one = True
                if updated_one:
                    obj.setFilenames(filenames)

    def get_macro(self, macro_name: str) -> str:
        """Returns the current value of a macro that is applied to our subwidgets."""
        return self._macro_values[macro_name]

    def _get_macro(self, macro_name: str) -> str:
        warnings.warn("_get_macro is deprecated, use get_macro instead.", category=DeprecationWarning, stacklevel=2)
        return self.get_macro(macro_name)

    def set_macro(self, macro_name: str, value: str):
        """Updates a macro to a new value and propagates to all subwidget properties appropriately."""
        self._macro_values[macro_name] = value
        self._updates_for_macro(macro_name)
        self.after_set_macro(macro_name=macro_name, value=value)

    def _set_macro(self, macro_name: str, value: str):
        warnings.warn("_set_macro is deprecated, use set_macro instead.", category=DeprecationWarning, stacklevel=2)
        return self.set_macro(macro_name, value)

    def after_set_macro(self, macro_name: str, value: str):
        """
        Hook for additional actions to take when a macro is set.

        This exists so you can extend this behavior without overriding set_macro,
        which could otherwise make it easy to break the widget.

        So, you override after_set_macro instead and define what you'd like to change
        after specific values are updated.

        Note that this runs after all built-in effects of set_macro.
        """
        ...

    def _updates_for_macro(self, macro_name: str):
        """Propagate updates to each widget that uses this macro."""
        for widget_name in self._macro_to_widget[macro_name]:
            self._update_widget_for_macros(widget_name)

    def _update_widget_for_macros(self, widget_name: str):
        """Update the widget if all needed macros are defined."""
        needed_macros = self._widget_to_macro[widget_name]
        if not all(self._macro_values[macro_name] for macro_name in needed_macros):
            # Skip! Not ready!
            return
        widget = getattr(self, widget_name)
        if not isinstance(widget, QWidget):
            raise TypeError(f"{widget_name} is not a widget: {widget}")
        for prop, templ in self._widget_to_pre_template[widget_name]:
            if isinstance(templ, str):
                value = Template(templ).substitute(self._macro_values)
            elif isinstance(templ, list):
                value = [Template(tp).substitute(self._macro_values) for tp in templ]
            else:
                raise TypeError(f"Unexpected template type, should be str or stringlist: {templ}")
            widget.setProperty(prop, value)


def fix_pcdswidgets_filename(filename: str) -> str:
    """
    If a relative filename starts with "pcdswidgets", make it absolute, attaching it to the pcdswidgets install root.

    Otherwise, return the original filename.
    """
    prefix_indicator = "pcdswidgets" + os.sep
    if filename.startswith(prefix_indicator):
        return str(MODULE_ROOT / filename.removeprefix(prefix_indicator))
    return filename


class MacroEditExtension:
    """
    Adds helpful macro editing options in designer on double or right click.

    See the BasicSettingsExtension from PyDM
    """

    def __init__(self, widget: DesignerWidget):
        self.widget = widget
        self.edit_macros_action = QAction("&Edit Core Properties", self.widget)
        self.edit_macros_action.triggered.connect(self.open_dialog)

    def actions(self) -> list[QAction]:
        """
        PyDM checks this to decide which actions to prepent in designer. The first action is mapped to double-click.
        """
        return [self.edit_macros_action]

    def open_dialog(self):
        dialog = MacroValueEditor(self.widget, parent=self.widget)
        dialog.exec_()


class MacroValueEditor(QDialog):
    """
    Dialog for MacroEditExtension

    See the BasicSettingsEditor from PyDM
    """

    def __init__(self, widget: DesignerWidget, parent: QWidget | None):
        super().__init__(parent)
        self.widget = widget
        self.edit_widgets: dict[str, QLineEdit] = {}
        self.choice_widgets: dict[str, QComboBox] = {}
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Widget Core Settings Editor")
        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(5, 5, 5, 5)
        outer_layout.setSpacing(5)
        self.setLayout(outer_layout)

        edit_form_layout = QFormLayout()
        outer_layout.addLayout(edit_form_layout)

        for macro_name, value in self.widget._macro_values.items():
            self.edit_widgets[macro_name] = QLineEdit()
            self.edit_widgets[macro_name].setText(value)
            edit_form_layout.addRow(macro_name.lower(), self.edit_widgets[macro_name])

        for prop_name, value in self.widget.editable_str_properties.items():
            self.edit_widgets[prop_name] = QLineEdit()
            self.edit_widgets[prop_name].setText(self.widget.property(prop_name) or value)
            edit_form_layout.addRow(prop_name.lower(), self.edit_widgets[prop_name])

        for prop_name, choices in self.widget.editable_choice_properties.items():
            combo = QComboBox()
            for label, value in choices.items():
                combo.addItem(label, value)
            # Pre-select the widget's current value. property() returns an int
            # (pyqt5) or an enum member (pyside6); normalize to the stored value.
            current = self.widget.property(prop_name)
            current = getattr(current, "value", current)
            index = combo.findData(current)
            combo.setCurrentIndex(index if index >= 0 else 0)
            self.choice_widgets[prop_name] = combo
            edit_form_layout.addRow(prop_name, combo)

        button_layout = QHBoxLayout()
        outer_layout.addLayout(button_layout)

        self.save_button = QPushButton("&Save")
        self.save_button.setAutoDefault(True)
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save_changes)
        update_button = QPushButton("&Update")
        update_button.clicked.connect(self.save_changes)
        cancel_button = QPushButton("&Cancel")
        cancel_button.clicked.connect(self.cancel_changes)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(update_button)
        button_layout.addWidget(self.save_button)

    def save_changes(self):
        for macro_name, widget in self.edit_widgets.items():
            update_property_for_widget(self.widget, macro_name.lower(), widget.text())
        for prop_name, combo in self.choice_widgets.items():
            update_property_for_widget(self.widget, prop_name, combo.currentData())
        if self.sender() == self.save_button:
            self.accept()

    def cancel_changes(self):
        self.close()


def get_icon_path(icon_file: str) -> str:
    return str(ICON_AREA / icon_file)
