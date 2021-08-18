class PluginValidationError(Exception):
    """plugin failed validation.

    :param object plugin: the plugin which failed validation,
        may be a module or an arbitrary object.
    """

    plugin: object

    def __init__(self, plugin: object, message: str):
        self.plugin = plugin
        super(Exception, self).__init__(message)
