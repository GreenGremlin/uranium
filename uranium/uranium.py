import logging
import os
from .classloader import ClassLoader
from .config import load_config_from_file
from .pip_manager import PipManager
from .buildout_adapter import BuildoutAdapter

LOGGER = logging.getLogger(__name__)


class UraniumException(Exception):
    pass


class Uranium(object):

    def __init__(self, file_path):
        self._classloader = ClassLoader()
        self._config = load_config_from_file(file_path)
        self._pip = PipManager()
        self._root = os.path.abspath(os.curdir)

        self._buildout = BuildoutAdapter(self)

        errors = self._config.validate()
        if errors:
            for error in errors:
                LOGGER.error(error)
            raise UraniumException("uranium.yaml is not valid.")

    @property
    def root(self):
        return self._root

    def run(self):
        phases = self.config.get('phases', {})

        self._install_eggs()

        if phases.get('post_build'):
            self._run_sections(phases.get('post_build'))

    def _install_eggs(self):
        develop_eggs = self._config.get('develop-eggs')
        if develop_eggs:
            self._pip.add_develop_eggs(develop_eggs)
        self._pip.install()

        eggs = self._config.get('eggs')
        if eggs:
            self._pip.add_eggs(eggs)
        self._pip.install()

    def _run_sections(self, section_names):
        for name in section_names:
            self._run_section(name)

    def _run_section(self, name):
        section = self.config.get_section(name)
        if section.is_recipe:
            section_instance = self._buildout.get_section_instance(section)
            self._buildout.install_section(section_instance)
