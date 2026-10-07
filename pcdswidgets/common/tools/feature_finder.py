"""Module for FeatureFinder"""
# Originally generated from jinja template ui_main_widget.j2
# This file can be safely edited to change the runtime behavior of the widget.

from __future__ import annotations

import json
import logging
import operator
import os
from datetime import datetime
from math import inf
from pathlib import Path
from string import Template
from sys import float_info

import numpy as np
from epics import caput
from pydm import PyDMChannel
from pydm.widgets import PyDMLabel, PyDMLineEdit, PyDMPushButton
from pyqtgraph import InfiniteLine, mkPen
from qtpy.QtCore import QTimer, Slot
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
)

from pcdswidgets.builder.designer_options import DesignerOptions
from pcdswidgets.generated.common.tools.feature_finder_base import FeatureFinderBase
from pcdswidgets.motion.common.svg_multi_state_led import SvgMultiStateLED

logger = logging.getLogger(__name__)


class FeatureFinder(FeatureFinderBase):
    designer_options = DesignerOptions(
        group="ECS Common Tools",
        is_container=False,
        icon="feature_finder_icon.png",
    )

    def __init__(self, parent=None, macros=None):
        super().__init__(parent=parent, macros=macros)

        # Attribute list convenience
        # motor
        self._step_size = 0
        self._motor_pv = ""
        self._motor_egu = ""
        self._lower_limit = 0
        self._upper_limit = 0
        self._dmov = None
        self._motor_buttons_connected = False
        self._limits_connected = False
        self._motor_egu_ch = None

        # Data arrays for plotting
        self._motor_positions = []
        self._detector_values = []
        # detector
        self._detector_pv = ""
        self._detector_egu = ""
        self._detector_egu_ch = None

        # Config file for caching
        self._config_file = Path.home() / ".config" / "feature_finder_settings.json"

        # Add the optional inversion for the x-axis with associated signal
        self._invert = False
        self.invert_x_checkbox.stateChanged.connect(self.update_invert)

        # Track motor state
        self._motor_moving = False
        self._step_called = False
        self._running = False
        self._run_direction = None

        # Timer for run mode
        self._run_timer = QTimer()
        self._run_timer.timeout.connect(self._continue_run)

        # Cross-hairs
        self._crosshair_timer = QTimer()
        self._crosshair_timer.timeout.connect(self._update_crosshair)
        self._crosshair_timer.start(100)  # Update every 100ms

        # Some stylization and housekeeping on QLabels
        ## Step size
        self.step_size_set.setMinimum(-inf)
        self.step_size_set.setMaximum(inf)
        self.step_size_set.editingFinished.connect(self.update_step_size)
        self.step_size_set.editingFinished.connect(self.save_settings)

        # Connect the reinitialize graph button
        self.reset_graph.clicked.connect(self._reset_graph)

        # Connect the button for swapping PVs
        self.change_pvs_button.clicked.connect(self.show_change_pvs_dialog)

        # Set a timer and wait for macros to be available
        self._macros_timer = QTimer(parent=self)
        self._macros_timer.timeout.connect(self.post_init_setup)
        self._macros_timer.setInterval(100)
        self._macros_timer.setSingleShot(True)

    def after_set_macro(self, macro_name: str, value: str) -> None:
        """
        Overriding the parent method for this to handle PyDMWidget channel swapping

        Parameters
        ----------
        macro_name : str
            key name of the macro. In this widget, one of: ['motor', 'detector']
        value : str
            The value of the macro. In this widget, this is a PV.
        """
        widget: PyDMLabel | PyDMLineEdit | PyDMPushButton | SvgMultiStateLED
        for widget_name in self._macro_to_widget[macro_name]:
            widget = getattr(self, widget_name)
            if hasattr(widget, "set_channel"):
                # We're going to be cautiously explicit about set_channel
                for prop, templ in self._widget_to_pre_template[widget_name]:
                    if prop == "channel":
                        chan = Template(templ).substitute(self._macro_values)
                        widget.set_channel(chan)

        if macro_name == "motor":
            self._motor_pv = value
            # Extra work to do for motor
            if self._dmov:
                self._dmov.disconnect(destroying=True)
            # Then add the new connection
            self._dmov = PyDMChannel(address=f"ca://{self._motor_pv}.DMOV", value_slot=self.on_motor_done_moving)
            self._dmov.connect()

            self.connect_motor()

        if macro_name == "detector":
            self.connect_detector()

        # Start the post-init timer
        self._macros_timer.start()

    def post_init_setup(self) -> None:
        """
        Need to wait for the object to exist for its macros to be available
        """
        if not self.get_macro("motor") or not self.get_macro("detector"):
            self._macros_timer.start()
            return

        # Load settings, if possible
        self.load_settings()

        # Set-up the graph
        self.setup_plot()

    def _get_config_key(self) -> str:
        """
        Generate a unique key for this motor/detector pairing.

        Returns
        -------
        str
            Configuration key in format 'motor_pv::detector_pv'
        """
        return f"{self._motor_pv}::{self._detector_pv}"

    def save_settings(self) -> None:
        """
        Save current settings to the config file for this motor/detector pair.
        """
        try:
            # Load existing configs
            if self._config_file.exists():
                with open(self._config_file, "r") as f:
                    all_configs = json.load(f)
            else:
                all_configs = {}

            # Update config for this motor/detector pair
            key = self._get_config_key()
            if key == "::":
                # Means we tried to save before macros loaded, ignore
                return
            all_configs[key] = {
                "step_size": self.step_size_set.value(),
                "lower_limit": self.lower_limit_set.value(),
                "upper_limit": self.upper_limit_set.value(),
                "motor_pv": self._motor_pv,
                "detector_pv": self._detector_pv,
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            # Save back to file
            with open(f"{self._config_file}.tmp", "w") as f:
                json.dump(all_configs, f, indent=2)

            logger.debug(f"Settings saved for {key}")

            os.replace(f"{self._config_file}.tmp", f"{self._config_file}")

        except Exception as e:
            logger.warning(f"Failed to save settings: {e}")

    def load_settings(self) -> None:
        """
        Load saved settings from the config file for this motor/detector pair.
        """
        setter: QDoubleSpinBox

        # Wait for the macros to actually finish connecting
        if not self._motor_pv or not self._detector_pv:
            QTimer.singleShot(100, self.load_settings)
            return

        try:
            if self._config_file.exists():
                with open(self._config_file, "r") as f:
                    all_configs = json.load(f)

                key = self._get_config_key()
                if key in all_configs:
                    config = all_configs[key]

                    properties = ["step_size", "lower_limit", "upper_limit"]

                    for prop in properties:
                        if prop in config:
                            setattr(self, f"_{prop}", config[prop])
                            setter = getattr(self, f"{prop}_set")
                            setter.setValue(config[prop])
                            logger.info(f"Loaded {prop.replace('_', ' ')}: " + str(getattr(self, f"_{prop}")))
                            # Manually call the update method to sync the attr
                            update_method = getattr(self, f"update_{prop}")
                            update_method()
                else:
                    logger.info(f"No saved settings for {key}")
            else:
                logger.info("No config file found, using defaults")
                self._lower_limit = 0
                self._upper_limit = 0

        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")

    def connect_motor(self) -> None:
        """
        Once the motor macro is available, connect all relevant attr, widgets, etc.
        """
        # Get the EGU as a channel
        if self._motor_egu_ch:
            self._motor_egu_ch.disconnect(destroying=True)

        self._motor_egu_ch = PyDMChannel(f"ca://{self._motor_pv}.EGU", value_slot=self.update_motor_egu)
        self._motor_egu_ch.connect()

        # Connect the step/run buttons
        self.connect_motor_buttons()
        # Connect the limits
        self.connect_limits()

    def update_motor_egu(self, value) -> None:
        """
        Call back to update the motor EGU units when they change.
        """
        setter: QDoubleSpinBox
        getter: QLabel

        self._motor_egu = value

        # Update our QLabel widgets
        for prop in ["step_size", "lower_limit", "upper_limit"]:
            setter = getattr(self, f"{prop}_set")
            getter = getattr(self, f"{prop}_get")
            prop_val = getattr(self, f"_{prop}")

            setter.setSuffix(f" {self._motor_egu}")
            getter.setText(f" {prop_val:.6e} {self._motor_egu}")

        self.plot.setLabel("bottom", f"{self._motor_pv}", units=self._motor_egu)

    def connect_motor_buttons(self) -> None:
        """
        Connect the motor widgets to their appropriate slots,
        presumptively after pydm already expanded macros.
        """
        widget: PyDMPushButton

        if self._motor_buttons_connected:
            logger.debug("Motor buttons already connected. No callbacks to update.")
            return

        logger.debug(f"Connecting motor buttons to: {self._motor_pv}")
        # Attach the step and run buttons to their slots
        for dir in ["fwd", "bwd"]:
            for act in ["step", "run"]:
                widget = getattr(self, f"{dir}_{act}")
                slot = getattr(self, f"_{dir}_{act}")
                widget.clicked.connect(slot)

        # And make sure the .STOP field also aborts continuous runs
        self.stop.clicked.connect(self._stop_run)
        self._motor_buttons_connected = True

    def connect_limits(self) -> None:
        """
        Connect the scan limit functions to their widgets, then format them.
        If they're already connected, update them.
        """
        widget: QDoubleSpinBox

        for lim in ["lower", "upper"]:
            # Find the setter widget
            widget = getattr(self, f"{lim}_limit_set")
            # Get the update function
            update = getattr(self, f"update_{lim}_limit")
            if not self._limits_connected:
                # Connect the signal to the updater
                widget.editingFinished.connect(update)
                widget.editingFinished.connect(self.save_settings)
                # Set the range for steps to big, big number
                widget.setRange(-float_info.max, float_info.max)
            widget.setSuffix(f" {self._motor_egu}")
            widget.setValue(getattr(self, f"_{lim}_limit"))
            # Then update the widget
            update()

        if not self._limits_connected:
            self._limits_connected = True

    def connect_detector(self) -> None:
        """
        Once the meter macro is available, connect all relevant widgets and update attr.
        """
        self._detector_pv = self.get_macro("detector")
        if self._detector_egu_ch:
            self._detector_egu_ch.disconnect(destroying=True)
        self._detector_egu_ch = PyDMChannel(f"ca://{self._detector_pv}.EGU", value_slot=self.update_detector_egu)
        self._detector_egu_ch.connect()

    def update_detector_egu(self, value: str) -> None:
        """
        Call back to update the detector EGU units when they change.
        """
        self._detector_egu = value
        self.plot.setLabel("left", f"{self._detector_pv}", units=self._detector_egu)

    @Slot()
    def show_change_pvs_dialog(self):
        """
        Show a dialog to change the motor and detector PV names.
        Includes a confirmation step before applying changes.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Change PVs")
        dialog.setModal(True)
        dialog.resize(400, 150)

        # Create form layout
        layout = QFormLayout()

        # Motor PV input
        self._motor_edit = QLineEdit(self._motor_pv)
        layout.addRow("Motor PV:", self._motor_edit)

        # Detector PV input
        self._detector_edit = QLineEdit(self._detector_pv)
        layout.addRow("Detector PV:", self._detector_edit)

        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(lambda: self.confirm_pv_changes(dialog))
        button_box.rejected.connect(dialog.reject)
        layout.addRow(button_box)

        dialog.setLayout(layout)

        # Adjust size to fit contents
        dialog.adjustSize()
        dialog.setFixedHeight(dialog.sizeHint().height())

        dialog.exec_()

    def confirm_pv_changes(self, dialog: QDialog):
        """
        Show confirmation dialog before applying PV changes.

        Parameters
        ----------
        dialog : QDialog
            The parent dialog to close after confirmation
        """
        new_motor_pv = self._motor_edit.text().strip()
        new_detector_pv = self._detector_edit.text().strip()

        # Validate PVs are not empty
        if not new_motor_pv or not new_detector_pv:
            QMessageBox.warning(dialog, "Invalid Input", "Motor and Detector PVs cannot be empty.")
            return

        # Check if anything actually changed
        if new_motor_pv == self._motor_pv and new_detector_pv == self._detector_pv:
            logger.warning("No changes to apply after PV change request.")
            dialog.accept()
            return

        # Show confirmation dialog
        confirm = QMessageBox.question(
            dialog,
            "Confirm PV Changes",
            f"Are these changes correct?\n\n"
            f"Motor:\n  {self._motor_pv} → {new_motor_pv}\n\n"
            f"Detector:\n  {self._detector_pv} → {new_detector_pv}\n\n"
            f"This will reset the current scan data.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # Default to No for safety
        )

        if confirm == QMessageBox.Yes:
            # User confirmed, apply changes
            try:
                self.save_settings()
                self._reset_graph()
                self.set_macro("motor", new_motor_pv)
                self.set_macro("detector", new_detector_pv)
                dialog.accept()
            except Exception as e:
                logger.error(f"Failed to apply PV changes: {e}")
                QMessageBox.critical(dialog, "Error", f"Failed to apply PV changes:\n{e}")
        else:
            # User cancelled - don't close the dialog, let them edit or cancel
            logger.debug("PV change cancelled by user.")

    @Slot(int)
    def on_motor_done_moving(self, val: int) -> None:
        """
        Monitor motor.DMOV falling edge to detect when movement completes.
        Return early if movement is not from the step functions.

        Parameters
        ----------
        val : int
            motor.DMOV field (0 = moving, 1 = done)
        """
        done = bool(val)

        # Return early if movement is not from a step
        if not self._step_called:
            return

        # Detect transition from moving to done
        if self._motor_moving and done:
            self.update_plot_data()

            # If we're in continuous run mode, schedule the next step
            if self._running:
                # Let's start the timer then
                self._run_timer.start(100)
        elif not done:
            self._motor_moving = True

    @Slot()
    def update_invert(self) -> None:
        """
        Update the optional x-axis inversion for plotting purposes
        """
        self._invert = self.invert_x_checkbox.isChecked()
        self.invert_x_axis()

    @Slot()
    def update_step_size(self) -> None:
        """
        Update the step size.
        """
        self._step_size = self.step_size_set.value()
        self.step_size_get.setText(f" {self._step_size:.6e} {self._motor_egu}")

    @Slot()
    def update_lower_limit(self) -> None:
        """
        Update the lower limit.
        """
        self._lower_limit = self.lower_limit_set.value()
        self.lower_limit_get.setText(f" {self._lower_limit:.6e} {self._motor_egu}")

    @Slot()
    def update_upper_limit(self) -> None:
        """
        Update the lower limit.
        """
        self._upper_limit = self.upper_limit_set.value()
        self.upper_limit_get.setText(f" {self._upper_limit:.6e} {self._motor_egu}")

    def check_limit(self, target: float, limit: str) -> float:
        if limit not in ["lower", "upper"]:
            raise ValueError(f"Invalid limit of {limit}")

        # If our limits aren't actually set, then the user isn't picky.
        if self._lower_limit == self._upper_limit and self._lower_limit == 0:
            return target

        # Else we should respect the limits
        if limit == "upper":
            lim = getattr(self, f"_{limit}_limit")
            target = lim if target > lim else target
        if limit == "lower":
            lim = getattr(self, f"_{limit}_limit")
            target = lim if target < lim else target

        return target

    @Slot()
    def _bwd_step(self) -> None:
        """
        Move the motor backward one step, restricted by the lower limit
        """
        target = self.position_get.value - self.step_size_set.value()
        lim = "lower" if self._step_size > 0 else "upper"
        target = self.check_limit(target, limit=lim)

        logger.info(f"Stepping to {target:.6f} {self._motor_egu}")
        self._step_called = True

        caput(pvname=f"{self._motor_pv}.VAL", value=target)

    @Slot()
    def _bwd_run(self) -> None:
        """
        Continually move the motor backwards, until we hit the
        lower limit for the scan. Clicking the button again
        will stop the run.

        The stop button will also override the run behavior.
        """
        limit = "_lower_limit" if self._step_size > 0 else "_upper_limit"
        compare = operator.le if self._step_size > 0 else operator.ge
        # Don't be silly and try to step with no step size
        if self._step_size == 0:
            logger.warning("Attempting to run scan with step size of 0!")
            return
        if compare(self.position_get.value, getattr(self, limit)):
            logger.warning(f"Attempting to scan to {getattr(self, limit)} when motor is already there!")
            return
        if self._running:
            # Stop the run
            self._stop_run()
        else:
            # Start running backward
            self.bwd_run.setStyleSheet("background-color: #FFEA02;")
            self.bwd_run.setToolTip("Click again to stop run")
            logger.info("Starting backward continuous run")
            self._running = True
            self._run_direction = "bwd"

            # Take the first step
            self._bwd_step()

    @Slot()
    def _fwd_step(self) -> None:
        """
        Move the motor forward one step, restricted by the upper limit.
        """
        target = self.position_get.value + self.step_size_set.value()
        lim = "upper" if self._step_size > 0 else "lower"
        target = self.check_limit(target, limit=lim)

        logger.info(f"Stepping to {target:.6f} {self._motor_egu}")
        self._step_called = True

        caput(pvname=f"{self._motor_pv}.VAL", value=target)

    @Slot()
    def _fwd_run(self) -> None:
        """
        Continually move the motor forwards, until we hit the
        lower limit for the scan
        """
        limit = "_upper_limit" if self._step_size > 0 else "_lower_limit"
        compare = operator.ge if self._step_size > 0 else operator.le
        # Don't be silly and try to step with no step size
        if self._step_size == 0:
            logger.warning("Attempting to run scan with step size of 0!")
            return

        if compare(self.position_get.value, getattr(self, limit)):
            logger.warning(f"Attempting to scan to {getattr(self, limit)} when motor is already there!")
            return

        if self._running:
            # Stop the run
            self._stop_run()
        else:
            # Start running forward
            self.fwd_run.setStyleSheet("background-color: #FFEA02;")
            self.fwd_run.setToolTip("Click again to stop run")
            logger.debug("Starting forward continuous run")
            self._running = True
            self._run_direction = "fwd"

            # Take the first step
            self._fwd_step()

    @Slot()
    def _continue_run(self) -> None:
        """
        Continue the run in the current direction if not at a limit.
        Called after motor finishes moving.
        """
        if not self._running:
            return
        # Stop the timer immediately to prevent multiple calls
        self._run_timer.stop()

        # And store these locals for convenience
        current_pos = self.position_get.value
        step_size = self._step_size

        # Check if we've hit the limits
        if self._run_direction == "fwd":
            # Check if we can take another step forward
            next_target = current_pos + step_size
            lim = "upper" if self._step_size > 0 else "lower"
            next_target = self.check_limit(next_target, limit=lim)

            if next_target == current_pos:
                # This means our next target is already
                # being throttled by the limit, do not pass go
                # do not collect $200
                self._stop_run()
                return

            # Take another step forward
            self._fwd_step()

        elif self._run_direction == "bwd":
            # Check if we can take another step backward
            next_target = current_pos - step_size
            lim = "lower" if self._step_size > 0 else "upper"
            next_target = self.check_limit(next_target, limit=lim)

            if next_target == current_pos:
                # You're already there silly, stop it.
                self._stop_run()
                return

            # Take another step backward
            self._bwd_step()

    def _stop_run(self) -> None:
        """
        Stop the continuous run.
        """
        if self._running:
            self._running = False
            self._run_direction = None
            for dir in ["fwd", "bwd"]:
                widget = getattr(self, f"{dir}_run")
                widget.setStyleSheet("background-color: #EEEEEE; color: #232323")
                widget.setToolTip(f"Run continuously {dir}")
            self._run_timer.stop()

    def setup_plot(self) -> None:
        """
        Configure the scatter plot.
        PyDMScatterPlot should've made this easy, but since we only want
        data to update when the steps are completed, it complicates things.
        """
        plot = self.plot

        plot.setLabel("left", f"{self._detector_pv}", units=self._detector_egu)
        plot.setLabel("bottom", f"{self._motor_pv}", units=self._motor_egu)

        # Configure plot appearance
        plot.showGrid(x=True, y=True, alpha=0.3)

        left_axis = plot.plotItem.getAxis("left")
        left_axis.enableAutoSIPrefix(False)

        # Create the curve using pyqtgraph directly
        self._scan_curve = plot.plotItem.plot(
            [],
            [],
            pen=mkPen(color="k", width=1),
            symbol="o",
            symbolSize=8,
            symbolBrush="k",
            name="scan_data",
        )

        if not hasattr(self, "_vline") or not hasattr(self, "_hline"):
            self._vline = InfiniteLine(angle=90, movable=False, pen=mkPen("r", width=1, style=2))
            self._hline = InfiniteLine(angle=0, movable=False, pen=mkPen("r", width=1, style=2))
            plot.plotItem.addItem(self._vline, ignoreBounds=True)
            plot.plotItem.addItem(self._hline, ignoreBounds=True)

        plot.plotItem.enableAutoRange()

    @Slot()
    def _reset_graph(self) -> None:
        """
        Reset the curve data and reinitialize data buffer.
        """
        logger.debug("Resetting curve and plot data.")

        self._motor_positions = []
        self._detector_values = []

        # Clear the curve data directly
        if hasattr(self, "_scan_curve"):
            self._scan_curve.setData([], [])

    def _update_axis_range(self, axis: str) -> None:
        """
        Manually set the range for an axis on the plot.

        Parameters
        ----------
        axis : str
            One of either ['x', 'y'].
        """

        if axis == "y":
            values = np.array(self._detector_values)
            crosshair = self.detector_get.value
            range_setter = self.plot.plotItem.setYRange

        elif axis == "x":
            # Need to be aware of optional inversion
            invert = -1 if self._invert else 1
            values = invert * np.array(self._motor_positions)
            crosshair = invert * self.position_get.value
            range_setter = self.plot.plotItem.setXRange

        else:
            # fed invalid axis param, bad!
            logger.warning(f"Invalid axis option: {axis}")
            return

        values = np.append(values, crosshair)

        if len(values) > 0:
            _min = float(values.min())
            _max = float(values.max())
            _range = _max - _min

            min_padding = 0.01 if axis == "x" else 1e-9

            if _range < min_padding:
                padding = min_padding
            else:
                padding = 0.1 * _range

            logger.debug(f"Setting {axis} axis range to:{_min - padding}, {_max + padding}")

            range_setter(_min - padding, _max + padding, padding=0)

    def invert_x_axis(self) -> None:
        """
        Update the plot after the inversion state changes, causes
        the plot to update immediately.
        """

        logger.debug("Inverting the x-axis, updating plot")

        invert = -1 if self._invert else 1

        # Invert the array
        x_values = invert * np.array(self._motor_positions)
        y_values = np.array(self._detector_values)

        # Send the update to the plot data
        self._scan_curve.setData(x=x_values, y=y_values)

        self._update_axis_range("x")

    def update_plot_data(self) -> None:
        """
        Update the plot after motor movement completes.
        """

        # Don't bother if the detector doesn't exist
        # or if we are manually moving the stage from elsewhere
        if not self._detector_pv or not self._step_called:
            return

        try:
            # Read current motor position and detector value
            motor_position = self.position_get.value
            detector_value = self.detector_get.value

            # Append to arrays
            self._motor_positions.append(motor_position)
            self._detector_values.append(detector_value)

            invert = -1 if self._invert else 1
            x_values = invert * np.array(self._motor_positions)
            y_values = np.array(self._detector_values)

            # Update the curve data
            self._scan_curve.setData(x=x_values, y=y_values)

            self._update_axis_range("x")
            self._update_axis_range("y")

            logger.debug(f"Plot updated: motor={motor_position:.4f},detector={detector_value:.5e}")

        except Exception as e:
            logger.error(f"Failed to update plot: {e}")

        # Make sure we reset this flag after an update
        finally:
            self._step_called = False

    @Slot()
    def _update_crosshair(self) -> None:
        """
        Update crosshair position from current PyDMLabel values.
        """
        if not hasattr(self, "_vline") or not hasattr(self, "_hline"):
            return

        invert = -1 if self._invert else 1

        # Get current values from the labels
        if self.position_get.value and self.detector_get.value:
            motor_position = invert * self.position_get.value
            detector_value = self.detector_get.value

            self._vline.setPos(motor_position)
            if not self._vline.isVisible():
                self._vline.setVisible(True)

            self._hline.setPos(detector_value)
            if not self._hline.isVisible():
                self._hline.setVisible(True)
