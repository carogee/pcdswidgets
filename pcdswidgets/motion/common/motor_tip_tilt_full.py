"""Module for MotorTipTiltFull"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

import json
import logging

from qtpy.QtCore import Q_ENUMS

from pcdswidgets.generated.motion.common.motor_tip_tilt_full_base import MotorTipTiltFullBase
from pcdswidgets.motion.common.motor_style import MotorStyle
from pcdswidgets.motion.common.motor_tip_tilt import MotorTipTiltMixin

try:
    from qtpy.QtCore import pyqtProperty
except ImportError:
    from qtpy.QtCore import Property as pyqtProperty  # type: ignore

logger = logging.getLogger(__name__)


class MotorTipTiltFull(MotorTipTiltMixin, MotorTipTiltFullBase):
    """See MotorTipTiltMixin for behavior; override methods here if this widget ever needs to diverge."""

    # Q_ENUMS and the motor_style property must be declared directly on this
    # QObject-derived class: PyQt5 doesn't reliably carry them through a plain mixin
    Q_ENUMS(MotorStyle)
    MotorStyle = MotorStyle
    MotorRecord = MotorStyle.MotorRecord
    Smaract = MotorStyle.Smaract

    def getMotorStyle(self) -> int:
        """Whether this widget drives standard motor record fields or SmarAct's custom step fields."""
        return self._motor_style

    def setMotorStyle(self, value: int) -> None:
        if value not in (MotorStyle.MotorRecord, MotorStyle.Smaract):
            logger.warning(f"Invalid motor_style {value!r}; expected MotorRecord (0) or Smaract (1)")
            return
        if value == self._motor_style:
            return
        self._motor_style = value
        self._apply_expert_screen_visibility()
        self._refresh_axis("vertical")
        self._refresh_axis("horizontal")

    motor_style = pyqtProperty(MotorStyle, getMotorStyle, setMotorStyle)

    def get_view_saver_properties(self) -> dict:
        """Resolved ViewSaver getter/setter pairs for this widget's saved state.

        getter returns a QSettings-storable value
        setter accepts and applies raw stored value
        """

        return {
            "horizontal_invert": (
                lambda: json.dumps(self.horizontal_invert.isChecked()),
                lambda raw: self.horizontal_invert.setChecked(json.loads(raw)),
            ),
            "vertical_invert": (
                lambda: json.dumps(self.vertical_invert.isChecked()),
                lambda raw: self.vertical_invert.setChecked(json.loads(raw)),
            ),
        }
