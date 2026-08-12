from typing import Any

from client.llm_client import LLMClient
from client.response import StreamEventType, TokenUsage
from context.context_manager import ContextManager
from prompts.system import get_compaction_prompt


class Compressor:
    def __init__(self, client: LLMClient):
        self.client = client

    def _format_chat_history(self, messages: list[dict[str, Any]]) -> str:
        output = [
            'Here is the conversation that needs to be continued \n',
        ]

        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')

            if role == 'system':
                continue

            if role == 'tool':
                tool_id = msg.get('tool_call_id', 'unknown')
                trucated = content[:2000] if len(content) > 2000 else content

                if len(content) > 2000:
                    trucated += '\n ...[tool output truncated]'

                output.append(f'[Tool Result ({tool_id})] -> \n{trucated}')

            elif role == 'assistant':
                tc_details = []

                if content:
                    trucated = content[:3000] if len(content) > 3000 else content
                    if len(content) > 3000:
                            trucated += '\n ...[response truncated]'

                    output.append(f'Assistant: \n{trucated}')

                if msg.get('tool_calls'):
                    for tc in msg['tool_calls']:
                        func = tc.get('function', {})
                        name = func.get('name', 'unknown')
                        args = func.get('args', '{}')

                        if len(args) > 500:
                            args = args[:500]

                        tc_details.append(f' - {name}({args})')

                    output.append(
                        f'Assistant called {len(tc_details)} tool(s) \n' +
                        '\n'.join(tc_details)
                    )

            else:
                trucated = content[:1500] if len(content) > 1500 else content
                if len(content) > 1500:
                        trucated += '\n ...[response truncated]'

                output.append(f'Assistant: \n{trucated}')     

        return '\n\n -- \n\n'.join(output)               

                                

    async def compress(self, context_manager: ContextManager) -> tuple[str | None, TokenUsage | None]:
        messages = context_manager.get_messages()

        if len(messages) < 3:
            return None, None

        compression_messages = [
            {
                'role': 'system',
                'content': get_compaction_prompt(),
            }, 
            {
                'role': 'user',
                'content': self._format_chat_history(messages),
            },
        ]

        try:
            summary = ""
            usage = None
            async for event in self.client.chat_completion(
                compression_messages,
                stream=False,
            ): 
                if event.type == StreamEventType.MESSAGE_COMPLETE:
                    usage = event.usage
                    summary += event.text_delta.content

            if not summary or not usage:
                return None, None

            return summary, usage

        except Exception as e:
            return None, None