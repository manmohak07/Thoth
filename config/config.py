from __future__ import annotations
import os
from pathlib import Path
from typing import Any, List

from pydantic import BaseModel, Field, model_validator

class ModelConfig(BaseModel):
    name: str = 'devstral-2512' # <- default model
    temperature: float = Field(default=0.4, ge=0.0, le=1.0) 
    content_window: int = 256_000

class ShellEnvironmentPolicy(BaseModel):
    ignore_default_excludes: bool = False # Ignore the list below
    exclude_patterns: list[str] = Field( # Ignore env-vars based on these patterns
        default_factory=lambda:[
            '*KEY*',
            '*TOKEN*',
            '*SECRET*',
        ]
    )
    set_vars: dict[str, str] = Field(default_factory=dict)

class MCPServerConfig(BaseModel):
    enabled: bool = True
    startup_timeout_seconds: float = 10

    command: str | None = None
    args: List[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Path | None = None

    url: str | None = None

    @model_validator(mode='after')
    def validate_transport(self) -> MCPServerConfig:
        has_command = self.command is not None
        has_url = self.url is not None

        if not has_command and not has_url:
            raise ValueError('MCP Server must have command or URL')

        if has_command and has_url:
            raise ValueError('MCP Server must have either command or URL')

        return self


class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)
    shell_environment: ShellEnvironmentPolicy = Field(
        default_factory=ShellEnvironmentPolicy
    )
    max_turns: int = 70
    # max_tool_output_tokens: int = 50_000
    mcp_servers: dict[str, MCPServerConfig] = Field(default_factory=dict)
    dev_instructions: str | None = None
    user_instructions: str | None = None

    debug: bool = False

    allowed_tools: list[str] | None = Field(
        None,
        description='If set, only these tools will be available to the agent.',
    )

    @property
    def api_key(self) -> str | None:
        return os.environ.get('API_KEY')
    
    @property
    def base_url(self) -> str | None:
        return os.environ.get('BASE_URL')

    @property
    def model_name(self) -> str:
        return self.model.name

    @model_name.setter
    def model_name(self, value: str) -> None:
        self.model.name = value
    
    @property
    def temperature(self) -> float:
        return self.model.temperature

    @model_name.setter
    def temperature(self, value: float) -> None:
        self.model.temperature = value

    def validate(self) -> list[str]:
        errors: list[str] = []
        
        if not self.api_key:
            errors.append('No API key found. Set it in .env file')
        
        if not self.cwd.exists():
            errors.append(f'Working directory does not exist -> {self.cwd}')
        

        return errors

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode='json')
