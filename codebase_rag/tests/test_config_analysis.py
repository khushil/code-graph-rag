"""Tests for configuration file analysis functionality."""

import json
import tempfile
from pathlib import Path

import pytest

from codebase_rag.analysis.config import ConfigAnalyzer, ConfigFile, ConfigValue


class TestConfigAnalyzer:
    """Test the configuration analysis functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create a configuration analyzer."""
        return ConfigAnalyzer()

    def test_config_value_dataclass(self):
        """Test ConfigValue dataclass."""
        value = ConfigValue(
            key="database.host",
            value="localhost",
            value_type="string",
            line_number=10,
            file_path="/config/app.yaml",
            section="database",
            is_reference=False,
        )

        assert value.key == "database.host"
        assert value.value == "localhost"
        assert value.value_type == "string"
        assert value.line_number == 10
        assert value.section == "database"
        assert not value.is_reference

    def test_config_file_dataclass(self):
        """Test ConfigFile dataclass."""
        values = [
            ConfigValue("key1", "value1", "string"),
            ConfigValue("key2", 42, "number"),
        ]

        config = ConfigFile(
            file_path="/config/app.yaml",
            format="yaml",
            values=values,
            sections=["database", "server"],
            dependencies=["base.yaml"],
            variables={"VAR1": "value1"},
        )

        assert config.file_path == "/config/app.yaml"
        assert config.format == "yaml"
        assert len(config.values) == 2
        assert len(config.sections) == 2
        assert len(config.dependencies) == 1
        assert "VAR1" in config.variables

    def test_parse_yaml(self, analyzer):
        """Test parsing YAML configuration files."""
        yaml_content = """
database:
  host: localhost
  port: 5432
  credentials:
    username: admin
    password: secret

server:
  host: 0.0.0.0
  port: 8080
  debug: true

features:
  - authentication
  - logging
  - monitoring
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            f.flush()

            config = analyzer.analyze_config_file(f.name)

        Path(f.name).unlink()

        assert config is not None
        assert config.format == "yaml"

        # Check values
        values_dict = {v.key: v for v in config.values}
        assert "database.host" in values_dict
        assert values_dict["database.host"].value == "localhost"
        assert values_dict["database.port"].value == 5432
        assert values_dict["database.port"].value_type == "number"

        assert "server.debug" in values_dict
        assert values_dict["server.debug"].value is True
        assert values_dict["server.debug"].value_type == "boolean"

        # Check array values
        assert "features[0]" in values_dict
        assert values_dict["features[0]"].value == "authentication"

        # Check sections
        assert "database" in config.sections
        assert "server" in config.sections
        assert "database.credentials" in config.sections

    def test_parse_json(self, analyzer):
        """Test parsing JSON configuration files."""
        json_content = {
            "name": "MyApp",
            "version": "1.0.0",
            "settings": {"debug": False, "max_connections": 100, "timeout": 30.5},
            "dependencies": ["lib1", "lib2"],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(json_content, f)
            f.flush()

            config = analyzer.analyze_config_file(f.name)

        Path(f.name).unlink()

        assert config is not None
        assert config.format == "json"

        # Check values
        values_dict = {v.key: v for v in config.values}
        assert "name" in values_dict
        assert values_dict["name"].value == "MyApp"
        assert values_dict["name"].value_type == "string"

        assert "settings.max_connections" in values_dict
        assert values_dict["settings.max_connections"].value == 100
        assert values_dict["settings.max_connections"].value_type == "number"

        assert "settings.timeout" in values_dict
        assert values_dict["settings.timeout"].value == 30.5
        assert values_dict["settings.timeout"].value_type == "number"

    def test_parse_makefile(self, analyzer):
        """Test parsing Makefile."""
        makefile_content = """
# Variables
CC = gcc
CFLAGS = -Wall -O2
SOURCES = main.c utils.c
OBJECTS = $(SOURCES:.c=.o)
TARGET = myapp

# Targets
all: $(TARGET)

$(TARGET): $(OBJECTS)
\techo "Building $(TARGET)"
\t$(CC) $(CFLAGS) -o $@ $^

