'''
PEP 8 Layout:
this is a style guide for Python code, it is a default contract for layout and naming
1. Lines are limited to 79 characters, and the guide itself says a team may agree on a longer limit.
2. Top-level function and class definitions get two blank lines around them.
3. Imports go at the top of the file, after the module docstring and before module-level globals, with standard-library imports first.
4. Indentation is four spaces per level, as above

module is a single .py file, use import to load modules
module docstring is the quoted sentence on the first line saying what the file is for
"""example file: file for examples"""

variables and functions in lowercase words joined by underscores (snake_case)
constants in upper case with underscores (UPPER_CASE)
classes in pascal case (PascalCase)

for commenting, some scripts start with a #! which is called a "shebang" where the operating system reads it to choose an interpreter
python skips this

PEP 8's layout for inline comment:
at least two spaces after the statement, then #, then a single space before the text

a comment says why, and the code says what

Python is dynamically typed. Names don't have types, objects do, and the type of x tells me the type of the object x is bound to right now
'''

priority = "high"
print(priority == "high")
print(priority is "high")