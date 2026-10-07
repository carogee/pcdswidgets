"""Module for CentroidTrackerFull"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

import json
import logging
import math

from pydm.widgets import PyDMImageView, PyDMLabel
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor, QDoubleValidator, QIcon, QPixmap

try:
    from qtpy.QtCore import pyqtProperty
except ImportError:
    from qtpy.QtCore import Property as pyqtProperty


from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.common.tools.pv_channel import PVChannel
from pcdswidgets.generated.imaging.common.centroid_tracker_full_base import CentroidTrackerFullBase
from pcdswidgets.icons.glyphs import CAM_COG, EYE, THICKNESS
from pcdswidgets.imaging.common.cam_marker import CamMarker, MarkerStyle
from pcdswidgets.imaging.common.centroid_marker_style_dialog import CentroidMarkerStyleDialog
from pcdswidgets.imaging.common.epics_roi_full import EpicsRoiFull

logger = logging.getLogger(__name__)

# Fixed suffixes for the Camera ROI plugin PVs this widget writes to.
_ROI_MINX_SUFFIX = "MinX"
_ROI_MINY_SUFFIX = "MinY"
_ROI_SIZEX_SUFFIX = "SizeX"
_ROI_SIZEY_SUFFIX = "SizeY"

# Fixed suffix for the Stats plugin's write-only centroid threshold PV.
_STATS_THRESHOLD_SUFFIX = "CentroidThreshold"

# threshold_mode_combo indices, in the order items are added in __init__.
_THRESHOLD_MODE_ONE_OVER_E2 = 0
_THRESHOLD_MODE_PERCENT = 1
_THRESHOLD_MODE_RAW = 2

_FWHM_TO_SIGMA = 2.355  # FWHM ≈ 2.355 x sigma for a Gaussian
_MIN_ROI_SIZE = 10  # pixels


class CentroidTrackerFull(CentroidTrackerFullBase):
    # Emitted when the marker's persisted visual state changes (color,
    # style, sigma-radius toggle, visibility) - not for live position/radius updates.
    state_changed = Signal()

    designer_options = DesignerOptions(
        group="ECS Imaging Common",
        is_container=False,
        icon=CAM_COG,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_macro_defaults()
        self._nickname = "Centroid Tracker"

        self._image_view: PyDMImageView = None
        self._view_box = None

        self._sigma_x = None
        self._sigma_y = None
        self._centroid_x = None
        self._centroid_y = None

        # The centroid readback is relative to the source ROI's own sub-array;
        # _update_absolute_centroid adds these back to get full-frame coordinates.
        self._source_roi_min_x: float = 0.0
        self._source_roi_min_y: float = 0.0
        self._centroid_x_raw = None
        self._centroid_y_raw = None

        # A second, optional view the marker is also mirrored onto
        # (display-only), offset live by its own feeding ROI's MinX/MinY.
        # Only actually connected once _link_secondary_view is given a view.
        self._secondary_view_linked = False
        self._secondary_view_box = None
        self._secondary_offset_x = 0.0
        self._secondary_offset_y = 0.0

        # Used to convert the 1/e^2 and % of max threshold modes to a raw value.
        self._max_value = None
        self._threshold_rbv = None

        # after_set_macro fires once per macro during initial load; this
        # ensures the value-label hooks below are only wired up once.
        self._labels_connected = False

        # If True, the marker's radius tracks the live sigma readbacks;
        # if False, it's pinned to _default_radius.
        self._use_sigma_radius = True
        self._default_radius = 20

        self._marker = CamMarker(
            "red", radius_x=self._default_radius, radius_y=self._default_radius, style=MarkerStyle.ELLIPSE
        )

        # Camera ROI plugin that the centroid-derived ROI is pushed to.
        self._roi_plugin = ":ROI2:"

        # Camera ROI plugins identifying the source ROI (always read)
        # and the one feeding the secondary view, if any.
        self._source_roi_plugin = ""  # example ":ROI2:"
        self._secondary_roi_plugin = ""  # example ":ROI2:"

        # Writers for the centroid-derived ROI, pushed to the shared Camera
        # ROI plugin that EpicsRoiFull (if available) also targets.
        self._roi_pv_connected = {}
        self._roi_minx_writer = self._make_roi_writer("minx")
        self._roi_miny_writer = self._make_roi_writer("miny")
        self._roi_sizex_writer = self._make_roi_writer("sizex")
        self._roi_sizey_writer = self._make_roi_writer("sizey")
        self.set_roi_button.setVisible(False)
        self._rebuild_roi_channels()

        self._threshold_writer = PVChannel(parent=self)
        self._rebuild_stats_channels()

        # Read-only: the source ROI's offset is always relevant (Stats
        # readbacks are inherently relative to whatever ROI feeds them), so
        # it's connected unconditionally. The secondary ROI's offset is only
        # relevant once a secondary view is actually linked, so it's
        # created here but not yet connected.
        self._source_roi_minx_reader = PVChannel(
            parent=self, value_slot=lambda v: self._on_source_roi_offset_changed(v, "x")
        )
        self._source_roi_miny_reader = PVChannel(
            parent=self, value_slot=lambda v: self._on_source_roi_offset_changed(v, "y")
        )
        self._rebuild_source_roi_channels()
        self._secondary_roi_minx_reader = PVChannel(parent=self, value_slot=self._on_secondary_offset_x_changed)
        self._secondary_roi_miny_reader = PVChannel(parent=self, value_slot=self._on_secondary_offset_y_changed)

        self._init_button_icons()
        self._apply_default_color()
        self._connect_buttons()
        self._init_threshold_controls()

        self.roi_multiplier_spinbox.setValue(1.7)
        self.roi_multiplier_spinbox.setMinimum(1.0)
        self.roi_multiplier_spinbox.setMaximum(10.0)
        self.roi_multiplier_spinbox.setSingleStep(0.5)

    def after_set_macro(self, macro_name, value):
        self._connect_value_labels()
        self._rebuild_roi_channels()
        self._rebuild_stats_channels()
        self._rebuild_source_roi_channels()
        if self._secondary_view_linked:
            self._rebuild_secondary_roi_channels()

    def _set_macro_defaults(self):
        """Populate unset macros with sensible defaults for the Stats plugin."""
        default_map = {
            "stat_plugin": ":Stats2:",
            "suffix_centroid_x": "CentroidX_RBV",
            "suffix_centroid_y": "CentroidY_RBV",
            "suffix_sigma_x": "SigmaX_RBV",
            "suffix_sigma_y": "SigmaY_RBV",
            "suffix_max_value": "MaxValue_RBV",
            "suffix_centroid_threshold_rbv": "CentroidThreshold_RBV",
        }
        for name, value in default_map.items():
            self._macro_values[name] = value

    def _make_roi_writer(self, key: str) -> PVChannel:
        """Create a write-only handle for one ROI PV, tracked for the "all connected" gate on set_roi_button."""
        self._roi_pv_connected[key] = False
        return PVChannel(
            parent=self, connection_slot=lambda connected, key=key: self._on_roi_pv_connection_changed(key, connected)
        )

    def _rebuild_roi_channels(self):
        """Point the ROI PV writers at the current cam_prefix macro and roi_plugin property."""
        cam_prefix = self.get_cam_prefix()
        if not cam_prefix:
            return
        base = f"ca://{cam_prefix}{self.get_roi_plugin()}"
        self._roi_minx_writer.set_address(base + _ROI_MINX_SUFFIX)
        self._roi_miny_writer.set_address(base + _ROI_MINY_SUFFIX)
        self._roi_sizex_writer.set_address(base + _ROI_SIZEX_SUFFIX)
        self._roi_sizey_writer.set_address(base + _ROI_SIZEY_SUFFIX)

    def _rebuild_stats_channels(self):
        """Point the CentroidThreshold writer at the current cam_prefix/stat_plugin macros.

        No-ops until cam_prefix is known - see _rebuild_source_roi_channels.
        """
        cam_prefix = self.get_cam_prefix()
        if not cam_prefix:
            return
        self._threshold_writer.set_address(f"ca://{cam_prefix}{self.get_stat_plugin()}{_STATS_THRESHOLD_SUFFIX}")

    def _rebuild_source_roi_channels(self):
        """Point the source ROI offset readers at the current cam_prefix macro and source_roi_plugin property."""
        cam_prefix = self.get_cam_prefix()
        if not cam_prefix or not self.source_roi_plugin:
            return
        base = f"ca://{cam_prefix}{self.source_roi_plugin}"
        self._source_roi_minx_reader.set_address(base + _ROI_MINX_SUFFIX)
        self._source_roi_miny_reader.set_address(base + _ROI_MINY_SUFFIX)

    def _rebuild_secondary_roi_channels(self):
        """Point the secondary ROI offset readers at the current cam_prefix macro and secondary_roi_plugin property."""
        cam_prefix = self.get_cam_prefix()
        if not cam_prefix or not self.secondary_roi_plugin:
            return
        base = f"ca://{cam_prefix}{self.secondary_roi_plugin}"
        self._secondary_roi_minx_reader.set_address(base + _ROI_MINX_SUFFIX)
        self._secondary_roi_miny_reader.set_address(base + _ROI_MINY_SUFFIX)

    def _on_roi_pv_connection_changed(self, key: str, connected: bool):
        """Only offer the "push ROI" button once all four ROI PVs are connected."""
        self._roi_pv_connected[key] = bool(connected)
        self.set_roi_button.setVisible(all(self._roi_pv_connected.values()))

    def _init_button_icons(self):
        icon_map = [
            (EYE, self.centroid_visibility_button),
            (THICKNESS, self.centroid_style_button),
        ]
        for path, button in icon_map:
            icon = QIcon()
            icon.addPixmap(QPixmap(path), QIcon.Normal, QIcon.Off)
            button.setIcon(icon)

    def _apply_default_color(self):
        self.centroid_color_button.set_color(self._marker.color)

    def _connect_buttons(self):
        self.centroid_visibility_button.setCheckable(True)
        self.centroid_visibility_button.toggled.connect(self._on_visibility_toggled)
        self.centroid_color_button.colorChanged.connect(self._on_color_changed)
        self.centroid_style_button.clicked.connect(self._open_style_dialog)
        self.set_roi_button.clicked.connect(self._set_roi_from_centroid)

    def _connect_value_labels(self):
        """Hook the centroid/sigma/threshold PyDMLabels to track their live values (wired up once)."""
        if self._labels_connected:
            return

        self._wrap_value_changed(self.centroid_x_label, lambda value: self._on_centroid_changed(value, "x"))
        self._wrap_value_changed(self.centroid_y_label, lambda value: self._on_centroid_changed(value, "y"))
        self._wrap_value_changed(self.sigma_x_label, lambda value: self._on_sigma_changed(value, "x"))
        self._wrap_value_changed(self.sigma_y_label, lambda value: self._on_sigma_changed(value, "y"))
        self._wrap_value_changed(self.max_value_label, self._on_max_value_changed)
        self._wrap_value_changed(self.threshold_rbv_label, self._on_threshold_rbv_changed)
        self._labels_connected = True

    @staticmethod
    def _wrap_value_changed(label: PyDMLabel, callback):
        """Patch *label* to also invoke *callback* with each new value.

        PyDMLabel has no public "new value" signal, so value_changed is
        wrapped in place.
        """
        original = label.value_changed

        def wrapped(new_value, _original=original, _callback=callback):
            _original(new_value)
            _callback(new_value)

        label.value_changed = wrapped

    def _on_centroid_changed(self, value: float, axis: str):
        """Update the marker overlay from a new centroid readback (still relative to the source ROI)."""
        if value is None:
            return

        try:
            value = float(value)
            if axis == "x":
                self._centroid_x_raw = value
            else:
                self._centroid_y_raw = value
            self._update_absolute_centroid()

        except (ValueError, TypeError):
            logger.warning(f"Invalid centroid value received for {axis} axis: {value}")

    def _on_source_roi_offset_changed(self, value: float, axis: str) -> None:
        """Track the source ROI's live MinX/MinY and re-derive the absolute centroid when it moves."""
        if value is None:
            return
        try:
            value = float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid source ROI offset value received for {axis} axis: {value}")
            return

        if axis == "x":
            self._source_roi_min_x = value
        else:
            self._source_roi_min_y = value
        self._update_absolute_centroid()

    def _update_absolute_centroid(self) -> None:
        """Recompute the full-frame centroid from the last raw readback plus the source ROI offset."""
        if self._centroid_x_raw is not None:
            self._centroid_x = self._source_roi_min_x + self._centroid_x_raw
            self._marker.x = self._centroid_x
        if self._centroid_y_raw is not None:
            self._centroid_y = self._source_roi_min_y + self._centroid_y_raw
            self._marker.y = self._centroid_y

    def _on_sigma_changed(self, value: float, axis: str):
        if value is None:
            return

        try:
            value = float(value)
            if axis == "x":
                self._sigma_x = value
            else:
                self._sigma_y = value

            if self._use_sigma_radius:
                self._update_marker_radius_from_sigma()

        except (ValueError, TypeError):
            logger.warning(f"Invalid sigma value received for {axis} axis: {value}")

    def _update_marker_radius_from_sigma(self):
        if self._sigma_x is not None:
            self._marker.set_radius_x(self._sigma_x)
        if self._sigma_y is not None:
            self._marker.set_radius_y(self._sigma_y)

    def _on_max_value_changed(self, value: float) -> None:
        """Track the live MaxValue_RBV and keep the threshold live in the max-derived modes."""
        if value is None:
            return
        try:
            self._max_value = float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid MaxValue_RBV received: {value}")
            return
        self._sync_threshold_for_live_modes()

    def _on_threshold_rbv_changed(self, value: float) -> None:
        """Track the live CentroidThreshold_RBV, used to seed the raw-mode line edit."""
        if value is None:
            return
        try:
            self._threshold_rbv = float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid CentroidThreshold_RBV received: {value}")

    def _init_threshold_controls(self):
        """Wire up the threshold mode combo and value entry.

        All three modes write to the same CentroidThreshold PV. 1/e^2 and %
        of max are max-derived, so they're kept live (rewritten whenever
        MaxValue_RBV updates or the mode/% value changes); raw mode only
        writes on a committed line edit value.
        """
        self.threshold_mode_combo.addItems(["1/e² of Max", "% of Max", "Raw Pixel Intensity"])
        # Raw mode is the default (nothing changes on load); 1/e^2 only
        # (re)writes on a combo index *change*, so it can't start selected.
        self.threshold_mode_combo.setCurrentIndex(_THRESHOLD_MODE_RAW)
        self._threshold_value_validator = QDoubleValidator(0.0, 1e9, 4, self.threshold_value_edit)
        self.threshold_value_edit.setValidator(self._threshold_value_validator)
        self._apply_threshold_mode_ui(self.threshold_mode_combo.currentIndex())

        # Connected only after the setup above so no synthetic
        # currentIndexChanged signal from it can trigger a write.
        self.threshold_mode_combo.currentIndexChanged.connect(self._on_threshold_mode_changed)
        self.threshold_value_edit.editingFinished.connect(self._on_threshold_value_committed)

    def _apply_threshold_mode_ui(self, mode: int) -> None:
        """Update the value line edit's enabled state, validator range, and placeholder for *mode*.

        Cosmetic only (never writes to EPICS), so it's safe to call during init.
        """
        self.threshold_value_edit.setEnabled(mode != _THRESHOLD_MODE_ONE_OVER_E2)
        if mode == _THRESHOLD_MODE_PERCENT:
            self._threshold_value_validator.setRange(0.0, 100.0, 4)
            self.threshold_value_edit.setPlaceholderText("% of max")
            if not self.threshold_value_edit.text():
                self.threshold_value_edit.setText("10")
        elif mode == _THRESHOLD_MODE_RAW:
            self._threshold_value_validator.setRange(0.0, 1e9, 4)
            self.threshold_value_edit.setPlaceholderText("raw counts")
            if not self.threshold_value_edit.text() and self._threshold_rbv is not None:
                self.threshold_value_edit.setText(str(self._threshold_rbv))
        else:
            self.threshold_value_edit.setPlaceholderText("")

    def _on_threshold_mode_changed(self, mode: int) -> None:
        self._apply_threshold_mode_ui(mode)
        self._sync_threshold_for_live_modes()

    def _threshold_for_mode(self, mode: int) -> float | None:
        """Compute the raw threshold value for *mode*, or None if a required input isn't known yet.

        Raw mode has no derivation - it's written directly from the
        committed line edit text in _on_threshold_value_committed - so it
        always returns None here.
        """
        if mode == _THRESHOLD_MODE_ONE_OVER_E2:
            return None if self._max_value is None else self._max_value / math.e**2
        if mode == _THRESHOLD_MODE_PERCENT:
            if self._max_value is None:
                return None
            try:
                pct = float(self.threshold_value_edit.text())
            except (ValueError, TypeError):
                return None
            return self._max_value * pct / 100.0
        return None

    def _sync_threshold_for_live_modes(self) -> None:
        """Rewrite the threshold PV from the latest inputs while in the 1/e^2 or % of max mode.

        Called whenever MaxValue_RBV updates or the mode/% value changes so
        these two modes always track the current max.
        """
        mode = self.threshold_mode_combo.currentIndex()
        if mode not in (_THRESHOLD_MODE_ONE_OVER_E2, _THRESHOLD_MODE_PERCENT):
            return
        value = self._threshold_for_mode(mode)
        if value is None:
            logger.warning("Cannot compute threshold: missing MaxValue_RBV or invalid % value")
            return
        self._write_threshold(value)

    def _on_threshold_value_committed(self) -> None:
        """Write the committed line edit text for the % of max or raw threshold modes."""
        mode = self.threshold_mode_combo.currentIndex()
        if mode == _THRESHOLD_MODE_ONE_OVER_E2:
            return  # no line edit in this mode

        if mode == _THRESHOLD_MODE_PERCENT:
            self._sync_threshold_for_live_modes()
            return

        try:
            value = float(self.threshold_value_edit.text())
        except (ValueError, TypeError):
            logger.warning(f"Invalid threshold value entered: {self.threshold_value_edit.text()!r}")
            return
        self._write_threshold(value)

    def _write_threshold(self, value: float) -> None:
        self._threshold_writer.write(value)

    def get_threshold_state(self) -> dict:
        """Return the threshold mode and its associated line-edit value, for persistence."""
        return {
            "mode": self.threshold_mode_combo.currentIndex(),
            "value": self.threshold_value_edit.text(),
        }

    def set_threshold_state(self, state: dict) -> None:
        """Apply a previously-saved threshold_state."""
        if "value" in state:
            self.threshold_value_edit.setText(state["value"])
        if "mode" in state:
            mode = state["mode"]
            self.threshold_mode_combo.blockSignals(True)
            self.threshold_mode_combo.setCurrentIndex(mode)
            self.threshold_mode_combo.blockSignals(False)
            self._apply_threshold_mode_ui(mode)

    def get_view_saver_properties(self) -> dict:
        """Resolved ViewSaver getter/setter pairs for this widget's saved state.

        getter returns a QSettings-storable value
        setter accepts and applies raw stored value
        """

        return {
            "threshold": (
                lambda: json.dumps(self.get_threshold_state()),
                lambda raw: self.set_threshold_state(json.loads(raw)),
            ),
            "marker_style": (
                lambda: json.dumps(self.get_marker_style_state()),
                lambda raw: self.set_marker_style_state(json.loads(raw)),
            ),
            "roi_multiplier": (
                lambda: str(self.roi_multiplier_spinbox.value()),
                lambda raw: self.roi_multiplier_spinbox.setValue(float(raw)),
            ),
        }

    def _set_roi_from_centroid(self):
        """Calculate a centroid +/- multiplier*FWHM ROI and push it to the shared EPICS ROI PVs."""
        if None in (self._centroid_x, self._centroid_y, self._sigma_x, self._sigma_y):
            logger.warning("Cannot set ROI: missing centroid or sigma values")
            return

        multiplier = self.roi_multiplier_spinbox.value()
        fwhm_x = self._sigma_x * _FWHM_TO_SIGMA
        fwhm_y = self._sigma_y * _FWHM_TO_SIGMA
        roi_width = max(_MIN_ROI_SIZE, multiplier * fwhm_x)
        roi_height = max(_MIN_ROI_SIZE, multiplier * fwhm_y)
        roi_min_x = self._centroid_x - (roi_width / 2.0)
        roi_min_y = self._centroid_y - (roi_height / 2.0)

        for writer, value in (
            (self._roi_minx_writer, roi_min_x),
            (self._roi_miny_writer, roi_min_y),
            (self._roi_sizex_writer, roi_width),
            (self._roi_sizey_writer, roi_height),
        ):
            writer.write(value)

        self._sync_epics_roi_full_buttons()

    def _sync_epics_roi_full_buttons(self):
        """Show the ROI and drop move-mode on any EpicsRoiFull pointed at the same cam_prefix/roi_plugin.

        EpicsRoiFull is fully independent of this widget - found only by
        searching the shared top-level window - so this is a no-op if none
        match, and updates every match if more than one does.
        """
        cam_prefix = self.get_cam_prefix()
        roi_plugin = self.get_roi_plugin()
        for roi_widget in self.window().findChildren(EpicsRoiFull):
            if roi_widget.get_cam_prefix() != cam_prefix or roi_widget.get_roi_plugin() != roi_plugin:
                continue
            roi_widget.visibility_button.setChecked(True)
            roi_widget.move_enabled_button.setChecked(False)

    def link_parent_widgets(self, parent) -> None:
        """Attach the marker to the parent's PyDMImageView and, if given, mirror it onto a second view.

        The source ROI offset (correcting the raw readback into an
        absolute value) is read directly from EPICS via cam_prefix and
        source_roi_plugin. `secondary_image_view` (if given) mirrors the
        marker onto a second view, offset the same way via secondary_roi_plugin
        """
        if hasattr(parent, "image_view"):
            self._image_view = parent.image_view
        else:
            return

        try:
            plot_item = self._image_view.getView()
            self._view_box = plot_item.getViewBox()
        except Exception:
            logger.error("Could not get ViewBox for centroid overlays")
            return

        self._marker.attach(self._view_box)
        self._link_secondary_view(getattr(parent, "secondary_image_view", None))

    def _link_secondary_view(self, secondary_image_view) -> None:
        """Mirror the marker onto a second view, offset live by secondary_roi_plugin's MinX/MinY.

        Independent of the source ROI offset: that one corrects the raw
        readback into an absolute value; this one re-renders that same
        absolute value in a second view's own local frame.
        """
        if secondary_image_view is None:
            return

        try:
            plot_item = secondary_image_view.getView()
            self._secondary_view_box = plot_item.getViewBox()
        except Exception:
            logger.error("Could not get ViewBox for secondary centroid overlay")
            return

        self._marker.attach(self._secondary_view_box, offset=(self._secondary_offset_x, self._secondary_offset_y))
        self._secondary_view_linked = True
        self._rebuild_secondary_roi_channels()

    def _on_secondary_offset_x_changed(self, value: float) -> None:
        if value is None:
            return
        try:
            value = float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid secondary ROI offset value received for x axis: {value}")
            return
        self._secondary_offset_x = value
        self._marker.set_offset(self._secondary_view_box, self._secondary_offset_x, self._secondary_offset_y)

    def _on_secondary_offset_y_changed(self, value: float) -> None:
        if value is None:
            return
        try:
            value = float(value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid secondary ROI offset value received for y axis: {value}")
            return
        self._secondary_offset_y = value
        self._marker.set_offset(self._secondary_view_box, self._secondary_offset_x, self._secondary_offset_y)

    def _on_visibility_toggled(self, checked: bool):
        self._marker.set_visible(checked)
        self.state_changed.emit()

    def _on_color_changed(self, color: QColor) -> None:
        self._marker.set_color(color)
        self.state_changed.emit()

    def _open_style_dialog(self):
        marker = self._marker
        dlg = CentroidMarkerStyleDialog(
            current_style=marker.style,
            current_width=marker.width,
            current_hatch_pattern=marker.hatch_pattern,
            current_use_sigma_radius=self._use_sigma_radius,
            current_default_radius=self._default_radius,
            parent=self,
        )
        if dlg.exec_() == CentroidMarkerStyleDialog.Accepted:
            marker.set_style(dlg.selected_style)
            marker.set_width(dlg.selected_width)
            marker.set_hatch_pattern(dlg.selected_hatch_pattern)

            self._use_sigma_radius = dlg.use_sigma_radius
            self._default_radius = dlg.selected_default_radius

            if self._use_sigma_radius:
                self._update_marker_radius_from_sigma()
            else:
                marker.set_radius(self._default_radius)

            self.state_changed.emit()

    def get_marker_style_state(self) -> dict:
        """Return the centroid marker's full visual state, for persistence."""
        return {
            "color": self._marker.color.name(),
            "style": int(self._marker.style),
            "width": self._marker.width,
            "hatch_pattern": int(self._marker.hatch_pattern),
            "use_sigma_radius": self._use_sigma_radius,
            "default_radius": self._default_radius,
            "visible": self.centroid_visibility_button.isChecked(),
        }

    def set_marker_style_state(self, state: dict) -> None:
        """Apply a previously-saved marker_style_state."""
        if "color" in state:
            self._set_marker_color(QColor(state["color"]))
        if "style" in state:
            self._marker.set_style(MarkerStyle(state["style"]))
        if "width" in state:
            self._marker.set_width(state["width"])
        if "hatch_pattern" in state:
            self._marker.set_hatch_pattern(Qt.PenStyle(state["hatch_pattern"]))
        if "use_sigma_radius" in state:
            self._use_sigma_radius = state["use_sigma_radius"]
        if "default_radius" in state:
            self._default_radius = state["default_radius"]
        if self._use_sigma_radius:
            self._update_marker_radius_from_sigma()
        else:
            self._marker.set_radius(self._default_radius)
        if "visible" in state:
            self.centroid_visibility_button.setChecked(state["visible"])

    def _get_marker_color(self) -> QColor:
        return self._marker.color

    def _set_marker_color(self, color: QColor) -> None:
        self._marker.set_color(color)
        self.centroid_color_button.set_color(color)

    ## Property for marker color that can be overwritten in designer.

    def get_marker_color(self) -> QColor:
        return self._get_marker_color()

    def set_marker_color(self, color: QColor) -> None:
        self._set_marker_color(color)

    marker_color = pyqtProperty(QColor, get_marker_color, set_marker_color)

    def get_nickname(self) -> str:
        return self._nickname

    def set_nickname(self, value: str) -> None:
        self._nickname = value

    nickname = pyqtProperty(str, get_nickname, set_nickname)

    ## Property for the shared Camera ROI plugin (e.g. ":ROI2:")

    def get_roi_plugin(self) -> str:
        return self._roi_plugin

    def set_roi_plugin(self, value: str) -> None:
        self._roi_plugin = value
        self._rebuild_roi_channels()

    roi_plugin = pyqtProperty(str, get_roi_plugin, set_roi_plugin)

    ## Property identifying the source ROI plugin (e.g. ":ROI1:") that the
    ## primary readback is relative to.

    def get_source_roi_plugin(self) -> str:
        return self._source_roi_plugin

    def set_source_roi_plugin(self, value: str) -> None:
        self._source_roi_plugin = value
        self._rebuild_source_roi_channels()

    source_roi_plugin = pyqtProperty(str, get_source_roi_plugin, set_source_roi_plugin)

    ## Property identifying the ROI plugin feeding the secondary view, if
    ## one is linked.

    def get_secondary_roi_plugin(self) -> str:
        return self._secondary_roi_plugin

    def set_secondary_roi_plugin(self, value: str) -> None:
        self._secondary_roi_plugin = value
        if self._secondary_view_linked:
            self._rebuild_secondary_roi_channels()

    secondary_roi_plugin = pyqtProperty(str, get_secondary_roi_plugin, set_secondary_roi_plugin)
