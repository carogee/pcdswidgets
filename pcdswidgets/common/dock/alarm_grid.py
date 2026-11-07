"""
A configurable matrix of device-status indicators.

``AlarmGrid`` lays out a table of device *categories* (rows, grouped under
bold section headers) against *locations* (columns).  Each interior cell shows
a single status box whose color reflects the **worst** EPICS alarm severity of
the devices configured for that category + location.  Clicking a category's
name (or any of its status boxes) pops up a dropdown ``QMenu`` -- in the same
style as the LFE ``IndicatorGrid`` device menu -- listing that category's
individual devices with their status icons and location; triggering a menu
entry opens that device's detailed PyDM screen.

The grid is driven entirely by a YAML config file (the ``configFile``
property), so there is no happi/typhos dependency -- any PV whose alarm
severity reflects device health can be used.

Config format::

    columns: [EBD, FEE]
    rows:
      - section: OPTICS SYSTEM          # bold header row, no cells
      - category: Mirrors
        cells:
          FEE:
            - {name: MR1L0, channel: "ca://XCS:...:STATUS",
               detail: "mirror.ui", macros: {P: "XCS:..."}}
          EBD: []
      - category: Slits
        cells:
          EBD:
            - {name: SL1L0, channel: "ca://XCS:...:STATUS"}

The color palette matches the Carbon Design System "Gray 10" theme
(``carbon_gray10.qss``): success green, warning yellow, error red, and a blank
box for disconnected / invalid.
"""

from __future__ import annotations

import enum
import functools
import logging
import os
from datetime import datetime
from typing import Any

import yaml
from pydm.utilities import find_file, is_qt_designer
from pydm.widgets import PyDMEmbeddedDisplay
from pydm.widgets.channel import PyDMChannel
from qtpy.QtCore import Property, QObject, QSize, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class StatusLevel(enum.IntEnum):
    """
    Device alarm state, mirroring PyDM / typhos severity levels.

    Values match PyDM's ``ALARM_*`` constants and typhos' ``AlarmLevel``:
    ``NO_ALARM=0, MINOR=1, MAJOR=2, INVALID=3, DISCONNECTED=4``.  The integer
    ordering is the "badness" order used by :meth:`worst` (DISCONNECTED ranks
    highest, as in typhos).
    """

    NO_ALARM = 0
    MINOR = 1
    MAJOR = 2
    INVALID = 3
    DISCONNECTED = 4

    @classmethod
    def from_severity(cls, severity: int | None, connected: bool = True) -> "StatusLevel":
        """
        Map an EPICS alarm severity + connection state to a ``StatusLevel``.

        Parameters
        ----------
        severity : int or None
            The EPICS alarm severity: 0 = NO_ALARM, 1 = MINOR, 2 = MAJOR,
            3 = INVALID.  ``None`` (no value yet) maps to ``DISCONNECTED``.
        connected : bool
            Whether the channel is connected.  A disconnected channel is always
            ``DISCONNECTED`` regardless of its last-known severity.
        """
        if not connected or severity is None:
            return cls.DISCONNECTED
        return cls(min(int(severity), int(cls.INVALID)))

    @classmethod
    def worst(cls, levels: "list[StatusLevel]") -> "StatusLevel":
        """Return the most severe level in ``levels`` (``NO_ALARM`` if empty)."""
        if not levels:
            return cls.NO_ALARM
        return max(levels)


# PyDM alarm palette (from pydm/default_stylesheet.qss): (fill, glyph, border,
# text_color).  Matches PyDM's 5-state alarm coloring.  DISCONNECTED uses a gray
# border so the white fill stays legible on the light carbon_gray10 page.
_LEVEL_STYLE: dict[StatusLevel, tuple[str, str, str, str]] = {
    StatusLevel.NO_ALARM: ("#00EB00", "✓", "#00EB00", "#000000"),      # green
    StatusLevel.MINOR: ("#EBEB00", "!", "#EBEB00", "#000000"),         # yellow
    StatusLevel.MAJOR: ("#FF0000", "✗", "#FF0000", "#FFFFFF"),         # red
    StatusLevel.INVALID: ("#EB00EB", "?", "#EB00EB", "#FFFFFF"),       # magenta
    StatusLevel.DISCONNECTED: ("#FFFFFF", "—", "#9aa0a5", "#55606a"),  # white
}

