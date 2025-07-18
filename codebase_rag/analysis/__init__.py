"""Analysis modules for advanced code analysis features."""

from .config import ConfigAnalyzer, ConfigFile, ConfigValue
from .data_flow import DataFlowAnalyzer, DataFlowEdge, VariableDefinition
from .dependencies import DependencyAnalyzer, DependencyInfo, Export, Import
from .inheritance import ClassInfo, InheritanceAnalyzer, InheritanceInfo, MethodOverride
from .security import SecurityAnalyzer, TaintFlow, Vulnerability
from .vcs import AuthorInfo, BlameInfo, CommitInfo, FileHistory, VCSAnalyzer

__all__ = [
    "AuthorInfo",
    "BlameInfo",
    "ClassInfo",
    "CommitInfo",
    "ConfigAnalyzer",
    "ConfigFile",
    "ConfigValue",
    "DataFlowAnalyzer",
    "DataFlowEdge",
    "DependencyAnalyzer",
    "DependencyInfo",
    "Export",
    "FileHistory",
    "Import",
    "InheritanceAnalyzer",
    "InheritanceInfo",
    "MethodOverride",
    "SecurityAnalyzer",
    "TaintFlow",
    "VCSAnalyzer",
    "VariableDefinition",
    "Vulnerability",
]
