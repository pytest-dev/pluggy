import eggsample

@eggsample.hookimpl
def eggsample_add_ingredients(ingredients):
    basics = ["egg", "egg", "salt", "pepper"]
    print(f"Add {basics}")
    ingredients.extend(basics)

@eggsample.hookimpl
def eggsample_prep_condiments(condiments):
    condiments["mint sauce"] = 1
