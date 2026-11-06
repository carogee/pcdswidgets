"""
A configurable matrix of device-status indicators.

``DeviceGrid`` lays out a table of device *categories* (rows, grouped under
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
from typing import Any

import yaml
from pydm.utilities import find_file, is_qt_designer
from pydm.widgets import PyDMEmbeddedDisplay
from pydm.widgets.channel import PyDMChannel
from qtpy.QtCore import Property, QObject, QSize, Qt, Signal
from qtpy.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from qtpy.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


class StatusLevel(enum.IntEnum):
    """
    Aggregate device-status level, ordered by increasing severity.

    The integer ordering is used by :meth:`worst` to pick the most severe
    level among a device's children.  ``NONE`` is the least severe (used for
    disconnected / unknown / empty cells) and sorts below ``OK`` so that a
    single connected-and-ok device still "wins" over a blank one.
    """

    NONE = 0
    OK = 1
    WARN = 2
    FAULT = 3

    @classmethod
    def from_severity(cls, severity: int | None, connected: bool = True) -> "StatusLevel":
        """
        Map an EPICS alarm severity + connection state to a ``StatusLevel``.

        Parameters
        ----------
        severity : int or None
            The EPICS alarm severity: 0 = NO_ALARM, 1 = MINOR, 2 = MAJOR,
            3 = INVALID.  ``None`` is treated as unknown.
        connected : bool
            Whether the channel is connected.  A disconnected channel is
            always ``NONE`` (blank) regardless of its last-known severity.
        """
        if not connected or severity is None:
            return cls.NONE
        if severity == 0:
            return cls.OK
        if severity == 1:
            return cls.WARN
        if severity >= 2:
            # MAJOR and INVALID both render as a fault.
            return cls.FAULT
        return cls.NONE

    @classmethod
    def worst(cls, levels: "list[StatusLevel]") -> "StatusLevel":
        """Return the most severe level in ``levels`` (``NONE`` if empty)."""
        if not levels:
            return cls.NONE
        return max(levels)


# Carbon Gray 10 status tokens: (fill, glyph, border).
# NONE renders as a blank box using the page/border surface tokens.
_LEVEL_STYLE: dict[StatusLevel, tuple[str, str, str]] = {
    StatusLevel.OK: ("#24a148", "✓", "#24a148"),     # check mark
    StatusLevel.WARN: ("#f1c21b", "!", "#f1c21b"),
    StatusLevel.FAULT: ("#da1e28", "✗", "#da1e28"),  # ballot x
    StatusLevel.NONE: ("#f4f4f4", "—", "#e0e0e0"),   # em dash
}


def status_icon(level: "StatusLevel", size: int = 16) -> QIcon:
    """Build a circular status-colored :class:`QIcon` for a menu entry."""
    fill, glyph, border = _LEVEL_STYLE[level]
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    rect = pixmap.rect().adjusted(1, 1, -1, -1)
    painter.setBrush(QColor(fill))
    painter.setPen(QPen(QColor(border), 1))
    painter.drawEllipse(rect)
    text_color = "#525252" if level == StatusLevel.NONE else "#ffffff"
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
    A small painted square showing a single :class:`StatusLevel`.

    Drawn with square corners (no border radius) to match the Carbon theme.
    Used for the aggregate box in each grid cell.  The ``level`` property drives
    a repaint.  Emits :attr:`clicked` on a left mouse press.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, *, size: int = 18, stretch: bool = False):
        super().__init__(parent)
        self._level = StatusLevel.NONE
        self._size = size
        if stretch:
            # Fixed height, free to grow in width (used for the cell aggregate box).
            self.setFixedHeight(size)
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        else:
            self.setFixedSize(size, size)

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
            self.setToolTip(self._level.name)
            self.update()

    # designable=False: this is a runtime-driven display property, not something
    # to set in Qt Designer.
    level = Property(int, get_level, set_level, designable=False)

    def paintEvent(self, event):
        fill, glyph, border = _LEVEL_STYLE[self._level]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QColor(fill))
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRect(rect)

        # Glyph: dark text on the blank box, white on colored boxes.
        text_color = "#525252" if self._level == StatusLevel.NONE else "#ffffff"
        painter.setPen(QColor(text_color))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, int(self._size * 0.55)))
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, glyph)
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
        self.changed.emit()

    def _severity_changed(self, address: str, severity: int) -> None:
        _, conn = self._state.get(address, (None, False))
        self._state[address] = (severity, conn)
        self.changed.emit()

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


class DeviceGridCell(QWidget):
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


class DeviceGrid(QWidget):
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

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._config_file = ""
        self._columns: list[str] = []
        # category title -> list of its cells (one per column)
        self._row_cells: dict[str, list[DeviceGridCell]] = {}
        # category title -> its device dropdown menu / header widget
        self._row_menus: dict[str, CategoryMenu] = {}
        self._row_headers: dict[str, QWidget] = {}
        self._channels: list[PyDMChannel] = []
        # True once we have successfully built from the config; lets showEvent
        # retry a build that failed earlier because the parent display (and thus
        # the base path for relative config paths) was not available yet.
        self._built = False

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(6, 6, 6, 6)
        self.grid.setHorizontalSpacing(1)
        self.grid.setVerticalSpacing(1)

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
            logger.exception("Failed to load DeviceGrid config %s", path)
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
                logger.error("DeviceGrid could not find config file %r", self._config_file)
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

        arrow = QToolButton(header)
        arrow.setArrowType(Qt.DownArrow)
        arrow.setFocusPolicy(Qt.NoFocus)
        arrow.setStyleSheet("QToolButton { border: none; background: transparent; }")
        arrow.setCursor(Qt.PointingHandCursor)
        header_layout.addWidget(arrow)

        label = QLabel(title)
        header_layout.addWidget(label)
        header_layout.addStretch()
        self.grid.addWidget(header, row_idx, 0)

        # Build the dropdown menu that lists this category's devices.
        menu = CategoryMenu(title, self)
        row_cells: list[DeviceGridCell] = []
        for col_idx, col_name in enumerate(self._columns):
            cell = DeviceGridCell()
            devices = [self._make_device(c, base_dir, col_name) for c in (cells_cfg.get(col_name, []) or [])]
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

    def _make_device(self, cfg: dict, base_dir: str, location: str = "") -> DeviceStatus:
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
            parent=self,
        )
