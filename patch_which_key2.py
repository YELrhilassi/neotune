import re

with open("src/ui/modals/which_key.py", "r") as f:
    code = f.read()

code = code.replace('("e", "Toggle Sidebar"),', '("e", "Toggle Sidebar"),\n                ("l", "Toggle Queue UI"),')

with open("src/ui/modals/which_key.py", "w") as f:
    f.write(code)
