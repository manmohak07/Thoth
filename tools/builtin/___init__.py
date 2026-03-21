# __init__ converts the builtin folder into a module.
# Can do imports more easily and makes the code cleaner.
# e.g. from tools.builtin import ReadFileTool

from tools.builtin.read_file import ReadFileTool

__all__ = [
    'ReadFileTool',
]

def get_all_builtin_tools() -> list[type]:

    return [
        ReadFileTool,
    ]