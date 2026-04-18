from pydantic import BaseModel, Field

from tools.base import Tool, ToolInvocation, ToolKind, ToolResult
from utils.paths import is_binary_file, resolve_path
from utils.text import count_tokens, truncate_text


class ReadFileParams(BaseModel):
    path: str = Field(
        ..., # <- ignore other attributes
        description='Path to the file to read',
    )

    offset: int = Field(
        1, # <- start from line 1
        ge=1, # <- ge refers to greater than or equal to; so it can't be < 1
        description='Line number to start reading from (1-based). Defaults to 1',
    )

    limit: int | None = Field(
        None,
        ge=1,
        description='Max number of lines to read. If not speficified, reads the entire file'
    )

class ReadFileTool(Tool):
    name = 'read_file'
    description = (
        'Reads the content of a text file. Returns the file content with line numbers.'
        'For large files, use offset & limits to read specific portions.'
        'Cannot read binary files like (images, executables, etc.).'
    )

    kind = ToolKind.READ
    schema = ReadFileParams
    MAX_FILE_SIZE = 1024 * 1024 * 10 # <- 10 MB
    MAX_TOKEN_COUNT = 30000
    
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        params = ReadFileParams(**invocation.params)
        path = resolve_path(invocation.cwd, params.path)

        if not path.exists():
            return ToolResult.error_result(f'File not found -> {path}')

        if not path.is_file():
            return ToolResult.error_result(f'Path is not a file -> {path}')
        
        
        file_size = path.stat().st_size
        if file_size > self.MAX_FILE_SIZE:
            # Terminate if the file is greater than 10 MB
            return ToolResult.error_result(
                f'File too large ({file_size / (1024 * 1024):.1f} MB)'
                f'Max is {self.MAX_FILE_SIZE / (1024 * 1024):.0f} MB'    
            )
        
        if is_binary_file(path):
            return ToolResult.error_result(
                f'Connot read a binary file -> {path.name}'    
            )
        
        # 1
        try:
            # Read the file
            # 2
            try:
                content = path.read_text(encoding='utf-8')
            # 2
            except UnicodeDecodeError:
                content = path.read_text(encoding='latin-1')

            lines = content.splitlines()
            total_lines = len(lines)

            if total_lines == 0:
                # The tool should not return an empty string, might confuse the LLM.
                # Return a success instead; though the file was read, it was empty.
                # Can help user to save tokens.
                return ToolResult.success_result(
                    'File is empty',
                    metadata={
                        'lines': 0,
                    },
                )
            
            start_idx = max(0, params.offset - 1)
            
            if params.limit is not None:
                end_idx = min(start_idx + params.limit, total_lines)
            else:
                end_idx = total_lines
            
            selected_lines = lines[start_idx : end_idx]

            formatted_lines = []
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                formatted_lines.append(f'{i : 6} | {line}')

            output = '\n'.join(formatted_lines)
            token_count = count_tokens(output, model='openrouter/elephant-alpha')
            
            truncated = False
            if token_count > self.MAX_TOKEN_COUNT:
                output = truncate_text(
                    output,
                    self.MAX_TOKEN_COUNT,
                    suffix=f'\n... [truncated {total_lines} total_lines]'
                )
                truncated = True
            
            metadata_lines = []
            if start_idx > 0 or end_idx < total_lines:
                metadata_lines.append(f'showing lines {start_idx + 1} - {end_idx} of {total_lines}')
            
            if metadata_lines:
                header = " | ".join(metadata_lines) + "\n\n"
                output = header + output
            
            return ToolResult.success_result(
                output=output,
                truncated=truncated,
                metadata={
                    'path': str(path),
                    'total_lines': total_lines,
                    'shown_start': start_idx + 1,
                    'shown_end': end_idx,                
                }
            )

        # 1
        except Exception as e:
            return ToolResult.error_result(f'Failed to read file -> {e}')