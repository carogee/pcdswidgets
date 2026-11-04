"""
Expanded motor state mover (variant 2).

A self-contained replacement for the Typhos expert screen (no Typhos dependency):
the plain :class:`MotorStateMover` on top (with its own Expert Screen button
hidden -- we are already in the expert screen), then a tab group with

* **Normal** -- always present: the raw device signals (busy, done, error,
  error_id, error_message, reset_cmd), matching the plain state-mover expert
  screen.
* **Configuration** -- shown *only* when there is a state count and a token list,
  from the caller or published by the IOC (the plain expert screen has no config
  tab; the configured one does). A read-only per-state config grid whose size is
  driven by two properties instead of a fixed .ui:

  - ``stateCount`` -- number of states (grid rows).
  - ``deviceTokens`` -- comma-separated per-device tokens (grid columns). The
    tokens are device specific (e.g. ``D1M1,D3M1``) and cannot be generated from a
    count, so they are listed explicitly. ``device_count`` == number of tokens.

  Both are optional: the IOC (pytmc) publishes the layout as
  ``{device}:STATE:MOTOR_TOKENS_RBV.VAL$``, ``STATE_COUNT_RBV`` and
  ``STATE_INDEX_DIGITS_RBV``. When set, they are checked against it (unknown
  tokens dropped, an oversized count capped, each with a warning and a tooltip);
  without those PVs (older IOCs) they are used as given.
  ``maxVisibleStates`` / ``maxVisibleMotors`` set how many rows / columns show
  before the grid scrolls, so the window size does not depend on the table.
* **Diagnostics** -- shown when the device and tokens are available. Per-motor
  ``MOVING`` and ``STATUS`` (relative to the goal state), a red status on an axis
  error, and a cog button opening the motor's own expert screen (``motorType``).

Everything here is read-only display (plus the reset command). Colors and fonts
live in ``motor_state_mover_expanded.qss``; the code only tags widgets for it.
Config cells
resolve to::

    ca://{motor}:STATE:{token}:{NN}:{leaf}_RBV

with ``{NN}`` the zero-padded state index (2 digits, or the width the IOC
publishes) and ``{leaf}`` one of ``NAME``, ``SETPOINT``.
"""

from __future__ import annotations

import functools
import logging
import math
import numbers
from pathlib import Path

from pydm.utilities import IconFont
from pydm.widgets.channel import PyDMChannel
from pydm.widgets.display_format import DisplayFormat
from pydm.widgets.enum_combo_box import PyDMEnumComboBox
from pydm.widgets.label import PyDMLabel
from pydm.widgets.pushbutton import PyDMPushButton
from pydm.widgets.shell_command import PyDMShellCommand
from qtpy import QtCore, QtGui, QtWidgets

from pcdswidgets.motion.common.motor_state_mover import MotorStateMover

try:
    from qtpy.QtCore import pyqtProperty
except ImportError:  # PySide fallback
    from qtpy.QtCore import Property as pyqtProperty  # type: ignore

logger = logging.getLogger(__name__)

# Colors, fonts and borders live in motor_state_mover_expanded.qss; the code only
# tags widgets with the properties that stylesheet selects on (see _tag).
_STYLESHEET = Path(__file__).with_suffix(".qss")

# MOTOR_TOKENS_RBV is an lsi (long string); a plain read is cut off at 40
# characters, so it is read as .VAL$ to get the whole string
_TOKENS_LEAF = "MOTOR_TOKENS_RBV.VAL$"

# how long to wait for the IOC's state-table metadata before warning
_METADATA_TIMEOUT_MS = 5000

# "Normal" tab device signals: (row label, PV suffix under ${MOTOR}, kind).
# kind: "led" -> boolean bar, always blue (Typhos-style);
#       "error_led" -> boolean bar, red (set) / blue (clear);
#       "text" -> numeric text;
#       "error_msg" -> char waveform decoded as a string, red while ERR is set.
_NORMAL_SIGNALS = (
    ("busy", "STATE:BUSY_RBV", "led"),
    ("done", "STATE:DONE_RBV", "led"),
    ("error", "STATE:ERR_RBV", "error_led"),
    ("error_id", "STATE:ERRID_RBV", "led"),
    ("error_message", "STATE:ERRMSG_RBV", "error_msg"),
)
_ERROR_SUFFIX = "STATE:ERR_RBV"
_RESET_SUFFIX = "STATE:RESET"

