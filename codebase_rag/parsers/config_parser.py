"""Configuration file parser for various formats."""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import json
import yaml
import toml
import configparser
from loguru import logger


@dataclass
class ConfigSetting:
    """Represents a configuration setting."""
    key: str
    value: Any
    path: List[str]  # Hierarchical path to the setting
    line_number: Optional[int] = None
    setting_type: str = "unknown"  # string, number, boolean, array, object
    
    def get_full_path(self) -> str:
        """Get the full dotted path to this setting."""
        return ".".join(self.path + [self.key])


@dataclass
class ConfigFile:
    """Information about a configuration file."""
    file_path: str
    format: str  # json, yaml, toml, ini, env, properties
    settings: List[ConfigSetting]
    raw_content: Dict[str, Any]
    dependencies: List[str] = None  # External dependencies referenced
    environments: List[str] = None  # Environment-specific configs
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.environments is None:
            self.environments = []


class ConfigParser:
    """Parses configuration files in various formats."""
    
    SUPPORTED_FORMATS = {
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'ini',
        '.env': 'env',
        '.properties': 'properties'
    }
    
    def __init__(self):
        self.parsers = {
            'json': self._parse_json,
            'yaml': self._parse_yaml,
            'toml': self._parse_toml,
            'ini': self._parse_ini,
            'env': self._parse_env,
            'properties': self._parse_properties
        }
    
    def parse_file(self, file_path: Path) -> Optional[ConfigFile]:
        """Parse a configuration file."""
        if not file_path.exists():
            logger.error(f"Configuration file not found: {file_path}")
            return None
        
        # Determine format
        suffix = file_path.suffix.lower()
        format_type = self.SUPPORTED_FORMATS.get(suffix)
        
        if not format_type:
            # Try to detect format from content
            format_type = self._detect_format(file_path)
            if not format_type:
                logger.warning(f"Unknown configuration file format: {file_path}")
                return None
        
        # Parse the file
        parser = self.parsers.get(format_type)
        if not parser:
            logger.error(f"No parser available for format: {format_type}")
            return None
        
        try:
            return parser(file_path)
        except Exception as e:
            logger.error(f"Failed to parse {format_type} file {file_path}: {e}")
            return None
    
    def _detect_format(self, file_path: Path) -> Optional[str]:
        """Try to detect format from file content."""
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Try JSON
            try:
                json.loads(content)
                return 'json'
            except:
                pass
            
            # Try YAML
            try:
                yaml.safe_load(content)
                # Check if it's not valid TOML (YAML is more permissive)
                try:
                    toml.loads(content)
                except:
                    return 'yaml'
            except:
                pass
            
            # Try TOML
            try:
                toml.loads(content)
                return 'toml'
            except:
                pass
            
            # Check for INI-style
            if any(line.strip().startswith('[') and line.strip().endswith(']') 
                   for line in content.split('\n') if line.strip()):
                return 'ini'
            
            # Check for env-style
            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.strip().startswith('#')]
            if all('=' in line for line in lines[:5] if line):  # Check first 5 non-empty lines
                return 'env'
            
        except Exception as e:
            logger.error(f"Error detecting format for {file_path}: {e}")
        
        return None
    
    def _parse_json(self, file_path: Path) -> Optional[ConfigFile]:
        """Parse JSON configuration file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            data = json.loads(content)
            
            settings = []
            self._extract_settings(data, [], settings)
            
            return ConfigFile(
                file_path=str(file_path),
                format='json',
                settings=settings,
                raw_content=data,
                dependencies=self._extract_dependencies(data),
                environments=self._extract_environments(data)
            )
        except Exception as e:
            logger.error(f"Failed to parse JSON file {file_path}: {e}")
            return None
    
    def _parse_yaml(self, file_path: Path) -> Optional[ConfigFile]:
        """Parse YAML configuration file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            data = yaml.safe_load(content)
            
            if data is None:
                data = {}
            
            settings = []
            self._extract_settings(data, [], settings)
            
            return ConfigFile(
                file_path=str(file_path),
                format='yaml',
                settings=settings,
                raw_content=data,
                dependencies=self._extract_dependencies(data),
                environments=self._extract_environments(data)
            )
        except Exception as e:
            logger.error(f"Failed to parse YAML file {file_path}: {e}")
            return None
    
    def _parse_toml(self, file_path: Path) -> Optional[ConfigFile]:
        """Parse TOML configuration file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            data = toml.loads(content)
            
            settings = []
            self._extract_settings(data, [], settings)
            
            # TOML-specific: check for common patterns
            dependencies = self._extract_dependencies(data)
            
            # Check for pyproject.toml specific sections
            if file_path.name == 'pyproject.toml':
                if 'project' in data and 'dependencies' in data['project']:
                    dependencies.extend(data['project']['dependencies'])
                if 'tool' in data:
                    for tool_name in data['tool']:
                        dependencies.append(f"tool:{tool_name}")
            
            return ConfigFile(
                file_path=str(file_path),
                format='toml',
                settings=settings,
                raw_content=data,
                dependencies=dependencies,
                environments=self._extract_environments(data)
            )
        except Exception as e:
            logger.error(f"Failed to parse TOML file {file_path}: {e}")
            return None
    
    def _parse_ini(self, file_path: Path) -> Optional[ConfigFile]:
        """Parse INI configuration file."""
        try:
            config = configparser.ConfigParser()
            config.read(file_path)
            
            settings = []
            data = {}
            
            for section in config.sections():
                data[section] = dict(config[section])
                for key, value in config[section].items():
                    setting = ConfigSetting(
                        key=key,
                        value=value,
                        path=[section],
                        setting_type=self._get_value_type(value)
                    )
                    settings.append(setting)
            
            return ConfigFile(
                file_path=str(file_path),
                format='ini',
                settings=settings,
                raw_content=data,
                dependencies=self._extract_dependencies(data),
                environments=list(config.sections()) if len(config.sections()) > 1 else []
            )
        except Exception as e:
            logger.error(f"Failed to parse INI file {file_path}: {e}")
            return None
    
    def _parse_env(self, file_path: Path) -> Optional[ConfigFile]:
        """Parse .env file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            settings = []
            data = {}
            
            for line_num, line in enumerate(content.split('\n'), 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value and value[0] in ('"', "'") and value[0] == value[-1]:
                        value = value[1:-1]
                    
                    data[key] = value
                    setting = ConfigSetting(
                        key=key,
                        value=value,
                        path=[],
                        line_number=line_num,
                        setting_type=self._get_value_type(value)
                    )
                    settings.append(setting)
            
            return ConfigFile(
                file_path=str(file_path),
                format='env',
                settings=settings,
                raw_content=data,
                dependencies=self._extract_env_dependencies(data)
            )
        except Exception as e:
            logger.error(f"Failed to parse env file {file_path}: {e}")
            return None
    
    def _parse_properties(self, file_path: Path) -> Optional[ConfigFile]:
        """Parse Java-style properties file."""
        try:
            content = file_path.read_text(encoding='utf-8')
            settings = []
            data = {}
            
            for line_num, line in enumerate(content.split('\n'), 1):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('!'):
                    continue
                
                # Handle multi-line values (ending with \)
                while line.endswith('\\') and line_num < len(content.split('\n')):
                    line = line[:-1] + content.split('\n')[line_num].strip()
                    line_num += 1
                
                if '=' in line:
                    key, value = line.split('=', 1)
                elif ':' in line:
                    key, value = line.split(':', 1)
                else:
                    continue
                
                key = key.strip()
                value = value.strip()
                
                data[key] = value
                setting = ConfigSetting(
                    key=key,
                    value=value,
                    path=[],
                    line_number=line_num,
                    setting_type=self._get_value_type(value)
                )
                settings.append(setting)
            
            return ConfigFile(
                file_path=str(file_path),
                format='properties',
                settings=settings,
                raw_content=data,
                dependencies=self._extract_dependencies(data)
            )
        except Exception as e:
            logger.error(f"Failed to parse properties file {file_path}: {e}")
            return None
    
    def _extract_settings(self, data: Any, path: List[str], settings: List[ConfigSetting]):
        """Recursively extract settings from nested data structures."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    self._extract_settings(value, path + [key], settings)
                else:
                    setting = ConfigSetting(
                        key=key,
                        value=value,
                        path=path.copy(),
                        setting_type=self._get_value_type(value)
                    )
                    settings.append(setting)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    self._extract_settings(item, path + [f"[{i}]"], settings)
                else:
                    setting = ConfigSetting(
                        key=f"[{i}]",
                        value=item,
                        path=path.copy(),
                        setting_type=self._get_value_type(item)
                    )
                    settings.append(setting)
    
    def _get_value_type(self, value: Any) -> str:
        """Determine the type of a configuration value."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "unknown"
    
    def _extract_dependencies(self, data: Any) -> List[str]:
        """Extract potential dependencies from configuration."""
        dependencies = []
        
        # Common dependency patterns
        dep_keys = ['dependencies', 'requires', 'imports', 'packages', 'libs', 'modules']
        
        def search_deps(obj: Any, key_path: str = ""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    lower_key = key.lower()
                    if any(dep_key in lower_key for dep_key in dep_keys):
                        if isinstance(value, list):
                            dependencies.extend(str(v) for v in value if isinstance(v, (str, int, float)))
                        elif isinstance(value, dict):
                            dependencies.extend(value.keys())
                        elif isinstance(value, str):
                            dependencies.append(value)
                    else:
                        search_deps(value, f"{key_path}.{key}" if key_path else key)
            elif isinstance(obj, list):
                for item in obj:
                    search_deps(item, key_path)
        
        search_deps(data)
        return list(set(dependencies))  # Remove duplicates
    
    def _extract_env_dependencies(self, data: Dict[str, str]) -> List[str]:
        """Extract dependencies from environment variables."""
        dependencies = []
        
        # Common patterns for dependencies in env vars
        for key, value in data.items():
            lower_key = key.lower()
            if any(pattern in lower_key for pattern in ['path', 'lib', 'module', 'package', 'dependency']):
                # Split by common delimiters
                for delimiter in [':', ';', ',']:
                    if delimiter in value:
                        parts = [p.strip() for p in value.split(delimiter) if p.strip()]
                        dependencies.extend(parts)
                        break
                else:
                    if value and not value.startswith('$'):
                        dependencies.append(value)
        
        return dependencies
    
    def _extract_environments(self, data: Any) -> List[str]:
        """Extract environment-specific configurations."""
        environments = []
        
        # Common environment patterns
        env_keys = ['env', 'environment', 'profile', 'stage', 'deployment']
        env_names = ['dev', 'development', 'test', 'testing', 'qa', 'staging', 'prod', 'production']
        
        def search_envs(obj: Any):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    lower_key = key.lower()
                    # Check if key suggests environment
                    if any(env_key in lower_key for env_key in env_keys):
                        if isinstance(value, dict):
                            environments.extend(value.keys())
                        elif isinstance(value, str):
                            environments.append(value)
                    # Check if key is an environment name
                    elif lower_key in env_names:
                        environments.append(key)
                    
                    # Recurse
                    search_envs(value)
            elif isinstance(obj, list):
                for item in obj:
                    search_envs(item)
        
        search_envs(data)
        return list(set(environments))  # Remove duplicates