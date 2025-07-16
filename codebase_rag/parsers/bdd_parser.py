"""BDD (Behavior-Driven Development) parser for Gherkin files."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import re
from loguru import logger


@dataclass
class BDDStep:
    """Represents a single BDD step (Given/When/Then)."""
    keyword: str  # Given, When, Then, And, But
    text: str
    line_number: int
    parameters: List[str] = field(default_factory=list)  # Extracted parameters
    data_table: Optional[List[List[str]]] = None
    doc_string: Optional[str] = None


@dataclass
class BDDScenario:
    """Represents a BDD scenario."""
    name: str
    line_number: int
    tags: List[str] = field(default_factory=list)
    steps: List[BDDStep] = field(default_factory=list)
    examples: Optional[List[Dict[str, str]]] = None  # For scenario outlines


@dataclass
class BDDFeature:
    """Represents a BDD feature."""
    name: str
    description: str
    line_number: int
    tags: List[str] = field(default_factory=list)
    background: Optional[BDDScenario] = None
    scenarios: List[BDDScenario] = field(default_factory=list)
    file_path: str = ""


class BDDParser:
    """Parser for Gherkin (.feature) files."""
    
    # Gherkin keywords
    FEATURE_KEYWORDS = ["Feature:", "功能:", "Fonctionnalité:", "Característica:"]
    SCENARIO_KEYWORDS = ["Scenario:", "场景:", "Scénario:", "Escenario:"]
    SCENARIO_OUTLINE_KEYWORDS = ["Scenario Outline:", "场景大纲:", "Plan du scénario:"]
    BACKGROUND_KEYWORDS = ["Background:", "背景:", "Contexte:", "Antecedentes:"]
    EXAMPLES_KEYWORDS = ["Examples:", "例子:", "Exemples:", "Ejemplos:"]
    STEP_KEYWORDS = ["Given", "When", "Then", "And", "But", "*",
                     "假如", "当", "那么", "而且", "但是",
                     "Soit", "Quand", "Alors", "Et", "Mais"]
    
    def __init__(self):
        self.features: List[BDDFeature] = []
        self.step_definitions: Dict[str, List[Tuple[str, str]]] = {}  # pattern -> [(file, function)]
        
    def parse_feature_file(self, file_path: str, content: str) -> BDDFeature:
        """Parse a Gherkin feature file."""
        lines = content.split('\n')
        line_num = 0
        
        feature = None
        current_element = None
        current_tags = []
        in_doc_string = False
        doc_string_delimiter = None
        doc_string_content = []
        in_data_table = False
        data_table_content = []
        
        while line_num < len(lines):
            line = lines[line_num].strip()
            line_num += 1
            
            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue
                
            # Handle tags
            if line.startswith('@'):
                current_tags.extend(self._parse_tags(line))
                continue
                
            # Handle doc strings
            if line in ['"""', "'''"]:
                if in_doc_string:
                    # End of doc string
                    if current_element and hasattr(current_element, 'steps') and current_element.steps:
                        current_element.steps[-1].doc_string = '\n'.join(doc_string_content)
                    in_doc_string = False
                    doc_string_content = []
                else:
                    # Start of doc string
                    in_doc_string = True
                    doc_string_delimiter = line
                continue
                
            if in_doc_string:
                doc_string_content.append(line)
                continue
                
            # Handle data tables
            if line.startswith('|'):
                if not in_data_table:
                    in_data_table = True
                    data_table_content = []
                data_table_content.append(self._parse_table_row(line))
                continue
            else:
                if in_data_table:
                    # End of data table
                    if current_element and hasattr(current_element, 'steps') and current_element.steps:
                        current_element.steps[-1].data_table = data_table_content
                    in_data_table = False
                    data_table_content = []
                    
            # Parse feature
            if self._is_keyword(line, self.FEATURE_KEYWORDS):
                feature_name = self._get_text_after_keyword(line, self.FEATURE_KEYWORDS)
                feature = BDDFeature(
                    name=feature_name,
                    description="",
                    line_number=line_num,
                    tags=current_tags,
                    file_path=file_path
                )
                current_tags = []
                # Read description
                desc_lines = []
                while line_num < len(lines):
                    next_line = lines[line_num].strip()
                    if (not next_line or next_line.startswith('@') or 
                        self._is_any_keyword(next_line)):
                        break
                    desc_lines.append(next_line)
                    line_num += 1
                feature.description = '\n'.join(desc_lines)
                continue
                
            # Parse background
            if self._is_keyword(line, self.BACKGROUND_KEYWORDS):
                background_name = self._get_text_after_keyword(line, self.BACKGROUND_KEYWORDS)
                feature.background = BDDScenario(
                    name=background_name or "Background",
                    line_number=line_num,
                    tags=current_tags
                )
                current_element = feature.background
                current_tags = []
                continue
                
            # Parse scenario
            if self._is_keyword(line, self.SCENARIO_KEYWORDS):
                scenario_name = self._get_text_after_keyword(line, self.SCENARIO_KEYWORDS)
                scenario = BDDScenario(
                    name=scenario_name,
                    line_number=line_num,
                    tags=current_tags
                )
                feature.scenarios.append(scenario)
                current_element = scenario
                current_tags = []
                continue
                
            # Parse scenario outline
            if self._is_keyword(line, self.SCENARIO_OUTLINE_KEYWORDS):
                scenario_name = self._get_text_after_keyword(line, self.SCENARIO_OUTLINE_KEYWORDS)
                scenario = BDDScenario(
                    name=scenario_name,
                    line_number=line_num,
                    tags=current_tags
                )
                feature.scenarios.append(scenario)
                current_element = scenario
                current_tags = []
                continue
                
            # Parse examples
            if self._is_keyword(line, self.EXAMPLES_KEYWORDS):
                # Read examples table
                examples = []
                # Skip to table header
                while line_num < len(lines) and not lines[line_num].strip().startswith('|'):
                    line_num += 1
                    
                if line_num < len(lines):
                    # Parse header
                    header = self._parse_table_row(lines[line_num])
                    line_num += 1
                    
                    # Parse rows
                    while line_num < len(lines) and lines[line_num].strip().startswith('|'):
                        row = self._parse_table_row(lines[line_num])
                        example = dict(zip(header, row))
                        examples.append(example)
                        line_num += 1
                        
                if current_element:
                    current_element.examples = examples
                continue
                
            # Parse steps
            if self._is_keyword(line, self.STEP_KEYWORDS):
                step_keyword = self._get_keyword(line, self.STEP_KEYWORDS)
                step_text = self._get_text_after_keyword(line, [step_keyword])
                
                # Extract parameters (words in quotes or angle brackets)
                parameters = self._extract_step_parameters(step_text)
                
                step = BDDStep(
                    keyword=step_keyword,
                    text=step_text,
                    line_number=line_num,
                    parameters=parameters
                )
                
                if current_element and hasattr(current_element, 'steps'):
                    current_element.steps.append(step)
                    
        return feature
        
    def parse_step_definition(self, content: str, file_path: str, language: str) -> List[Tuple[str, str, str]]:
        """Parse step definitions from code files.
        Returns list of (pattern, function_name, step_type) tuples.
        """
        step_definitions = []
        
        if language == "python":
            # Behave-style step definitions
            pattern = r'@(given|when|then|step)\s*\([\'"](.+?)[\'"]\)\s*\n\s*def\s+(\w+)'
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                step_type = match.group(1)
                step_pattern = match.group(2)
                function_name = match.group(3)
                step_definitions.append((step_pattern, function_name, step_type))
                
        elif language in ["javascript", "typescript"]:
            # Cucumber-style step definitions
            pattern = r'(Given|When|Then)\s*\(/(.+?)/,\s*(?:async\s+)?(?:function\s*)?(?:\w+\s*)?\('
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                step_type = match.group(1).lower()
                step_pattern = match.group(2)
                # Function name not easily extractable in JS
                step_definitions.append((step_pattern, "anonymous", step_type))
                
        elif language == "java":
            # Java Cucumber step definitions
            pattern = r'@(Given|When|Then|And|But)\s*\("(.+?)"\)\s*\n\s*public\s+void\s+(\w+)'
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                step_type = match.group(1).lower()
                step_pattern = match.group(2)
                function_name = match.group(3)
                step_definitions.append((step_pattern, function_name, step_type))
                
        return step_definitions
        
    def match_step_to_definition(self, step: BDDStep, step_definitions: List[Tuple[str, str, str]]) -> Optional[str]:
        """Match a BDD step to its implementing function."""
        step_text = step.text
        
        for pattern, function_name, step_type in step_definitions:
            # Check if step type matches (Given/When/Then)
            if step_type != "step" and step_type != step.keyword.lower():
                continue
                
            # Try to match the pattern
            if self._matches_pattern(step_text, pattern):
                return function_name
                
        return None
        
    def _matches_pattern(self, text: str, pattern: str) -> bool:
        """Check if a step text matches a step definition pattern."""
        # Convert step definition pattern to regex
        # Replace parameter placeholders with regex groups
        regex_pattern = pattern
        
        # Common parameter patterns in different frameworks
        # {parameter} or <parameter> -> captured group
        regex_pattern = re.sub(r'\{[^}]+\}', r'(.+)', regex_pattern)
        regex_pattern = re.sub(r'<[^>]+>', r'(.+)', regex_pattern)
        
        # Escape special regex characters except our groups
        regex_pattern = re.escape(regex_pattern)
        regex_pattern = regex_pattern.replace(r'\(.+\)', '(.+)')
        
        try:
            return bool(re.match(f"^{regex_pattern}$", text))
        except re.error:
            # If pattern is already a regex, try direct match
            try:
                return bool(re.match(f"^{pattern}$", text))
            except re.error:
                return False
                
    def _is_keyword(self, line: str, keywords: List[str]) -> bool:
        """Check if line starts with any of the keywords."""
        for keyword in keywords:
            if line.startswith(keyword):
                return True
        return False
        
    def _is_any_keyword(self, line: str) -> bool:
        """Check if line starts with any Gherkin keyword."""
        all_keywords = (self.FEATURE_KEYWORDS + self.SCENARIO_KEYWORDS + 
                       self.SCENARIO_OUTLINE_KEYWORDS + self.BACKGROUND_KEYWORDS + 
                       self.EXAMPLES_KEYWORDS + self.STEP_KEYWORDS)
        return self._is_keyword(line, all_keywords)
        
    def _get_keyword(self, line: str, keywords: List[str]) -> str:
        """Get the keyword that the line starts with."""
        for keyword in keywords:
            if line.startswith(keyword):
                return keyword
        return ""
        
    def _get_text_after_keyword(self, line: str, keywords: List[str]) -> str:
        """Get the text after the keyword."""
        for keyword in keywords:
            if line.startswith(keyword):
                return line[len(keyword):].strip()
        return line
        
    def _parse_tags(self, line: str) -> List[str]:
        """Parse tags from a line starting with @."""
        return [tag.strip() for tag in line.split() if tag.startswith('@')]
        
    def _parse_table_row(self, line: str) -> List[str]:
        """Parse a table row from a line starting with |."""
        cells = line.split('|')[1:-1]  # Skip first and last empty elements
        return [cell.strip() for cell in cells]
        
    def _extract_step_parameters(self, step_text: str) -> List[str]:
        """Extract parameters from step text (quoted strings or angle brackets)."""
        parameters = []
        
        # Extract quoted strings
        quoted = re.findall(r'"([^"]+)"', step_text)
        parameters.extend(quoted)
        
        # Extract single-quoted strings
        single_quoted = re.findall(r"'([^']+)'", step_text)
        parameters.extend(single_quoted)
        
        # Extract angle bracket parameters (for scenario outlines)
        angle_params = re.findall(r'<([^>]+)>', step_text)
        parameters.extend(angle_params)
        
        return parameters