%.o: %.c
\t$(CC) $(CFLAGS) -c $< -o $@

clean:
\trm -f $(OBJECTS) $(TARGET)

include config.mk
-include optional.mk
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".mk", delete=False) as f:
            f.write(makefile_content)
            f.flush()

            config = analyzer.analyze_config_file(f.name)

        Path(f.name).unlink()

        assert config is not None
        assert config.format == "makefile"

        # Check variables
        assert "CC" in config.variables
        assert config.variables["CC"] == "gcc"
        assert "CFLAGS" in config.variables
        assert config.variables["CFLAGS"] == "-Wall -O2"

        # Check values
        values_dict = {v.key: v for v in config.values}
        assert "CC" in values_dict
        assert values_dict["CC"].value == "gcc"

        # Check sections (targets)
        assert "target:all" in config.sections
        assert "target:clean" in config.sections

        # Check dependencies
        assert "config.mk" in config.dependencies
        assert "optional.mk" in config.dependencies

    def test_parse_kconfig(self, analyzer):
        """Test parsing Kconfig files."""
        kconfig_content = """
config ENABLE_FEATURE_X
\tbool "Enable feature X"
\tdefault y
\thelp
\t  This enables feature X which provides...

config MAX_BUFFER_SIZE
\tint "Maximum buffer size"
\tdefault 1024
\trange 256 4096
\tdepends on ENABLE_FEATURE_X

menu "Network Options"

config ENABLE_IPV6
\tbool "Enable IPv6 support"
\tdefault n

source "drivers/Kconfig"

# Actual config values
CONFIG_ENABLE_FEATURE_X=y
CONFIG_MAX_BUFFER_SIZE=2048
# CONFIG_ENABLE_IPV6 is not set
"""

        with tempfile.NamedTemporaryFile(mode="w", prefix="Kconfig", delete=False) as f:
            f.write(kconfig_content)
            f.flush()

            config = analyzer.analyze_config_file(f.name)

        Path(f.name).unlink()

        assert config is not None
        assert config.format == "kconfig"

        # Check sections
        assert "config:ENABLE_FEATURE_X" in config.sections
        assert "config:MAX_BUFFER_SIZE" in config.sections
        assert "menu:Network Options" in config.sections

        # Check values
        values_dict = {v.key: v for v in config.values}
        assert "CONFIG_ENABLE_FEATURE_X" in values_dict
        assert values_dict["CONFIG_ENABLE_FEATURE_X"].value == "y"
        assert values_dict["CONFIG_ENABLE_FEATURE_X"].value_type == "tristate"

        assert "CONFIG_MAX_BUFFER_SIZE" in values_dict
        assert values_dict["CONFIG_MAX_BUFFER_SIZE"].value == "2048"

        # Check disabled config
        assert "CONFIG_ENABLE_IPV6" in values_dict
        assert values_dict["CONFIG_ENABLE_IPV6"].value is None
        assert values_dict["CONFIG_ENABLE_IPV6"].value_type == "disabled"

        # Check dependencies
        assert "drivers/Kconfig" in config.dependencies

    def test_parse_ini(self, analyzer):
        """Test parsing INI configuration files."""
        ini_content = """
[DEFAULT]
debug = false
timeout = 30

[database]
host = localhost
port = 5432
user = admin

[server]
host = 0.0.0.0
port = 8080
workers = 4
ssl_enabled = true

; This is a comment
[logging]
level = INFO
file = /var/log/app.log
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
            f.write(ini_content)
            f.flush()

            config = analyzer.analyze_config_file(f.name)

        Path(f.name).unlink()

        assert config is not None
        assert config.format == "ini"

        # Check sections
        assert "DEFAULT" in config.sections
        assert "database" in config.sections
        assert "server" in config.sections
        assert "logging" in config.sections

        # Check values
        values_dict = {v.key: v for v in config.values}

        # Check type detection
        assert values_dict["debug"].value is False
        assert values_dict["debug"].value_type == "boolean"

        assert values_dict["timeout"].value == 30
        assert values_dict["timeout"].value_type == "number"

        # Find the database host specifically
        db_host = next(
            v for v in config.values if v.key == "host" and v.section == "database"
        )
        assert db_host.value == "localhost"
        assert db_host.value_type == "string"

        # Check sections are assigned correctly
        db_values = [v for v in config.values if v.section == "database"]
        assert len(db_values) == 3

    def test_build_config_graph(self, analyzer):
        """Test building configuration graph."""
        config_files = [
            ConfigFile(
                file_path="/config/app.yaml",
                format="yaml",
                values=[
                    ConfigValue("database.host", "localhost", "string"),
                    ConfigValue("include", "base.yaml", "string", is_reference=True),
                ],
                sections=["database"],
                dependencies=["base.yaml"],
                variables={},
            ),
            ConfigFile(
                file_path="/config/base.yaml",
                format="yaml",
                values=[
                    ConfigValue("defaults.timeout", 30, "number"),
                ],
                sections=["defaults"],
                dependencies=[],
                variables={},
            ),
        ]

        nodes, relationships = analyzer.build_config_graph(config_files)

        # Check ConfigFile nodes
        config_nodes = [n for n in nodes if n["label"] == "ConfigFile"]
        assert len(config_nodes) == 2

        app_config = next(
            n
            for n in config_nodes
            if n["properties"]["file_path"] == "/config/app.yaml"
        )
        assert app_config["properties"]["format"] == "yaml"
        assert app_config["properties"]["value_count"] == 2

        # Check CONFIGURES relationships
        configures_rels = [r for r in relationships if r["rel_type"] == "CONFIGURES"]
        assert len(configures_rels) == 2

        # Check INCLUDES_CONFIG relationships
        includes_rels = [r for r in relationships if r["rel_type"] == "INCLUDES_CONFIG"]
        assert len(includes_rels) == 1
        assert includes_rels[0]["start_value"] == "/config/app.yaml"
        assert includes_rels[0]["end_value"] == "base.yaml"

        # Check REFERENCES_CONFIG relationships
        ref_rels = [r for r in relationships if r["rel_type"] == "REFERENCES_CONFIG"]
        assert len(ref_rels) == 1
        assert ref_rels[0]["properties"]["config_key"] == "include"
        assert ref_rels[0]["properties"]["config_value"] == "base.yaml"

    def test_generate_config_report(self, analyzer):
        """Test generating configuration report."""
        config_files = [
            ConfigFile(
                file_path="/config/app.yaml",
                format="yaml",
                values=[
                    ConfigValue(f"key{i}", f"value{i}", "string") for i in range(60)
                ],
                sections=["section1", "section2", "section3"],
                dependencies=["base.yaml", "common.yaml"],
                variables={},
            ),
            ConfigFile(
                file_path="/config/settings.json",
                format="json",
                values=[ConfigValue(f"setting{i}", i, "number") for i in range(20)],
                sections=["app", "database"],
                dependencies=[],
                variables={},
            ),
            ConfigFile(
                file_path="/config/Makefile",
                format="makefile",
                values=[ConfigValue("CC", "gcc", "string")],
                sections=["target:all"],
                dependencies=["common.mk"],
                variables={"CC": "gcc", "CFLAGS": "-O2"},
            ),
        ]

        report = analyzer.generate_config_report(config_files)

        # Check basic statistics
        assert report["total_config_files"] == 3
        assert report["total_config_values"] == 81  # 60 + 20 + 1

        # Check format distribution
        assert report["format_distribution"]["yaml"] == 1
        assert report["format_distribution"]["json"] == 1
        assert report["format_distribution"]["makefile"] == 1

        # Check complex configs
        assert len(report["complex_configs"]) == 1
        assert report["complex_configs"][0]["file"] == "/config/app.yaml"
        assert report["complex_configs"][0]["values"] == 60

        # Check dependency graph
        assert "/config/app.yaml" in report["dependency_graph"]
        assert "base.yaml" in report["dependency_graph"]["/config/app.yaml"]

    def test_unsupported_format(self, analyzer):
        """Test handling of unsupported file formats."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("some content")
            f.flush()

            config = analyzer.analyze_config_file(f.name)

        Path(f.name).unlink()

        assert config is None  # Should return None for unsupported formats