# "Diagnostics" tab per-motor columns: (header, PV leaf under ${DEVICE}:, kind).
# Each cell resolves to ca://{device}:{leaf}:{NN}_RBV with {NN} the
# zero-padded motor index (position in deviceTokens, starting at 1).
_DIAG_COLUMNS = (
    ("Moving", "MOVING", "bool"),
    ("Status", "STATUS", "status"),
)
# E_MotorTransitStatus values -> the bar's ``state`` in the stylesheet
_TRANSIT_STATES = {0: "unknown", 1: "at-state", 2: "in-transit"}
# per-motor axis error flag: ca://{device}:{token}:bError_RBV (red status bar while set)
_AXIS_ERROR_LEAF = "bError_RBV"
# Motor types understood by MotorClassicRow (selects its expert-screen command)
_MOTOR_TYPES = ("GENERIC", "IMS", "BECKHOFF", "BECKHOFF_LEGACY")

# PMPS variant Configuration rows: (row label, PV suffix under ${DEVICE}).
# Each row shows a value readback (ca://{device}:{suffix}_RBV) and a setpoint
# selector (ca://{device}:{suffix}). Confirm the suffixes against the IOC.
_PMPS_ROWS = (
    ("arb_enable", "STATE:PMPS:ARB:ENABLE"),
    ("maint_mode", "STATE:PMPS:MAINT"),
)

# Configuration tab state grid: row geometry, and how many state rows / motor
# columns are shown before the grid scrolls (so the window size does not depend
# on the state or motor count). Both are overridable via properties.
_STATE_ROW_HEIGHT = 28
_STATE_HEADER_HEIGHT = 22
_STATE_GRID_SPACING = 5
_SCROLLBAR_GAP = 8
_STATE_NAME_COLUMN_WIDTH = 128
_MIN_MOTOR_COLUMN_WIDTH = 90
_DEFAULT_VISIBLE_STATES = 3
_DEFAULT_VISIBLE_MOTORS = 3

# fixed width of the plain state mover (matches the Form width in
# motor_state_mover.ui) so the expert's top row keeps the plain screen's size
_PLAIN_MOVER_WIDTH = 680
# height of the GET/SET widgets in motor_state_mover.ui -- the Clear Error button
# is matched to this once it moves onto the main row in the expert
_MAIN_ROW_HEIGHT = 46


class _TabPage(QtWidgets.QWidget):
    """Tab page. The Normal page (``reference`` is None) reports its natural size;
    every other page reports the Normal page's size, so all tabs share one size
    and switching tabs never resizes the window."""

    def __init__(self, reference: _TabPage | None = None, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._reference = reference

    def sizeHint(self) -> QtCore.QSize:
        return super().sizeHint() if self._reference is None else self._reference.sizeHint()

    def minimumSizeHint(self) -> QtCore.QSize:
        return super().minimumSizeHint() if self._reference is None else self._reference.minimumSizeHint()


def _scrolling_page(reference: _TabPage) -> tuple[_TabPage, QtWidgets.QVBoxLayout]:
    """A tab page sized like ``reference`` whose content scrolls vertically when it
    does not fit. Returns the page and the layout to put the content in."""
    page = _TabPage(reference)
    page_layout = QtWidgets.QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)

    scroll = QtWidgets.QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
    _tag(scroll, "transparent")
    content = QtWidgets.QWidget()
    content_layout = QtWidgets.QVBoxLayout(content)
    content_layout.setContentsMargins(12, 12, 12, 12)
    scroll.setWidget(content)
    page_layout.addWidget(scroll)
    return page, content_layout


