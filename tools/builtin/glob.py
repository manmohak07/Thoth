import os

from pathlib import Path
from pydantic import BaseModel, Field

from tools.base import FileDiff, Tool, ToolInvocation, ToolKind, ToolResult
from utils.paths import is_binary_file, resolve_path

class GlobParams(BaseModel):
    pattern: str = Field(
        ...,
        description='The glob pattern to match (e.g. **/*.py).'
    )
    path: str = Field(
        '.',
        description='Directory path to list (default: current directory).'
    )

class GlobTool(Tool):
    name = 'glob'
    description = 'Find files matching a glob pattern. Supports ** for recursive search.'
    kind = ToolKind.READ
    schema = GlobParams

    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = GlobParams(**invocation.params)

        search_path = resolve_path(invocation.cwd, params.path)

        if not search_path.exists() or not search_path.is_dir():
            return ToolResult.error_result(
                f'Directory does not exist -> {search_path}'
            )
        
        ignored_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', '.idea', '.vscode'}

        try:
            matches = [
                match for match in search_path.glob(params.pattern)
                if match.is_file()
                and not ignored_dirs.intersection(match.parts)
            ]
        except Exception as e:
            return ToolResult.error_result(
                f'Error searching -> {e}'
            )

        output_lines = []
        for file_path in matches[:750]:
            try:
                relative_path = file_path.relative_to(invocation.cwd)
            except Exception:
                relative_path = file_path

            output_lines.append(str(relative_path))
        
        if len(matches) > 750:
            output_lines.append(f'... and {len(matches) - 750} more files')
        return ToolResult.success_result(
            '\n'.join(output_lines),
            metadata={
                'path': str(search_path),
                'matches': len(matches)
            },
        )