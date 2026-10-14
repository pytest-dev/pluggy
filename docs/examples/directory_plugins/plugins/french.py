import pluggy


hookimpl = pluggy.HookimplMarker("greetings")


@hookimpl
def greeting(name: str) -> str:
    return f"Bonjour {name}!"
