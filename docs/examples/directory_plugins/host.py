import importlib
import pkgutil

import hookspecs
import plugins

import pluggy


def main() -> None:
    manager = pluggy.PluginManager("greetings")
    manager.add_hookspecs(hookspecs)

    module_names = sorted(
        info.name
        for info in pkgutil.iter_modules(plugins.__path__, plugins.__name__ + ".")
        if not info.ispkg
    )
    for name in module_names:
        manager.register(importlib.import_module(name), name=name)
    manager.check_pending()

    for greeting in manager.hook.greeting(name="Ada"):
        print(greeting)


if __name__ == "__main__":
    main()