# Word labels shown in the large aggregate cell box (the small dropdown-menu
# icons keep the glyphs from _LEVEL_STYLE above).
_LEVEL_TEXT: dict[StatusLevel, str] = {
    StatusLevel.NO_ALARM: "OK",
    StatusLevel.MINOR: "Warning",
    StatusLevel.MAJOR: "Error",
    StatusLevel.INVALID: "Invalid",
    StatusLevel.DISCONNECTED: "Disconnected",
}


def status_icon(level: "StatusLevel", size: int = 16) -> QIcon:
    """Build a circular status-colored :class:`QIcon` for a menu entry."""
    fill, glyph, border, text_color = _LEVEL_STYLE[level]
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    rect = pixmap.rect().adjusted(1, 1, -1, -1)
    painter.setBrush(QColor(fill))
    painter.setPen(QPen(QColor(border), 1))
    painter.drawEllipse(rect)
    painter.setPen(QColor(text_color))
    font = painter.font()
    font.setBold(True)
    font.setPointSize(max(7, int(size * 0.55)))
    painter.setFont(font)
    painter.drawText(rect, Qt.AlignCenter, glyph)
    painter.end()
    return QIcon(pixmap)


class StatusIndicator(QWidget):
    """
    The large aggregate status box for a grid cell.

    Drawn with square corners (no border radius) to match the Carbon theme and
    labelled with the status word ("OK" / "Warning" / "Error" / "Disconnected").
    A cell with no configured devices renders as an empty box (no word).  The
    ``level`` property drives a repaint; emits :attr:`clicked` on a left press.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, *, size: int = 18, stretch: bool = False):
        super().__init__(parent)
        self._level = StatusLevel.NO_ALARM
        self._empty = False
        self._size = size
        if stretch:
            # Fixed height, free to grow in width (used for the cell aggregate box).
            self.setFixedHeight(size)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            # Wide enough that the longest status word ("Disconnected") fits.
            self.setMinimumWidth(
                QFontMetrics(self._label_font()).horizontalAdvance(_LEVEL_TEXT[StatusLevel.DISCONNECTED]) + 16
            )
        else:
            self.setFixedSize(size, size)

    def _label_font(self) -> QFont:
        font = QFont()
        font.setBold(True)
        font.setPointSize(max(8, int(self._size * 0.5)))
        return font

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

    def sizeHint(self) -> QSize:
        return QSize(self._size, self._size)

    def get_level(self) -> StatusLevel:
        return self._level

    def set_level(self, level: StatusLevel) -> None:
        level = StatusLevel(level)
        if level != self._level:
            self._level = level
            self.setToolTip("" if self._empty else _LEVEL_TEXT[self._level])
            self.update()

    # designable=False: this is a runtime-driven display property, not something
    # to set in Qt Designer.
    level = Property(int, get_level, set_level, designable=False)

    def set_empty(self, empty: bool) -> None:
        """Mark the box as having no devices, so it renders blank (no word)."""
        if empty != self._empty:
            self._empty = empty
            self.setToolTip("" if self._empty else _LEVEL_TEXT[self._level])
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = self.rect().adjusted(1, 1, -1, -1)

        if self._empty:
            # No devices configured: a neutral blank box, no word.
            painter.setBrush(QColor("#f4f4f4"))
            painter.setPen(QPen(QColor("#e0e0e0"), 1))
            painter.drawRect(rect)
            painter.end()
            return

        fill, _glyph, border, text_color = _LEVEL_STYLE[self._level]
        painter.setBrush(QColor(fill))
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRect(rect)

        painter.setPen(QColor(text_color))
        painter.setFont(self._label_font())
        painter.drawText(rect, Qt.AlignCenter, _LEVEL_TEXT[self._level])
        painter.end()


class DeviceStatus(QObject):
    """
    The model for one device: its PV channel(s), derived status, detail screen.

    A device may monitor one PV or several (e.g. the four blades of a slit).
    Each address gets its own :class:`PyDMChannel`; the device's :attr:`level`
    is the **worst** status across all of them, so a single menu entry can
    represent a multi-PV device.  Emits :attr:`changed` whenever the computed
    level may have changed so the parent cell can recompute its aggregate.  It
    is not a widget -- the devices are presented as entries in the category
    :class:`QMenu` dropdown.
    """

    changed = Signal()

    def __init__(
        self,
        name: str,
        channels: "str | list[str]",
        *,
        detail: str | None = None,
        macros: dict[str, Any] | None = None,
        typhos_name: str | None = None,
        location: str = "",
        category: str = "",
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.name = name
        # Normalize to a list of addresses; a device may watch 1..N PVs.
        if isinstance(channels, str):
            self.addresses = [channels] if channels else []
        else:
            self.addresses = [c for c in channels if c]
        self.detail = detail
        self.macros = macros or {}
        self.typhos_name = typhos_name
        self.location = location
        self.category = category

        # Acknowledgement state (in-session; cleared when the alarm clears).
        self.acknowledged = False
        self.ack_time: datetime | None = None

        # Per-address (severity, connected) state, keyed by address.
        self._state: dict[str, tuple[int | None, bool]] = dict.fromkeys(self.addresses, (None, False))
        self._display: QWidget | None = None
        self.channels: list[PyDMChannel] = []

    @property
    def level(self) -> StatusLevel:
        """The worst :class:`StatusLevel` across this device's PV(s)."""
        return StatusLevel.worst(
            [StatusLevel.from_severity(sev, conn) for sev, conn in self._state.values()]
        )

    @property
    def ackable(self) -> bool:
        """True if this device is in an alarm state that can be acknowledged."""
        return self.level != StatusLevel.NO_ALARM

    def acknowledge(self, when: datetime | None = None) -> None:
        """Mark this device's alarm acknowledged, stamping the time."""
        if not self.ackable:
            return
        self.acknowledged = True
        self.ack_time = when or datetime.now()
        self.changed.emit()

    def menu_text(self) -> str:
        """The label shown for this device in the dropdown menu."""
        if self.location:
            return f"{self.name}    ({self.location})"
        return self.name

    def create_channel(self) -> None:
        """Connect the PV channel(s).  Call only on a live (non-designer) screen."""
        if self.channels or not self.addresses:
            return
        for address in self.addresses:
            channel = PyDMChannel(
                address=address,
                connection_slot=functools.partial(self._connection_changed, address),
                severity_slot=functools.partial(self._severity_changed, address),
            )
            channel.connect()
            self.channels.append(channel)

    def destroy_channel(self) -> None:
        for channel in self.channels:
            channel.disconnect()
        self.channels = []

    def _connection_changed(self, address: str, conn: bool) -> None:
        sev, _ = self._state.get(address, (None, False))
        self._state[address] = (sev, conn)
        self._state_changed()

    def _severity_changed(self, address: str, severity: int) -> None:
        _, conn = self._state.get(address, (None, False))
        self._state[address] = (severity, conn)
        self._state_changed()

    def set_status(self, severity: int | None, connected: bool, address: str | None = None) -> None:
        """
        Set the (severity, connected) state for one of this device's addresses.

        Intended for testing / programmatic updates; the live callbacks use
        :meth:`_severity_changed` / :meth:`_connection_changed` per address.
        ``address`` defaults to the device's first address.
        """
        if address is None:
            if not self.addresses:
                return
            address = self.addresses[0]
        self._state[address] = (severity, connected)
        self._state_changed()

    def _state_changed(self) -> None:
        """Clear a stale acknowledgement if the alarm cleared, then notify."""
        if self.acknowledged and self.level == StatusLevel.NO_ALARM:
            self.acknowledged = False
            self.ack_time = None
        self.changed.emit()

    def open_detail(self) -> None:
        """
        Open this device's detail screen, docking it like the KFE/LFE home.

        A ``detail`` PyDM ``.ui`` (opened with macro substitution) takes
        precedence; if none is configured, fall back to the Typhos device
        display named by ``typhos_name`` (a happi device name).  Does nothing
        if neither is configured.

        The screen is handed to a :class:`TabDock` via
        ``add_to_dock_user_keybinds`` -- exactly how ``IndicatorGrid`` opens
        device screens on the KFE home screen -- so it docks as a tab (Ctrl =
        new tab, Shift = new window).  If no ``TabDock`` exists on the screen,
        we fall back to a floating window.
        """
        if self.detail:
            builder = self._build_ui_display
        elif self.typhos_name:
            # Fail fast (and quietly) if the optional deps are missing, so we
            # never hand the dock a builder that will raise.
            try:
                import happi  # noqa: F401
                import typhos  # noqa: F401
            except ImportError:
                logger.error("Cannot open Typhos screen for %s: happi/typhos not available", self.name)
                return
            builder = self._build_typhos_display
        else:
            return
        self._dock(builder)

    def _dock(self, builder) -> None:
        """Dock the builder's widget into the TabDock, or float it if none."""
        from pcdswidgets.common.dock.tab_dock import TabDock

        if TabDock.dock_exists():
            TabDock.add_to_dock_user_keybinds(widget=builder, title=self.name)
        else:
            # No dock on this screen: build and show as a standalone window.
            widget = builder()
            if widget is not None:
                self._display = widget
                widget.show()
                widget.raise_()

    def _build_typhos_display(self) -> "QWidget | None":
        """Build a Typhos device display, loaded from happi by name."""
        # Reuse the IndicatorGrid helpers so we get the same client caching and
        # display construction the KFE/LFE home screen uses.
        from pcdswidgets.common.dock.indicator_grid import display_for_device, get_happi_client

        try:
            results = get_happi_client().search(name=self.typhos_name)
            if not results:
                logger.error("No happi device named %r for %s", self.typhos_name, self.name)
                return None
            display = display_for_device(results[0].get())
        except Exception:
            logger.exception("Failed to open Typhos screen for %s (%s)", self.name, self.typhos_name)
            return None
        display.setWindowTitle(self.name)
        return display

    def _build_ui_display(self) -> QWidget:
        """Build the configured PyDM ``.ui`` detail screen with macros."""
        display = PyDMEmbeddedDisplay()
        macros = self.macros
        if isinstance(macros, dict):
            import json

            macros = json.dumps(macros)
        display.set_macros_and_filename(self.detail, macros)
        display.setWindowTitle(self.name)
        return display


