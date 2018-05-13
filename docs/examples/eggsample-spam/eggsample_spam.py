import eggsample

@eggsample.hookimpl
def eggsample_add_ingredients(ingredients):
    if len([e for e in ingredients if e == "egg"]) > 2:
        ingredients.remove("egg")
    spam = ["lovely spam", "wonderous spam", "splendiferous spam"]
    print(f"Add {spam}")
    return spam

@eggsample.hookimpl
def eggsample_prep_condiments(condiments):
    try:
        del condiments["steak sauce"]
    except KeyError:
        pass
