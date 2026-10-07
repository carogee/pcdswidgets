==========================
Best Practices for Testing
==========================

``pcdswidgets`` is inherently driven by the user experience,
so there will need to be a mix of automated and interactive testing.


Unit Tests
----------
Any widget that has testable components,
i.e. any behavior with an objectively correct answer,
should have that behavior tested in the unit tests suite.

This will help avoid critical regressions.

The unit test suite uses ``pytest-qt`` to help manage tests
that need to create and manipulate widgets.


Designer Tests
--------------
Before merging and after any functional commits,
widgets should be tested using the following workflow:

1. Open a blank screen in ``designer``
2. Add the widget in
3. Try each of the options
4. Save, open in pydm
5. Confirm behavior

It's important to start this step from the very beginning
to make sure the first experience is smooth.
It's very easy to break the ``designer`` experience while
maintaining runtime logic.


Testing with ``pcdswidgets-show``
---------------------------------
Widgets should also be tested with ``pcdswidgets_show``,
see :doc:`/pcdswidgets_show`.

Every widget should be openable from this command-line tool.
