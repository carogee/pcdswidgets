"""A dock button with a standard beamline device symbol rendered"""

from enum import IntEnum, auto
from pathlib import Path

from pydm.widgets.channel import PyDMChannel
from qtpy.QtCore import Q_ENUMS, QRect, Qt
from qtpy.QtGui import QCloseEvent, QPainter, QPaintEvent, QPalette, QPen, QPixmap
from qtpy.QtWidgets import QSizePolicy, QWidget

import pcdswidgets

from .tab_dock_button import ScreenSource, TabDockButton

try:
    from qtpy.QtCore import Property  # type: ignore
except ImportError:
    from qtpy.QtCore import pyqtProperty as Property  # type: ignore


IMAGE_FOLDER = Path(pcdswidgets.__file__).parent / "icons" / "diagram"  # type: ignore


class DiagramOption(IntEnum):
    """
    Options for which diagram to show on the widget.

    If you want to add a new option:
    - Add an entry here, note that order/count don't affect anything and won't break old screens.
      (Old screens need the old enum name to exist and nothing more)
    - Copy the new entry into the enums specified at the top of the class body below
      (This makes the enums work up properly in designer)
    - Add a new svg to pcdswidgets/icons/diagram whose name matches the entry
      (If the new enum is "NAME", the file should be "name.svg")
    """

    BLANK = auto()
    ATTENUATOR = auto()
    BEAM_STOPPER = auto()
    BURN_THRU_MONITOR = auto()
    DIFF_ION_PUMP = auto()
    EBD_MAGNETS = auto()
    EBD_SAMPLE_CHAMBER = auto()
    ENERGY_MONITOR = auto()
    FAST_VALVE = auto()
    FOCUSING_LENS = auto()
    GATE_VALVE = auto()
    GRATING = auto()
    IMAGER = auto()
    MIRROR = auto()
    MONOCHROMATOR = auto()
    PHOTON_COLLIMATOR = auto()
    POLARIZATION_SWITCH = auto()
    PULSE_SELECTOR = auto()
    REFERENCE_LASER = auto()
    SLIT = auto()
    SPECTROMETER = auto()
    WAVE_FRONT_SENSOR = auto()

    def get_image_path(self) -> Path:
        """Return a Path object pointing to the image we should use."""
        if self == DiagramOption.BLANK:
            raise ValueError("No image for blank diagram")
        return IMAGE_FOLDER / f"{self.name.lower()}.svg"

    def get_pixmap(self) -> QPixmap:
        """Return the pixmap to display for this enum."""
        return QPixmap(str(self.get_image_path()))


