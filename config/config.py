import os
from pathlib import Path

from pydantic import BaseModel, Field

class ModelConfig(BaseModel):
    name: str = 'openrouter/elephant-alpha' # <- default model
    temperature: float = Field(default=0.4, ge=0.0, le=1.0) 
    content_window: int = 256_000

class Config(BaseModel):
    model: ModelConfig = Field(default_factory=ModelConfig)
    cwd: Path = Field(default_factory=Path.cwd)

    max_turns: int = 70
    max_tool_output_tokens: int = 50_000

    dev_instructions: str | None = None
    user_instructions: str | None = None

    debug: bool = False

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
