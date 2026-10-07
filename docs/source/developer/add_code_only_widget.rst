===========================
Adding a Code-only Widget
===========================

Using the ``designer`` tool and the build pipeline for managing ``.ui`` layouts is not
strictly required for adding a widget to ``pcdswidgets``.
These are convenience tools for making the development lifecycle smooth for
widgets developed outside of the library,
but you can also add widgets that are fully code-based.


Where to Place the Widget
-------------------------
Even though these are built differently,
the code should be organized similar to the build pipeline.

That is: we should place the widget in the module hierarchy that
best describes the widget's category.

As an example: a common-use motion widget would still be placed
in pcdswidgets/motion/common.


Requirements and Guidelines
---------------------------
- The widget must inherit from ``QWidget`` or from a subclass of ``QWidget``.
- The widget must add a class member that is a designer settings dictionary for ``pydm``, e.g.

    .. code-block:: python

        _qt_designer_ = {
            "group": "ECS Containers",
            "is_container": False,
        }

- You still want to ``make`` to get the widget into the ``designer`` entrypoint.
