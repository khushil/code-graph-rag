"""Test inheritance analysis functionality."""

import pytest

from codebase_rag.analysis.inheritance import (
    InheritanceAnalyzer,
)
from codebase_rag.parser_loader import load_parsers


class TestInheritanceAnalysis:
    """Test inheritance analysis for various languages."""

    @pytest.fixture(scope="class")
    def parsers_and_queries(self):
        """Load parsers and queries once for all tests."""
        parsers, queries = load_parsers()
        return parsers, queries

    def test_python_simple_inheritance(self, parsers_and_queries):
        """Test simple Python class inheritance."""
        parsers, queries = parsers_and_queries

        python_code = """
class Animal:
    def speak(self):
        pass

class Dog(Animal):
    def speak(self):
        return "Woof!"

    def bark(self):
        return "Bark!"

class Cat(Animal):
    def speak(self):
        return "Meow!"
"""

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.py", python_code, "test_module"
        )

        # Check inheritance relationships
        assert len(inheritance_info) == 2

        # Check Dog inherits from Animal
        dog_inheritance = next(
            i for i in inheritance_info if i.child_class == "test_module.Dog"
        )
        assert dog_inheritance.parent_class == "test_module.Animal"
        assert dog_inheritance.inheritance_type == "extends"

        # Check Cat inherits from Animal
        cat_inheritance = next(
            i for i in inheritance_info if i.child_class == "test_module.Cat"
        )
        assert cat_inheritance.parent_class == "test_module.Animal"
        assert cat_inheritance.inheritance_type == "extends"

        # Check method overrides
        assert len(method_overrides) >= 2  # Both Dog and Cat override speak

        # Check class info
        assert len(class_info) == 3
        animal_info = next(c for c in class_info if c.name == "Animal")
        assert "speak" in animal_info.methods

    def test_python_multiple_inheritance(self, parsers_and_queries):
        """Test Python multiple inheritance."""
        parsers, queries = parsers_and_queries

        python_code = """
class Flyable:
    def fly(self):
        pass

class Swimmable:
    def swim(self):
        pass

class Duck(Flyable, Swimmable):
    def fly(self):
        return "Flying!"

    def swim(self):
        return "Swimming!"
"""

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.py", python_code, "test_module"
        )

        # Check Duck inherits from both Flyable and Swimmable
        duck_inheritances = [
            i for i in inheritance_info if i.child_class == "test_module.Duck"
        ]
        assert len(duck_inheritances) == 2

        parent_classes = {i.parent_class for i in duck_inheritances}
        assert "test_module.Flyable" in parent_classes
        assert "test_module.Swimmable" in parent_classes

        # Check method overrides
        overrides = [
            o for o in method_overrides if o.child_method.startswith("test_module.Duck")
        ]
        assert len(overrides) >= 2  # fly and swim

    def test_python_abstract_classes(self, parsers_and_queries):
        """Test Python abstract classes and methods."""
        parsers, queries = parsers_and_queries

        python_code = """
from abc import ABC, abstractmethod

class Shape(ABC):
    @abstractmethod
    def area(self):
        pass

    @abstractmethod
    def perimeter(self):
        pass

class Rectangle(Shape):
    def __init__(self, width, height):
        self.width = width
        self.height = height

    def area(self):
        return self.width * self.height

    def perimeter(self):
        return 2 * (self.width + self.height)
"""

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.py", python_code, "test_module"
        )

        # Check Shape is marked as abstract
        shape_info = next(c for c in class_info if c.name == "Shape")
        assert shape_info.is_abstract

        # Check Rectangle inherits from Shape
        rect_inheritance = next(
            i for i in inheritance_info if i.child_class == "test_module.Rectangle"
        )
        assert (
            "Shape" in rect_inheritance.parent_class
        )  # May be abc.ABC.Shape or similar

        # Check abstract method implementations
        overrides = [
            o
            for o in method_overrides
            if o.child_method.startswith("test_module.Rectangle")
        ]
        assert len(overrides) >= 2  # area and perimeter

    def test_python_metaclass(self, parsers_and_queries):
        """Test Python metaclass detection."""
        parsers, queries = parsers_and_queries

        python_code = """
class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Singleton(metaclass=SingletonMeta):
    def __init__(self):
        self.value = None
"""

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.py", python_code, "test_module"
        )

        # Check Singleton has SingletonMeta as metaclass
        singleton_metaclass = [
            i
            for i in inheritance_info
            if i.child_class == "test_module.Singleton"
            and i.inheritance_type == "metaclass"
        ]
        assert len(singleton_metaclass) == 1
        assert singleton_metaclass[0].parent_class == "test_module.SingletonMeta"

        # Check class info
        singleton_info = next(c for c in class_info if c.name == "Singleton")
        assert singleton_info.metaclass == "test_module.SingletonMeta"

    def test_python_mixin_pattern(self, parsers_and_queries):
        """Test Python mixin pattern detection."""
        parsers, queries = parsers_and_queries

        python_code = """
class LoggerMixin:
    def log(self, message):
        pass  # print(f"[{self.__class__.__name__}] {message}")

class TimestampMixin:
    def get_timestamp(self):
        import time
        return time.time()

class MyClass(LoggerMixin, TimestampMixin):
    def do_something(self):
        self.log("Doing something")
        return self.get_timestamp()
"""

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.py", python_code, "test_module"
        )

        # Check MyClass inherits from both mixins
        myclass_inheritances = [
            i for i in inheritance_info if i.child_class == "test_module.MyClass"
        ]
        assert len(myclass_inheritances) == 2

        # Check mixin detection (based on naming convention)
        logger_info = next(c for c in class_info if c.name == "LoggerMixin")
        assert logger_info.is_mixin  # Should detect based on "Mixin" suffix

    def test_python_builtin_inheritance(self, parsers_and_queries):
        """Test Python built-in class inheritance."""
        parsers, queries = parsers_and_queries

        python_code = """
class MyError(Exception):
    pass

class MyDict(dict):
    def __setitem__(self, key, value):
        pass  # print(f"Setting {key} = {value}")
        super().__setitem__(key, value)

class MyList(list):
    def append(self, item):
        pass  # print(f"Appending {item}")
        super().append(item)
"""

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.py", python_code, "test_module"
        )

        # Check built-in inheritance
        error_inheritance = next(
            i for i in inheritance_info if i.child_class == "test_module.MyError"
        )
        assert error_inheritance.parent_class == "builtins.Exception"

        dict_inheritance = next(
            i for i in inheritance_info if i.child_class == "test_module.MyDict"
        )
        assert dict_inheritance.parent_class == "builtins.dict"

        # Check method overrides with super calls
        setitem_override = next(
            o
            for o in method_overrides
            if o.child_method == "test_module.MyDict.__setitem__"
        )
        assert setitem_override.has_super_call

        append_override = next(
            o for o in method_overrides if o.child_method == "test_module.MyList.append"
        )
        assert append_override.has_super_call

    def test_python_import_resolution(self, parsers_and_queries):
        """Test Python import resolution for inheritance."""
        parsers, queries = parsers_and_queries

        python_code = """
from collections import OrderedDict
from typing import List
import unittest

class MyOrderedDict(OrderedDict):
    pass

class MyTestCase(unittest.TestCase):
    def test_something(self):
        self.assertEqual(1, 1)
"""

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.py", python_code, "test_module"
        )

        # Check imported class inheritance resolution
        ordered_dict_inheritance = next(
            i for i in inheritance_info if i.child_class == "test_module.MyOrderedDict"
        )
        assert ordered_dict_inheritance.parent_class == "collections.OrderedDict"
        assert ordered_dict_inheritance.is_resolved

        testcase_inheritance = next(
            i for i in inheritance_info if i.child_class == "test_module.MyTestCase"
        )
        assert testcase_inheritance.parent_class == "unittest.TestCase"
        assert testcase_inheritance.is_resolved

    def test_javascript_class_inheritance(self, parsers_and_queries):
        """Test JavaScript ES6 class inheritance."""
        parsers, queries = parsers_and_queries

        if "javascript" not in parsers:
            pytest.skip("JavaScript parser not available")

        js_code = """
class Animal {
    constructor(name) {
        this.name = name;
    }

    speak() {
        console.log(`${this.name} makes a sound`);
    }
}

class Dog extends Animal {
    constructor(name, breed) {
        super(name);
        this.breed = breed;
    }

    speak() {
        console.log(`${this.name} barks`);
    }

    wagTail() {
        console.log("Wagging tail");
    }
}
"""

        analyzer = InheritanceAnalyzer(
            parsers["javascript"], queries["javascript"], "javascript"
        )
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.js", js_code, "test_module"
        )

        # Check inheritance
        assert len(inheritance_info) >= 1
        dog_inheritance = next(
            i for i in inheritance_info if i.child_class == "test_module.Dog"
        )
        assert dog_inheritance.parent_class == "Animal"  # Not fully qualified in JS
        assert dog_inheritance.inheritance_type == "extends"

    def test_class_attributes_extraction(self, parsers_and_queries):
        """Test extraction of class attributes."""
        parsers, queries = parsers_and_queries

        python_code = """
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
        self._private = "private"

    def set_email(self, email):
        self.email = email

    def update_info(self):
        self.last_updated = "today"
"""

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file(
            "test.py", python_code, "test_module"
        )

        # Check class attributes were extracted
        person_info = next(c for c in class_info if c.name == "Person")
        assert "name" in person_info.attributes
        assert "age" in person_info.attributes
        assert "_private" in person_info.attributes
        assert "email" in person_info.attributes
        assert "last_updated" in person_info.attributes

    def test_build_inheritance_graph(self, parsers_and_queries):
        """Test building inheritance graph nodes and relationships."""
        parsers, queries = parsers_and_queries

        from codebase_rag.analysis.inheritance import (
            ClassInfo,
            InheritanceInfo,
            MethodOverride,
        )

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")

        # Create test data
        inheritance_info = [
            InheritanceInfo(
                child_class="module.Child",
                parent_class="module.Parent",
                inheritance_type="extends",
                line_number=10,
                is_resolved=True,
            ),
            InheritanceInfo(
                child_class="module.Implementation",
                parent_class="module.Interface",
                inheritance_type="implements",
                line_number=20,
                is_resolved=True,
            ),
        ]

        method_overrides = [
            MethodOverride(
                child_method="module.Child.do_something",
                parent_method="module.Parent.do_something",
                override_type="override",
                line_number=15,
                has_super_call=True,
            )
        ]

        class_info = [
            ClassInfo(
                qualified_name="module.Child",
                name="Child",
                module="module",
                line_number=10,
                methods=["do_something", "child_method"],
                attributes=["child_attr"],
            ),
            ClassInfo(
                qualified_name="module.Parent",
                name="Parent",
                module="module",
                line_number=1,
                is_abstract=True,
                methods=["do_something"],
                attributes=["parent_attr"],
            ),
        ]

        nodes, relationships = analyzer.build_inheritance_graph(
            inheritance_info, method_overrides, class_info
        )

        # Check nodes
        assert len(nodes) == 2
        child_node = next(n for n in nodes if n["value"] == "module.Child")
        assert child_node["label"] == "Class"
        assert child_node["properties"]["method_count"] == 2
        assert child_node["properties"]["attribute_count"] == 1
        assert not child_node["properties"]["is_abstract"]

        parent_node = next(n for n in nodes if n["value"] == "module.Parent")
        assert parent_node["properties"]["is_abstract"]

        # Check relationships
        inherits_rels = [r for r in relationships if r["rel_type"] == "INHERITS_FROM"]
        assert len(inherits_rels) == 2

        implements_rels = [r for r in relationships if r["rel_type"] == "IMPLEMENTS"]
        assert len(implements_rels) == 1

        override_rels = [r for r in relationships if r["rel_type"] == "OVERRIDES"]
        assert len(override_rels) == 1
        assert override_rels[0]["properties"]["has_super_call"]

    def test_generate_inheritance_report(self, parsers_and_queries):
        """Test generating inheritance analysis report."""
        parsers, queries = parsers_and_queries

        from codebase_rag.analysis.inheritance import (
            ClassInfo,
            InheritanceInfo,
            MethodOverride,
        )

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")

        # Create test data with various scenarios
        inheritance_info = [
            InheritanceInfo(
                child_class="module.Child1",
                parent_class="module.Parent",
                inheritance_type="extends",
                line_number=10,
                is_resolved=True,
            ),
            InheritanceInfo(
                child_class="module.Child2",
                parent_class="module.Parent",
                inheritance_type="extends",
                line_number=20,
                is_resolved=True,
            ),
            InheritanceInfo(
                child_class="module.MultiChild",
                parent_class="module.Parent1",
                inheritance_type="extends",
                line_number=30,
                is_resolved=True,
            ),
            InheritanceInfo(
                child_class="module.MultiChild",
                parent_class="module.Mixin",
                inheritance_type="extends",
                line_number=30,
                is_resolved=True,
            ),
            InheritanceInfo(
                child_class="module.UnresolvedChild",
                parent_class="UnknownParent",
                inheritance_type="extends",
                line_number=40,
                is_resolved=False,
            ),
        ]

        method_overrides = [
            MethodOverride(
                child_method="module.Child1.method",
                parent_method="module.Parent.method",
                override_type="override",
                line_number=15,
                has_super_call=True,
            ),
            MethodOverride(
                child_method="module.Child2.method",
                parent_method="module.Parent.method",
                override_type="override",
                line_number=25,
                has_super_call=False,
            ),
            MethodOverride(
                child_method="module.Child1.abstract_method",
                parent_method="module.Parent.abstract_method",
                override_type="abstract_implementation",
                line_number=18,
                is_abstract=False,
            ),
        ]

        class_info = [
            ClassInfo(
                qualified_name="module.Parent",
                name="Parent",
                module="module",
                line_number=1,
                is_abstract=True,
                methods=["method", "abstract_method"],
            ),
            ClassInfo(
                qualified_name="module.Child1",
                name="Child1",
                module="module",
                line_number=10,
                methods=["method", "abstract_method"],
            ),
            ClassInfo(
                qualified_name="module.Child2",
                name="Child2",
                module="module",
                line_number=20,
                methods=["method"],
            ),
            ClassInfo(
                qualified_name="module.MultiChild",
                name="MultiChild",
                module="module",
                line_number=30,
                methods=["method"],
            ),
            ClassInfo(
                qualified_name="module.Mixin",
                name="Mixin",
                module="module",
                line_number=35,
                is_mixin=True,
                methods=["mixin_method"],
            ),
        ]

        report = analyzer.generate_inheritance_report(
            inheritance_info, method_overrides, class_info
        )

        # Check basic counts
        assert report["total_classes"] == 5
        assert report["abstract_classes"] == 1
        assert report["mixins"] == 1
        assert report["inheritance_relationships"] == 5
        assert report["method_overrides"] == 3

        # Check override statistics
        assert report["override_statistics"]["with_super_call"] == 1
        assert report["override_statistics"]["without_super_call"] == 2
        assert report["override_statistics"]["abstract_implementations"] == 1

        # Check multiple inheritance
        assert len(report["multiple_inheritance"]) == 1
        multi = report["multiple_inheritance"][0]
        assert multi["class"] == "module.MultiChild"
        assert multi["parent_count"] == 2

        # Check unresolved parents
        assert len(report["unresolved_parents"]) == 1
        unresolved = report["unresolved_parents"][0]
        assert unresolved["child"] == "module.UnresolvedChild"

        # Check inheritance depth
        assert 0 in report["inheritance_depth"]  # Parent and Mixin
        assert 1 in report["inheritance_depth"]  # Children
