import logging
import os
import virtualenv
from .config import Config
from .executables import Executables
from .hooks import Hooks
from .history import History
from .packages import Packages
from .tasks import Tasks
from .environment_variables import EnvironmentVariables
from .lib.script_runner import build_script, get_public_functions
from .lib.asserts import get_assert_function
from .exceptions import UraniumException, ScriptException
from .lib.sandbox.venv.activate_this import write_activate_this
from .lib.sandbox import Sandbox
from .lib.log_templates import STARTING_URANIUM, ENDING_URANIUM
from .lib.utils import log_multiline
from .remote import get_remote_script

u_assert = get_assert_function(UraniumException)

LOGGER = logging.getLogger(__name__)


class Build(object):
    """
    the build class is the object passed to the main method of the
    uranium script.

    it's designed to serve as the public API to controlling the build process.

    Build is designed to be executed within the sandbox
    itself. Attempting to execute this outside of the sandbox could
    lead to corruption of the python environment.
    """
    URANIUM_CACHE_DIR = ".uranium"
    HISTORY_NAME = "history.json"

    def __init__(self, root, config=None, with_sandbox=True):
        self._config = config or Config()
        self._root = root
        self._executables = Executables(root)
        self._hooks = Hooks()
        self._packages = Packages()
        self._tasks = Tasks()
        self._envvars = EnvironmentVariables()
        self._options = None
        self._history = History(
            os.path.join(self._root, self.URANIUM_CACHE_DIR, self.HISTORY_NAME)
        )
        self._sandbox = Sandbox(root) if with_sandbox else None

    @property
    def config(self):
        return self._config

    @property
    def envvars(self):
        return self._envvars

    @property
    def executables(self):
        return self._executables

    @property
    def hooks(self):
        return self._hooks

    @property
    def history(self):
        return self._history

    @property
    def options(self):
        return self._options

    @property
    def packages(self):
        return self._packages

    @property
    def root(self):
        return self._root

    def run_task(self, task_name):
        return self._tasks[task_name](self)

    def task(self, f):
        """
        a decorator that adds the given function as a task.

        e.g.

        @build.task
        def main(build):
            build.packages.install("httpretty")

        this is useful in the case where tasks are being sourced from
        a different file, besides ubuild.py
        """
        self._tasks.add(f)
        return f

    def include(self, script_path):
        """ executes the script at the specified path. """
        get_remote_script(script_path, build=self)

    def run(self, options):
        if not self._sandbox:
            return self._run(options)

        with self._sandbox:
            output = self._run(options)
        self._sandbox.finalize()
        return output

    def _run(self, options):
        self._options = options
        code = 1
        try:
            self._warmup()
            path = os.path.join(self.root, options.build_file)
            u_assert(os.path.exists(path),
                     "build file at {0} does not exist".format(path))
            try:
                log_multiline(LOGGER, logging.INFO, STARTING_URANIUM)
                code = self._run_script(path, options.directive,
                                        override_func=options.override_func)
            except ScriptException as e:
                log_multiline(LOGGER, logging.INFO, str(e))
            finally:
                self._finalize()
                log_multiline(LOGGER, logging.INFO, ENDING_URANIUM)
        finally:
            self._options = None
            return code

    def _run_script(self, path, task_name, override_func=None):
        """
        override_func: if this is not None, the _run_script will
        execute this function (passing in the script object) instead
        of executing the task_name.
        """
        script = build_script(path, {"build": self})

        if override_func:
            return override_func(script)

        for f in get_public_functions(script):
            if f.__name__ not in self._tasks:
                self._tasks.add(f)

        if task_name not in self._tasks:
            raise ScriptException("{0} does not have a {1} function. available public task_names: \n{2}".format(
                path, task_name, _get_formatted_public_tasks(script)
            ))
        self.hooks.run("initialize", self)
        output = self._tasks.run(task_name, self)
        self.hooks.run("finalize", self)
        return output

    def _warmup(self):
        self.history.load()

    def _finalize(self):
        virtualenv.make_environment_relocatable(self._root)
        activate_content = ""
        activate_content += self.envvars.generate_activate_content()
        write_activate_this(self._root, additional_content=activate_content)
        self.history.save()


def _get_formatted_public_tasks(script):
    public_directives = get_public_functions(script)

    def fmt(func):
        return "  {0}: {1}".format(func.__name__, func.__doc__ or "")

    return "\n".join([fmt(f) for f in public_directives])
