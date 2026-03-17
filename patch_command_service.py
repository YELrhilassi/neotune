import re

with open("src/core/command_service.py", "r") as f:
    code = f.read()

new_cmd = """
class ToggleQueueCommand(Command):
    def execute(self, app, *args, **kwargs):
        is_visible = app.store.get("queue_visible", False)
        app.store.set("queue_visible", not is_visible)

class CommandService:
"""

code = code.replace("class CommandService:", new_cmd)

reg_default = """
            ("fuzzy_search", FuzzySearchCommand()),
            ("toggle_queue", ToggleQueueCommand()),
"""

code = code.replace('("fuzzy_search", FuzzySearchCommand()),', reg_default)

with open("src/core/command_service.py", "w") as f:
    f.write(code)
