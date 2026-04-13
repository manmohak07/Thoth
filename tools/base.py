from __future__ import annotations
import abc
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, ValidationError
from pydantic.json_schema import model_json_schema
from typing import Any


# abstract class
class ToolKind(str, Enum):
    READ = 'read'
    WRITE = 'write'
    SHELL = 'shell'
    NETWORK = 'network'
    MEMORY = 'memory'
    MCP = 'mcp'


@dataclass
class ToolInvocation:
    params: dict[str, Any]
    cwd: Path

@dataclass
class ToolConfirmation:
    tool_name: str
    params: dict[str, Any]
    description: str

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict) # <- if nothing is present, we get an empty dict instead of null
    truncated: bool = False

    @classmethod
    def error_result(
        cls,
        error: str,
        output: str = '',
        **kwargs: Any,
    ):
        return cls(
            success=False,
            output=output,
            error=error
        )
    
    @classmethod
    def success_result(
        cls,
        output: str = '',
        **kwargs: Any,
    ):
        return cls(
            success=True,
            output=output,
            error=None,
            **kwargs,
        )
    
    def to_model_output(self) -> str:
        if self.success:
            return self.output
        
        return f'Error: {self.error}\n\nOutput:\n{self.output}'



class Tool(abc.ABC):
    name: str = 'base_tool'
    description: str = 'Base tool'
    kind: ToolKind = ToolKind.READ

    def __init__(self) -> None:
        pass

    @property
    def schema(self) -> dict[str, Any] | type['BaseModel']:
        raise NotImplementedError('Schema must be defined for each tool')
    
    @abc.abstractmethod
    async def execute(self, invocation: ToolInvocation) -> ToolResult:
        pass
    
    def validate_params(self, params: dict[str, Any]) -> list[str]:
        schema = self.schema
        
        # If the type of schema is BaseModel from Pydantic
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            try:
                schema(**params)
            except ValidationError as e:
                errors = []
                for error in e.errors():
                    field = ".".join(str(x) for x in error.get('loc', []))
                    msg = error.get('msg', 'Validation error')
                    errors.append(f'Parameter {field} -> {msg}')

                return errors
            
            except Exception as e:
                return [str(e)]
        
        return []

    def is_mutating(self, params: dict[str, Any]) -> bool:
        return self.kind in {
            ToolKind.WRITE,
            ToolKind.SHELL,
            ToolKind.NETWORK,
            ToolKind.MEMORY,
        }
        
    async def get_confirmation(self, invocation: ToolInvocation) -> ToolInvocation | None:
        if not self.is_mutating(invocation.params):
            return None

        return ToolConfirmation(
            tool_name=self.name,
            params=invocation.params,
            description=f'Excecute {self.name}',
        )
    
    def to_openai_schema(self) -> dict[str, Any]:
        schema = self.schema

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            json_schema = model_json_schema(schema, mode='serialization')

            # OpenAI SDK Tool Schema format
            return {
                'name': self.name,
                'description': self.description,
                'parameters': {
                    'type': 'object',
                    'properties': json_schema.get('properties', {}),
                    'required': json_schema.get('required', []),
                },
            } 
    
        if isinstance(schema, dict):
            result = {
                'name': self.name,
                'description': self.description,
            }

            if 'parameters' in schema:
                result['parameters'] = schema['parameters']
            else:
                result['paramters'] = schema

            return result

        raise ValueError(f'Invalid Schema type for tool -> {self.name}: {type(schema)}')