class _StateScrollArea(QtWidgets.QScrollArea):
    """Scroll area around the per-state grid. With more motor columns than
    ``visible_columns`` it sizes every setpoint column to a ``visible_columns``-way
    share of the viewport, so the extra columns scroll horizontally instead of
    squeezing in or widening the window."""

    def __init__(self, grid: QtWidgets.QGridLayout, columns: int, visible_columns: int):
        super().__init__()
        self._grid = grid
        self._columns = columns
        self._visible_columns = visible_columns

    @property
    def scrolls_horizontally(self) -> bool:
        return self._columns > self._visible_columns

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_columns()

    def _fit_columns(self) -> None:
        available = self.viewport().width()
        if not self.scrolls_horizontally or available <= 0:
            return
        spacing = self._grid.horizontalSpacing()
        share = available - _STATE_NAME_COLUMN_WIDTH - spacing * self._visible_columns
        width = max(_MIN_MOTOR_COLUMN_WIDTH, share // self._visible_columns)
        for col in range(1, self._columns + 1):
            self._grid.setColumnMinimumWidth(col, width)


class MotorStateMoverExpanded(QtWidgets.QFrame):
    """Plain state mover + a read-only, dynamically sized state-config grid."""

    # Plain QFrame (not a DesignerWidget), so PyDM reads _qt_designer_ directly.
    _qt_designer_ = {
        "group": "ECS Motion Common",
        "is_container": False,
    }

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._device = ""
        self._state_count = 0
        self._state_start = 1
        self._max_visible_states = _DEFAULT_VISIBLE_STATES
        self._max_visible_motors = _DEFAULT_VISIBLE_MOTORS
        self._device_tokens = ""
        self._motor_type = "BECKHOFF"
        # layout of the device's state table, as published by the IOC under
        # ca://{device}:STATE:{MOTOR_TOKENS,STATE_COUNT}_RBV (None until known)
        self._pv_tokens: list[str] | None = None
        self._pv_state_count: int | None = None
        self._pv_state_digits: int | None = None
        self._metadata_channels: list[PyDMChannel] = []
        self._notes: list[str] = []
        channels = self._metadata_channels
        self.destroyed.connect(lambda: [_safe_disconnect(c) for c in channels])
        # PV updates arrive one at a time; rebuild once for the batch
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._rebuild_grid)
        # tabs depend on the IOC's metadata PVs unless the properties are set;
        # say so if nothing has arrived after a while
        self._metadata_timer = QtCore.QTimer(self)
        self._metadata_timer.setSingleShot(True)
        self._metadata_timer.timeout.connect(self._warn_no_metadata)

        self.setStyleSheet(_stylesheet())
        self._outer = QtWidgets.QVBoxLayout(self)
        self._outer.setContentsMargins(8, 8, 8, 8)
        self._outer.setSpacing(8)

        # plain state mover on top, always visible (reused verbatim, minus its
        # own Expert Screen button -- we are already inside the expert screen --
        # and its error message, which the Normal tab already shows)
        self.plainMover = MotorStateMover(self)
        expert_btn = getattr(self.plainMover, "expertScreenButton", None)
        if expert_btn is not None:
            expert_btn.hide()
        error_status = getattr(self.plainMover, "errorStatus", None)
        if error_status is not None:
            error_status.hide()
        # move Clear Error up onto the main row, in line with the GET/SET widgets
        # (its own status row is now empty -- error message lives in the Normal tab)
        clear_btn = getattr(self.plainMover, "clearErrorButton", None)
        if clear_btn is not None and hasattr(self.plainMover, "mainRow"):
            clear_btn.setFixedHeight(_MAIN_ROW_HEIGHT)  # match the GET/SET height
            self.plainMover.mainRow.addWidget(clear_btn)
        status_row = getattr(self.plainMover, "statusRow", None)
        if status_row is not None:
            for i in reversed(range(status_row.count())):
                if status_row.itemAt(i).spacerItem() is not None:
                    status_row.takeAt(i)  # drop the leftover spacer so the row collapses
        # keep the plain mover at the plain screen's fixed width so the GET/SET
        # widgets stay the same size (and don't stretch to the config grid width)
        self.plainMover.setFixedWidth(_PLAIN_MOVER_WIDTH)
        top_row = QtWidgets.QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.addWidget(self.plainMover)
        top_row.addStretch(1)
        self._outer.addLayout(top_row)

        self.tabs = QtWidgets.QTabWidget(self)
        self.tabs.setObjectName("expertTabs")

        # "Normal" tab: always present -- the raw device signals. Its size is the
        # size of every tab (see _TabPage).
        self._normal_tab = _TabPage()
        self._normal_layout = QtWidgets.QVBoxLayout(self._normal_tab)
        self._normal_layout.setContentsMargins(14, 14, 14, 14)
        self.tabs.addTab(self._normal_tab, "Normal")

        # "Configuration" tab: built here but attached only when state_count and
        # device tokens are available (see _sync_tabs)
        self._config_tab, self._config_layout = _scrolling_page(self._normal_tab)

        # "Diagnostics" tab: per-motor transit breakdown, attached only when
        # device tokens are available (see _sync_tabs)
        self._diag_tab, self._diag_layout = _scrolling_page(self._normal_tab)

        self._outer.addWidget(self.tabs)
        self._rebuild_normal()
        self._rebuild_grid()

    # props
    def get_device(self) -> str:
        return self._device

    def set_device(self, value: str) -> None:
        self._device = value
        self.plainMover.setProperty("device", value)
        self._connect_metadata()
        self._rebuild_normal()
        self._rebuild_grid()

    device = pyqtProperty(str, get_device, set_device)

    def get_state_count(self) -> int:
        return self._state_count

    def set_state_count(self, value: int) -> None:
        self._state_count = max(0, int(value))
        self._rebuild_grid()

    stateCount = pyqtProperty(int, get_state_count, set_state_count)

    def get_state_start(self) -> int:
        return self._state_start

    def set_state_start(self, value: int) -> None:
        self._state_start = int(value)
        self._rebuild_grid()

    stateStartIndex = pyqtProperty(int, get_state_start, set_state_start)

    def get_max_visible_states(self) -> int:
        return self._max_visible_states

    def set_max_visible_states(self, value: int) -> None:
        self._max_visible_states = max(1, int(value))
        self._rebuild_grid()

    # state rows shown in the Configuration grid before it scrolls vertically
    maxVisibleStates = pyqtProperty(int, get_max_visible_states, set_max_visible_states)

    def get_max_visible_motors(self) -> int:
        return self._max_visible_motors

    def set_max_visible_motors(self, value: int) -> None:
        self._max_visible_motors = max(1, int(value))
        self._rebuild_grid()

    # motor columns shown in the Configuration grid (and motor rows in the
    # Diagnostics tab) before it scrolls
    maxVisibleMotors = pyqtProperty(int, get_max_visible_motors, set_max_visible_motors)

    def get_device_tokens(self) -> str:
        return self._device_tokens

    def set_device_tokens(self, value: str) -> None:
        self._device_tokens = value
        self._rebuild_grid()

    deviceTokens = pyqtProperty(str, get_device_tokens, set_device_tokens)

    def get_motor_type(self) -> str:
        return self._motor_type

    def set_motor_type(self, value: str) -> None:
        value = str(value).strip().upper()
        self._motor_type = value if value in _MOTOR_TYPES else "BECKHOFF"
        self._rebuild_diag()

    # MotorClassicRow motor type used by the Diagnostics cog buttons
    motorType = pyqtProperty(str, get_motor_type, set_motor_type)

    # build
    def _connect_metadata(self) -> None:
        """(Re)subscribe to the state-table metadata the IOC publishes for the
        current device (see pytmc's MOTOR_TOKENS_RBV / STATE_COUNT_RBV records)."""
        for chan in self._metadata_channels:
            _safe_disconnect(chan)
        self._metadata_channels.clear()
        self._pv_tokens = None
        self._pv_state_count = None
        self._pv_state_digits = None
        self._notes.clear()
        self._config_tab.setToolTip("")
        self._diag_tab.setToolTip("")
        self._metadata_timer.stop()
        if not self._device:
            return
        self._metadata_timer.start(_METADATA_TIMEOUT_MS)
        for leaf, slot in (
            (_TOKENS_LEAF, self._on_pv_tokens),
            ("STATE_COUNT_RBV", self._on_pv_state_count),
            ("STATE_INDEX_DIGITS_RBV", self._on_pv_state_digits),
        ):
            chan = PyDMChannel(address=f"ca://{self._device}:STATE:{leaf}", value_slot=slot)
            chan.connect()
            self._metadata_channels.append(chan)

    def _warn_no_metadata(self) -> None:
        if self._tokens and self._effective_state_count() > 0:
            return
        missing = [
            leaf
            for leaf, value in ((_TOKENS_LEAF, self._pv_tokens), ("STATE_COUNT_RBV", self._pv_state_count))
            if not value
        ]
        logger.warning(
            "%s: no usable %s received from ca://%s:STATE:. The Configuration and Diagnostics tabs "
            "need them (or the deviceTokens/stateCount properties). Check that the IOC was built "
            "with a pytmc that generates them (MOTOR_TOKENS_RBV is an lsi, read as .VAL$).",
            self._device,
            ", ".join(missing),
            self._device,
        )

    def _on_pv_tokens(self, value) -> None:
        tokens = _decode_tokens(value) or None
        logger.debug("%s: MOTOR_TOKENS_RBV -> %s", self._device, tokens)
        if tokens != self._pv_tokens:
            self._pv_tokens = tokens
            self._refresh_timer.start(0)

    def _on_pv_state_count(self, value) -> None:
        try:
            count = int(value)
        except (TypeError, ValueError):
            return
        count = count if count > 0 else None
        if count != self._pv_state_count:
            self._pv_state_count = count
            self._refresh_timer.start(0)

    def _on_pv_state_digits(self, value) -> None:
        try:
            digits = int(value)
        except (TypeError, ValueError):
            return
        digits = digits if digits > 0 else None
        if digits != self._pv_state_digits:
            self._pv_state_digits = digits
            self._refresh_timer.start(0)

    def _note(self, message: str) -> None:
        """Log a configuration/IOC mismatch once and expose it as a tooltip."""
        if message in self._notes:
            return
        self._notes.append(message)
        logger.warning("%s: %s", self._device, message)
        tip = "\n".join(self._notes)
        self._config_tab.setToolTip(tip)
        self._diag_tab.setToolTip(tip)

    @property
    def _tokens(self) -> list[str]:
        """Device tokens to show. The IOC's list is used when ``deviceTokens`` is
        empty; otherwise ``deviceTokens`` is kept (in its order) minus any token
        the IOC does not publish."""
        user = [t.strip() for t in self._device_tokens.split(",") if t.strip()]
        published = self._pv_tokens
        if not published:
            return user
        if not user:
            return list(published)
        unknown = [t for t in user if t not in published]
        if unknown:
            self._note(
                f"deviceTokens not published by the IOC were ignored: {', '.join(unknown)} "
                f"(IOC publishes: {', '.join(published)})"
            )
        return [t for t in user if t in published]

    def _effective_state_count(self) -> int:
        """State rows to show: the IOC's count when ``stateCount`` is unset, else
        ``stateCount`` capped at what the IOC has."""
        user, published = self._state_count, self._pv_state_count
        if not published:
            return user
        if user <= 0:
            return published
        if user > published:
            self._note(f"stateCount {user} exceeds the {published} states the IOC publishes; using {published}")
            return published
        return user

    def _motor_index(self, token: str, position: int) -> int:
        """1-based motor index used in the ``{leaf}:{NN}`` diagnostics PVs: the
        token's place in the IOC's list, else its position in ``deviceTokens``."""
        published = self._pv_tokens
        if published and token in published:
            return published.index(token) + 1
        return position + 1

    def _motor_index_width(self) -> int:
        count = len(self._pv_tokens) if self._pv_tokens else len(self._tokens)
        return _index_width(count)

    def _state_index_width(self) -> int:
        # the IOC publishes the width pytmc used; it follows the declared array
        # bound, which can exceed what the shown state count would suggest.
        # Older IOCs: assume the slice reaches the declared bound.
        if self._pv_state_digits:
            return self._pv_state_digits
        count = self._pv_state_count or self._effective_state_count()
        return _index_width(self._state_start + count - 1)

    def _channel(self, token: str, index: int, leaf: str) -> str:
        return f"ca://{self._device}:STATE:{token}:{index:0{self._state_index_width()}d}:{leaf}_RBV"

    @staticmethod
    def _clear_layout(layout: QtWidgets.QLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)  # remove from view now; deleteLater is async
                widget.deleteLater()

    def _rebuild_normal(self) -> None:
        self._clear_layout(self._normal_layout)

        panel = QtWidgets.QWidget()
        form = QtWidgets.QGridLayout(panel)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
        form.setColumnStretch(1, 1)

        error_channel = f"ca://{self._device}:{_ERROR_SUFFIX}"
        row = 0
        for label, suffix, kind in _NORMAL_SIGNALS:
            form.addWidget(_row_label(label), row, 0)
            channel = f"ca://{self._device}:{suffix}"
            if kind == "led":
                # non-error signals stay blue whatever the value (Typhos-style)
                widget = _bool_bar(channel, "always-on")
            elif kind == "error_led":
                widget = _bool_bar(channel, "error")
            elif kind == "error_msg":
                widget = _error_message(channel, error_channel)
            else:  # text
                widget = _signal_value(channel)
            form.addWidget(widget, row, 1)
            row += 1

        # reset_cmd: the command button, kept but with no (redundant) label text
        form.addWidget(_row_label("reset_cmd"), row, 0)
        form.addWidget(_command_button(f"ca://{self._device}:{_RESET_SUFFIX}"), row, 1)

        self._normal_layout.addWidget(panel)
        self._normal_layout.addStretch(1)

    def _config_provided(self) -> bool:
        """The Configuration tab exists once there is a state count and tokens,
        from the caller or published by the IOC."""
        return self._effective_state_count() > 0 and bool(self._tokens)

    def _diag_provided(self) -> bool:
        """The Diagnostics tab needs the device prefix and the motor tokens."""
        return bool(self._device) and bool(self._tokens)

    def _sync_tabs(self) -> None:
        """Attach/detach the optional tabs, keeping Normal / Configuration /
        Diagnostics order."""
        self._rebuild_diag()
        idx = self.tabs.indexOf(self._config_tab)
        if self._config_provided():
            if idx == -1:
                self.tabs.insertTab(1, self._config_tab, "Configuration")
        elif idx != -1:
            self.tabs.removeTab(idx)  # detach (does not delete the widget)

        idx = self.tabs.indexOf(self._diag_tab)
        if self._diag_provided():
            if idx == -1:
                self.tabs.addTab(self._diag_tab, "Diagnostics")
        elif idx != -1:
            self.tabs.removeTab(idx)
        self.tabs.updateGeometry()

    def _rebuild_diag(self) -> None:
        self._clear_layout(self._diag_layout)
        if not self._diag_provided():
            return

        box = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        for col, (title, _leaf, _kind) in enumerate(_DIAG_COLUMNS, start=1):
            header = _hdr(title, sub=True)
            header.setFixedHeight(22)
            grid.addWidget(header, 0, col)
            grid.setColumnStretch(col, 1)

        motor_width = self._motor_index_width()
        for r, token in enumerate(self._tokens):
            # no minimum width: the token column only needs to fit the token
            grid.addWidget(_row_label(token, min_width=0), r + 1, 0)
            motor_index = self._motor_index(token, r)
            for col, (_title, leaf, kind) in enumerate(_DIAG_COLUMNS, start=1):
                channel = f"ca://{self._device}:{leaf}:{motor_index:0{motor_width}d}_RBV"
                if kind == "bool":
                    widget = _bool_bar(channel, "led")
                else:
                    # a set axis error turns the status bar red whatever the status is
                    widget = _status_bar(channel, _axis_error_channel(self._device, token))
                grid.addWidget(widget, r + 1, col)
            grid.addWidget(_expert_button(f"{self._device}:{token}", self._motor_type), r + 1, len(_DIAG_COLUMNS) + 1)

        # Shows at most maxVisibleMotors rows (plus the header) and scrolls for
        # more, so the window does not grow with the motor count. Row height is
        # taken from the laid-out content rather than hard-coded.
        rows = len(self._tokens)
        visible = min(rows, self._max_visible_motors)
        content_height = box.sizeHint().height()
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        header_height = 22
        scroll.setFixedHeight(header_height + visible * (content_height - header_height) // max(rows, 1))
        _tag(scroll, "transparent")
        scroll.setWidget(box)

        self._diag_layout.addWidget(_group("Per-Motor Diagnostics", scroll))
        self._diag_layout.addStretch(1)

    def _build_state_grid(self) -> QtWidgets.QGroupBox | None:
        """ "States" frame holding the scrollable per-state grid (state name |
        "<motor>: Position" x N), or None when no state count / tokens were supplied."""
        tokens = self._tokens
        state_count = self._effective_state_count()
        if not (state_count > 0 and tokens):
            return None

        box = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(box)
        # keep the cells off the vertical scroll bar when there is one
        scrolls_vertically = state_count > self._max_visible_states
        grid.setContentsMargins(0, 0, _SCROLLBAR_GAP if scrolls_vertically else 0, 0)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(_STATE_GRID_SPACING)

        # header row: one "<motor>: Position" column per device token; the state
        # column is fixed, the setpoint columns share the remaining width equally
        for col, token in enumerate(tokens, start=1):
            header = _hdr(f"{token}: Position", sub=True)
            header.setFixedHeight(_STATE_HEADER_HEIGHT)
            grid.addWidget(header, 0, col)
            grid.setColumnStretch(col, 1)

        for r in range(state_count):
            index = self._state_start + r
            row = r + 1
            # state name: read from the first device token (char waveform -> string)
            name = _cell_label(
                self._channel(tokens[0], index, "NAME"),
                bold=True,
                align=QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter,
                as_string=True,
            )
            grid.addWidget(name, row, 0)

            for col, token in enumerate(tokens, start=1):
                grid.addWidget(_cell_label(self._channel(token, index, "SETPOINT")), row, col)

        # The view shows at most maxVisibleStates rows (plus the header) and
        # maxVisibleMotors columns, and scrolls for more, so the window does not
        # grow with the state or motor count.
        grid.setColumnMinimumWidth(0, _STATE_NAME_COLUMN_WIDTH)
        visible = min(state_count, self._max_visible_states)
        scroll = _StateScrollArea(grid, len(tokens), self._max_visible_motors)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        height = _STATE_HEADER_HEIGHT + visible * (_STATE_GRID_SPACING + _STATE_ROW_HEIGHT)
        if scroll.scrolls_horizontally:
            scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            height += scroll.horizontalScrollBar().sizeHint().height()
        else:
            scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setFixedHeight(height)
        _tag(scroll, "transparent")
        scroll.setWidget(box)
        return _group("States", scroll)

    def _rebuild_grid(self) -> None:
        self._clear_layout(self._config_layout)
        if not self._config_provided():
            self._sync_tabs()
            return

        box = self._build_state_grid()
        if box is not None:
            self._config_layout.addWidget(box)
        # top-aligned like the Diagnostics tab, not centered in the leftover height
        self._config_layout.addStretch(1)
        self._sync_tabs()


class MotorStateMoverExpandedPMPS(MotorStateMoverExpanded):
    """PMPS variant: the Configuration tab holds the PMPS controls (arb_enable,
    maint_mode) -- each a value readback plus a setpoint selector, sharing the
    ${DEVICE} prefix -- with the per-state motor grid shown below them (when
    state count / tokens are supplied)."""

    def _config_provided(self) -> bool:
        # the PMPS controls only need the device prefix (no state count / tokens)
        return bool(self._device)

    def _build_pmps_box(self) -> QtWidgets.QGroupBox:
        box = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        for r, (label, suffix) in enumerate(_PMPS_ROWS):
            grid.addWidget(_row_label(label), r, 0)
            grid.addWidget(_bool_bar(f"ca://{self._device}:{suffix}_RBV", "always-on"), r, 1)
            grid.addWidget(_setpoint_combo(f"ca://{self._device}:{suffix}"), r, 2)

        return _group("PMPS", box)

    def _rebuild_grid(self) -> None:
        self._clear_layout(self._config_layout)
        if not self._config_provided():
            self._sync_tabs()
            return

        self._config_layout.addWidget(self._build_pmps_box())

        # per-state settings shown below the PMPS controls, for consistency with
        # the standard expert (only when state count / tokens are supplied)
        state_box = self._build_state_grid()
        if state_box is not None:
            self._config_layout.addSpacing(4)
            self._config_layout.addWidget(state_box)
        self._config_layout.addStretch(1)
        self._sync_tabs()


# helpers
def _index_width(max_index: int) -> int:
    """Zero-pad width pytmc uses for array-index PV suffixes: one digit more than
    the largest selected index needs (up to 9 -> 2 digits, 10..99 -> 3)."""
    return math.floor(math.log10(max(max_index, 1))) + 2


def _decode_tokens(value) -> list[str]:
    """Names from MOTOR_TOKENS_RBV: normally an array of strings; also accepts a
    comma-joined string or a char array (array of character codes, as an lsi
    read through ``.VAL$`` is delivered)."""
    if value is None:
        return []
    items = [value] if isinstance(value, (str, bytes)) else list(value)
    if items and all(isinstance(i, numbers.Integral) and 0 <= i < 256 for i in items):
        items = [bytes(int(i) for i in items if i)]
    tokens: list[str] = []
    for item in items:
        if isinstance(item, bytes):
            item = item.decode(errors="ignore")
        tokens.extend(t.strip() for t in str(item).strip("\x00").split(",") if t.strip())
    return tokens


@functools.lru_cache(maxsize=1)
def _stylesheet() -> str:
    return _STYLESHEET.read_text(encoding="utf-8")


def _tag(widget: QtWidgets.QWidget, role: str, **properties: str) -> None:
    """Mark ``widget`` for the stylesheet: its ``role`` plus any extra selectors."""
    widget.setProperty("role", role)
    for name, value in properties.items():
        widget.setProperty(name, value)


def _set_state(widget: QtWidgets.QWidget, name: str, value: str) -> None:
    """Change a property the stylesheet selects on and restyle the widget."""
    if widget.property(name) == value:
        return
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def _group(title: str, content: QtWidgets.QWidget) -> QtWidgets.QGroupBox:
    """Titled frame around ``content``."""
    group = QtWidgets.QGroupBox(title)
    _tag(group, "group")
    layout = QtWidgets.QVBoxLayout(group)
    layout.setContentsMargins(8, 8, 8, 8)
    layout.addWidget(content)
    return group


def _hdr(text: str, sub: bool = False) -> QtWidgets.QLabel:
    lab = QtWidgets.QLabel(text)
    lab.setAlignment(QtCore.Qt.AlignCenter)
    _tag(lab, "header-sub" if sub else "header")
    return lab


def _cell_label(channel: str, bold: bool = False, align=QtCore.Qt.AlignCenter, as_string: bool = False) -> PyDMLabel:
    lab = PyDMLabel()
    _tag(lab, "cell", bold="true" if bold else "false")
    lab.setFixedHeight(_STATE_ROW_HEIGHT)
    lab.setMinimumWidth(80)
    lab.setAlignment(align)
    lab.showUnits = True
    if as_string:
        # NAME_RBV is a char waveform; decode it to a string instead of showing
        # the raw array of character codes.
        lab.displayFormat = DisplayFormat.String
    lab.channel = channel
    return lab


def _row_label(text: str, min_width: int = 100) -> QtWidgets.QLabel:
    lab = QtWidgets.QLabel(text)
    _tag(lab, "row-label")
    lab.setMinimumWidth(min_width)
    lab.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    return lab


def _signal_value(channel: str) -> PyDMLabel:
    lab = PyDMLabel()
    _tag(lab, "signal")
    lab.setMinimumHeight(26)
    lab.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    lab.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    lab.channel = channel
    return lab


class _BoolBar(PyDMLabel):
    """Full-width rounded bar (Typhos-style) with the value shown as text. Its
    ``variant`` (led, error or always-on) decides the colors for the set / clear
    ``state`` in the stylesheet."""

    def __init__(self, variant: str = "led", parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        _tag(self, "bar", variant=variant, state="off")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMinimumHeight(26)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.alarmSensitiveContent = False
        self.alarmSensitiveBorder = False

    def value_changed(self, new_value) -> None:
        super().value_changed(new_value)  # renders the value text
        _set_state(self, "state", "on" if new_value else "off")


class _StatusBar(PyDMLabel):
    """Enum text (``E_MotorTransitStatus``) on a rounded bar whose ``state`` in the
    stylesheet follows the value: AT_STATE, IN_TRANSIT or UNKNOWN (the "stopped
    mid-transit" symptom this tab exists to expose). While the motor's axis error
    flag (``error_channel``) is set the state is ``error`` regardless of the status."""

    def __init__(self, error_channel: str = "", parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        _tag(self, "bar", variant="status", state="none")
        self.setAlignment(QtCore.Qt.AlignCenter)
        self.setMinimumHeight(26)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.alarmSensitiveContent = False
        self.alarmSensitiveBorder = False
        self._status = None
        self._axis_error = False

        if error_channel:
            self._error_chan = PyDMChannel(address=error_channel, value_slot=self._error_changed)
            self._error_chan.connect()
            chan = self._error_chan
            self.destroyed.connect(lambda: _safe_disconnect(chan))

    def _paint(self) -> None:
        state = "error" if self._axis_error else _TRANSIT_STATES.get(self._status, "none")
        _set_state(self, "state", state)

    def value_changed(self, new_value) -> None:
        super().value_changed(new_value)  # renders the enum string
        try:
            self._status = int(new_value)
        except (TypeError, ValueError):
            self._status = None
        self._paint()

    def _error_changed(self, value) -> None:
        self._axis_error = bool(value)
        self._paint()


class _ErrorMessage(PyDMLabel):
    """Decoded error-message string (char waveform). Flagged as an error in the
    stylesheet only while the separate error flag (``error_channel``) is set."""

    def __init__(self, error_channel: str, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        _tag(self, "message", error="false")
        self.setMinimumHeight(26)
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.displayFormat = DisplayFormat.String
        self.alarmSensitiveContent = False
        self.alarmSensitiveBorder = False

        # a second channel drives only the error flag
        self._error_chan = PyDMChannel(address=error_channel, value_slot=self._error_changed)
        self._error_chan.connect()
        chan = self._error_chan
        self.destroyed.connect(lambda: _safe_disconnect(chan))

    def _error_changed(self, value) -> None:
        _set_state(self, "error", "true" if value else "false")


def _axis_error_channel(device: str, token: str) -> str:
    return f"ca://{device}:{token}:{_AXIS_ERROR_LEAF}"


def _safe_disconnect(chan: PyDMChannel) -> None:
    # Called from the widget's destroyed signal; the underlying connection may
    # already be gone during app teardown, so ignore that case.
    try:
        chan.disconnect()
    except Exception:
        pass


def _bool_bar(channel: str, variant: str) -> _BoolBar:
    bar = _BoolBar(variant)
    bar.channel = channel
    return bar


def _status_bar(channel: str, error_channel: str) -> _StatusBar:
    bar = _StatusBar(error_channel)
    bar.channel = channel
    return bar


def _error_message(channel: str, error_channel: str) -> _ErrorMessage:
    lab = _ErrorMessage(error_channel)
    lab.channel = channel
    return lab


def _setpoint_combo(channel: str) -> PyDMEnumComboBox:
    combo = PyDMEnumComboBox()
    _tag(combo, "setpoint-combo")
    combo.setMinimumHeight(28)
    combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    combo.channel = channel
    return combo


class _ExpertButton(PyDMShellCommand):
    """Icon-only shell-command button: grey cog at rest, white on the blue hover."""

    _ICON = "cog"

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.showIcon = False  # drop PyDM's default icon; we set our own
        self._rest_icon = IconFont().icon(self._ICON, QtGui.QColor(90, 90, 90))
        self._hover_icon = IconFont().icon(self._ICON, QtGui.QColor("white"))
        self.setIconSize(QtCore.QSize(16, 16))
        self._set_icon(self._rest_icon)

    def _set_icon(self, icon) -> None:
        if icon is not None:  # None when no QApplication yet
            self.setIcon(icon)

    def enterEvent(self, event) -> None:
        self._set_icon(self._hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_icon(self._rest_icon)
        super().leaveEvent(event)


def _expert_button(motor: str, motor_type: str) -> _ExpertButton:
    """Opens the motor row for ``motor`` in a new window. ``motor_type`` selects
    which expert screen MotorClassicRow's own button then launches."""
    btn = _ExpertButton()
    _tag(btn, "icon-button")
    btn.setFixedSize(34, 26)
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.setToolTip(f"Open the {motor_type.lower()} motor screen for {motor}")
    btn.commands = [f"pcdswidgets-show MotorClassicRow --motor {motor} --motor_type {motor_type}"]
    return btn


def _command_button(channel: str) -> PyDMPushButton:
    # No label -- the "Command" text was redundant; the button still writes.
    btn = PyDMPushButton()
    _tag(btn, "command-button")
    btn.setText("")
    btn.setMinimumHeight(26)
    btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
    btn.pressValue = "1"
    btn.setCursor(QtCore.Qt.PointingHandCursor)
    btn.channel = channel
    return btn
