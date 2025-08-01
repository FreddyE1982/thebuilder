from ml_plugins import MLModelPlugin

class SamplePlugin(MLModelPlugin):
    """Example plugin setting a flag on the service."""

    def register(self, service) -> None:
        setattr(service, "sample_plugin_loaded", True)

