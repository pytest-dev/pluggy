import random

import pluggy

from eggsample import hookspecs, lib

condiments_tray = {"pickled walnuts": 13, "steak sauce": 4, "mushy peas": 2}

class EggselentCook:
    def __init__(self, hook):
        self.hook = hook
        self.ingredients = []

    def add_ingredients(self):
        self.hook.eggsample_add_ingredients(ingredients=self.ingredients)

    def prepare_the_food(self):
        random.shuffle(self.ingredients)

    def serve_the_food(self):
        self.hook.eggsample_prep_condiments(condiments=condiments_tray)
        print(f"Your food: {', '.join(self.ingredients)}")
        print(f"Some condiments: {', '.join(condiments_tray.keys())}")

def main():
    pluginmanager = pluggy.PluginManager("eggsample")
    pluginmanager.add_hookspecs(hookspecs)
    pluginmanager.load_setuptools_entrypoints("eggsample")
    pluginmanager.register(lib)
    fm2000 = EggselentCook(pluginmanager.hook)
    fm2000.add_ingredients()
    fm2000.prepare_the_food()
    fm2000.serve_the_food()

if __name__ == '__main__':
    main()
