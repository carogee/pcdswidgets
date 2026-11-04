"""Overridden combo box widgets.

Ignore mouse wheel events as they interfere with scrolling the page
"""

from pydm.utilities.iconfont import IconFont
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QComboBox


class NoScrollMixin:
    """Mixin that ignores wheel events."""

    def wheelEvent(self, event):
        event.ignore()


class ComboBoxNoScroll(NoScrollMixin, QComboBox):
    """regular ``QComboBox`` that ignores wheel events unless focused."""

    _designer_icon_name = "list-ol"

    _qt_designer_ = {
        "group": "ECS Common Widgets",
        "is_container": False,
    }

    @classmethod
    def get_designer_icon(cls) -> QIcon:
        """Icon used to represent this widget in Qt Designer."""
        return IconFont().icon(cls._designer_icon_name)
