===========================
Creating a Composite Widget
===========================

"Composite widget" is a term we use to describe a widget that is composed entirely of smaller standard widgets.
These start their lifecycles as standard ``pydm`` screens and should be created *outside* of ``pcdswidgets``.


Provisioning a Composite Widget
-------------------------------
Before setting up a development environment,
you should aim to create your widget as a ``pydm`` screen and try it out.
It will be simpler and faster to iterate on your design this way
and you can get immediate feedback without doing any library work.

If you don't know how to do this, refer to the ``pydm`` documentation:

- `PyDM Macro Substitution <https://slaclab.github.io/pydm/tutorials/intro/macros.html>`__
- `Creating a small (widget) ui file with macros <https://slaclab.github.io/pydm/tutorials/action/designer_inline.html>`__
- `Creating a screen that uses embedded displays <https://slaclab.github.io/pydm/tutorials/action/designer_main.html>`__

Prematurely putting a widget into ``pcdswidgets`` can put you into an awkward spot of needing to maintain
a fork of ``pcdswidgets`` to run your screen.
This is to be avoided, since running with an official tag provides you with stability and clear upgrade paths.


Widget Sizing
-------------
We have some loose guidelines on widget sizing. These are established to
give us some consistency in application of widgets, as well as to make
it simpler to avoid resizing a widget between library releases.

Device control widgets should fall into exactly one of the following
size classes, but they do not have to if there's a good reason to
diverge. (Note: we can add more size classes if necessary).

.. list-table::
   :header-rows: 1

   * - Size Class
     - Width
     - Height
   * - Double
     - 400 px
     - 250 px
   * - Full
     - 400 px
     - 125 px
   * - Compact
     - 100 px
     - 75 px
   * - Row
     - 800 px
     - 50 px
   * - Stretch
     - Custom/Big
     - Custom/Big

Note that this isn't enforced in any way.

To ensure sizing consistency, set the minimum and maximum sizes to
values that look good throughout your desired size range. It's
recommended to use fixed sizing when possible because dynamic sizing is
hard to implement correctly.

Widgets should always be maintained to work at the original designed
size, because changing this can break existing screens.


Adding Logic to a Composite Widget
----------------------------------
The above instructions are sufficient if your screen can be expressed
entirely through standard qt and pydm widgets, but you'll need some additional
steps to add logic if you'd like to customize the behavior further.


Option 1: ``pydm`` Built-ins
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The first way to do this is to follow the ``pydm`` instructions for
adding logic to a screen. This involves creating a python file
with a ``Display`` class that references your ``ui`` file.

See `Adding Code into the Main Display <https://slaclab.github.io/pydm/tutorials/action/little_code.html>`_
from the ``pydm`` docs for more information on this.


Option 2: Import from ``pcdswidgets``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The other most logical way is to use the ``pcdswidgets`` internals to set up your widget classes.
This takes some additional work up front, but does have some advantages,
including some automated type hints and a more straightforward
transfer into ``pcdswidgets`` later if you decide to add it.

The critical imports you'll want to use are:

.. code-block:: python

    from pcdswidgets.builder.build import build_uic, build_base_widget

Calling these functions will create two python files:

- One is a translation of the ui file using pyuic, plus some tweaks
- The other, the base widget, is a widget that uses the pyuic translation and adds some nice helpers such as type hinting

.. note::
    You will need to regenerate these files each time you update your ``ui`` file.

You'll then want to create a widget that inherits from the base class to add additional logic.
There is some guidance for how to do this in :doc:`add_composite_widget`.


My Widget is Great, Can I Merge it in?
--------------------------------------
See :doc:`add_composite_widget`.
