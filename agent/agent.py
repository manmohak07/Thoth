from __future__ import annotations
from pathlib import Path
from typing import AsyncGenerator
from agent.events import AgentEvent, AgentEventType
from client.llm_client import LLMClient
from client.response import StreamEventType, ToolCall, ToolResultMessage
from context.context_manager import ContextManager
from tools.registry import create_default_registry

class Agent:
    def __init__(self):
        self.client = LLMClient()
        self.context_manager = ContextManager()
        self.tool_registry = create_default_registry()

    async def run(self, message: str):
        yield AgentEvent.agent_start(message)
        self.context_manager.add_user_message(message)

        final_response: str | None = None

        async for event in self._agentic_loop():
            yield event

            if event.type == AgentEventType.TEXT_COMPLETE:
                final_response = event.data.get('content')

        yield AgentEvent.agent_end(final_response)

    async def _agentic_loop(self) -> AsyncGenerator[AgentEvent, None]:
        # messages = [{
        #     'role': 'user',
        #     'content': 'Hey, how are ya?',
        # }]

        tool_schemas = self.tool_registry.get_schemas()

        response_text = ""
        tool_calls: list[ToolCall] = []

        async for event in self.client.chat_completion(
            self.context_manager.get_messages(),
            tools=tool_schemas if tool_schemas else None,
            # stream=True,
        ):
            if event.type == StreamEventType.TEXT_DELTA:
                if event.text_delta: 
                    content = event.text_delta.content
                    response_text += content
                    yield AgentEvent.text_delta(content)
                    
            elif event.type == StreamEventType.TOOL_CALL_COMPLETE:
                if event.tool_call:
                    tool_calls.append(event.tool_call)

            elif event.type == StreamEventType.ERROR:
                yield AgentEvent.agent_error(event.error or "Unknown Error Occured")
        
        self.context_manager.add_assistant_message(
            response_text or None,
            # Add context for what tool was called
            [
                {
                    'id': tc.call_id,
                    'type': 'function',
                    'function': {
                        'name': tc.name,
                        'arguments': str(tc.arguments),
                    },
                }
                for tc in tool_calls
            ]
            if tool_calls else None # If tool_call is not present, just add null.
        )
        if response_text:
            yield AgentEvent.text_complete(response_text)

        tool_call_result: list[ToolResultMessage] = []

        for tc in tool_calls:
            yield AgentEvent.tool_call_start(
                tc.call_id,
                tc.name,
                tc.arguments,
            )
            
            result = await self.tool_registry.invoke(
                tc.name,
                tc.arguments,
                Path.cwd(),
            )

            yield AgentEvent.tool_call_complete(
                tc.call_id,
                tc.name,
                result,
            )

            tool_call_result.append(
                ToolResultMessage(
                    tool_call_id=tc.call_id,
                    content=result.to_model_output(),
                    is_error=not result.success,
                )
            )

        for tr in tool_call_result:
            self.context_manager.add_tool_result(
                tr.tool_call_id,
                tr.content,
            )



    async def __aenter__(self) -> Agent:
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.client:
            await self.client.close()
            self.client = None
