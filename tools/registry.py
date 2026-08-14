from pathlib import Path
from typing import Any

from config.config import Config
from safety.approval_manager import ApprovalManager
from tools.base import Tool, ToolInvocation, ToolResult
from tools.builtin import ReadFileTool, get_all_builtin_tools
import logging

from tools.subagents import SubAgent, get_default_subagent_definitions

from safety.approval_manager import ApprovalContext, ApprovalDecision

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self, config: Config):
        self._tools: dict[str, Tool] = {}
        self._mcp_tools: dict[str, Tool] = {}
        self.config = config
    
    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            logger.warning(f'Tool already exists: {tool.name}.')
        
        self._tools[tool.name] = tool
        logger.debug(f'Registered Tool -> {tool.name}')

    def register_mcp_tool(self, tool: Tool) -> None:            
        self._mcp_tools[tool.name] = tool
        logger.debug(f'Registered MCP Tool -> {tool.name}')

    def unregister(self, name: str) -> bool:
        if name in self._tools:
            del self._tools[name]
            logger.info(f'Tool has been removed -> {name}')
            return True

        logger.warning(f'Tried to remove a tool which does not exist -> {name}')
        return False

    def get(self, name: str) -> Tool | None:
            if name in self._tools:
                return self._tools[name]
    
            elif name in self._mcp_tools:
                return self._mcp_tools[name]
    
            return None
    
    def get_schemas(self) -> list[dict[str, Any]]:
        return [tool.to_openai_schema() for tool in self.get_tools()]

    def get_tools(self) -> list[Tool]:
        tools: list[Tool] = []

        for tool in self._tools.values():
            tools.append(tool)

        for mcp_tool in self._mcp_tools.values():
            tools.append(mcp_tool)
        
        if self.config.allowed_tools:
            allowed_tools_set = set(self.config.allowed_tools)
            tools = [t for t in tools if t.name in allowed_tools_set]
            
        return tools

    async def invoke(
        self,
        name: str, 
        params: dict[str, Any], 
        cwd: Path,
        approval_manager: ApprovalManager | None = None
    ) -> ToolResult:
        
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

        if approval_manager:
            confirmation = await tool.get_confirmation(invocation)
            if confirmation:
                context = ApprovalContext(
                    tool_name=name,
                    params=params,
                    is_mutating=tool.is_mutating(params),
                    affected_paths=confirmation.affected_paths,
                    cmd=confirmation.cmd,
                    is_dangerous=confirmation.is_dangerous,
                )

                decision = await approval_manager.check_approval(context)
                if decision == ApprovalDecision.REJECTED:
                    return ToolResult.error_result('Operation was rejected (safety policy)')

                elif decision == ApprovalDecision.NEEDS_CONFIRMATION:
                    approved = approval_manager.request_confirmation(confirmation)

                    if not approved:
                        return ToolResult.error_result('Operation rejected by user')

        # 1
        try:
            return await tool.execute(invocation)
        # 1
        except Exception as e:
            logger.exception(f'Tool -> {name} raised unexpected error -> {str(e)}')
            return ToolResult.error_result(
                f'Internal error {str(e)}',
                metadata={
                    'tool_name': name,
                }
            )

def create_default_registry(config: Config) -> ToolRegistry:
    registry = ToolRegistry(config)
    BUILTIN_TOOLS = [ReadFileTool]

    for tool_class in get_all_builtin_tools():
        registry.register(tool_class(config))

    for subagent_def in get_default_subagent_definitions():
        registry.register(SubAgent(config, subagent_def))
    return registry

