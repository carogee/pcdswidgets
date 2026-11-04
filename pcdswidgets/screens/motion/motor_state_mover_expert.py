"""
Expert screen for the motor state mover (migration off Typhos).

Opened from the plain :class:`MotorStateMover` "Expert Screen" button. Wraps one
:class:`MotorStateMoverExpanded` (plain mover on top + Normal/Configuration tabs)
and configures it from the incoming macros.

Macros:
    DEVICE       base prefix, e.g. ``TST:D3`` (required)
    PMPS         truthy ("1"/"true") -> PMPS variant: the Configuration tab adds
                 the PMPS controls (arb_enable, maint_mode) above the per-state
                 motor grid.
    STATE_COUNT  number of states (int), e.g. ``4``; optional -- defaults to the
                 IOC's ``{DEVICE}:STATE:STATE_COUNT_RBV``, and is capped at it
    DEVICE_TOKENS comma-separated per-device tokens, e.g. ``D1M1,D2M1,D3M1``
                 (also drives the Diagnostics tab, one row per token); optional
                 -- defaults to the IOC's ``{DEVICE}:STATE:MOTOR_TOKENS_RBV``,
                 and tokens the IOC does not publish are dropped
    MOTOR_TYPE   optional motor type for the Diagnostics cog buttons:
                 GENERIC, IMS, BECKHOFF (default) or BECKHOFF_LEGACY
    MAX_VISIBLE_STATES  optional (default 3): state rows shown in the Configuration
                 grid before it scrolls vertically
    MAX_VISIBLE_MOTORS  optional (default 3): motor columns shown in the
                 Configuration grid before it scrolls horizontally, and motor
                 rows shown in the Diagnostics tab before it scrolls vertically
"""

from pydm import Display
from qtpy import QtWidgets

from pcdswidgets.motion.common.motor_state_mover_expanded import (
    MotorStateMoverExpanded,
    MotorStateMoverExpandedPMPS,
)

_TRUTHY = {"1", "true", "yes", "on"}


class MotorStateMoverExpert(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        macros = self.macros()  # Display stores the macros; returns {} if none

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if str(macros.get("PMPS", "")).strip().lower() in _TRUTHY:
            self.expanded = MotorStateMoverExpandedPMPS()
        else:
            self.expanded = MotorStateMoverExpanded()

        # both variants use the per-state grid (the PMPS one shows it below its
        # arb_enable / maint_mode controls), so feed all three to either widget
        self.expanded.setProperty("device", macros.get("DEVICE", ""))
        self.expanded.setProperty("deviceTokens", macros.get("DEVICE_TOKENS", ""))
        self.expanded.setProperty("motorType", macros.get("MOTOR_TYPE", "BECKHOFF"))
        try:
            self.expanded.setProperty("stateCount", int(macros.get("STATE_COUNT", 0)))
        except (TypeError, ValueError):
            self.expanded.setProperty("stateCount", 0)
        for macro, prop in (("MAX_VISIBLE_STATES", "maxVisibleStates"), ("MAX_VISIBLE_MOTORS", "maxVisibleMotors")):
            if str(macros.get(macro, "")).strip():
                try:
                    self.expanded.setProperty(prop, int(macros[macro]))
                except (TypeError, ValueError):
                    pass  # keep the default

        layout.addWidget(self.expanded)
        # PyDM sizes the window from the display's initial size; start at the
        # content's natural size rather than the default widget size
        self.resize(self.sizeHint())

    def ui_filename(self):
        # UI is built in __init__, so there is no .ui file to load.
        return None
