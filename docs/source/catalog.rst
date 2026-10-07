============================
Widget Catalog
============================

This page has names and images of
the most useful widgets provided by qt and pydm
and all the widgets provided by pcdswidgets.

It is intended to be used as a first-pass reference
for users trying to understand which widgets should be used in a screen.

It will contain links to each widget's dedicated documentation page.


**Frequently Used Widget Classes:**
___________________________________

Display / read-only output
--------------------------

.. list-table::
   :header-rows: 1

   * - Widget Name
     - Class
     - Function
     - Example
   * - `Label <https://doc.qt.io/qt-6/qlabel.html>`__
     - QLabel
     - | Static text/image label such as captions, titles, field names,
       | and other non-interactive display text.
     - .. image:: /_static/catalog/qlabel.png
   * - `PyDMLabel <https://slaclab.github.io/pydm/widgets/label.html>`__
     - PyDMLabel
     - | Live read-only display of an EPICS PV value (numbers, strings,
       | enums), optionally formatted with units/precision
     - .. image:: /_static/catalog/pydm_label.png
   * - `PyDMByteIndicator <https://slaclab.github.io/pydm/widgets/byte.html>`__
     - PyDMLabel
     - | Displays individual bits of an integer PV as colored indicators
       | useful as status/alarm bit flags.
     - .. image:: /_static/catalog/pydm_byte_indicator.png

Input / control (write to PV)
-----------------------------

.. list-table::
   :header-rows: 1

   * - Widget Name
     - Class
     - Function
     - Example
   * - `PyDMPushButton <https://slaclab.github.io/pydm/widgets/pushbutton.html>`__
     - PyDMPushButton
     - | Button that writes a fixed/preset value to a PV when clicked
       | (e.g. open, close, set, reset).
     - .. image:: /_static/catalog/pydm_push_button.png
   * - `PyDMLineEdit <https://slaclab.github.io/pydm/widgets/line_edit.html#pydmlineedit>`__
     - PyDMLineEdit
     - Editable text field for reading and writing a PV value. A user
       types a setpoint and it's written to the PV.
     - .. image:: /_static/catalog/pydm_line_edit.png
   * - `PyDMShellCommand <https://slaclab.github.io/pydm/widgets/shell_command.html#pydmshellcommand>`__
     - PyDMShellCommand
     - Button that executes a linked bash shell command.
     - .. image:: /_static/catalog/pydm_shell_command.png

Plots
-----

.. list-table::
   :header-rows: 1

   * - Widget Name
     - Class
     - Function
     - Example
   * - `PyDMTimePlot <https://slaclab.github.io/pydm/widgets/timeplot.html#pydmtimeplot>`__
     - PyDMTimePlot
     - Plot a PV as a function of time.
     - .. image:: /_static/catalog/pydm_time_plot.png
   * - `PyDMScatterPlot <https://slaclab.github.io/pydm/widgets/scatterplot.html#pydmscatterplot>`__
     - PyDMScatterPlot
     - Plot a PV as a function of another PV in a scatter plot.
     - .. image:: /_static/catalog/pydm_scatter_plot.png

Layout / structure
------------------

.. list-table::
   :header-rows: 1

   * - Widget Name
     - Class
     - Function
     - Example
   * - `Vertical Layout <https://doc.qt.io/archives/qtforpython-5/PySide2/QtWidgets/QVBoxLayout.html>`__
     - QVBoxLayout
     - Vertical layout manager — arranges child widgets top-to-bottom.
     - .. image:: /_static/catalog/qvbox_layout.png
   * - `Horizontal Layout <https://doc.qt.io/archives/qtforpython-5/PySide2/QtWidgets/QHBoxLayout.html>`__
     - QHBoxLayout
     - Horizontal layout manager — arranges child widgets left-to-right.
     - .. image:: /_static/catalog/qhbox_layout.png
   * - `Grid Layout <https://doc.qt.io/archives/qtforpython-5/PySide2/QtWidgets/QGridLayout.html>`__
     - QGridLayout
     - Grid layout manager — arranges child widgets in rows and columns.
     - .. image:: /_static/catalog/qgrid_layout.png

Containers
----------

.. list-table::
   :header-rows: 1

   * - Widget Name
     - Class
     - Function
     - Example
   * - `PyDMEmbeddedDisplay <https://slaclab.github.io/pydm/widgets/embedded_display.html#pydmembeddeddisplay>`__
     - PyDMEmbeddedDisplay
     - | Embeds another ``.ui`` screen inside the current one, typically
       | with macros — enables reusable sub-panels and templated rows.
     - N/a

**Composite Widget Templates:**
________________________________

**Common**
----------

Dock: pcdswidgets/common/dock
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::

   * - Widget
     - Function
     - Example
   * - :any:`IndicatorGrid`
     - Standalone implementation of the classic "lucid" grid.
     - .. image:: /_static/catalog/indicator_grid.png
   * - :any:`TabDock`
     - Standalone implementation of the "lucid" tabbed dock.
     - .. image:: /_static/catalog/tab_dock.png
   * - :any:`TabDockButton`
     - Opens a screen in the TabDock.
     - .. image:: /_static/catalog/tab_dock_button.png
   * - :any:`TabDockDiagramButton`
     - | Displays a beamline schematic component, and opens a screen in
       | the TabDock
     - .. image:: /_static/catalog/tab_dock_diagram_button.png

