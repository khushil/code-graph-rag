"""Test configuration file parser functionality."""

import pytest
from pathlib import Path
import tempfile
import json
import yaml
import toml

from codebase_rag.parsers.config_parser import ConfigParser, ConfigFile, ConfigSetting


class TestConfigParser:
    """Test configuration file parsing."""
    
    @pytest.fixture
    def config_parser(self):
        """Create a ConfigParser instance."""
        return ConfigParser()
    
    def test_json_parsing(self, config_parser):
        """Test parsing JSON configuration files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_content = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "credentials": {
                        "username": "admin",
                        "password": "secret"
                    }
                },
                "features": ["auth", "api", "ui"],
                "debug": True
            }
            json.dump(json_content, f)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            
            assert config_file is not None
            assert config_file.format == "json"
            assert len(config_file.settings) > 0
            
            # Check specific settings
            settings_by_path = {s.get_full_path(): s for s in config_file.settings}
            assert "database.host" in settings_by_path
            assert settings_by_path["database.host"].value == "localhost"
            assert settings_by_path["database.port"].value == 5432
            assert settings_by_path["database.port"].setting_type == "integer"
            
            Path(f.name).unlink()
    
    def test_yaml_parsing(self, config_parser):
        """Test parsing YAML configuration files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml_content = """
database:
  host: localhost
  port: 5432
  ssl: true

environments:
  development:
    debug: true
  production:
    debug: false
    
dependencies:
  - flask
  - sqlalchemy
"""
            f.write(yaml_content)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            
            assert config_file is not None
            assert config_file.format == "yaml"
            assert "development" in config_file.environments
            assert "production" in config_file.environments
            assert "flask" in config_file.dependencies
            
            Path(f.name).unlink()
    
    def test_toml_parsing(self, config_parser):
        """Test parsing TOML configuration files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            toml_content = {
                "project": {
                    "name": "test-project",
                    "version": "1.0.0",
                    "dependencies": ["requests", "pytest"]
                },
                "tool": {
                    "pytest": {
                        "minversion": "6.0"
                    }
                }
            }
            toml.dump(toml_content, f)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            
            assert config_file is not None
            assert config_file.format == "toml"
            assert len(config_file.dependencies) >= 2
            assert "requests" in config_file.dependencies
            
            Path(f.name).unlink()
    
    def test_ini_parsing(self, config_parser):
        """Test parsing INI configuration files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            ini_content = """[database]
host = localhost
port = 5432

[logging]
level = INFO
file = app.log
"""
            f.write(ini_content)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            
            assert config_file is not None
            assert config_file.format == "ini"
            assert len(config_file.settings) >= 4
            
            # Check sections are captured
            settings_by_path = {s.get_full_path(): s for s in config_file.settings}
            assert "database.host" in settings_by_path
            assert "logging.level" in settings_by_path
            
            Path(f.name).unlink()
    
    def test_env_parsing(self, config_parser):
        """Test parsing .env files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            env_content = """# Database config
DATABASE_URL=postgresql://user:pass@localhost/db
API_KEY=abc123
DEBUG=true
PORT=8080
"""
            f.write(env_content)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            
            assert config_file is not None
            assert config_file.format == "env"
            assert len(config_file.settings) == 4
            
            # Check env vars
            settings_by_key = {s.key: s for s in config_file.settings}
            assert "DATABASE_URL" in settings_by_key
            assert "PORT" in settings_by_key
            assert settings_by_key["PORT"].value == "8080"
            
            Path(f.name).unlink()
    
    def test_properties_parsing(self, config_parser):
        """Test parsing Java-style properties files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.properties', delete=False) as f:
            props_content = """# Application properties
app.name=MyApp
app.version=1.0.0
server.port=8080
database.url=jdbc:mysql://localhost/mydb
"""
            f.write(props_content)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            
            assert config_file is not None
            assert config_file.format == "properties"
            assert len(config_file.settings) == 4
            
            settings_by_key = {s.key: s for s in config_file.settings}
            assert "app.name" in settings_by_key
            assert settings_by_key["app.name"].value == "MyApp"
            
            Path(f.name).unlink()
    
    def test_format_detection(self, config_parser):
        """Test automatic format detection."""
        # Test JSON without extension
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            json.dump({"key": "value"}, f)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            assert config_file is not None
            assert config_file.format == "json"
            
            Path(f.name).unlink()
    
    def test_dependency_extraction(self, config_parser):
        """Test extracting dependencies from various formats."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_content = {
                "dependencies": ["dep1", "dep2"],
                "devDependencies": {
                    "test-lib": "^1.0.0"
                },
                "requires": ["module1"],
                "database": {
                    "driver": "postgresql"
                }
            }
            json.dump(json_content, f)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            
            assert "dep1" in config_file.dependencies
            assert "dep2" in config_file.dependencies
            assert "test-lib" in config_file.dependencies
            assert "module1" in config_file.dependencies
            
            Path(f.name).unlink()
    
    def test_environment_extraction(self, config_parser):
        """Test extracting environment configurations."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_content = {
                "environments": {
                    "dev": {"url": "http://localhost"},
                    "prod": {"url": "https://api.example.com"}
                },
                "profiles": ["test", "staging"]
            }
            json.dump(json_content, f)
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            
            assert "dev" in config_file.environments
            assert "prod" in config_file.environments
            
            Path(f.name).unlink()
    
    def test_invalid_file(self, config_parser):
        """Test handling of invalid files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json {")
            f.flush()
            
            config_file = config_parser.parse_file(Path(f.name))
            assert config_file is None
            
            Path(f.name).unlink()
    
    def test_pyproject_toml_special_handling(self, config_parser):
        """Test special handling for pyproject.toml files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            # Rename to pyproject.toml
            pyproject_path = Path(f.name).parent / "pyproject.toml"
            
            toml_content = {
                "project": {
                    "name": "my-project",
                    "dependencies": ["numpy", "pandas"]
                },
                "tool": {
                    "pytest": {"minversion": "6.0"},
                    "mypy": {"python_version": "3.8"}
                }
            }
            
            with open(pyproject_path, 'w') as pf:
                toml.dump(toml_content, pf)
            
            config_file = config_parser.parse_file(pyproject_path)
            
            assert config_file is not None
            assert "numpy" in config_file.dependencies
            assert "pandas" in config_file.dependencies
            assert "tool:pytest" in config_file.dependencies
            assert "tool:mypy" in config_file.dependencies
            
            pyproject_path.unlink()