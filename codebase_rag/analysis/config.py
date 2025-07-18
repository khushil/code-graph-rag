"""Configuration file analysis for various config formats."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from loguru import logger


@dataclass
class ConfigValue:
    """Represents a configuration value."""

    key: str
    value: Any
    value_type: str  # "string", "number", "boolean", "array", "object"
    line_number: int | None = None
    file_path: str | None = None
    section: str | None = None  # For hierarchical configs
    is_reference: bool = False  # If it references another config value


@dataclass
class ConfigFile:
    """Represents a configuration file."""

    file_path: str
    format: str  # "yaml", "json", "makefile", "kconfig", "ini", "toml"
    values: list[ConfigValue]
    sections: list[str]
    dependencies: list[str]  # Other config files referenced
    variables: dict[str, Any]  # Variable definitions (for Makefiles)


class ConfigAnalyzer:
    """Analyzes configuration files of various formats."""

    def __init__(self):
        self.supported_formats = {
            ".yaml": self._parse_yaml,
            ".yml": self._parse_yaml,
            ".json": self._parse_json,
            ".mk": self._parse_makefile,
            "Makefile": self._parse_makefile,
            "makefile": self._parse_makefile,
            "Kconfig": self._parse_kconfig,
            ".config": self._parse_kconfig,
            ".ini": self._parse_ini,
            ".toml": self._parse_toml,
        }

    def analyze_config_file(self, file_path: str) -> ConfigFile | None:
        """Analyze a configuration file and extract its structure."""
        path = Path(file_path)

        # Determine parser based on file extension or name
        parser = None
        if path.name in self.supported_formats:
            parser = self.supported_formats[path.name]
        elif path.suffix in self.supported_formats:
            parser = self.supported_formats[path.suffix]
        elif path.name.startswith("Kconfig"):
            # Handle Kconfig files with suffixes
            parser = self._parse_kconfig

        if not parser:
            logger.warning(f"Unsupported config file format: {file_path}")
            return None

        try:
            return parser(file_path)
        except Exception as e:
            logger.error(f"Error parsing config file {file_path}: {e}")
            return None

    def _parse_yaml(self, file_path: str) -> ConfigFile:
        """Parse a YAML configuration file."""
        values = []
        sections = []

        with Path(file_path).open(encoding="utf-8") as f:
            content = f.read()
            data = yaml.safe_load(content)

        # Extract values recursively
        self._extract_nested_values(data, values, sections)

        # Look for includes/references
        dependencies = self._find_yaml_dependencies(data)

        return ConfigFile(
            file_path=file_path,
            format="yaml",
            values=values,
            sections=list(set(sections)),
            dependencies=dependencies,
            variables={},
        )

    def _parse_json(self, file_path: str) -> ConfigFile:
        """Parse a JSON configuration file."""
        values = []
        sections = []

        with Path(file_path).open(encoding="utf-8") as f:
            data = json.load(f)

        # Extract values recursively
        self._extract_nested_values(data, values, sections)

        # Look for references
        dependencies = self._find_json_dependencies(data)

        return ConfigFile(
            file_path=file_path,
            format="json",
            values=values,
            sections=list(set(sections)),
            dependencies=dependencies,
            variables={},
        )

    def _parse_makefile(self, file_path: str) -> ConfigFile:
        """Parse a Makefile."""
        values = []
        sections = []
        variables = {}
        dependencies = []

        with Path(file_path).open(encoding="utf-8") as f:
            lines = f.readlines()

        current_target = None
        for i, line in enumerate(lines):
            stripped_line = line.strip()

            # Skip comments and empty lines
            if stripped_line.startswith("#") or not stripped_line:
                continue

            # Variable assignment
            if "=" in stripped_line and ":" not in stripped_line.split("=")[0]:
                var_match = re.match(r"^(\w+)\s*[:?+]?=\s*(.*)$", stripped_line)
                if var_match:
                    var_name, var_value = var_match.groups()
                    variables[var_name] = var_value
                    values.append(
                        ConfigValue(
                            key=var_name,
                            value=var_value,
                            value_type="string",
                            line_number=i + 1,
                            file_path=file_path,
                            section="variables",
                        )
                    )

            # Target definition
            elif ":" in stripped_line:
                target_match = re.match(r"^([^:]+):\s*(.*)$", stripped_line)
                if target_match:
                    target, deps = target_match.groups()
                    current_target = target.strip()
                    sections.append(f"target:{current_target}")

                    # Parse dependencies
                    if deps:
                        dep_list = deps.split()
                        for dep in dep_list:
                            values.append(
                                ConfigValue(
                                    key=f"{current_target}_dependency",
                                    value=dep,
                                    value_type="string",
                                    line_number=i + 1,
                                    file_path=file_path,
                                    section=f"target:{current_target}",
                                    is_reference=True,
                                )
                            )

            # Include directives
            elif stripped_line.startswith(("include ", "-include ")):
                include_match = re.match(r"^-?include\s+(.+)$", stripped_line)
                if include_match:
                    included = include_match.group(1).strip()
                    dependencies.append(included)

        return ConfigFile(
            file_path=file_path,
            format="makefile",
            values=values,
            sections=list(set(sections)),
            dependencies=dependencies,
            variables=variables,
        )

    def _parse_kconfig(self, file_path: str) -> ConfigFile:
        """Parse a Kconfig file."""
        values = []
        sections = []
        dependencies = []

        with Path(file_path).open(encoding="utf-8") as f:
            lines = f.readlines()

        current_config = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Skip comments
            if stripped.startswith("#") and not stripped.startswith("# CONFIG_"):
                continue

            # Config option
            if stripped.startswith("config "):
                config_name = stripped[7:].strip()
                current_config = config_name
                sections.append(f"config:{config_name}")

            # Menu entry
            elif stripped.startswith("menu "):
                menu_name = stripped[5:].strip('"')
                sections.append(f"menu:{menu_name}")

            # Source directive (include)
            elif stripped.startswith("source "):
                source_file = stripped[7:].strip('"')
                dependencies.append(source_file)

            # Config value
            elif stripped.startswith("CONFIG_"):
                config_match = re.match(r"^(CONFIG_\w+)=(.*)$", stripped)
                if config_match:
                    key, value = config_match.groups()
                    # Determine type
                    if value in ["y", "n", "m"]:
                        value_type = "tristate"
                    elif value.isdigit():
                        value_type = "number"
                    else:
                        value_type = "string"
                        value = value.strip('"')

                    values.append(
                        ConfigValue(
                            key=key,
                            value=value,
                            value_type=value_type,
                            line_number=i + 1,
                            file_path=file_path,
                            section=f"config:{current_config}"
                            if current_config
                            else None,
                        )
                    )

            # Disabled config
            elif stripped.startswith("# CONFIG_") and stripped.endswith(" is not set"):
                key = stripped.split()[1]
                values.append(
                    ConfigValue(
                        key=key,
                        value=None,
                        value_type="disabled",
                        line_number=i + 1,
                        file_path=file_path,
                    )
                )

            # Dependencies
            elif current_config and stripped.startswith("depends on "):
                deps = stripped[11:].strip()
                values.append(
                    ConfigValue(
                        key=f"{current_config}_depends",
                        value=deps,
                        value_type="dependency",
                        line_number=i + 1,
                        file_path=file_path,
                        section=f"config:{current_config}",
                        is_reference=True,
                    )
                )

        return ConfigFile(
            file_path=file_path,
            format="kconfig",
            values=values,
            sections=list(set(sections)),
            dependencies=dependencies,
            variables={},
        )

    def _parse_ini(self, file_path: str) -> ConfigFile:
        """Parse an INI configuration file."""
        values = []
        sections = []

        with Path(file_path).open(encoding="utf-8") as f:
            lines = f.readlines()

        current_section = "DEFAULT"

        for i, line in enumerate(lines):
            stripped_line = line.strip()

            # Skip comments and empty lines
            if not stripped_line or stripped_line.startswith(("#", ";")):
                continue

            # Section header
            if stripped_line.startswith("[") and stripped_line.endswith("]"):
                current_section = stripped_line[1:-1]
                sections.append(current_section)

            # Key-value pair
            elif "=" in stripped_line:
                key, value = stripped_line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Determine type
                if value.lower() in ["true", "false"]:
                    value_type = "boolean"
                    value = value.lower() == "true"
                elif value.isdigit():
                    value_type = "number"
                    value = int(value)
                else:
                    value_type = "string"

                values.append(
                    ConfigValue(
                        key=key,
                        value=value,
                        value_type=value_type,
                        line_number=i + 1,
                        file_path=file_path,
                        section=current_section,
                    )
                )

        return ConfigFile(
            file_path=file_path,
            format="ini",
            values=values,
            sections=list(set(sections)),
            dependencies=[],
            variables={},
        )

    def _parse_toml(self, file_path: str) -> ConfigFile:
        """Parse a TOML configuration file."""
        # For now, treat it similar to INI
        # TODO: Implement proper TOML parsing with toml library
        return self._parse_ini(file_path)

    def _extract_nested_values(
        self,
        data: Any,
        values: list[ConfigValue],
        sections: list[str],
        prefix: str = "",
        section: str | None = None,
    ) -> None:
        """Recursively extract values from nested data structures."""
        if isinstance(data, dict):
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key

                if isinstance(value, dict | list):
                    # Add section
                    sections.append(full_key)
                    self._extract_nested_values(
                        value, values, sections, full_key, full_key
                    )
                else:
                    # Add value
                    value_type = self._determine_type(value)
                    values.append(
                        ConfigValue(
                            key=full_key,
                            value=value,
                            value_type=value_type,
                            section=section,
                        )
                    )

        elif isinstance(data, list):
            for i, item in enumerate(data):
                item_key = f"{prefix}[{i}]"
                if isinstance(item, dict | list):
                    self._extract_nested_values(
                        item, values, sections, item_key, section
                    )
                else:
                    value_type = self._determine_type(item)
                    values.append(
                        ConfigValue(
                            key=item_key,
                            value=item,
                            value_type=value_type,
                            section=section,
                        )
                    )

    def _determine_type(self, value: Any) -> str:
        """Determine the type of a configuration value."""
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int | float):
            return "number"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "string"

    def _find_yaml_dependencies(self, data: Any) -> list[str]:
        """Find references to other files in YAML data."""
        dependencies = []

        # Common patterns for includes in YAML
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ["include", "includes", "import", "imports", "extends"]:
                    if isinstance(value, str):
                        dependencies.append(value)
                    elif isinstance(value, list):
                        dependencies.extend(str(v) for v in value if isinstance(v, str))
                elif isinstance(value, dict):
                    dependencies.extend(self._find_yaml_dependencies(value))

        return dependencies

    def _find_json_dependencies(self, data: Any) -> list[str]:
        """Find references to other files in JSON data."""
        dependencies = []

        # Common patterns for includes in JSON
        if isinstance(data, dict):
            for key, value in data.items():
                if key in ["$ref", "$include", "extends", "import"]:
                    if isinstance(value, str):
                        dependencies.append(value)
                elif key == "$schema" and isinstance(value, str):
                    # JSON schema reference
                    dependencies.append(value)
                elif isinstance(value, dict):
                    dependencies.extend(self._find_json_dependencies(value))

        return dependencies

    def build_config_graph(
        self,
        config_files: list[ConfigFile],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Build graph nodes and relationships for configuration data."""
        nodes = []
        relationships = []

        for config in config_files:
            # Create ConfigFile node
            config_node = {
                "label": "ConfigFile",
                "properties": {
                    "file_path": config.file_path,
                    "format": config.format,
                    "section_count": len(config.sections),
                    "value_count": len(config.values),
                    "has_variables": bool(config.variables),
                },
            }
            nodes.append(config_node)

            # Create CONFIGURES relationship to Module
            configures_rel = {
                "start_label": "ConfigFile",
                "start_key": "file_path",
                "start_value": config.file_path,
                "rel_type": "CONFIGURES",
                "end_label": "Module",
                "end_key": "file_path",
                "end_value": str(Path(config.file_path).parent),
                "properties": {
                    "format": config.format,
                },
            }
            relationships.append(configures_rel)

            # Create relationships for dependencies
            for dep in config.dependencies:
                dep_rel = {
                    "start_label": "ConfigFile",
                    "start_key": "file_path",
                    "start_value": config.file_path,
                    "rel_type": "INCLUDES_CONFIG",
                    "end_label": "ConfigFile",
                    "end_key": "file_path",
                    "end_value": dep,
                    "properties": {},
                }
                relationships.append(dep_rel)

            # Create REFERENCES_CONFIG relationships for config references
            for value in config.values:
                if value.is_reference and value.value:
                    # This config value references another config
                    ref_rel = {
                        "start_label": "Module",
                        "start_key": "qualified_name",
                        "start_value": f"{config.file_path}:{value.key}",
                        "rel_type": "REFERENCES_CONFIG",
                        "end_label": "ConfigFile",
                        "end_key": "file_path",
                        "end_value": config.file_path,
                        "properties": {
                            "config_key": value.key,
                            "config_value": str(value.value),
                            "value_type": value.value_type,
                        },
                    }
                    relationships.append(ref_rel)

        return nodes, relationships

    def generate_config_report(
        self,
        config_files: list[ConfigFile],
    ) -> dict[str, Any]:
        """Generate a configuration analysis report."""
        report = {
            "total_config_files": len(config_files),
            "format_distribution": {},
            "total_config_values": 0,
            "complex_configs": [],
            "dependency_graph": {},
            "common_patterns": {},
        }

        # Format distribution
        format_counts = {}
        for config in config_files:
            format_counts[config.format] = format_counts.get(config.format, 0) + 1
            report["total_config_values"] += len(config.values)

        report["format_distribution"] = format_counts

        # Complex configs (many sections or values)
        complex_configs = []
        for config in config_files:
            if len(config.sections) > 10 or len(config.values) > 50:
                complex_configs.append(
                    {
                        "file": config.file_path,
                        "format": config.format,
                        "sections": len(config.sections),
                        "values": len(config.values),
                    }
                )

        report["complex_configs"] = sorted(
            complex_configs, key=lambda x: x["values"], reverse=True
        )[:10]

        # Dependency graph
        dep_graph = {}
        for config in config_files:
            if config.dependencies:
                dep_graph[config.file_path] = config.dependencies

        report["dependency_graph"] = dep_graph

        # Common configuration patterns
        key_patterns = {}
        for config in config_files:
            for value in config.values:
                # Extract common prefixes
                key_parts = value.key.split(".")
                if len(key_parts) > 1:
                    prefix = key_parts[0]
                    key_patterns[prefix] = key_patterns.get(prefix, 0) + 1

        report["common_patterns"] = dict(
            sorted(key_patterns.items(), key=lambda x: x[1], reverse=True)[:20]
        )

        return report
