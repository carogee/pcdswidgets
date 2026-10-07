===========================
Adding a Composite Widget
===========================

If you've created a composite widget (:doc:`create_composite_widget`)
and are ready to add it into this library,
this is the page for you.

.. note::
    This process will require you to set up your development environment,
    see :doc:`environment`.


Part 1: Copy your .ui file in
-----------------------------

1. Decide on your widget category: this is the subsystem and the type of
   the widget.

   - Example subsystems include ``motion`` and ``vacuum``.
   - Example types include ``common``, ``smaract``, and ``beckhoff``.

2. Copy your ``.ui`` file into ``pcdswidgets`` in the folder
   corresponding with your choices in step 1:
   ``pcdswidgets/ui/${subsystem}/${type}``

   - Example: ``pcdswidgets/ui/motion/beckhoff``
   - If this folder does not exist, consider if an existing folder is
     appropriate.
   - If no existing folder is appropriate, feel free to create a new
     folder.

3. Rename your ``.ui`` file to match the widget naming convention below.

   - It's important to be intentional about widget naming because
     renaming a widget can break existing screens.


Widget Naming
-------------

Widget names and ui filenames should have one to one correspondence and
contain three parts:

- Type of device controlled
- Descriptor word to differentiate this widget from other possible
  widgets with the same device type and size
- Optional size class signifier
  (or, if none are suitable, another descriptive suffix)

For casing:

- ``.ui`` filenames should be lowercase_with_underscores for ease of working with filenames.
- Class names should use CamelCase to match qt and python naming conventions.
- The class name will be generated automatically from the ui filename.

Examples:

- ``motor_classic_full.ui`` (``MotorClassicFull``)
  - Controls a generic EPICS motor record
  - Is inspired by the classic EDM style
  - Is sized to be the "full" size
- ``motor_tc_classic_row.ui`` (``MotorTcClassicRow``)
  - Controls a generic EPICS motor record with a thermocouple added
  - Is inspired by the classic EDM style
  - Is sized to be the "row" size

Other guidelines:

- The name should not be unnecessarily long, but avoid abbreviations.
- If multiple devices are controlled, include them in order of
  importance, e.g. ``MotorTcClassicRow``.
- There is no need to end a widget name or filename with "Widget".
  Please avoid this.
- Widgets should never be renamed between tags, this will break existing
  screens.
- Widgets named before 2026 may break some of these rules because we
  don't want to rename them.


Part 2: Build and Test
----------------------

4. Run ``make`` to generate the code and update the project metadata.

   - This will generate at least three ``.py`` files and edit some other files.
   - Do not edit the files in ``generated``.
   - See :doc:`build` for more information about what this process does.

5. Try it out!

   - Run ``pixi run designer`` and make a test screen.
     (Which, reminder: only works on rocky9 at LCLS).
   - After you've made a test screen, then do
     ``pixi run pydm my_screen.ui`` for further testing.
   - Make sure to take screenshots to include in your pull request.

At this point, if you like what you see, you're actually done.
You can commit, push, and make a pull request if you'd like.
The next few sections are optional.

.. note::
    - If you edit the ui file, you should ``make`` again,
      or your changes will not take effect.
    - If you change your mind about which subsystem and type directory you'd
      like to use, you must manually delete the generated files from the old
      locations.


Optional: Edit the Designer Settings
------------------------------------

One of the built files is in ``pcdswidgets/ui/${subsystem}/${type}``.

Unlike the files in ``generated``, this file is free to edit, and, among
other things, contains a ``DesignerOptions`` specification for the
widget.

This looks something like:

.. code-block:: Python

   class MyClassFull(MyClassFullBase):
       designer_options = DesignerOptions(
           group="ECS Subsystem Type",
           is_container=False,
           icon=IconOptions.NONE,
       )

The editable options are

- ``group``, which determines which category the widget sorts into in the designer sidebar.
- ``is_container``, which tells designer if we should be able to drag other widgets into this one in designer.
- ``icon``, which tells designer which icon to use in the designer sidebar (see next section).


