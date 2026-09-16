"""Load a config file into the resolved path set."""

from .config import ConfigFile
from .locator import ConfigLocator, PackConfigLocator
from .pack import Pack, resolve_pack_root
from .resolver import PathResolver
from .wiring import Wiring


class HarnessConfig:
    """Interpret a ConfigFile into resolved Wiring."""

    def __init__(self, file: ConfigFile, pack: Pack):
        self._file = file
        self._pack = pack
        self._paths = PathResolver(file.directory)

    def wiring(self) -> Wiring:
        root = self._paths.path
        features = self._file.value("features")
        return Wiring(
            pack_root=self._pack.root,
            workspace_root=root(self._file.value("workspace_root", "..")),
            state_root=root(self._file.value("state_root", ".swarmforge")),
            artifacts_root=root(self._file.value("artifacts_root", "dump")),
            hot_tests=root(self._file.value("hot_tests", "hot_tests")),
            persistent_tests=self._paths.persistent_tests(
                self._file.entries("persistent_tests")
            ),
            source_roots=self._paths.paths(
                self._file.value("source_roots", ["src"])
            ),
            features=self._paths.optional_path(features),
            config_path=self._file.path,
        )


def load(config=None, locator: ConfigLocator | None = None, environ=None) -> Wiring:
    """Resolve every path a tool needs from the selected config."""
    pack = Pack(resolve_pack_root(environ))
    source = locator or PackConfigLocator(pack, config, environ)
    file = ConfigFile(source.locate())
    return HarnessConfig(file, pack).wiring()
