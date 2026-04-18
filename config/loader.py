import logging
logger = logging.getLogger(__name__)
from pathlib import Path
from platformdirs import user_config_dir
import tomli
from typing import Any

from config.config import Config
from utils.errors import ConfigError

AGENT_MD_FILE = 'AGENT.md'
CONFIG_FILE_NAME = 'config.toml'

# User can have TWO TYPES OF CONFIGS
# 1. A GENERIC config
#   ~/.config/ai-agent/config.toml
# 2. A PROJECT SPECIFIC config 
#   Users/username/Desktop/project_name/.ai_agent/config.toml
# The second one, i.e. the project specific config is prioritised and shall override the generic one.   

def get_config_dir() -> Path:
    return Path(user_config_dir('ai-agent'))

def get_system_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE_NAME

def load_config(cwd: Path | None) -> Config:
    cwd = cwd or Path.cwd()

    sys_path = get_system_config_path()

    config_dict: dict[str, Any] = {}

    if sys_path.is_file():
        try:
            config_dict = _parse_toml(sys_path)
        except ConfigError:
            logger.warning(f'Skipping invalid system config: {sys_path}')
    
    project_path = _get_project_config(cwd)
    if project_path:
        try:
            project_config_dict = _parse_toml(project_path)
            config_dict = _merge_dicts(config_dict, project_config_dict) # <- project config overrides
        except ConfigError:
            logger.warning(f'Skipping invalid system config: {sys_path}')
    
    if 'cwd' not in config_dict:
        config_dict['cwd'] = cwd
    
    if 'dev_instructions' not in config_dict:
        # If dev instructions are not provided, read AGENTS.md file which is specific to a project.
        agent_md_content = _get_agent_md_files(cwd)
        if agent_md_content:
            config_dict['dev_instructions'] = agent_md_content
    
    try:
        config = Config(**config_dict)
    except Exception as e:
        raise ConfigError(f'Invalid config -> {e}') from e

    return config

def _get_agent_md_files(cwd: Path) -> Path | None:
    current = cwd.resolve()

    if current.is_dir():
        agent_md_file = current / AGENT_MD_FILE

        if agent_md_file.is_file():
            try:
                content = agent_md_file.read_text(encoding='utf-8')
                return content
            except Exception as e:
                logger.warning(f'Something went wrong -> {e}')

            return None
    
    return None

def _get_project_config(cwd: Path) -> Path | None:
    current = cwd.resolve()
    agent_dir = current / '.ai-agent'

    if agent_dir.is_dir():
        config_file = agent_dir / CONFIG_FILE_NAME

        if config_file.is_file():
            return config_file
    
    return None

def _merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    # Perform a deep copy recursively
    result = base.copy()

    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _merge_dicts(result[k], v)
        else:
            result[k] = v
        
    return result


def _parse_toml(path: Path):
    try:
        with open(path, 'rb') as f:
            return tomli.load(f)
    except tomli.TOMLDecodeError as e:
        raise ConfigError('Invalid TOML in {path}: {e}', config_file=str(path)) from e
    except (OSError, IOError) as e:
        raise ConfigError('Failed to read the config file {path}: {e}', config_file=str(path)) from e
        


