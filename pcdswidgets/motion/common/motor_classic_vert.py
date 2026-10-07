"""Module for MotorClassicVert"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

from qtpy.QtWidgets import QWidget

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.builder.icon_options import IconOptions
from pcdswidgets.generated.motion.common.motor_classic_vert_base import MotorClassicVertBase

try:
    from qtpy.QtCore import pyqtProperty
except ImportError:
    from qtpy.QtCore import Property as pyqtProperty  # type: ignore


class MotorTypes:
    """Options for motor type to select the expert screen command."""

    GENERIC = 0
    IMS = 1
    BECKHOFF = 2
    BECKHOFF_LEGACY = 3


class MotorClassicVert(MotorClassicVertBase):
    """
    Generic motor widget in a vertical layout.

    This class is extended to allow us to support multiple
    types of motor IOCs with the same ui layout.

    The user can set the `motor_type` enum to change the
    following behavior:

    - Expert screen command

    There are four options:

    - GENERIC: default, no expert screen button.
    - IMS: standard IMS IOC (not motor record).
    - BECKHOFF: Motor that uses the 2026+ version of our TwinCAT motion libraries.
    - BECKHOFF_LEGACY: uses the pre-2026 version of the above.
    """

    designer_options = DesignerOptions(
        group="ECS Motion Common",
        is_container=False,
        icon=IconOptions.NONE,
    )
    # Expose motor_type as a dropdown in the Core Settings editor
    editable_choice_properties = {
        "motor_type": {"GENERIC": 0, "IMS": 1, "BECKHOFF": 2, "BECKHOFF_LEGACY": 3},
    }
    # Boilerplate to make the enum property work
    from PyQt5.QtCore import Q_ENUM

    Q_ENUM(MotorTypes)
    MotorTypes = MotorTypes
    GENERIC = MotorTypes.GENERIC
    IMS = MotorTypes.IMS
    BECKHOFF = MotorTypes.BECKHOFF
    BECKHOFF_LEGACY = MotorTypes.BECKHOFF_LEGACY

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._motor_type = MotorTypes.GENERIC
        self._expert_command = "motor-expert-screen {motor}"
        self.PyDMShellCommand_expert.hide()

    def after_set_macro(self, macro_name: str, value: str):
        """Puts motor prefix into expert screen command."""
        if macro_name == "MOTOR":
            self.new_expert_command_motor(value)

    def get_motor_type(self) -> MotorTypes | int:
        return self._motor_type

    def set_motor_type(self, value: MotorTypes | int) -> None:
        self._motor_type = value
        match value:
            case MotorTypes.IMS:
                self.new_expert_command_template("motor-expert-screen {motor}")
                self.PyDMShellCommand_expert.show()
            case MotorTypes.BECKHOFF:
                self.new_expert_command_template("pcdswidgets-show MotorExpertScreenBeckhoff --motor {motor}")
                self.PyDMShellCommand_expert.show()
            case MotorTypes.BECKHOFF_LEGACY:
                self.new_expert_command_template("pcdswidgets-show MotorExpertScreenBeckhoff --motor {motor}")
                self.PyDMShellCommand_expert.show()
            case _:
                self.PyDMShellCommand_expert.hide()

    motor_type = pyqtProperty(MotorTypes, get_motor_type, set_motor_type)

    def new_expert_command_template(self, template: str):
        self._expert_command = template
        if motor := self.get_macro("MOTOR"):
            self.new_expert_command_motor(motor)

    def new_expert_command_motor(self, motor: str):
        self.PyDMShellCommand_expert.commands = [self._expert_command.format(motor=motor)]
