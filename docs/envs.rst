=====================
Environment Variables
=====================

An environment variable set within uranium is active for not only the
lifetime of the build, but for any entry points or scripts generated as well.

environment variables can be modified as a regular dictionary:


.. code:: python

    import os

    def main(build):
        build.environment["EDITOR"] = "emacs"
        build.environment["LD_LIBRARY_PATH"] = os.path.join(build.root, "lib")


------------------
Full API Reference
------------------


.. autoclass:: uranium.environment_variables.EnvironmentVariables
    :members: __setitem__, __getitem__
