import eggsample

@eggsample.hookimpl
def eggsample_add_ingredients(ingredients):
    """Here we get an immutable object, so we return something to the caller."""
    if "egg" in ingredients:
        spam = ["lovely spam", "wonderous spam"]
    else:
        spam = ["splendiferous spam", "magnificent spam"]
    print(f"Add {spam}")
    return spam

@eggsample.hookimpl
def eggsample_prep_condiments(condiments):
    """Here we get a mutable object, so we just mess with it directly."""
    try:
        del condiments["steak sauce"]
    except KeyError:
        pass
    condiments['spam sauce'] = 42
    print(f"Now. this is what I call a condiments tray!")
