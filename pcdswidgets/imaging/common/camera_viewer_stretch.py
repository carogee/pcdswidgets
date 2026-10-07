"""Module for CameraViewerStretch"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

import logging
from collections import deque

from pydm.widgets import PyDMImageView
from qtpy import QtGui, QtWidgets
from qtpy.QtCore import QChildEvent, QEvent, Qt, QTimer

try:
    from qtpy.QtCore import pyqtProperty
except ImportError:
    from qtpy.QtCore import Property as pyqtProperty

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.builder.icon_options import IconOptions
from pcdswidgets.generated.imaging.common.camera_viewer_stretch_base import (
    CameraViewerStretchBase,
)

from .collapsible_section import CollapsibleSection

logger = logging.getLogger(__name__)


class CameraViewerStretch(CameraViewerStretchBase):
    sidebar_toggle: QtWidgets.QPushButton
    sidebar_scroll: QtWidgets.QScrollArea
    image_view: PyDMImageView
    display_fps_label: QtWidgets.QLabel
    main_splitter: QtWidgets.QSplitter
    active_pv_label: QtWidgets.QLabel

    designer_options = DesignerOptions(
        group="ECS Imaging Common",
        is_container=True,
        icon=IconOptions.camera,
    )

    # names of base widgets in this class
    _internal_widget_names: set[str] = set()

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        self._initializing = True
        self._adopted_widgets: list[QtWidgets.QWidget] = []
        self._show_nickname = True
        super().__init__(parent)

        self._set_macro_defaults()

        self._frame_count = 0
        self._fps_rolling_buffer = deque(maxlen=5)
        self._first_show = True

        # snapshot internal widgets to distinguish them from added widgets
        if not CameraViewerStretch._internal_widget_names:
            CameraViewerStretch._internal_widget_names = {
                child.objectName() for child in self.findChildren(QtWidgets.QWidget) if child.objectName()
            }

        # Fix axis orientation: Area Detector uses C-order (row-major) data
        self.image_view.readingOrder = 1  # Clike

        # Display FPS timer
        self._fps_timer = QTimer(self)
        self._fps_timer.setInterval(1000)
        self._fps_timer.timeout.connect(self._update_display_fps)
        self._fps_timer.start()  # Connect image update signal for FPS counting
        try:
            self.image_view.newImageSignal.connect(self._on_new_image)
        except AttributeError:
            # some pydm versions may not have this signal
            pass

        self.sidebar_toggle.toggled.connect(self._toggle_sidebar)
        self.nickname_label.setVisible(self._show_nickname)
        self.active_pv_label.setCursor(Qt.PointingHandCursor)
        self.active_pv_label.setToolTip("Click to copy")
        self.active_pv_label.installEventFilter(self)
        self._initializing = False

    def eventFilter(self, obj, event) -> bool:
        """Copy the camera prefix to the clipboard when active_pv_label is clicked."""
        if obj is self.active_pv_label and event.type() == QEvent.MouseButtonPress:
            QtWidgets.QApplication.clipboard().setText(self.cam_prefix)
            QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), "Copied!", self.active_pv_label)
            return True
        return super().eventFilter(obj, event)

    def _set_macro_defaults(self):
        """Populate unset macros with sensible defaults for ROI1."""
        default_map = {
            "stream_plugin": ":IMAGE1:",
            "img_protocol": "ca://",
            "suffix_waveform_channel": "ArrayData",
            "suffix_width_channel": "ArraySize0_RBV",
        }
        for name, value in default_map.items():
            self._macro_values[name] = value

    def _toggle_sidebar(self, checked: bool) -> None:
        self.sidebar_scroll.setVisible(checked)

    # -- Display FPS -------------------------------------------------------

    def _on_new_image(self) -> None:
        self._frame_count += 1

    def _update_display_fps(self) -> None:
        self._fps_rolling_buffer.append(self._frame_count)
        avg_fps = sum(self._fps_rolling_buffer) / len(self._fps_rolling_buffer)
        self.display_fps_label.setText(f"{avg_fps:.1f}")
        self._frame_count = 0

    # -- Sub-Widget Adoption ----------------------------------

    def childEvent(self, event: QChildEvent) -> None:
        """Mark externally added widgets with '_sidebar_widget' for later adoption."""
        super().childEvent(event)
        if self._initializing:
            return
        if event.type() == QEvent.ChildAdded:
            child = event.child()
            if not isinstance(child, QtWidgets.QWidget):
                return
            if self._is_external(child):
                child.setProperty("_sidebar_widget", True)

    def _is_external(self, widget: QtWidgets.QWidget) -> bool:
        """Return True if widget is NOT one of our known internal children."""
        if widget.parent() is not self:
            return False
        name = widget.objectName()
        if name and name in self._internal_widget_names:
            return False
        # Layouts and spacers get added as children too, these should be ignored
        if isinstance(widget, (QtWidgets.QLayout, QtWidgets.QSpacerItem)):
            return False
        return True

    def _is_designer_editing(self) -> bool:
        """Return True if widget is in Designer's edit mode (not preview)."""
        try:
            from qtpy.QtDesigner import QDesignerFormWindowInterface

            return QDesignerFormWindowInterface.findFormWindow(self) is not None
        except ImportError:
            return False

    def showEvent(self, event) -> None:
        """Hooks into the first show event to adopt child widgets added in designer"""
        super().showEvent(event)
        if self._initializing:
            return
        if self._first_show:
            self._first_show = False
            if not self._is_designer_editing():
                self._adopt_child_widgets()

    def _adopt_child_widgets(self) -> None:
        """
        Move user-dropped widgets from *self* into the sidebar layout.

        Finds all direct children marked with the '_sidebar_widget' dynamic
        property (set by childEvent in Designer or persisted in the .ui file)
        and wraps them in CollapsibleSection widgets inside sidebar_scroll.
        """
        sidebar_layout = self.sidebar_scroll.widget().layout()
        if sidebar_layout is None:
            sidebar_layout = QtWidgets.QVBoxLayout(self.sidebar_scroll.widget())
            sidebar_layout.setContentsMargins(0, 0, 0, 0)
            sidebar_layout.setSpacing(2)

        # sort all widgets marked as sidebar_widgets by the current y location
        candidates = sorted(
            (
                child
                for child in self.findChildren(QtWidgets.QWidget)
                if child.parent() is self and child.property("_sidebar_widget")
            ),
            key=lambda w: w.y(),
        )
        # add the children in collapsible sections
        cam_prefix = self._macro_values.get("cam_prefix", "")
        cam_stream_plugin = self._macro_values.get("stream_plugin", "IMAGE1")

        for child in candidates:
            section = CollapsibleSection(
                child,
                parent=self.sidebar_scroll.widget(),
                collapsed=True,
            )
            section.setObjectName(f"{child.objectName()}_collapse")
            sidebar_layout.addWidget(section)
            section.show()
            self._adopted_widgets.append(child)
            # Propagate macros to sub-widget at adoption time
            if cam_prefix and hasattr(child, "cam_prefix"):
                child.cam_prefix = cam_prefix
            if cam_stream_plugin and hasattr(child, "stream_plugin"):
                child.stream_plugin = cam_stream_plugin
            # Link sub-widget to our image_view if it supports it
            if hasattr(child, "link_parent_widgets"):
                child.link_parent_widgets(self)
            logger.debug(
                "Adopted child %s'",
                child.objectName() or type(child).__name__,
            )
        # close the sidebar and hide the toggle button if no children exists
        if len(candidates) == 0:
            self.sidebar_toggle.setChecked(False)
            self.sidebar_toggle.setVisible(False)
            self.sidebar_scroll.setVisible(False)

        # add a vertical spacer to push all widgets to the top
        sidebar_layout.addStretch()

    # Property for showing/hiding the nickname label.

    def get_show_nickname(self) -> bool:
        return self._show_nickname

    def set_show_nickname(self, show: bool) -> None:
        self._show_nickname = show
        self.nickname_label.setVisible(show)

    show_nickname = pyqtProperty(bool, get_show_nickname, set_show_nickname)

    ## Property for the main splitter's orientation.

    def get_orientation(self) -> Qt.Orientation:
        return self.main_splitter.orientation()

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        self.main_splitter.setOrientation(orientation)

    orientation = pyqtProperty(Qt.Orientation, get_orientation, set_orientation)
