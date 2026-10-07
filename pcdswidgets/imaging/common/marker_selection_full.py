"""Module for MarkerSelectionFull"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

import json
import logging

from pydm.widgets import PyDMImageView, PyDMSpinbox
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor, QIcon, QPixmap
from qtpy.QtWidgets import QPushButton

try:
    from qtpy.QtCore import pyqtProperty
except ImportError:
    from qtpy.QtCore import Property as pyqtProperty  # type: ignore

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.common.tools.pv_channel import PVChannel
from pcdswidgets.generated.imaging.common.marker_selection_full_base import MarkerSelectionFullBase
from pcdswidgets.icons.glyphs import CAM_COG, CROSSHAIR, EYE, THICKNESS
from pcdswidgets.imaging.common.cam_marker import CamMarker, MarkerStyle
from pcdswidgets.imaging.common.marker_style_dialog import MarkerStyleDialog

logger = logging.getLogger(__name__)

# Default colors per marker index (these can be overwritten in designer)
_DEFAULT_COLORS = [
    QColor("green"),
    QColor("yellow"),
    QColor("cyan"),
    QColor("magenta"),
]
NUM_MARKERS = 4

# Fixed suffixes for the secondary ROI's offset, matching NDPluginROI's field names.
_ROI_MINX_SUFFIX = "MinX"
_ROI_MINY_SUFFIX = "MinY"


class MarkerSelectionFull(MarkerSelectionFullBase):
    """Interactive marker overlay widget for EPICS area-detector cameras.

    Provides click-to-place, visibility toggle, and style/thickness controls
    for up to 4 point-of-interest markers overlaid on a PyDMImageView.

    Positions are synced to EPICS via PyDMSpinboxes.
    """

    designer_options = DesignerOptions(
        group="ECS Imaging Common",
        is_container=False,
        icon=CAM_COG,
    )

    # Emitted whenever a marker's persisted-worthy visual state changes
    # (color, style/width/arm_length/radius/hatch_pattern, or visibility).
    state_changed = Signal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_macro_defaults()
        self._nickname = "Point Marker Selection"

        self._image_view: PyDMImageView = None
        self._view_box = None
        self._active_select_idx: int | None = None  # which marker is in select mode

        # A second, optional view the markers are also mirrored onto,
        # offset live by its own feeding ROI's MinX/MinY. Only actually
        # connected once _link_secondary_view is given a view.
        self._secondary_view_linked = False
        self._secondary_view_box = None
        self._secondary_offset_x = 0.0
        self._secondary_offset_y = 0.0
        self._secondary_roi_plugin = ":ROI2:"
        self._secondary_roi_minx_reader = PVChannel(parent=self, value_slot=self._on_secondary_offset_x_changed)
        self._secondary_roi_miny_reader = PVChannel(parent=self, value_slot=self._on_secondary_offset_y_changed)

        # Create marker overlays
        self._markers: list[CamMarker] = []
        for i in range(NUM_MARKERS):
            color = _DEFAULT_COLORS[i]
            marker = CamMarker(color, width=2, style=MarkerStyle.CROSSHAIR_LENGTH)
            self._markers.append(marker)

        self._init_button_icons()
        self._apply_default_colors()
        self._connect_buttons()
        self._connect_spinboxes()

    def after_set_macro(self, macro_name, value):
        if self._secondary_view_linked:
            self._rebuild_secondary_roi_channels()

    def _rebuild_secondary_roi_channels(self):
        """Point the secondary ROI offset readers at the current cam_prefix macro and secondary_roi_plugin property."""
        base = f"ca://{self.get_cam_prefix()}{self.secondary_roi_plugin}"
        self._secondary_roi_minx_reader.set_address(base + _ROI_MINX_SUFFIX)
        self._secondary_roi_miny_reader.set_address(base + _ROI_MINY_SUFFIX)

    def _set_macro_defaults(self):
        """Populate unset macros with sensible defaults."""
        default_map = {}
        for i in range(NUM_MARKERS):
            default_map[f"suffix_{i + 1}x"] = f":Over1:{i + 5}:PositionX"
            default_map[f"suffix_{i + 1}y"] = f":Over1:{i + 5}:PositionY"

        for name, value in default_map.items():
            self._macro_values[name] = value

    def _init_button_icons(self):
        """Assign SVG icons to the select, visibility, and style buttons."""
        for i in range(NUM_MARKERS):
            icon_map = {
                CROSSHAIR: self._select_button(i),
                EYE: self._visibility_button(i),
                THICKNESS: self._style_button(i),
            }
            for path, button in icon_map.items():
                icon = QIcon()
                icon.addPixmap(
                    QPixmap(path),
                    QIcon.Normal,
                    QIcon.Off,
                )
                button.setIcon(icon)

    def _apply_default_colors(self):
        """Sync color buttons with the marker default colors."""
        for i in range(NUM_MARKERS):
            self._color_button(i).set_color(self._markers[i].color)

    def _connect_buttons(self):
        """Wire up all button signals."""
        for i in range(NUM_MARKERS):
            select_btn = self._select_button(i)
            select_btn.setCheckable(True)
            select_btn.toggled.connect(lambda checked, idx=i: self._on_select_toggled(idx, checked))

            vis_btn = self._visibility_button(i)
            vis_btn.setCheckable(True)
            vis_btn.toggled.connect(lambda checked, idx=i: self._on_visibility_toggled(idx, checked))

            color_btn = self._color_button(i)
            color_btn.colorChanged.connect(lambda color, idx=i: self._on_color_changed(idx, color))

            style_btn = self._style_button(i)
            style_btn.clicked.connect(lambda _checked, idx=i: self._open_style_dialog(idx))

    def _connect_spinboxes(self):
        """connect on-screen overlayed markers to the spinbox values."""
        for idx in range(NUM_MARKERS):
            for axis in ["x", "y"]:
                sb = self._spinbox(axis, idx)
                sb.valueChanged.connect(
                    lambda value, axis=axis, index=idx: self._on_spinbox_changed(value, axis, index)
                )

    ## helper functions to get control widget by marker index
    def _spinbox(self, axis: str, idx: int) -> PyDMSpinbox:
        return getattr(self, f"{axis}_spinbox_{idx + 1}")

    def _select_button(self, idx: int) -> QPushButton:
        return getattr(self, f"point_{idx + 1}_select")

    def _visibility_button(self, idx: int) -> QPushButton:
        return getattr(self, f"visibility_{idx + 1}")

    def _color_button(self, idx: int):
        return getattr(self, f"color_{idx + 1}_button")

    def _style_button(self, idx: int) -> QPushButton:
        suffix = "" if idx == 0 else f"_{idx + 1}"
        return getattr(self, f"style_select{suffix}")

    def link_parent_widgets(self, parent) -> None:
        """Connect this marker widget to a parent's PyDMImageView.

        Called by the parent widget at adoption time. Attaches marker
        overlay items to the ViewBox, and - if the parent also carries a
        `secondary_image_view` - mirrors the same markers onto it too,
        click-to-place included, offset live via secondary_roi_plugin (see
        _link_secondary_view).
        """
        if hasattr(parent, "image_view"):
            self._image_view = parent.image_view
        else:
            return

        try:
            plot_item = self._image_view.getView()
            self._view_box = plot_item.getViewBox()
        except Exception:
            logger.error("Could not get ViewBox for marker overlays")
            return

        for marker in self._markers:
            marker.attach(self._view_box)

        # Listen for mouse clicks. The primary (Camera) view is always in
        # full-frame coordinates, i.e. offset (0, 0).
        self._view_box.scene().sigMouseClicked.connect(
            lambda event: self._on_scene_clicked(event, self._view_box, (0.0, 0.0))
        )

        self._link_secondary_view(getattr(parent, "secondary_image_view", None))

    def _link_secondary_view(self, secondary_image_view) -> None:
        """Mirror all markers onto a second view, offset live by secondary_roi_plugin's MinX/MinY.

        Also lets the user click-to-place markers from that view: a click
        there gives coordinates local to it, so the offset is added back
        before writing to EPICS - the exact inverse of the display
        transform. A marker can only be placed within that view's
        *currently visible* region this way; to place one outside it, use
        the primary view instead.
        """
        if secondary_image_view is None:
            return

        try:
            plot_item = secondary_image_view.getView()
            self._secondary_view_box = plot_item.getViewBox()
        except Exception:
            logger.error("Could not get ViewBox for secondary marker overlays")
            return

        for marker in self._markers:
            marker.attach(self._secondary_view_box, offset=(self._secondary_offset_x, self._secondary_offset_y))

        self._secondary_view_linked = True
        self._rebuild_secondary_roi_channels()

        # Live offset (not a snapshot) so a click always uses the ROI's
        # current position, not whatever it was when this connection was made.
        self._secondary_view_box.scene().sigMouseClicked.connect(
            lambda event: self._on_scene_clicked(
                event, self._secondary_view_box, (self._secondary_offset_x, self._secondary_offset_y)
            )
        )

    def _on_secondary_offset_x_changed(self, value: float) -> None:
        if value is None:
            return
        try:
            value = float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid secondary ROI offset value received for x axis: {value}")
            return
        self._secondary_offset_x = value
        self._apply_secondary_offset()

    def _on_secondary_offset_y_changed(self, value: float) -> None:
        if value is None:
            return
        try:
            value = float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid secondary ROI offset value received for y axis: {value}")
            return
        self._secondary_offset_y = value
        self._apply_secondary_offset()

    def _apply_secondary_offset(self) -> None:
        for marker in self._markers:
            marker.set_offset(self._secondary_view_box, self._secondary_offset_x, self._secondary_offset_y)

    def _on_select_toggled(self, idx: int, checked: bool):
        """Enter or exit point-select mode for marker *idx*."""
        if checked:
            # Deactivate any other active select buttons
            for i in range(NUM_MARKERS):
                if i != idx:
                    self._select_button(i).setChecked(False)
            self._active_select_idx = idx
        else:
            if self._active_select_idx == idx:
                self._active_select_idx = None

    def _on_visibility_toggled(self, idx: int, checked: bool):
        """Toggle marker overlay visibility."""
        self._markers[idx].set_visible(checked)
        self.state_changed.emit()

    def _on_color_changed(self, idx: int, color: QColor) -> None:
        self._markers[idx].set_color(color)
        self.state_changed.emit()

    def _on_scene_clicked(self, event, view_box, offset: tuple[float, float]):
        """Handle mouse clicks on a ViewBox scene for point-select mode.

        Works the same regardless of which view (primary or secondary) the
        click came from - `view_box` converts the click to that view's local
        coordinates, then `offset` (0, 0 for the primary view; the live ROI
        offset for the secondary one) is added back to recover the absolute
        full-frame position that's actually written to EPICS.
        """
        if self._active_select_idx is None:
            return
        if event.button() != Qt.LeftButton:
            return

        idx = self._active_select_idx
        scene_pos = event.scenePos()
        data_pos = view_box.mapSceneToView(scene_pos)

        x_sb = self._spinbox("x", idx)
        y_sb = self._spinbox("y", idx)
        # point to spinboxes (note this triggers set_position)
        x_sb.setValue(data_pos.x() + offset[0])
        y_sb.setValue(data_pos.y() + offset[1])
        # spinboxes to EPICS
        x_sb.send_value()
        y_sb.send_value()

        # force marker to be visible
        self._visibility_button(idx).setChecked(True)

        # finish selection
        self._select_button(idx).setChecked(False)
        event.accept()

    def _on_spinbox_changed(self, value: float, axis: str, index: int):
        """Update marker overlay when spinbox values change externally."""
        if axis == "x":
            self._markers[index].x = value
        else:
            self._markers[index].y = value

    def _open_style_dialog(self, idx: int):
        """Open the style/thickness dialog for marker *idx*."""
        marker = self._markers[idx]
        dlg = MarkerStyleDialog(
            current_style=marker.style,
            current_width=marker.width,
            current_arm_length=marker.arm_length,
            current_radius=marker.radius,
            current_hatch_pattern=marker.hatch_pattern,
            parent=self,
        )
        if dlg.exec_() == MarkerStyleDialog.Accepted:
            targets = self._markers if dlg.apply_to_all else [marker]
            for m in targets:
                m.set_style(dlg.selected_style)
                m.set_width(dlg.selected_width)
                m.set_arm_length(dlg.selected_arm_length)
                m.set_radius(dlg.selected_radius)
                m.set_hatch_pattern(dlg.selected_hatch_pattern)
            self.state_changed.emit()

    def get_marker_state(self, marker_number: int) -> dict:
        """Return marker_number's (1-4) full visual state, for persistence."""
        idx = marker_number - 1
        marker = self._markers[idx]
        return {
            "color": marker.color.name(),
            "style": int(marker.style),
            "width": marker.width,
            "arm_length": marker.arm_length,
            "radius_x": marker.radius_x,
            "radius_y": marker.radius_y,
            "hatch_pattern": int(marker.hatch_pattern),
            "visible": self._visibility_button(idx).isChecked(),
        }

    def set_marker_state(self, marker_number: int, state: dict) -> None:
        """Apply a previously-saved marker_state to marker_number (1-4)."""
        idx = marker_number - 1
        marker = self._markers[idx]
        if "color" in state:
            self._set_marker_color(idx, QColor(state["color"]))
        if "style" in state:
            marker.set_style(MarkerStyle(state["style"]))
        if "width" in state:
            marker.set_width(state["width"])
        if "arm_length" in state:
            marker.set_arm_length(state["arm_length"])
        if "radius_x" in state:
            marker.set_radius_x(state["radius_x"])
        if "radius_y" in state:
            marker.set_radius_y(state["radius_y"])
        if "hatch_pattern" in state:
            marker.set_hatch_pattern(Qt.PenStyle(state["hatch_pattern"]))
        if "visible" in state:
            self._visibility_button(idx).setChecked(state["visible"])

    def get_all_marker_states(self) -> dict:
        """Return every marker's state, keyed by marker number as a string, for persistence."""
        return {str(n): self.get_marker_state(n) for n in range(1, NUM_MARKERS + 1)}

    def set_all_marker_states(self, states: dict) -> None:
        """Apply states produced by :meth:`get_all_marker_states`."""
        for marker_number, state in states.items():
            self.set_marker_state(int(marker_number), state)

    def get_view_saver_properties(self) -> dict:
        """Resolved ViewSaver getter/setter pairs for this widget's saved state.

        getter returns a QSettings-storable value
        setter accepts and applies raw stored value
        """

        return {
            "markers": (
                lambda: json.dumps(self.get_all_marker_states()),
                lambda raw: self.set_all_marker_states(json.loads(raw)),
            ),
        }

    def _get_marker_color(self, idx: int) -> QColor:
        return self._markers[idx].color

    def _set_marker_color(self, idx: int, color: QColor) -> None:
        self._markers[idx].set_color(color)
        self._color_button(idx).set_color(color)

    ## Explicit properties for each marker that can be overwritten in designer.

    def get_color_1(self) -> QColor:
        return self._get_marker_color(0)

    def set_color_1(self, color: QColor) -> None:
        self._set_marker_color(0, color)

    color_1 = pyqtProperty(QColor, get_color_1, set_color_1)

    def get_color_2(self) -> QColor:
        return self._get_marker_color(1)

    def set_color_2(self, color: QColor) -> None:
        self._set_marker_color(1, color)

    color_2 = pyqtProperty(QColor, get_color_2, set_color_2)

    def get_color_3(self) -> QColor:
        return self._get_marker_color(2)

    def set_color_3(self, color: QColor) -> None:
        self._set_marker_color(2, color)

    color_3 = pyqtProperty(QColor, get_color_3, set_color_3)

    def get_color_4(self) -> QColor:
        return self._get_marker_color(3)

    def set_color_4(self, color: QColor) -> None:
        self._set_marker_color(3, color)

    color_4 = pyqtProperty(QColor, get_color_4, set_color_4)

    def get_nickname(self) -> str:
        return self._nickname

    def set_nickname(self, value: str) -> None:
        self._nickname = value

    nickname = pyqtProperty(str, get_nickname, set_nickname)

    ## Property identifying the ROI plugin feeding the secondary view, if
    ## one is linked.

    def get_secondary_roi_plugin(self) -> str:
        return self._secondary_roi_plugin

    def set_secondary_roi_plugin(self, value: str) -> None:
        self._secondary_roi_plugin = value
        if self._secondary_view_linked:
            self._rebuild_secondary_roi_channels()

    secondary_roi_plugin = pyqtProperty(str, get_secondary_roi_plugin, set_secondary_roi_plugin)
