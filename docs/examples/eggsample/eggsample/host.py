import random

from eggsample import hookimpl, hookspecs, lib, pm

condiments_tray = {"pickled walnuts": 13, "steak sauce": 4, "mushy peas": 2}

class FoodMaster2000:
    def __init__(self):
        self.ingredients = []

    def add_ingredients(self):
        pm.hook.eggsample_add_ingredients(ingredients=self.ingredients)

    def prepare_the_food(self):
        random.shuffle(self.ingredients)

    def serve_the_food(self):
        pm.hook.eggsample_prep_condiments(condiments=condiments_tray)
        print(f"Your food: {', '.join(self.ingredients)}")
        print(f"Some condiments: {', '.join(condiments_tray.keys())}")

def main():
    pm.add_hookspecs(hookspecs)
    pm.load_setuptools_entrypoints("eggsample")
    pm.register(lib)
    fm2000 = FoodMaster2000()
    fm2000.add_ingredients()
    fm2000.prepare_the_food()
    fm2000.serve_the_food()

if __name__ == '__main__':
    main()
