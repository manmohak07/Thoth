from pathlib import Path
from typing import Any

from tools.base import Tool, ToolInvocation, ToolResult
from tools.builtin import ReadFileTool, get_all_builtin_tools
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def get(self, name: str) -> Tool | None:
        if name in self._tools:
            return self._tools[name]

        return None
    
    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning(f'Tool already exists: {tool.name}.')
        
        self._tools[tool.name] = tool
        logger.debug(f'Registered Tool -> {tool.name}')

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            logger.info(f'Tool has been removed -> {name}')
            return True

        logger.warning(f'Tried to remove a tool which does not exist -> {name}')
        return False
    
    def get_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_openai_schema() for tool in self.get_tools()]

    def get_tools(self) -> list[Tool]:
        tools: list[Tool] = []

        for tool in self._tools.values:
            tools.append(tool)
        
        return tools

    async def invoke(
        self,
        name: str, 
        params: dict[str, Any], 
        cwd: Path | None
    ) -> None:
        
        tool = self.get(name)
        if tool is None:
            return ToolResult.error_result(
                f'Unknown Tool -> {name}',
                metadata={
                    'tool_name': name,
                }
            )
        
        validation_errors = tool.validate_params(params)
        if validation_errors:
            return ToolResult.error_result(
                f'Invalid Parameters -> {'; '.join(validation_errors)} ',
                metadata={
                    'tool_name': name,
                    'validation_errors': validation_errors,
                },
            )
        
        invocation = ToolInvocation(
            params=params,
            cwd=cwd,
        )

        # 1
        try:
            await tool.execute(invocation)
        # 1
        except Exception as e:
            logger.exception(f'Tool -> {name} raised unexpected error -> {str(e)}')
            return ToolResult.error_result(
                f'Internal error {str(e)}',
                metadata={
                    'tool_name',
                    name,
                }
            )

def create_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    BUILTIN_TOOLS = [ReadFileTool]

    for tool_class in get_all_builtin_tools():
        registry.register(tool_class())

    return registry