class TabDockDiagramButton(TabDockButton):
    """
    Behaves identically to TabDockButton, but renders a standard symbol and lightpath info.
    """

    # Re-declare the inherited ``source`` enum *and* its Property on this
    # subclass. Qt serializes an enum property under the class that declares the
    # Property, so without this Designer writes ``TabDockButton::FILE_PATH`` --
    # but only subclasses listed in a .ui's <customwidgets> are registered with
    # the uiloader, so that base-class scope raises NoSuchClassError on load.
    # Re-declaring here moves the serialized scope to ``TabDockDiagramButton::``,
    # which does resolve. (The Property body just defers to the base getter/setter.)
    Q_ENUMS(ScreenSource)
    ScreenSource = ScreenSource
    FILE_PATH = ScreenSource.FILE_PATH
    SCREEN_NAME = ScreenSource.SCREEN_NAME
    WIDGET_NAME = ScreenSource.WIDGET_NAME
    source = Property(ScreenSource, TabDockButton.readSource, TabDockButton.setSource)

    Q_ENUMS(DiagramOption)
    DiagramOption = DiagramOption
    BLANK = DiagramOption.BLANK
    ATTENUATOR = DiagramOption.ATTENUATOR
    BEAM_STOPPER = DiagramOption.BEAM_STOPPER
    BURN_THRU_MONITOR = DiagramOption.BURN_THRU_MONITOR
    DIFF_ION_PUMP = DiagramOption.DIFF_ION_PUMP
    EBD_MAGNETS = DiagramOption.EBD_MAGNETS
    EBD_SAMPLE_CHAMBER = DiagramOption.EBD_SAMPLE_CHAMBER
    ENERGY_MONITOR = DiagramOption.ENERGY_MONITOR
    FAST_VALVE = DiagramOption.FAST_VALVE
    FOCUSING_LENS = DiagramOption.FOCUSING_LENS
    GATE_VALVE = DiagramOption.GATE_VALVE
    GRATING = DiagramOption.GRATING
    IMAGER = DiagramOption.IMAGER
    MIRROR = DiagramOption.MIRROR
    MONOCHROMATOR = DiagramOption.MONOCHROMATOR
    PHOTON_COLLIMATOR = DiagramOption.PHOTON_COLLIMATOR
    POLARIZATION_SWITCH = DiagramOption.POLARIZATION_SWITCH
    PULSE_SELECTOR = DiagramOption.PULSE_SELECTOR
    REFERENCE_LASER = DiagramOption.REFERENCE_LASER
    SLIT = DiagramOption.SLIT
    SPECTROMETER = DiagramOption.SPECTROMETER
    WAVE_FRONT_SENSOR = DiagramOption.WAVE_FRONT_SENSOR

    _qt_designer = {
        "group": "ECS Common Dock",
        "is_container": False,
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._image_pixmap: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setFlat(True)
        self.setDiagram(DiagramOption.BLANK)
        self._lightpath_channel_obj = None
        self.setLightpathChannel("")

    def readDiagram(self) -> DiagramOption:
        """Returns the enum of the diagram that is currently in-use."""
        return self._diagram

    def setDiagram(self, diagram: DiagramOption) -> None:
        """Sets the enum of the diagram to use."""
        # Designer sets enum properties as raw ints, so coerce to DiagramOption.
        try:
            diagram = DiagramOption(diagram)
        except ValueError as err:
            raise ValueError(
                f"Invalid diagram option {diagram}, options are: {', '.join(item.name for item in DiagramOption)}"
            ) from err
        if diagram == DiagramOption.BLANK:
            self._image_pixmap = None
        else:
            self._image_pixmap = diagram.get_pixmap()
        self._diagram = diagram
        self.repaint()

    diagram = Property(DiagramOption, readDiagram, setDiagram)

    def readLightpathChannel(self) -> str:
        """Returns the channel used to determine if beam is reaching this widget."""
        return self._lightpath_channel_text

    def setLightpathChannel(self, ch: str) -> None:
        """Selects the channel used to determine if beam is reaching this widget."""
        if not ch:
            self._lightpath_channel_text = ch
            if self._lightpath_channel_obj is not None:
                self._lightpath_channel_obj.disconnect()
            self._lightpath_channel_obj = None
            self._lightpath_status = None
            return
        if ch == self._lightpath_channel_text:
            return
        self._lightpath_channel_text = ch
        self._lightpath_status = False
        if self._lightpath_channel_obj is not None:
            self._lightpath_channel_obj.disconnect()
        self._lightpath_channel_obj = PyDMChannel(
            address=self._lightpath_channel_text, value_slot=self.new_lightpath_state
        )
        self._lightpath_channel_obj.connect()
        self.repaint()

    lightpath_channel = Property(str, readLightpathChannel, setLightpathChannel)

    def new_lightpath_state(self, value: bool):
        """Callback to update the visuals of the lightpath indicator when the channel value changes."""
        self._lightpath_status = value
        self.repaint()

    def paintEvent(self, a0: QPaintEvent) -> None:
        """Render the image and the lightpath indicator when it's time to paint this widget."""
        self.setFlat(True)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        # Draw the image first
        self.draw_image(painter=painter)
        # Draw the lightpath indicator on top of the image
        self.draw_lightpath_indicator(painter=painter)
        # Draw the text on top of the image too
        return super().paintEvent(a0)

    def draw_image(self, painter: QPainter):
        """
        Render the selected diagram widget.

        This will be a QPixmap at the bottom-center of the widget bounds,
        and it will also include the widget background-color rendered
        behind the "square" portion of the diagram.
        """
        if self._image_pixmap is None:
            return
        # Align image with bottom horizontal center and scale as big as will fit
        try:
            image_ratio = self._image_pixmap.height() / self._image_pixmap.width()
        except ZeroDivisionError:
            return
        if image_ratio == 0:
            return
        height_if_full_width = self.width() * image_ratio
        if height_if_full_width <= self.height():
            draw_width = self.width()
            draw_height = int(height_if_full_width)
        else:
            draw_width = int(self.height() / image_ratio)
            draw_height = self.height()
        # Draw the background color in the lower square
        # This usually is unset and ends up being grey
        painter.save()
        bg_color = self.palette().color(QPalette.Background)
        painter.setBrush(bg_color)
        sq_side = min(draw_height, draw_width)
        painter.drawRect(QRect((self.width() - sq_side) // 2, self.height() - sq_side, sq_side, sq_side))
        painter.restore()
        painter.drawPixmap(
            QRect((self.width() - draw_width) // 2, self.height() - draw_height, draw_width, draw_height),
            self._image_pixmap,
        )

    def draw_lightpath_indicator(self, painter: QPainter):
        """
        Render the lightpath state.

        This will be an ellipse at the top-left of the widget bounds,
        filled with cyan if the lightpath channel is "true".
        """
        painter.save()
        if self._lightpath_status is None:
            return
        indicator_size = int(min(self.width(), self.height()) / 5)
        if not indicator_size:
            return
        pen = QPen()
        pen_width = max(1, int(indicator_size * 0.10))
        pen.setWidth(pen_width)
        painter.setPen(pen)
        if self._lightpath_status:
            painter.setBrush(Qt.cyan)
        painter.drawEllipse(pen_width, pen_width, indicator_size, indicator_size)
        painter.restore()

    def closeEvent(self, a0: QCloseEvent) -> None:
        """On close, clean up the pydm channel."""
        if self._lightpath_channel_obj is not None:
            self._lightpath_channel_obj.disconnect()
        return super().closeEvent(a0)

    def setFlat(self, a0: bool) -> None:
        """Prevent flat = False which interferes with our rendering."""
        super().setFlat(True)