class AlarmGridCell(QWidget):
    """
    A single interior cell of the grid.

    Shows one aggregate :class:`StatusIndicator` reflecting the worst status of
    its child devices.  The individual devices are presented as entries in the
    row's :class:`CategoryMenu` dropdown, not inline.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.devices: list[DeviceStatus] = []

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(2)

        # Aggregate box stretches across the cell width like the mockup.
        self.aggregate = StatusIndicator(self, size=20, stretch=True)
        self._layout.addWidget(self.aggregate)

    def add_device(self, device: DeviceStatus) -> None:
        self.devices.append(device)
        device.changed.connect(self.update_aggregate)

    def update_aggregate(self) -> None:
        """Recompute the aggregate indicator from the children's levels."""
        self.aggregate.set_empty(not self.devices)
        self.aggregate.set_level(StatusLevel.worst([d.level for d in self.devices]))

    def create_channels(self) -> None:
        for device in self.devices:
            device.create_channel()
        self.update_aggregate()

    def destroy_channels(self) -> None:
        for device in self.devices:
            device.destroy_channel()


class CategoryMenu(QMenu):
    """
    A dropdown :class:`QMenu` listing the devices of one category.

    Pops up at the cursor when the category name (or any of its status boxes)
    is clicked, in the same style as the LFE ``IndicatorGrid`` device menu.
    Each entry carries a colored status icon + the device name (with its
    location); triggering an entry opens that device's detail screen.  The
    entries are rebuilt on ``aboutToShow`` so their status icons reflect the
    current alarm level.
    """

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(title, parent)
        self._devices: list[DeviceStatus] = []
        # A bold, non-clickable title row at the top of the menu.
        self._title_action = self.addAction(title)
        self._title_action.setEnabled(False)
        font = self._title_action.font()
        font.setBold(True)
        self._title_action.setFont(font)
        self.addSeparator()
        self.aboutToShow.connect(self._refresh_icons)

    def add_devices(self, devices: "list[DeviceStatus]") -> None:
        """Add device entries to the menu."""
        for device in devices:
            self._devices.append(device)
            action = self.addAction(device.menu_text())
            action.setData(device)
            action.triggered.connect(device.open_detail)

    def has_content(self) -> bool:
        """True if any device was added to the menu."""
        return bool(self._devices)

    def _refresh_icons(self) -> None:
        """Update each entry's status icon to the device's current level."""
        for action in self.actions():
            device = action.data()
            if isinstance(device, DeviceStatus):
                action.setIcon(status_icon(device.level))


