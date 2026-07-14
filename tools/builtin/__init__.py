# __init__ converts the builtin folder into a module.
# Can do imports more easily and makes the code cleaner.
# e.g. from tools.builtin import ReadFileTool

from tools.builtin.edit_file import EditTool
from tools.builtin.read_file import ReadFileTool
from tools.builtin.shell import ShellTool
from tools.builtin.write_file import WriteFileTool

__all__ = [
    'ReadFileTool',
    'WriteFileTool',
    'EditTool',
    'ShellTool',
]

def get_all_builtin_tools() -> list[type]:

    return [
        ReadFileTool,
        WriteFileTool,
        EditTool,
        ShellTool,
    ]