import pluggy

hookspec = pluggy.HookspecMarker("eggsample")

@hookspec
def eggsample_add_ingredients(ingredients):
    """Change the used ingredients.

    :param list ingredients: the ingredients to be modified
    """

@hookspec
def eggsample_prep_condiments(condiments):
    """Reorganize the condiments tray.

    :param dict condiments: some sauces and stuff
    """