Toolbar: pcdswidgets/common/toolbar
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::

   * - Widget
     - Function
     - Example
   * - :any:`YamlToolbar`
     - | Standalone implementation of the classic "lucid" toolbar.
       | Loads related display, script, and dock buttons from a yaml
       | config.
     - .. image:: /_static/catalog/yaml_toolbar.png

Tools: pcdswidgets/common/tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::

   * - Widget
     - Function
     - Example
   * - :any:`FeatureFinder`
     - Generic "scanner" application to optimize signal.
     - .. image:: /_static/catalog/feature_finder.png
   * - :any:`ViewSaver`
     - | A Tool for adding persistence to screens (the view state is
       | saved to a file, and recovered on reload). Add this widget
       | container to your project and any widget that is supported
       | will automatically be saved. In designer you can opt-out
       | specific widgets and set a dir/file path for the save file.
       | NOTE: widget is invisible at runtime (border goes away).
     - .. image:: /_static/catalog/view_saver.png

**Imaging**
-----------

Common: pcdswidgets/ui/imaging/common
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::

   * - Widget
     - Function
     - Example
   * - :any:`AcquisitionControlFull`
     - | A panel for controlling camera acquisition, such as
       | starting/stopping and setting the capture mode.
     - N/a
   * - :any:`CameraViewerStretch`
     - | Top-level camera viewer that displays the live image alongside a
       | sidebar of collapsible control panels.
     - N/a
   * - :any:`CentroidTrackerFull`
     - N/a
     - N/a
   * - :any:`ColormapIntesityControlFull`
     - | A panel for selecting the colormap and adjusting image intensity
       | levels via a histogram.
     - N/a
   * - :any:`EpicsRoiFull`
     - A panel for drawing, moving, and locking a region-of-interest box
       that syncs its geometry to EPICS PVs.
     - .. image:: /_static/catalog/epics_roi_full.png
   * - :any:`ExposureTimingControlFull`
     - A panel for adjusting exposure time and acquisition timing/rate.
     - N/a
   * - :any:`MarkerSelectionFull`
     - | Widget for placing and configuring up to four crosshair markers
       | (position, color, style, visibility) on camViewer image.
     - .. image:: /_static/catalog/marker_selection_full.png

**Motion**
----------

Common: pcdswidgets/ui/motion/common
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::

   * - Widget
     - Function
     - Example
   * - :any:`MotorBeckhoffSlits`
     - | Motor control for Beckhoff slits to control slit center position
       | and gap.
     - .. image:: /_static/catalog/motor_beckhoff_slits.png
   * - :any:`MotorClassicFull`
     - | Classic full layout for IMS, Beckhoff, or SmarAct motor control.
       | Define "motor_type" for full functionality.
     - .. image:: /_static/catalog/motor_classic_full.png
   * - :any:`MotorClassicRow`
     - | Classic row layout for IMS, Beckhoff, or SmarAct motor control.
       | Define "motor_type" for full functionality.
     - .. image:: /_static/catalog/motor_classic_row.png
   * - :any:`MotorClassicVert`
     - | Classic vertical layout for IMS, Beckhoff, or SmarAct motor
       | control.
       | Define "motor_type" for full functionality.
     - .. image:: /_static/catalog/motor_classic_vert.png
   * - :any:`MotorStateMover`
     - State mover motor control
     - .. image:: /_static/catalog/motor_state_mover.png
   * - :any:`MotorStateMoverExpanded`
     - N/a
     - N/a
   * - :any:`MotorStateMoverExpandedPMPS`
     - N/a
     - N/a
   * - :any:`MotorTcClassicRow`
     - | Classic row layout for IMS, Beckhoff, or SmarAct motor control
       | including motor temperature interlock
     - .. image:: /_static/catalog/motor_classic_row.png
   * - :any:`MotorTipTiltDouble`
     - | Tip/tilt motion control for two motors. Set "motor_style" to
       | drive standard motor record or SmarAct step fields.
     - .. image:: /_static/catalog/motor_tip_tilt_double.png
   * - :any:`MotorTipTiltFull`
     - | Full tip/tilt motion control layout. Set "motor_style" to
       | drive standard motor record or SmarAct step fields.
     - .. image:: /_static/catalog/motor_tip_tilt_full.png
   * - :any:`SvgMultiStateLED`
     - N/a
     - N/a

Expert: pcdswidgets/ui/motion/expert
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::

   * - Widget
     - Function
     - Example
   * - :any:`MotorExpertScreenBeckhoff`
     - Expert configuration options for Beckhoff motors.
     - .. image:: /_static/catalog/motor_expert_screen_beckhoff.png

SmarAct: pcdswidgets/ui/motion/smaract
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::

   * - Widget
     - Function
     - Example
   * - :any:`SmaractOpenLoopClassicRow`
     - N/a
     - N/a
   * - :any:`SmaractOpenLoopContextDouble`
     - SmarAct detailed motion control
     - .. image:: /_static/catalog/smaract_open_loop_context_double.png
