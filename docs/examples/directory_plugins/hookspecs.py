import pluggy


hookspec = pluggy.HookspecMarker("greetings")


@hookspec
def greeting(name: str) -> str:
    """Return a greeting for the given name."""