class _ListTable(QTableWidget):
    """
    QTableWidget whose Device column never gets condensed.

    Every other column sizes to its content; the Device column takes all the
    remaining width but never shrinks below ``device_min`` (a horizontal
    scrollbar appears instead), so device names stay readable even when the
    widget is narrow.
    """

    device_col = 1
    device_min = 160

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_device_column()

    def fit_device_column(self) -> None:
        others = sum(
            self.columnWidth(c) for c in range(self.columnCount()) if c != self.device_col
        )
        avail = self.viewport().width() - others
        self.setColumnWidth(self.device_col, max(self.device_min, avail))


class AlarmGrid(QWidget):
    """
    A matrix of device-status indicators, configured from a YAML file.

    Set the ``configFile`` property to a YAML file (see the module docstring
    for the format) to populate the grid.  Rows are device categories grouped
    under bold section headers; columns are locations.  Each category row has a
    dropdown triangle; clicking a category name (or any of its status boxes)
    pops up a :class:`QMenu` listing that category's individual devices, in the
    same style as the LFE ``IndicatorGrid`` device menu.  Triggering a menu
    entry opens that device's detail screen.
    """

    _qt_designer_ = {
        "group": "ECS Common",
        "is_container": False,
    }

    # List-view columns.
    _COL_STATE, _COL_DEVICE, _COL_CATEGORY, _COL_LOCATION, _COL_STATUS, _COL_ACK, _COL_ACKTIME = range(7)
    _LIST_HEADERS = ["", "Device", "Category", "Location", "Status", "Ack", "Ack Time"]
    _ACK_TIME_FMT = "%Y-%m-%d %H:%M:%S"

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._config_file = ""
        self._columns: list[str] = []
        # category title -> list of its cells (one per column)
        self._row_cells: dict[str, list[AlarmGridCell]] = {}
        # category title -> its device dropdown menu / header widget
        self._row_menus: dict[str, CategoryMenu] = {}
        self._row_headers: dict[str, QWidget] = {}
        self._channels: list[PyDMChannel] = []
        # True once we have successfully built from the config; lets showEvent
        # retry a build that failed earlier because the parent display (and thus
        # the base path for relative config paths) was not available yet.
        self._built = False
        # List-view sort state: default = Status column, descending (worst first).
        self._sort_col = self._COL_STATUS
        self._sort_desc = True

        # Outer layout: a top bar with the Grid/List toggle, then a stack of the
        # two views.
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)
        outer.addLayout(self._build_toggle_bar())

        self._stack = QStackedWidget(self)
        outer.addWidget(self._stack)

        # Page 0: the matrix ("grid") view.
        self._grid_container = QWidget()
        self.grid = QGridLayout(self._grid_container)
        self.grid.setContentsMargins(6, 6, 6, 6)
        self.grid.setHorizontalSpacing(1)
        self.grid.setVerticalSpacing(1)
        self._stack.addWidget(self._grid_container)

        # Page 1: the sortable, acknowledgeable "list" view.
        self._stack.addWidget(self._build_list_view())

        # Coalesce bursts of channel updates into one list refresh.
        self._list_timer = QTimer(self)
        self._list_timer.setSingleShot(True)
        self._list_timer.setInterval(50)
        self._list_timer.timeout.connect(self._refresh_list)

    # -- view toggle + list view construction -----------------------------
    def _build_toggle_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.setContentsMargins(6, 2, 6, 0)
        bar.addStretch()
        self._view_buttons = QButtonGroup(self)
        self._view_buttons.setExclusive(True)
        for idx, text in ((0, "⊞ Grid"), (1, "≡ List")):
            btn = QToolButton(self)
            btn.setText(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setChecked(idx == 0)
            btn.clicked.connect(lambda _c=False, i=idx: self._set_view(i))
            self._view_buttons.addButton(btn, idx)
            bar.addWidget(btn)
        return bar

    def _set_view(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        btn = self._view_buttons.button(index)
        if btn is not None:
            btn.setChecked(True)
        if index == 1:
            self._refresh_list()

    def _build_list_view(self) -> QWidget:
        container = QWidget()
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(6, 2, 6, 6)
        vbox.setSpacing(4)

        controls = QHBoxLayout()
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter devices…")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.setMaximumWidth(240)
        self._filter_edit.textChanged.connect(self._apply_filter)
        controls.addWidget(self._filter_edit)

        self._ack_all_btn = QPushButton("Ack all (0)")
        self._ack_all_btn.setCursor(Qt.PointingHandCursor)
        self._ack_all_btn.clicked.connect(self._acknowledge_all)
        controls.addWidget(self._ack_all_btn)

        controls.addStretch()
        self._count_label = QLabel("0 devices")
        self._count_label.setStyleSheet("QLabel { color: #525252; }")
        controls.addWidget(self._count_label)
        vbox.addLayout(controls)

        self._table = _ListTable(0, len(self._LIST_HEADERS))
        self._table.device_col = self._COL_DEVICE
        self._table.setHorizontalHeaderLabels(self._LIST_HEADERS)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QTableWidget.NoSelection)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setShowGrid(False)
        header = self._table.horizontalHeader()
        # Every column hugs its content; the Device column (handled by
        # _ListTable) takes the slack but never collapses below its minimum.
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self._COL_DEVICE, QHeaderView.Interactive)
        header.setSectionsClickable(True)
        header.sectionClicked.connect(self._on_header_clicked)
        self._table.cellClicked.connect(self._on_cell_clicked)
        vbox.addWidget(self._table)
        self._row_devices: list[DeviceStatus] = []
        return container

    # -- list view data / sorting -----------------------------------------
    def _sorted_devices(self) -> list[DeviceStatus]:
        """All devices ordered by the current list-view sort."""
        devices = list(self._iter_devices())
        col, desc = self._sort_col, self._sort_desc
        # Stable multi-pass: apply least-significant key first.
        devices.sort(key=lambda d: d.name.lower())
        if col in (self._COL_STATE, self._COL_STATUS):
            # Within a severity, unacked rows always above acked ones, so acking
            # sinks an alarm to the bottom of its severity band.
            devices.sort(key=lambda d: d.acknowledged)
            devices.sort(key=lambda d: d.level.value, reverse=desc)
        elif col == self._COL_CATEGORY:
            devices.sort(key=lambda d: d.category.lower(), reverse=desc)
        elif col == self._COL_LOCATION:
            devices.sort(key=lambda d: d.location.lower(), reverse=desc)
        elif col == self._COL_ACK:
            devices.sort(key=lambda d: d.acknowledged, reverse=desc)
        elif col == self._COL_ACKTIME:
            devices.sort(key=lambda d: d.ack_time or datetime.min, reverse=desc)
        else:  # _COL_DEVICE
            devices.sort(key=lambda d: d.name.lower(), reverse=desc)
        return devices

    def _schedule_list_refresh(self) -> None:
        """Coalesce channel-update bursts into a single list refresh."""
        if hasattr(self, "_list_timer"):
            self._list_timer.start()

    def _refresh_list(self) -> None:
        if not hasattr(self, "_table"):
            return
        devices = self._sorted_devices()
        self._row_devices = devices
        table = self._table
        table.setRowCount(len(devices))
        for row, device in enumerate(devices):
            self._fill_list_row(row, device)
        count = len(devices)
        self._count_label.setText(f"{count} device{'' if count == 1 else 's'}")
        self._update_ack_all()
        self._apply_filter(self._filter_edit.text())
        self._table.fit_device_column()

    def _fill_list_row(self, row: int, device: DeviceStatus) -> None:
        table = self._table
        level = device.level
        fill, _glyph, _border, _text = _LEVEL_STYLE[level]

        state_item = QTableWidgetItem()
        state_item.setIcon(status_icon(level))
        state_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, self._COL_STATE, state_item)

        # The device name is a clickable link to its detail screen.
        device_item = QTableWidgetItem(device.name)
        if device.detail or device.typhos_name:
            device_item.setForeground(QColor("#0f62fe"))
            device_item.setToolTip("Open detail screen")
        table.setItem(row, self._COL_DEVICE, device_item)
        table.setItem(row, self._COL_CATEGORY, QTableWidgetItem(device.category))
        table.setItem(row, self._COL_LOCATION, QTableWidgetItem(device.location))

        status_item = QTableWidgetItem(_LEVEL_TEXT[level])
        status_item.setForeground(QColor(fill))
        font = status_item.font()
        font.setBold(True)
        status_item.setFont(font)
        table.setItem(row, self._COL_STATUS, status_item)

        # Acknowledge checkbox (centered), enabled only for active alarms.
        wrapper = QWidget()
        box = QHBoxLayout(wrapper)
        box.setContentsMargins(0, 0, 0, 0)
        box.addStretch()
        cb = QCheckBox()
        cb.setEnabled(device.ackable)
        cb.setChecked(device.acknowledged)
        cb.toggled.connect(functools.partial(self._on_ack_toggled, device))
        box.addWidget(cb)
        box.addStretch()
        table.setCellWidget(row, self._COL_ACK, wrapper)

        ack_text = device.ack_time.strftime(self._ACK_TIME_FMT) if device.ack_time else ""
        table.setItem(row, self._COL_ACKTIME, QTableWidgetItem(ack_text))

    def _on_ack_toggled(self, device: DeviceStatus, checked: bool) -> None:
        if checked:
            device.acknowledge()
        elif device.acknowledged:
            device.acknowledged = False
            device.ack_time = None
            device.changed.emit()

    def _on_cell_clicked(self, row: int, col: int) -> None:
        """Clicking a device name opens that device's detail screen."""
        if col == self._COL_DEVICE and 0 <= row < len(self._row_devices):
            self._row_devices[row].open_detail()

    def _on_header_clicked(self, col: int) -> None:
        if col == self._sort_col:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_col = col
            # Severity / ack columns default to "most-notable first".
            self._sort_desc = col in (self._COL_STATE, self._COL_STATUS, self._COL_ACK, self._COL_ACKTIME)
        self._refresh_list()

    def _apply_filter(self, text: str) -> None:
        needle = (text or "").strip().lower()
        for row, device in enumerate(self._row_devices):
            haystack = " ".join(
                [device.name, device.category, device.location, _LEVEL_TEXT[device.level]]
            ).lower()
            self._table.setRowHidden(row, bool(needle) and needle not in haystack)

    def _update_ack_all(self) -> None:
        pending = sum(1 for d in self._iter_devices() if d.ackable and not d.acknowledged)
        self._ack_all_btn.setText(f"Ack all ({pending})")
        self._ack_all_btn.setEnabled(pending > 0)

    def _acknowledge_all(self) -> None:
        now = datetime.now()
        for device in self._iter_devices():
            if device.ackable and not device.acknowledged:
                device.acknowledge(now)
        self._refresh_list()

    # -- PyDM contract ----------------------------------------------------
    def channels(self) -> list[PyDMChannel]:
        """Tell PyDM about our channels so it closes them at exit."""
        return self._channels

    # -- configFile property ---------------------------------------------
    def get_config_file(self) -> str:
        return self._config_file

    def set_config_file(self, filename: str) -> None:
        self._config_file = filename
        self.rebuild()

    configFile = Property(str, get_config_file, set_config_file)

    def showEvent(self, event):
        """
        Retry the build when first shown.

        When a ``.ui`` is loaded, ``configFile`` is set before this widget is
        parented into the display, so a relative config path cannot be resolved
        against the parent display's directory yet.  By the time we are shown,
        the parent display is available, so retry the build if it has not
        succeeded.
        """
        super().showEvent(event)
        if not self._built and self._config_file:
            self.rebuild()

    # -- path resolution --------------------------------------------------
    def _find_parent_display(self):
        """Walk up the parent chain to the enclosing PyDM Display, if any."""
        from pydm import Display

        widget = self.parent()
        while widget is not None:
            if isinstance(widget, Display):
                return widget
            widget = widget.parent()
        return None

    def _resolve_config_path(self) -> str | None:
        """
        Resolve ``configFile`` to an absolute path.

        Searches (via :func:`pydm.utilities.find_file`) the parent display's
        directory first, then the Qt Designer form path, the current working
        directory, and ``PYDM_DISPLAYS_PATH`` -- the same order PyDM uses for
        embedded displays.
        """
        if not self._config_file:
            return None
        if os.path.isabs(self._config_file):
            return self._config_file if os.path.exists(self._config_file) else None

        base_path = ""
        parent_display = self._find_parent_display()
        if parent_display is not None:
            try:
                base_path = os.path.dirname(parent_display.loaded_file())
            except Exception:
                base_path = ""
        return find_file(self._config_file, base_path=base_path) or None

    # -- building ---------------------------------------------------------
    def _clear(self) -> None:
        for device in self._iter_devices():
            device.destroy_channel()
            device.setParent(None)
            device.deleteLater()
        for menu in self._row_menus.values():
            menu.setParent(None)
            menu.deleteLater()
        self._channels = []
        self._row_cells = {}
        self._row_menus = {}
        self._row_headers = {}
        self._columns = []
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _iter_devices(self):
        for cells in self._row_cells.values():
            for cell in cells:
                yield from cell.devices

    def _load_config(self, path: str) -> dict | None:
        try:
            with open(path) as fp:
                return yaml.safe_load(fp)
        except Exception:
            logger.exception("Failed to load AlarmGrid config %s", path)
            return None

    def _load_resolved_config(self) -> "tuple[dict, str] | None":
        """Resolve + load the config file, returning ``(config, base_dir)``."""
        if not self._config_file:
            return None
        path = self._resolve_config_path()
        if not path:
            # Could not locate the file yet.  If we have a parent display this
            # is a real error; otherwise showEvent() will retry once attached.
            if self._find_parent_display() is not None or is_qt_designer():
                logger.error("AlarmGrid could not find config file %r", self._config_file)
            return None
        config = self._load_config(path)
        if not config:
            return None
        return config, os.path.dirname(os.path.abspath(path))

    def rebuild(self) -> None:
        """Clear and rebuild the grid from the current ``configFile``."""
        self._clear()
        self._built = False
        loaded = self._load_resolved_config()
        if loaded is None:
            return
        config, base_dir = loaded

        self._built = True
        self._columns = list(config.get("columns", []))

        # Header row: blank corner + column labels.
        for col_idx, col_name in enumerate(self._columns):
            self.grid.addWidget(self._make_column_header(col_name), 0, col_idx + 1)

        row_idx = 1
        for entry in config.get("rows", []):
            if "section" in entry:
                self._add_section_row(entry["section"], row_idx)
                row_idx += 1
            elif "category" in entry:
                self._add_category_row(entry, row_idx, base_dir)
                row_idx += 1

        # In a live screen, connect all channels now and register them with PyDM.
        if not is_qt_designer():
            for cell in (c for cells in self._row_cells.values() for c in cells):
                cell.create_channels()
            self._channels = [ch for d in self._iter_devices() for ch in d.channels]

        # Keep the list view in sync with device status changes.
        for device in self._iter_devices():
            device.changed.connect(self._schedule_list_refresh)
        self._refresh_list()

    def _make_column_header(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet("QLabel { background-color: #e0e0e0; padding: 4px; }")
        return label

    def _add_section_row(self, text: str, row_idx: int) -> None:
        label = QLabel(text)
        font = QFont()
        font.setBold(True)
        label.setFont(font)
        label.setStyleSheet("QLabel { background-color: #e0e0e0; padding: 4px; }")
        self.grid.addWidget(label, row_idx, 0, 1, len(self._columns) + 1)

    def _add_category_row(self, entry: dict, row_idx: int, base_dir: str) -> None:
        title = entry["category"]
        cells_cfg = entry.get("cells", {}) or {}

        # Row header: a dropdown triangle on the left, then the category name.
        # The whole header bar is clickable and pops up the device menu.
        header = QWidget()
        header.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 1, 4, 1)
        header_layout.setSpacing(4)

        # A filled down-triangle drawn as text so we control its color (the
        # theme's native QToolButton arrow renders too light to see here).
        arrow = QToolButton(header)
        arrow.setText("▾")  # ▾ black down-pointing small triangle
        arrow.setFocusPolicy(Qt.NoFocus)
        arrow.setStyleSheet(
            "QToolButton { border: none; background: transparent; color: #393939; font-size: 14px; }"
            "QToolButton:hover { color: #0f62fe; }"
        )
        arrow.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(arrow)

        label = QLabel(title)
        header_layout.addWidget(label)
        header_layout.addStretch()
        self.grid.addWidget(header, row_idx, 0)

        # Build the dropdown menu that lists this category's devices.
        menu = CategoryMenu(title, self)
        row_cells: list[AlarmGridCell] = []
        for col_idx, col_name in enumerate(self._columns):
            cell = AlarmGridCell()
            devices = [self._make_device(c, base_dir, col_name, title) for c in (cells_cfg.get(col_name, []) or [])]
            for device in devices:
                cell.add_device(device)
            cell.update_aggregate()
            menu.add_devices(devices)
            # Clicking a cell's aggregate box also opens the category menu.
            cell.aggregate.clicked.connect(lambda t=title: self._show_menu(t))
            self.grid.addWidget(cell, row_idx, col_idx + 1)
            row_cells.append(cell)

        self._row_cells[title] = row_cells
        self._row_menus[title] = menu
        self._row_headers[title] = header
        # Clicking the header (bar or arrow) pops up the device menu.
        arrow.clicked.connect(lambda _checked=False, t=title: self._show_menu(t))
        header.mousePressEvent = lambda _ev, t=title: self._show_menu(t)

    def _show_menu(self, title: str) -> None:
        """Pop up the device menu for the given category, below its name."""
        menu = self._row_menus.get(title)
        header = self._row_headers.get(title)
        if menu is None or header is None or not menu.has_content():
            return
        global_pos = header.mapToGlobal(header.rect().bottomLeft())
        menu.exec_(global_pos)

    def _make_device(self, cfg: dict, base_dir: str, location: str = "", category: str = "") -> DeviceStatus:
        detail = cfg.get("detail")
        if detail and not os.path.isabs(detail):
            # Resolve relative detail paths against the config file's directory.
            detail = os.path.join(base_dir, detail)
        # A device watches either a single "channel" or a list of "channels".
        channels = cfg.get("channels", cfg.get("channel", ""))
        return DeviceStatus(
            name=cfg.get("name") or (channels[0] if isinstance(channels, list) and channels else channels),
            channels=channels,
            detail=detail,
            macros=cfg.get("macros"),
            typhos_name=cfg.get("typhos"),
            location=location,
            category=category,
            parent=self,
        )
