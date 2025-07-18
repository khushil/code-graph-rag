"""Analysis modules for advanced code analysis features."""

from .data_flow import DataFlowAnalyzer, DataFlowEdge, VariableDefinition
from .dependencies import DependencyAnalyzer, DependencyInfo, Export, Import
from .inheritance import ClassInfo, InheritanceAnalyzer, InheritanceInfo, MethodOverride
from .security import SecurityAnalyzer, TaintFlow, Vulnerability

__all__ = [
    "ClassInfo",
    "DataFlowAnalyzer",
    "DataFlowEdge",
    "DependencyAnalyzer",
    "DependencyInfo",
    "Export",
    "Import",
    "InheritanceAnalyzer",
    "InheritanceInfo",
    "MethodOverride",
    "SecurityAnalyzer",
    "TaintFlow",
    "VariableDefinition",
    "Vulnerability",
]
