import re

with open("src/ui/modals/which_key.py", "r") as f:
    code = f.read()

code = code.replace('("l", "Like/Unlike Track"),', '("l", "Like/Unlike Track"),\n                ("q", "Add to Queue"),\n                ("x / del", "Remove from Queue (in Up Next)"),')

with open("src/ui/modals/which_key.py", "w") as f:
    f.write(code)
