============================
Command-line Interface
============================

``pcdswidgets-show`` is a command-line interface that allows the user to open a widget or screen bundled with ``pcdswidgets`` in a standalone window from the command line.
This is useful for giving easy access to expert screens implemented in ``pcdswidgets`` to users in other contexts, as well as for testing.

Note that, despite a few screens being featured in the help text,
*every* widget and screen defined in ``pcdswidgets`` is available. Use ``pcdswidgets-show --options`` to show all of the options.

Sample invocation::

    pcdswidgets-show motor_state_mover_expert --DEVICE IM3L0:PPM:MMS --PMPS


The current help text for pcdswidgets-show is::

    usage: pcdswidgets-show [-h] [--options] {motor_state_mover_expert,FeatureFinder} ...

    Show a pcdswidgets expert screen or single widget as a screen. Pass --help to individual widget types for specific options.

    options:
    -h, --help            show this help message and exit
    --options             show all screen and widget options and exit

    highlighted screens:
    {motor_state_mover_expert,FeatureFinder}
        motor_state_mover_expert
                            Expert screen for state movers
        FeatureFinder       Live plotting GUI
