import pluggy

hookimpl = pluggy.HookimplMarker("eggsample")
"""Marker to be imported and used in plugins"""

pm = pluggy.PluginManager("eggsample")
"""The manager ... you know? to manage the plugins!"""