Optional: Choose a Designer Icon
--------------------------------

The designer icon is the symbol that appears to the left of the widget
name in the left-hand widget box. The default designer icon is simply
the ``Qt`` logo. If you'd like to change it, you have a few options.

1. Option 1: use ``IconOptions`` (recommended)

   - ``pydm`` provides the free subset of fontawesome as icons.
   - You can select one of these by changing ``IconOptions.NONE`` to any
     of the other enum options.
   - If you're using an IDE, the options should autocomplete.
   - To see all of the options, run ``show_icon_options.sh``. This will
     open up a grid with all of the options and names.

Here's an example:

.. code-block:: python

   class MyClassFull(MyClassFullBase):
       designer_options = DesignerOptions(
           group="ECS Subsystem Type",
           is_container=False,
           icon=IconOptions.expand_arrows_alt,
       )

2. Option 2: create an image file and place it in the ``icons`` folder.

   - You can set ``icon="my_image.png"`` and it should load
     appropriately in designer.

3. Option 3: Create your own ``QIcon`` however you like

   - You can use the ``Qt`` APIs to create your own icon object.
   - Please refer to the ``Qt``/``PyQt`` docs for how to do this.
   - Keep ``icon=IconOptions.NONE``, or remove the line entirely.
   - Override the ``get_designer_icon`` method on your widget to return
     your ``QIcon``. This must be either a ``classmethod`` or a
     ``staticmethod`` (use the decorators):

   .. code-block:: python

      class MyClassFull(MyClassFullBase):
          designer_options = DesignerOptions(
              group="ECS Subsystem Type",
              is_container=False,
              icon=IconOptions.NONE
          )

          @staticmethod
          def get_designer_icon() -> str:
              """Icon for usage in Qt designer."""
              return QIcon("path/to/your/awesome/icon.png")


Optional: Add Logic to a Composite Widget
-----------------------------------------

The widget class here that includes the ``designer_options`` object is
exactly the class that will be used when your widget is included in a
screen. This means you can add code to the widget to override and extend
any built-in behavior.

There are a few things to keep in mind when you do this:

1. If you override ``__init__``, you must call ``super().__init__(parent)`` before
   doing any other ``Qt``-related operations.
2. There is no way to pass custom arguments to ``__init__`` in ``designer``.
   - Any parameterization should be done via ``Qt`` properties, which will show up in the sidebar.
   - If you do this, do not assume that the properties will be set in any particular order.
   - Make your code work regardless of which order the properties are set in.
3. Be wary of backwards compatibility.
   - Removing properties from a widget will break existing screens.

Here is an example where we add a single configuration parameter that
does nothing. In practice, you would also change something meaningful
about the widget during the setter.

.. code-block:: python

   try:
       from qtpy.QtCore import pyqtProperty
   except ImportError:
       from qtpy.QtCore import Property as pyqtProperty  # type: ignore


   class MyClassFull(MyClassFullBase):
       designer_options = DesignerOptions(
           group="ECS Subsystem Type",
           is_container=False,
           icon=IconOptions.NONE,
       )

       def __init__(self, parent: QWidget | None = None):
           super().__init__(parent)
           self._my_value = 0

       def get_my_value(self) -> int:
           return self._my_value

       def set_my_value(self, value: int) -> None:
           self._my_value = value

       my_value = pyqtProperty(int, get_my_value, set_my_value)


Composite Widget Limitations
----------------------------

- Widgets that contain ``PyDMEmbeddedDisplay`` are not supported:
  bootstrap these by turning the contents into widgets themselves.
- The automatic type hinting runs into issues when the qt object names
  are the same as the classnames. If you want to extend the composite
  widget class in python, giving your child widgets more unique names
  will result in more useful type hints, automatically.
- Only direct ``QString`` and ``QStringList`` properties are supported.
  We still need to implement support for item-based ``QString`` widgets
  such as ``QListWidget``.
- In ``pydm``, you can edit a ui file by hand and add a macro anywhere.
  This is not supported for composite widgets.
