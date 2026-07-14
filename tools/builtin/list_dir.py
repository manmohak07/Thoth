from pydantic import BaseModel, Field

from tools.base import FileDiff, Tool, ToolInvocation, ToolKind, ToolResult
from utils.paths import ensure_parent_directory, resolve_path

class ListDirectoryParams(BaseModel):
    path: str = Field(
        '.',
        description='Directory path to list (default: current directory).'
    )
    include_hidden_files: bool = Field(
        False,
        description='Whether to include hidden files or directories (default: false).'
    )

class ListDirectoryTool(Tool):
    name = 'list_dir'
    description = 'List contents of a directory.'
    kind = ToolKind.READ
    schema = ListDirectoryParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ListDirectoryParams(**invocation.params)

        dir_path = resolve_path(invocation.cwd, params.path)

        if not dir_path.exists() or not dir_path.is_dir():
            return ToolResult.error_result(
                f'Directory does not exist -> {dir_path}'
            )

        try:
            items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except Exception as e:
            return ToolResult.error_result(
                f'Error listing directory -> {e}'
            )
        
        if not params.include_hidden_files:
            items = [item for item in items if not item.name.startswith('.')]
        
        if not items:
            return ToolResult.success_result(
                f'Directory is empty.',
                metadata={
                    'path': str(dir_path),
                    'entries': 0,
                }
            )
        
        lines = []
        for item in items:
            if item.is_dir():
                lines.append(f'{item.name}/')
            else:
                lines.append(item.name)
        
        return ToolResult.success_result(
            '\n'.join(lines),
            metadata={
                'path': str(dir_path),
                'entries': len(items),
            }
        )
