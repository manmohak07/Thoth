from pathlib import Path

from rich import box # <- lower case
from rich.console import Console
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from typing import Any, Tuple

from utils.paths import display_path_relative_to_cwd

import re

from utils.text import truncate_text

AGENT_THEME = Theme(
    {
        # General 
        'info': 'cyan',
        'warning': 'yellow',
        'error': 'bright_red bold',
        'success': 'green',
        'dim': 'dim',
        'muted': 'grey50',
        'border': 'grey35',
        'highlight': 'bold cyan',

        # Roles
        'user': 'bright_blue bold',
        'assistant': 'bright_white',

        # Tools
        'tool': 'bright_magenta bold',
        'tool.read_file': 'cyan',
        'tool.read': 'cyan',
        'tool.write': 'yellow',
        'tool.shell': 'magenta',
        'tool.network': 'bright_blue',
        'tool.memory': 'green',
        'tool.mcp': 'bright_cyan',

        # Code
        'code': 'bright_white',
    }
)

_console: Console | None = None

def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console(theme=AGENT_THEME, highlight=False)
    
    return _console

class TUI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = _console or get_console()
        self._assistant_stream_open = False
        self._tool_args_by_call_id: dict[str, dict[str, Any]] = {}
        self.cwd = Path.cwd()

    def begin_assistant(self) -> None:
        self.console.print()
        self.console.print(Rule(Text('Assistant', style='assistant')))
        self._assistant_stream_open = True
    
    def end_assistant(self) -> None:
        if self._assistant_stream_open:
            self.console.print()
        
        self._assistant_stream_open = False
    
    def stream_assistant_delta(self, content: str) -> None:
        # Displays sentence nicely without any formatting
        # End is set to an empty string so that streaming output is printed properly and new line for each token can be avoided
        self.console.print(content, end='', markup=False)

    def _ordered_args(self, tool_name: str, args: dict[str, Any]) -> list[tuple]:
        _PREFERRED_ORDER = {
            'read_file': ['path', 'offset', 'limit'],
        }

        preferred = _PREFERRED_ORDER.get(tool_name, [])
        ordered: list[tuple[str, Any]] = []
        seen = set()

        for key in preferred:
            if key in args:
                ordered.append((key, args[key]))
                seen.add(key)
        
        remaining_keys = set(args.keys() - seen)
        ordered.extend((key, args[key]) for key in remaining_keys)

        return ordered

    def _render_args_table(self, tool_name: str, args: dict[str, Any]) -> Table:
        table = Table.grid(padding=(0, 1))
        table.add_column(style='muted', justify='right', no_wrap=True)
        table.add_column(style='code', overflow='fold')

        for key, value in self._ordered_args(tool_name, args):
            table.add_row(key, value)
        
        return table

    def tool_call_start(
            self,
            call_id: str,
            tool_kind: str | None,
            name: str,
            arguments: dict[str, Any],
    ) -> None:
        self._tool_args_by_call_id[call_id] = arguments
        border_style = f'tool.{tool_kind}' if tool_kind else 'tool'

        title = Text.assemble(
            ('🫡  ', 'muted'),
            (name, 'tool'),
            ('  ', 'muted'),
            (f'{call_id[:8]}', 'muted'),
        )

        display_args = dict(arguments)
        for key in ('path', 'cwd'):
            val = display_args.get(key)
            if isinstance(val, str) and self.cwd:
                display_args[key] = str(display_path_relative_to_cwd(val, self.cwd))

        panel = Panel(
            self._render_args_table(name, display_args) if display_args else Text('(no args)', style='muted'),
            title=title,
            title_align='left',
            subtitle=Text('running', style='muted'),
            subtitle_align='right',
            border_style=border_style,
            box=box.ROUNDED,
            padding=(1, 2),
        )
        
        self.console.print()
        self.console.print(panel)

    def tool_call_complete(
            self,
            call_id: str,
            tool_kind: str | None,
            name: str,
            success: bool,
            output: str | None,
            error: str | None,
            metadata: dict[str, Any] | None,
            truncated: bool,
    ) -> None:
        border_style = f'tool.{tool_kind}' if tool_kind else 'tool'
        status_icon = '👍 ' if success else '👎 '
        status_style = 'success' if success else 'error'

        title = Text.assemble(
            (f'{status_icon}', 'muted'),
            (name, 'tool'),
            ('  ', 'muted'),
            (f'{call_id[:8]}', 'muted'),
        )

        primary_path = None
        blocks = []
        if isinstance(metadata, dict) and isinstance(metadata.get('path'), str):
            primary_path = metadata.get('path')

        if name == 'read_file' and success:
            if primary_path:
                extracted = self._extract_code_rf(output)

                if extracted:
                    start_line, code = extracted
                    shown_start = metadata.get('shown_start')
                    shown_end = metadata.get('shown_end')
                    total_lines = metadata.get('total_lines')
                    programming_language = self._get_programming_language(primary_path)

                    header_parts = [display_path_relative_to_cwd(primary_path, self.cwd)]
                    header_parts.append(' ~ ')

                    if shown_start and shown_end and total_lines:
                        header_parts.append(f'lines {shown_start}-{shown_end} of {total_lines}')

                    header = ''.join(header_parts)
                    blocks.append(Text(header, style='muted'))
                    blocks.append(
                        Syntax(
                            code,
                            programming_language,
                            theme='monokai',
                            line_numbers=True,
                            start_line=start_line,
                            word_wrap=False,
                        )
                    )
                else:
                    # Case when extraction fails
                    output_display = truncate_text(output or '', '', 240)
                    blocks.append(
                        Syntax(
                            output_display,
                            'text',
                            theme='monokai',
                            word_wrap=False,
                        )
                    )
            else:
                # Case when path is not present
                output_display = truncate_text(output, '', 240, )
                blocks.append(
                    Syntax(
                        output_display,
                        'text',
                        theme='monokai',
                        word_wrap=False,
                    )
                )
        
        if truncated:
            blocks.append(Text('Tool output was truncated', style='warning'))

        panel = Panel(
            Group(
                *blocks,
            ),
            title=title,
            title_align='left',
            subtitle=Text('done' if success else 'failed', style=status_style),
            subtitle_align='right',
            border_style=border_style,
            box=box.ROUNDED,
            padding=(1, 2),
        )
        
        self.console.print()
        self.console.print(panel)
    
    def _extract_code_rf(self, text: str) -> tuple[int, str] | None:
        # Format:
        # Showing lines x-y of z \n\n1| def main():\n 2|
        
        body = text
        header_match = re.match(r'^Showing lines (\d+)-(\d+) of (\d+)\n\n', text)

        if header_match:
            body = text[header_match.end() : ]
        
        code_lines: list[str] = []
        start_line: int | None = None

        for line in body.splitlines():
            l = re.match(r'^\s*(\d+)\|(.*)$', line)
            if not l:
                return None
            
            line_no = int(l.group(1))
            if start_line is None:
                start_line = line_no
            
            code_lines.append(l.group(2))
        
        if start_line is None:
            return None

        return start_line, '\n'.join(code_lines)
    
    def _get_programming_language(path: str | None) -> str:
        '''Helps the agent to know what programming language the file is written in.'''

        if not path:
            return 'text'
        
        suffix = Path(path).suffix.lower()
        # Some of them might not be known as a programming language but it's still nice to have syntax highlighting for the same.
        return {
            '.java': 'java',
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.go': 'go',
            '.rb': 'ruby',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.html': 'html',
            '.css': 'css',  
            '.json': 'json',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.tsx': 'tsx',
            '.jsx': 'jsx',
            '.toml': 'toml',
            '.sh': 'bash',
            '.kt': 'kotlin',
            '.swift': 'swift',
            '.sql': 'sql',
        }.get(suffix, 'text')
        
        
