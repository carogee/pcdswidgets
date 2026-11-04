import json
import logging

from pydm.widgets import PyDMSymbol
from qtpy.QtCore import QRectF, QSize, QSizeF, Qt
from qtpy.QtGui import QPixmap
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QStyle, QStyleOption

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.builder.designer_widget import DesignerWidget
from pcdswidgets.icons.glyphs import DISCONNECTED, ERROR, MOVING, OK, WARNING

try:
    from qtpy.QtCore import pyqtProperty
except ImportError:
    from qtpy.QtCore import Property as pyqtProperty  # type: ignore

logger = logging.getLogger(__name__)

# Clockwise rotation (degrees) applied to the MOVING arrow icon, which
# points right by default, so it can point the direction of travel.
_MOVE_DIRECTION_ANGLES = {"right": 0, "down": 90, "left": 180, "up": 270}


class SvgMultiStateLED(PyDMSymbol, DesignerWidget):
    # Designer Widget handlers
    _macro_to_widget = {}
    _widget_to_macro = {}
    _widget_to_pre_template = {}

    designer_options = DesignerOptions(
        group="ECS Motion Common",
        is_container=False,
        icon="multi_state_led_icon.png",
    )

    editable_str_properties = {"motor": ""}

    def __init__(self, *args, **kwargs):
        self._macro_values = {}
        self._motor = ""
        # Let's give the option for additional channels
        self._additional_channels = []
        self._additional_channel_objs = []

        # For simplicitity, we'll assume these 5 states
        # And make a simple dict out of it
        self._icon_paths = [OK, MOVING, WARNING, ERROR, DISCONNECTED]
        self._state_dict = {"OK": 0, "MOVING": 1, "WARNING": 2, "ERROR": 3, "DISCONNECTED": 4}
        self._connected = False

        # Direction the MOVING arrow icon should point, e.g. set by an
        # external jog button's clicked signal via set_move_direction().
        self._move_direction = "right"

        super().__init__(*args, **kwargs)

        # Some size hinting and whatnot
        self.setMinimumSize(QSize(20, 20))
        self.setMaximumSize(QSize(64, 64))
        self.resize(20, 20)

        # setImageFiles just needs a json style dict, so if you want to
        # you can make self._icon_paths a more sophisticate dict and pass
        # the pairs you care about.
        self.setImageFiles(json.dumps(dict(enumerate(self._icon_paths))))

        # Finally, let's assume we're disconnected. I hate that this is idx based
        # Edit this if you want a different initial state and icon.
        self._state = self._state_dict["DISCONNECTED"]

    def paintEvent(self, event):
        """
        Override to center the SVG rendering.
        Minimal modification of PyDMSymbol's paintEvent.
        Annoying, but had to be done for aesthetics.
        """
        self._painter.begin(self)
        opt = QStyleOption()
        opt.initFrom(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, self._painter, self)

        if self._current_key is None:
            logger.warning("paintEvent: _current_key is None")
            self._painter.end()
            return

        logger.debug(f"paintEvent: _current_key={self._current_key}")

        image_to_draw = self._state_images.get(self._current_key, (None, None))[1]

        if image_to_draw is None:
            logger.warning(f"paintEvent: No image for key {self._current_key}")
            logger.warning(f"Available keys in _state_images: {list(self._state_images.keys())}")
            self._painter.end()
            return

        logger.debug(f"paintEvent: Drawing image for key {self._current_key}, type={type(image_to_draw)}")

        if isinstance(image_to_draw, QPixmap):
            w = float(image_to_draw.width())
            h = float(image_to_draw.height())
            if self._aspect_ratio_mode == Qt.IgnoreAspectRatio:
                scale = (event.rect().width() / w, event.rect().height() / h)
            elif self._aspect_ratio_mode == Qt.KeepAspectRatio:
                sf = min(event.rect().width() / w, event.rect().height() / h)
                scale = (sf, sf)
            elif self._aspect_ratio_mode == Qt.KeepAspectRatioByExpanding:
                sf = max(event.rect().width() / w, event.rect().height() / h)
                scale = (sf, sf)
            self._painter.scale(scale[0], scale[1])
            self._painter.drawPixmap(event.rect().x(), event.rect().y(), image_to_draw)
        elif isinstance(image_to_draw, QSvgRenderer):
            is_moving = self._current_key == self._state_dict["MOVING"]
            angle = _MOVE_DIRECTION_ANGLES[self._move_direction] if is_moving else 0

            # 90/270 rotation swaps axes on screen, so fit against a
            # transposed target to avoid clipping the landscape icon.
            fit_target = QSizeF(event.rect().size())
            if angle in (90, 270):
                fit_target.transpose()

            draw_size = QSizeF(image_to_draw.defaultSize())
            draw_size.scale(fit_target, self._aspect_ratio_mode)

            # CENTER THE SVG, so annoying this had to be done.
            x = (event.rect().width() - draw_size.width()) / 2.0
            y = (event.rect().height() - draw_size.height()) / 2.0

            logger.debug(
                f"paintEvent: Rendering SVG at ({x}, {y}) with size ({draw_size.width()}, {draw_size.height()})"
            )
            draw_rect = QRectF(x, y, draw_size.width(), draw_size.height())

            if angle:
                self._painter.save()
                self._painter.translate(draw_rect.center())
                self._painter.rotate(angle)
                self._painter.translate(-draw_rect.center())
                image_to_draw.render(self._painter, draw_rect)
                self._painter.restore()
            else:
                image_to_draw.render(self._painter, draw_rect)

        self._painter.end()

    # Define methods for motor property
    def get_motor(self) -> str:
        """Get the motor macro"""
        return self._motor

    def set_motor(self, value: str) -> None:
        self._motor = value
        self.set_channel(f"ca://{self._motor}.MSTA")

    motor = pyqtProperty(str, get_motor, set_motor)

    def connection_changed(self, connected):
        """
        Override PyDMWidget's connection callback to handle disconnection.

        Parameters
        ----------
        connected : bool
            True if connected, False if disconnected
        """
        # Call parent implementation
        super().connection_changed(connected)

        # Track connection state
        self._main_channel_connected = connected

        if not connected:
            # Update to disconnected state
            self._state = self._state_dict["DISCONNECTED"]
            self.set_current_key(self._state)
            self.setToolTip("Motor disconnected")
            logger.debug(f"Motor {self._motor} disconnected")
        else:
            logger.debug(f"Motor {self._motor} connected")

    def check_enable_state(self) -> None:
        """
        Override to force disconnected icon when not connected.
        This is called by PyDMWidget regularly.
        """

        # Check parent's connection state
        if not self._connected:
            if self._current_key != self._state_dict["DISCONNECTED"]:
                logger.debug("check_enable_state: Not connected, forcing disconnected icon")
                logger.debug(f"_state_images keys: {list(self._state_images.keys())}")
                logger.debug(f"Setting key to: {self._state_dict['DISCONNECTED']}")
                logger.debug(f"Image exists: {self._state_dict['DISCONNECTED'] in self._state_images}")

                self._state = self._state_dict["DISCONNECTED"]
                self.set_current_key(self._state)

                logger.debug(f"Current key is now: {self._current_key}")

                self.update()

        # Call parent implementation for alarm handling etc.
        super().check_enable_state()

    def channels(self) -> list[str]:
        """
        Return all channels used by this widget.

        Returns
        -------
        list
            List of PyDMChannel objects
        """
        channels = super().channels()

        if self._additional_channel_objs:
            channels.extend(self._additional_channel_objs)

        return channels

    def set_move_direction(self, direction: str) -> None:
        """
        Set which direction the MOVING arrow icon should point.

        Meant to be called from outside, e.g. connected to a jog button's
        `clicked` signal, so the arrow reflects the button that was pressed.

        Parameters
        ----------
        direction : str
            One of "up", "down", "left", "right".
        """
        if direction not in _MOVE_DIRECTION_ANGLES:
            logger.warning(f"Invalid move direction: {direction!r}")
            return

        self._move_direction = direction

        if self._current_key == self._state_dict["MOVING"]:
            self.update()

    def value_changed(self, new_val) -> None:
        """
        Override the value_changed method to do bitmask checks on MSTA,
        then update the state of the widget.
        """
        if not self._main_channel_connected:
            self._state = self._state_dict["DISCONNECTED"]
            self.set_current_key(self._state)
            return

        bit_mask = int(new_val)

        # bitwise operations for checking individual states
        # Remember, MSTA starts bit 1 instead of bit 0 on the docs!
        done = bool(bit_mask & (1 << 1))
        slip_stall = bool(bit_mask & (1 << 6))
        problem = bool(bit_mask & (1 << 9))
        moving = bool(bit_mask & (1 << 10))
        comm_err = bool(bit_mask & (1 << 12))

        if slip_stall or problem or comm_err:
            self._state = self._state_dict["ERROR"]
            err_str = "Errors:\n"

            if slip_stall:
                err_str += "Slip Stall\n"
            if problem:
                err_str += "Unknown Problem\n"
            if comm_err:
                err_str += "Communication error\n"

            self.setToolTip(err_str)

        elif not done or moving:
            self._state = self._state_dict["MOVING"]
            self.setToolTip("Motor is moving")

        elif done:
            self._state = self._state_dict["OK"]
            self._move_direction = "right"  # fall back to 0 rotation

        else:
            self.setToolTip("Current motor Status")

        self.set_current_key(self._state)
