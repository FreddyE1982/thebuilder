import os


class MLModelPlugin:
    """Base class for ML model plugins."""

    def register(self, service) -> None:
        raise NotImplementedError()


class PluginManager:
    """Loads ML model plugins from a directory."""

    def __init__(self, path: str = "plugins") -> None:
        self.path = path
        self.plugins: list[MLModelPlugin] = []

    def load_plugins(self, service) -> None:
        import importlib
        import pkgutil
        if not os.path.isdir(self.path):
            return
        for finder, name, _ in pkgutil.iter_modules([self.path]):
            module = importlib.import_module(f"{self.path}.{name}")
            for attr in dir(module):
                cls = getattr(module, attr)
                if (
                    isinstance(cls, type)
                    and issubclass(cls, MLModelPlugin)
                    and cls is not MLModelPlugin
                ):
                    plugin = cls()
                    plugin.register(service)
                    self.plugins.append(plugin)

