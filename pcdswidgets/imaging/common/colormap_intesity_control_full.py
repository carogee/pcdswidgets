"""Module for ColormapIntesityControlFull"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

import json

import numpy as np
from pydm.widgets import PyDMImageView
from pydm.widgets.colormaps import PyDMColorMap, cmap_names, cmaps
from pyqtgraph import ColorMap
from pyqtgraph.widgets.HistogramLUTWidget import HistogramLUTWidget
from qtpy import QtCore, QtWidgets

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.generated.imaging.common.colormap_intesity_control_full_base import ColormapIntesityControlFullBase
from pcdswidgets.icons.glyphs import CAM_COG

_COLORMAP_ORDER = [
    PyDMColorMap.Inferno,
    PyDMColorMap.Hot,
    PyDMColorMap.Magma,
    PyDMColorMap.Plasma,
    PyDMColorMap.Viridis,
    PyDMColorMap.Jet,
    PyDMColorMap.Monochrome,
]


class ColormapIntesityControlFull(ColormapIntesityControlFullBase):
    colormap_combo: QtWidgets.QComboBox
    normalize_check: QtWidgets.QCheckBox
    histogram_container: QtWidgets.QWidget

    # Emitted once per user drag of the histogram that sets manual color-map levels
    state_changed = QtCore.Signal()

    designer_options = DesignerOptions(
        group="ECS Imaging Common",
        is_container=False,
        icon=CAM_COG,
    )

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._image_view: PyDMImageView | None = None
        self._secondary_image_view: PyDMImageView | None = None
        self._image_stream_paused = False
        self._graph_press_active = False
        self._user_level_drag = False

        for cmap_enum in _COLORMAP_ORDER:
            self.colormap_combo.addItem(cmap_names[cmap_enum], cmap_enum)

        # histogram widget for manual intensity control
        layout = QtWidgets.QVBoxLayout(self.histogram_container)
        layout.setContentsMargins(0, 0, 0, 0)
        self._histogram = HistogramLUTWidget(
            parent=self.histogram_container,
            orientation="horizontal",
        )
        layout.addWidget(self._histogram)

        # link callbacks for ui
        self.colormap_combo.currentIndexChanged.connect(self._on_colormap_changed)
        self.normalize_check.toggled.connect(self._on_normalize_toggled)

    def link_parent_widgets(self, parent: any) -> None:
        """
        Connect this config widget to a PyDMImageView.

        Called by the parent widget at adoption time. Links the histogram
        to the image item and syncs the UI state to current image settings.

        If the parent also carries a `secondary_image_view`, colormap,
        normalization, and level changes are mirrored onto it too, so both
        views always share the same appearance. The histogram itself stays
        bound only to the primary view.
        """
        if hasattr(parent, "image_view"):
            self._image_view = parent.image_view
        else:
            return
        self._secondary_image_view = getattr(parent, "secondary_image_view", None)

        # Link histogram to the image's ImageItem for live level control
        self._histogram.setImageItem(self._image_view.getImageItem())

        # update colormap on image to default
        idx = self.colormap_combo.currentIndex()
        self._on_colormap_changed(idx)

        # Pause incoming frames while left mouse is held in histogram graph area.
        self._histogram.viewport().installEventFilter(self)

        # When histogram levels change, update the image view's colormap limits
        self._histogram.sigLevelChangeFinished.connect(self._on_levels_changed)

    def _pause_image_stream(self) -> None:
        if self._image_view is None or self._image_stream_paused:
            return

        image_channel = getattr(self._image_view, "_imagechannel", None)
        if image_channel is None:
            return

        image_channel.disconnect()
        self._image_stream_paused = True

    def _resume_image_stream(self) -> None:
        if self._image_view is None or not self._image_stream_paused:
            return

        image_channel = getattr(self._image_view, "_imagechannel", None)
        if image_channel is not None:
            image_channel.connect()
        self._image_stream_paused = False

    def eventFilter(self, obj, event) -> bool:
        if obj is self._histogram.viewport():
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.LeftButton:
                    self._graph_press_active = True
                    self._user_level_drag = True
                    self._pause_image_stream()
            elif event.type() == QtCore.QEvent.MouseButtonRelease:
                if event.button() == QtCore.Qt.LeftButton and self._graph_press_active:
                    self._graph_press_active = False
                    self._resume_image_stream()
                    # The drag's final sigLevelChangeFinished only lands once the scene
                    # sees this release, i.e. after this filter, so unlatch a turn later.
                    QtCore.QTimer.singleShot(0, self._end_user_level_drag)
        return super().eventFilter(obj, event)

    def _end_user_level_drag(self) -> None:
        self._user_level_drag = False

    def _sync_histogram_gradient(self, cmap_enum) -> None:
        """Set the histogram gradient to match the given colormap."""
        cm_colors = cmaps[cmap_enum]
        pos = np.linspace(0.0, 1.0, num=len(cm_colors))
        colormap = ColorMap(pos, cm_colors)
        self._histogram.item.gradient.setColorMap(colormap)

    def _linked_image_views(self):
        """The primary image view plus the secondary one, if linked."""
        return [v for v in (self._image_view, self._secondary_image_view) if v is not None]

    def _on_colormap_changed(self, index: int) -> None:
        if self._image_view is None:
            return
        cmap_enum = self.colormap_combo.itemData(index)
        if cmap_enum is None:
            return
        for image_view in self._linked_image_views():
            image_view._setColorMap(cmap_enum)
        self._sync_histogram_gradient(cmap_enum)

    def _on_normalize_toggled(self, checked: bool) -> None:
        if self._image_view is None:
            return
        for image_view in self._linked_image_views():
            image_view.setNormalizeData(checked)
            image_view.needs_redraw = True
            image_view.redrawImage()

    def _on_levels_changed(self, hist_item) -> None:
        """
        Update image view min/max when the user drags histogram levels.

        Changes the user did not make are ignored: pyqtgraph also emits
        sigLevelChangeFinished when the histogram re-syncs to the image item's
        levels, which PyDM does every frame while normalize is on.
        """
        if self._image_view is None or not self._user_level_drag:
            return
        mn, mx = hist_item.getLevels()
        for image_view in self._linked_image_views():
            image_view.setColorMapLimits(mn, mx)
        self.state_changed.emit()

    def get_levels(self) -> tuple[float, float]:
        """Return the histogram's current (min, max) color-map levels, for persistence."""
        mn, mx = self._histogram.item.getLevels()
        return float(mn), float(mx)

    def set_levels(self, mn: float, mx: float) -> None:
        """Apply a previously-saved (min, max) level pair."""
        self._histogram.item.setLevels(mn, mx)
        for image_view in self._linked_image_views():
            image_view.setColorMapLimits(mn, mx)

    def get_view_saver_properties(self) -> dict:
        """Resolved ViewSaver getter/setter pairs for this widget's saved state.

        getter returns a QSettings-storable value
        setter accepts and applies raw stored value
        """
        return {
            "colormap_index": (
                lambda: str(self.colormap_combo.currentIndex()),
                lambda raw: self.colormap_combo.setCurrentIndex(int(raw)),
            ),
            "normalize": (
                lambda: json.dumps(self.normalize_check.isChecked()),
                lambda raw: self.normalize_check.setChecked(json.loads(raw)),
            ),
            "levels": (
                lambda: json.dumps(self.get_levels()),
                lambda raw: self.set_levels(*json.loads(raw)),
            ),
        }
