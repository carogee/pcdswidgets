"""Overridden spinbox widgets.

Override mix-ins for PyDMSpinbox and QTSpinbox widget to change two behaviors
- ignore wheel events unless the spinbox has keyboard
- validate/send value and clear focus on <Enter> for PyDM spinboxes.
"""

from pydm.utilities.iconfont import IconFont
from pydm.widgets import PyDMSpinbox
from qtpy.QtCore import Qt
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QDoubleSpinBox, QSpinBox


class ClickToScrollMixin:
    """Mixin that ignores wheel events unless the widget has keyboard focus.

    Prevents accidental value changes while scrolling the page.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class SpinBoxClickToScroll(ClickToScrollMixin, QSpinBox):
    """regular ``QSpinBox`` that ignores wheel events unless focused."""

    _designer_icon_name = "sort-numeric-up"

    _qt_designer_ = {
        "group": "ECS Common Widgets",
        "is_container": False,
    }

    @classmethod
    def get_designer_icon(cls) -> QIcon:
        """Icon used to represent this widget in Qt Designer."""
        return IconFont().icon(cls._designer_icon_name)


class DoubleSpinBoxClickToScroll(ClickToScrollMixin, QDoubleSpinBox):
    """regular ``QDoubleSpinBox`` that ignores wheel events unless focused."""

    _designer_icon_name = "sort-numeric-up"

    _qt_designer_ = {
        "group": "ECS Common Widgets",
        "is_container": False,
    }

    @classmethod
    def get_designer_icon(cls) -> QIcon:
        """Icon used to represent this widget in Qt Designer."""
        return IconFont().icon(cls._designer_icon_name)


class PyDMSpinBoxClickToScroll(ClickToScrollMixin, PyDMSpinbox):
    """PyDMSpinbox with some ECS Overrides for more intuitive interaction
    Overrides:
        ClickToScrollMixin prevents mouse wheel scroll unless has focus
        <Enter> press always validates text before sending the value.
        <Enter> press clears focus. Assumes user is done with this value.
    """

    _designer_icon_name = "sort-numeric-up"

    _qt_designer_ = {
        "group": "ECS Common Widgets",
        "is_container": False,
    }

    def keyPressEvent(self, ev):
        """
        The default <Enter> press event does not validate text if
        keyboardTracking is off causing a stale value to be sent.

        Also want focus to clear after a new value is set.
        """
        if ev.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.interpretText()
            self.send_value()
            self.clearFocus()
        else:
            super().keyPressEvent(ev)

    @classmethod
    def get_designer_icon(cls) -> QIcon:
        """Icon used to represent this widget in Qt Designer."""
        return IconFont().icon(cls._designer_icon_name)
