===========================
Widget Development
===========================

This subtree contains developer documentation for
creating new widgets and including them in the library.


Why would I add a widget?
-------------------------

Before starting, consider why you might add a widget to ``pcdswidgets``.
Some good reasons may be:

- Making a particularly useful or ubiquitous widget globally available and discoverable
- Making a high-usage widget easier to add to screens and control the settings of

The alternative is to pass your widget around via filepath and macros
using ``PyDMEmbeddedDisplay``, which works great and may be sufficient
for many use cases.


Documenting a Widget
--------------------
All widgets need an entry in the :doc:`/catalog` and an entry for their module in the :doc:`/developer/widgets` subtree.


Creating a Widget
-----------------

.. toctree::
    :maxdepth: 1

    create_composite_widget.rst
    add_composite_widget.rst
    add_code_only_widget.rst
    add_symbol_widget.rst
