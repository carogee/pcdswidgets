"""Module for EpicsRoiFull"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

import json
import logging

from pydm.widgets import PyDMImageView
from qtpy.QtCore import QPointF, Qt, Signal
from qtpy.QtGui import QColor, QIcon, QPixmap
from qtpy.QtWidgets import QPushButton

try:
    from qtpy.QtCore import pyqtProperty
except ImportError:
    from qtpy.QtCore import Property as pyqtProperty  # type: ignore

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.generated.imaging.common.epics_roi_full_base import EpicsRoiFullBase
from pcdswidgets.icons.glyphs import CAM_COG, CROSSHAIR, EYE, MOVE, PEN_TOOL, THICKNESS
from pcdswidgets.imaging.common.cam_roi import CamROI

logger = logging.getLogger(__name__)


class EpicsRoiFull(EpicsRoiFullBase):
    """Interactive ROI overlay widget for EPICS area-detector cameras.

    Provides draw, center-select, move/resize, and color/thickness controls
    for a rectangular ROI overlaid on a PyDMImageView.

    ROI geometry is synchronised with EPICS PVs via PyDMSpinbox
    channels.
    """

    draw_roi_button: QPushButton
    select_center_button: QPushButton
    visibility_button: QPushButton
    color_selection_button: QPushButton
    move_enabled_button: QPushButton
    line_thickness_button: QPushButton

    # Emitted whenever this ROI's persisted-worthy appearance changes (color,
    # thickness, or visibility).
    state_changed = Signal()

    designer_options = DesignerOptions(
        group="ECS Imaging Common",
        is_container=False,
        icon=CAM_COG,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._set_macro_defaults()
        self._nickname = "ROI Selection"

        self._image_view: PyDMImageView = None
        self._view_box = None
        self._draw_origin: QPointF = None

        self.roi_rect = CamROI(self.get_roi_color(), 3, self)

        # if the X,Y epics PVs define center of box or starting edge
        self._is_xy_center = False

        self._init_button_icons()
        self._connect_buttons()

        # monitor spinboxes for changes (camonitor / initial read/ user typed)
        for spinbox in self.roi_spinboxes:
            spinbox.valueChanged.connect(self._on_spinbox_changed)

    def _set_macro_defaults(self):
        """Populate unset macros with sensible defaults for ROI1."""
        default_map = {
            "roi_plugin": ":ROI1:",
            "suffix_X": "MinX",
            "suffix_Y": "MinY",
            "suffix_WidthX": "SizeX",
            "suffix_WidthY": "SizeY",
        }
        for name, value in default_map.items():
            self._macro_values[name] = value

    def _init_button_icons(self):
        """Assign SVG icons to the toolbar buttons."""
        icon_map = {
            PEN_TOOL: self.draw_roi_button,
            CROSSHAIR: self.select_center_button,
            EYE: self.visibility_button,
            MOVE: self.move_enabled_button,
            THICKNESS: self.line_thickness_button,
        }
        for path, button in icon_map.items():
            icon = QIcon()
            icon.addPixmap(
                QPixmap(path),
                QIcon.Normal,
                QIcon.Off,
            )
            button.setIcon(icon)

    def _connect_buttons(self):
        """Wire up button click signals."""
        self.draw_roi_button.setCheckable(True)
        self.select_center_button.setCheckable(True)
        self.move_enabled_button.setCheckable(True)
        self.visibility_button.setCheckable(True)

        # mode select toggles
        self.draw_roi_button.clicked.connect(self._on_draw_toggle)
        self.select_center_button.toggled.connect(self._on_centering_toggle)
        self.move_enabled_button.toggled.connect(self._on_move_toggle)

        # link appearance control buttons to ROI
        self.visibility_button.toggled.connect(self._on_visibility_toggled)
        self.color_selection_button.colorChanged.connect(self._on_color_changed)
        self.line_thickness_button.clicked.connect(self._on_thickness_dialog)

    def _on_visibility_toggled(self, visible: bool) -> None:
        self.roi_rect.visible(visible)
        self.state_changed.emit()

    def _on_color_changed(self, color: QColor) -> None:
        self.roi_rect.update_color(color)
        self.state_changed.emit()

    def _on_thickness_dialog(self) -> None:
        self.roi_rect.thickness_dialog()
        self.state_changed.emit()

    def get_style_state(self) -> dict:
        """Return this ROI's color/thickness/visibility, for persistence."""
        return {
            "color": self.get_roi_color().name(),
            "thickness": self.roi_rect.pen.width(),
            "visible": self.visibility_button.isChecked(),
        }

    def set_style_state(self, state: dict) -> None:
        """Apply a previously-saved style_state."""
        if "color" in state:
            self.set_roi_color(QColor(state["color"]))
        if "thickness" in state:
            self.roi_rect.change_pen(width=state["thickness"])
        if "visible" in state:
            self.visibility_button.setChecked(state["visible"])

    def get_view_saver_properties(self) -> dict:
        """Resolved ViewSaver getter/setter pairs for this widget's saved state.

        getter returns a QSettings-storable value
        setter accepts and applies raw stored value
        """

        return {
            "style": (
                lambda: json.dumps(self.get_style_state()),
                lambda raw: self.set_style_state(json.loads(raw)),
            ),
        }

    def link_parent_widgets(self, parent) -> None:
        """
        Connect this ROI widget to a parent's PyDMImageView.

        Called by the parent widget at adoption time.  Creates the ROI
        overlay item, attaches it to the ViewBox.
        """

        # link the ROI rect to the image_view box
        if hasattr(parent, "image_view"):
            self._image_view = parent.image_view
        else:
            return
        try:
            plot_item = self._image_view.getView()
            self._view_box = plot_item.getViewBox()
        except Exception:
            logger.error("Could not get ViewBox for overlays")
            return
        self._view_box.addItem(self.roi_rect)

        # Listen for mouse clicks on the view for draw/center modes
        self._view_box.scene().sigMouseClicked.connect(self._on_scene_clicked)
        self._view_box.scene().sigMouseMoved.connect(self._on_scene_moved)

    # ── Event Handlers ───────────────────────────────────────

    def _on_draw_toggle(self, is_enabled: bool):
        self._draw_origin = None
        if is_enabled:
            # always disable other modes
            self.move_enabled_button.setChecked(False)
            self.select_center_button.setChecked(False)

    def _on_move_toggle(self, is_enabled: bool):
        self.roi_rect.set_movable(is_enabled)
        # always disable other modes
        if is_enabled:
            self.draw_roi_button.setChecked(False)
            self.select_center_button.setChecked(False)

            # link "move" mode event handlers
            self.roi_rect.sigRegionChangeFinished.connect(self._push_roi_to_spinbox)
        else:
            self.roi_rect.sigRegionChangeFinished.disconnect(self._push_roi_to_spinbox)

    def _on_centering_toggle(self, is_enabled: bool):
        if is_enabled:
            # always disable other modes
            self.move_enabled_button.setChecked(False)
            self.draw_roi_button.setChecked(False)

    def _on_scene_clicked(self, event):
        """Handle mouse clicks on the ViewBox scene for draw/center modes."""
        # Only respond to left-click
        if event.button() != Qt.LeftButton:
            return

        scene_pos = event.scenePos()
        data_pos = self._view_box.mapSceneToView(scene_pos)

        if self.draw_roi_button.isChecked():
            if self._draw_origin is None:
                # First click – start drawing
                self._draw_origin = data_pos
                self.roi_rect.setPos(data_pos.x(), data_pos.y())
                self.roi_rect.setSize([1, 1])
            else:
                # Second click – finalise
                self.roi_rect.set_from_corners(self._draw_origin, data_pos)
                self._draw_origin = None
                self._push_roi_to_spinbox()
                # Exit draw mode
                self.draw_roi_button.setChecked(False)
        elif self.select_center_button.isChecked():
            self.roi_rect.move_center_to(data_pos)
            # Exit center mode
            self._push_roi_to_spinbox()
            self.select_center_button.setChecked(False)
        else:
            return

        self.visibility_button.setChecked(True)
        event.accept()

    def _push_roi_to_spinbox(self):
        """Push current ROI geometry to the EPICS spinbox channels."""
        if self._is_xy_center:
            geometry = self.roi_rect.get_geometry_wrt_center()
        else:
            geometry = self.roi_rect.get_geometry_wrt_corner()
        for spinbox, value in zip(self.roi_spinboxes, geometry, strict=True):
            spinbox.setValue(value)
            spinbox.send_value()

    def _on_scene_moved(self, scene_pos):
        """Live-update ROI shape while dragging during draw mode."""
        if self._draw_origin is not None:
            data_pos = self._view_box.mapSceneToView(scene_pos)
            self.roi_rect.set_from_corners(self._draw_origin, data_pos)

    def _on_spinbox_changed(self, new_value=None):
        """update the ROI if spinbox values change not due to user input"""
        # only update ROI displayed if the move controls are not active
        if not self.user_moving_roi:
            sender = self.sender()
            values = []
            for sb in self.roi_spinboxes:
                if sb is sender and new_value is not None:
                    values.append(new_value)
                else:
                    values.append(sb.value)
            if None in values:
                return
            if self.is_xy_center:
                self.roi_rect.set_geometry_from_center(*values)
            else:
                self.roi_rect.set_geometry_from_corner(*values)

    # ── Properties ───────────────────────────────────────

    @property
    def roi_spinboxes(self):
        """Coordinate control spinboxes in geometry order: (x, y, width_x, width_y)."""
        return (self.x_spinbox, self.y_spinbox, self.width_spinbox, self.height_spinbox)

    @property
    def interactive_buttons(self):
        return (self.move_enabled_button, self.select_center_button, self.draw_roi_button)

    @property
    def user_moving_roi(self):
        for button in self.interactive_buttons:
            button: QPushButton
            if button.isChecked():
                return True
        return False

    def get_roi_color(self) -> QColor:
        return self.color_selection_button.get_color()

    def set_roi_color(self, color: QColor) -> None:
        self.color_selection_button.set_color(color)

    roi_color = pyqtProperty(QColor, get_roi_color, set_roi_color)

    def get_nickname(self) -> str:
        return self._nickname

    def set_nickname(self, value: str) -> None:
        self._nickname = value

    nickname = pyqtProperty(str, get_nickname, set_nickname)

    def get_is_xy_center(self) -> bool:
        return self._is_xy_center

    def set_is_xy_center(self, value: bool) -> None:
        self._is_xy_center = value

    is_xy_center = pyqtProperty(bool, get_is_xy_center, set_is_xy_center)
