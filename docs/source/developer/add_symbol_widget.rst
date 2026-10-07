==========================
Adding a New Symbol Widget
==========================

This page details the development process for adding a new symbol widget.
All symbol widgets are currently vacuum widgets.
It was made during the process of creating the PneumaticValveDA widget.


Requirements
------------
You should have the following things in mind before you begin:

- What should the widget look like?
- Is there any existing widget that this is similar to?
- What are my interlock, error, state readback, and control PVs?


Implementation Overview
-----------------------
You'll need to do the following things:

- Add a new icon widget.
- Add a new symbol widget that uses the icon.
- Add your new widget to the designer.
- Update stylesheets to be consistent for your new widget.
- Add a new device class for your widget's expert screen.


Adding a New Symbol
-------------------
The symbols are stored in pcdswidgets/symbols and are implemented by
using the QtGui painter tools. I suggest you pick a class that almost
does what you want as a starting point.
With ``BaseSignalIcon`` as a parent class, the only method you need to override
is ``draw_icon``. Check out the other icons for examples and feel free to
browse the qt documentation.
This process will take a lot of iterations
(edit the file, check the ui, repeat).
To make this process smoother, I added a script embedded in the icons module.
Try this to open an application that simply displays a widget:

.. code-block:: bash

   python -m pcdswidgets.icons.demo ControlValve

Some tips:

- The coordinate system starts from the top left of the icon, so positive y is down
- The expected size of the widget icon is from 0 to 1 in both x and y
- If you want something to be modifiable via stylesheet, PV, etc., you can make it
  a property with qt's @Property flag. This is useful for alarm sensitive coloring,
  for example.
- When drawing a shape, it's useful to parameterize it even if you only use it once.
  This is because you may later want to edit the specifics, but if your QPolygon
  is just a list of numbers this will be very hard. A list of variables like
  "arrow_length" are easier to modify later.
- When designing your shape, note that the widget might need to look good at
  different sizes. Pay particular care in designing widget icons with small features,
  these can become indistinguishable as we shrink the shapes down.


Adding a New Widget Class
-------------------------
Symbol widget classes in ``pcdswidgets`` are constructed from a network of mix-ins and parent
classes. A good place to start is simply copying the most similar existing
widget and modifying the specifics to match yours. Barring something extremely
similar existing, you'll need to delve into the specifics of the inner workings
and I can't encapsulate that in a guide.

In some cases, you may be able to get away with simply copying a widget
and changing the docstrings, attributes, and super calls as appropriate.

For deeper dives, I recommend looking at each mix-in class in isolation to
understand how that particular feature is implemented.

You can test your new widget quickly by running the helper script:

.. code-block:: bash

   python -m pcdswidgets.vacuum.demo PneumaticValveDA CRIX:VGC:11

But you should make some screens with it to explore the finer details.


Adding your Widget to the Designer
----------------------------------
This is probably the easiest step of the process. Simply import your new widget
in designer.py and add an appropriate entry using the qtplugin_factory.

To check that this worked, you can simply open designer. You should see
your widget added to the list.


Stylesheets
-----------
For the widget to properly display its state, it needs an entry in the stylesheet.
For widgets that are exceedingly similar to existing widgets, this might just
involve copying and pasting existing entries in the stylesheet, and editing the
copy to refer to your new widget. This is appropriate for adding a new valve type
for example.

In other cases, you'll need to do involved testing to figure out what stylesheet
gives the look and feel you want for the widget, and make sure this ends up in
the master stylesheet.

The master stylesheet is held in this repo at ``pcdswidgets/stylesheets/masterStyleSheet.qss``

To activate this stylesheet for dev use, you need to set your
``PYDM_STYLESHEET`` environment variable appropriately.
This is done automatically in the pixi env setup,
but you'll have to do it again in your prod environment setup after installing ``pcdswidgets``.

Make sure to open a pull request with your updated stylesheet in that repo and make
sure that your edits get deployed in dev/prod.


The Expert Screen
-----------------
Expert screens can be generated from typhos, but they can also be hand-made.
See ``pcdswidgets/screens``.
