import asyncio
from typing import Any, AsyncGenerator
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
import os
from dotenv import load_dotenv
# from mistralai import Mistral
# from mistralai.models import UserMessage

from client.response import StreamEventType, StreamEvent, TextDelta, TokenUsage

load_dotenv()

class LLMClient:
    def __init__(self) -> None:
        self._client : AsyncOpenAI | None = None
        self._max_retries: int = 3
    
    def get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=os.getenv('OPEN_ROUTER_API_KEY'),
                base_url='https://openrouter.ai/api/v1',
            )

        return self._client
    
    # def get_mistral_client(self):
    #     api_key = os.getenv('MISTRAL_API_KEY')
    #     model = 'mistral-large-latest'

    #     client = Mistral(api_key=api_key)

    #     return client
            
    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None
    
    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        stream: bool = True,
    ) -> AsyncGenerator[StreamEvent, None]:
        
        max = self._max_retries
        client = self.get_client()
        # client = self.get_mistral_client()

        kwargs = {
            'model': 'arcee-ai/trinity-large-preview:free',
            'messages': messages,
            'stream': stream,
        }
        
        for attempt in range(max + 1):
            try:
                if stream:
                    async for event in self._stream_response(client, kwargs):
                        yield event
                else:
                    event = await self._non_stream_response(client, kwargs)
                    yield event
                return
        
            except RateLimitError as e:
                if attempt < max:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Rate Limit Exceeded -> {e}",
                    )
                    return

            except APIConnectionError as e:
                if attempt < max:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Connection error -> {e}",
                    )
                    return
            
            except APIError as e:
                if attempt < max:
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"Connection error -> {e}",
                    )
                    return
            

            
    
    async def _stream_response(
        self,
        client: AsyncOpenAI,
        kwargs: dict[str, any]
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        Streams the response in form of chunks.
        
        :param self: LLM Client that the user is using
        :param client: 
        :type client: AsyncOpenAI
        :param kwargs: Message from either user or the LLM(str) and the response(Any).
        :type kwargs: dict[str, any]
        :return: Returns the response from the LLM
        :rtype: AsyncGenerator[StreamEvent, None]
        """
        response = await client.chat.completions.create(**kwargs)
        
        usage: TokenUsage | None = None
        finish_reason: str | None = None

        async for chunk in response:
            if hasattr(chunk, 'usage') and chunk.usage:
                usage = TokenUsage(
                    prompt_tokens=chunk.usage.prompt_tokens,
                    completion_tokens=chunk.usage.completion_tokens,
                    total_tokens=chunk.usage.total_tokens,
                    cached_tokens=chunk.usage.prompt_tokens_details.cached_tokens
                )
            
            if not chunk.choices:
                continue

            choice = chunk.choices[0]
            delta = choice.delta

            if choice.finish_reason:
                finish_reason = choice.finish_reason
            
            if delta.content:
                yield StreamEvent(
                    type=StreamEventType.TEXT_DELTA,
                    text_delta=TextDelta(delta.content),
                )
        
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            finish_reason=finish_reason,
            usage=usage,
        )

    async def _non_stream_response(
        self,
        client: AsyncOpenAI,
        kwargs: dict[str, Any]
    ) -> StreamEvent:
        """
        Fetches the entire reponse first, and then shows it.
        
        :param self: LLM Client that the user is using
        :param client:
        :type client: AsyncOpenAI
        :param kwargs: Message from either user or the LLM(str) and the response(Any).
        :type kwargs: dict[str, Any]
        :return: Returns the response from the LLM
        :rtype: StreamEvent
        """

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        text_delta = None
        if message.content:
            text_delta = TextDelta(content=message.content)

        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cached_tokens=response.usage.prompt_tokens_details.cached_tokens
            )
        
        return StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            text_delta=text_delta,
            finish_reason=choice.finish_reason,
            usage=usage,
        )
        
            