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

        python_code = '''
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
'''

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check inheritance relationships
        assert len(inheritance_info) == 2

        # Check Dog inherits from Animal
        dog_inheritance = [i for i in inheritance_info if i.child_class == "test_module.Dog"][0]
        assert dog_inheritance.parent_class == "test_module.Animal"
        assert dog_inheritance.inheritance_type == "extends"

        # Check Cat inherits from Animal
        cat_inheritance = [i for i in inheritance_info if i.child_class == "test_module.Cat"][0]
        assert cat_inheritance.parent_class == "test_module.Animal"
        assert cat_inheritance.inheritance_type == "extends"

        # Check method overrides
        assert len(method_overrides) >= 2  # Both Dog and Cat override speak

        # Check class info
        assert len(class_info) == 3
        animal_info = [c for c in class_info if c.name == "Animal"][0]
        assert "speak" in animal_info.methods

    def test_python_multiple_inheritance(self, parsers_and_queries):
        """Test Python multiple inheritance."""
        parsers, queries = parsers_and_queries

        python_code = '''
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
'''

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check Duck inherits from both Flyable and Swimmable
        duck_inheritances = [i for i in inheritance_info if i.child_class == "test_module.Duck"]
        assert len(duck_inheritances) == 2

        parent_classes = {i.parent_class for i in duck_inheritances}
        assert "test_module.Flyable" in parent_classes
        assert "test_module.Swimmable" in parent_classes

        # Check method overrides
        overrides = [o for o in method_overrides if o.child_method.startswith("test_module.Duck")]
        assert len(overrides) >= 2  # fly and swim

    def test_python_abstract_classes(self, parsers_and_queries):
        """Test Python abstract classes and methods."""
        parsers, queries = parsers_and_queries

        python_code = '''
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
'''

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check Shape is marked as abstract
        shape_info = [c for c in class_info if c.name == "Shape"][0]
        assert shape_info.is_abstract

        # Check Rectangle inherits from Shape
        rect_inheritance = [i for i in inheritance_info if i.child_class == "test_module.Rectangle"][0]
        assert "Shape" in rect_inheritance.parent_class  # May be abc.ABC.Shape or similar

        # Check abstract method implementations
        overrides = [o for o in method_overrides if o.child_method.startswith("test_module.Rectangle")]
        assert len(overrides) >= 2  # area and perimeter

    def test_python_metaclass(self, parsers_and_queries):
        """Test Python metaclass detection."""
        parsers, queries = parsers_and_queries

        python_code = '''
class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

class Singleton(metaclass=SingletonMeta):
    def __init__(self):
        self.value = None
'''

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check Singleton has SingletonMeta as metaclass
        singleton_metaclass = [i for i in inheritance_info if i.child_class == "test_module.Singleton" and i.inheritance_type == "metaclass"]
        assert len(singleton_metaclass) == 1
        assert singleton_metaclass[0].parent_class == "test_module.SingletonMeta"

        # Check class info
        singleton_info = [c for c in class_info if c.name == "Singleton"][0]
        assert singleton_info.metaclass == "test_module.SingletonMeta"

    def test_python_mixin_pattern(self, parsers_and_queries):
        """Test Python mixin pattern detection."""
        parsers, queries = parsers_and_queries

        python_code = '''
class LoggerMixin:
    def log(self, message):
        print(f"[{self.__class__.__name__}] {message}")

class TimestampMixin:
    def get_timestamp(self):
        import time
        return time.time()

class MyClass(LoggerMixin, TimestampMixin):
    def do_something(self):
        self.log("Doing something")
        return self.get_timestamp()
'''

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check MyClass inherits from both mixins
        myclass_inheritances = [i for i in inheritance_info if i.child_class == "test_module.MyClass"]
        assert len(myclass_inheritances) == 2

        # Check mixin detection (based on naming convention)
        logger_info = [c for c in class_info if c.name == "LoggerMixin"][0]
        assert logger_info.is_mixin  # Should detect based on "Mixin" suffix

    def test_python_builtin_inheritance(self, parsers_and_queries):
        """Test Python built-in class inheritance."""
        parsers, queries = parsers_and_queries

        python_code = '''
class MyError(Exception):
    pass

class MyDict(dict):
    def __setitem__(self, key, value):
        print(f"Setting {key} = {value}")
        super().__setitem__(key, value)

class MyList(list):
    def append(self, item):
        print(f"Appending {item}")
        super().append(item)
'''

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check built-in inheritance
        error_inheritance = [i for i in inheritance_info if i.child_class == "test_module.MyError"][0]
        assert error_inheritance.parent_class == "builtins.Exception"

        dict_inheritance = [i for i in inheritance_info if i.child_class == "test_module.MyDict"][0]
        assert dict_inheritance.parent_class == "builtins.dict"

        # Check method overrides with super calls
        setitem_override = [o for o in method_overrides if o.child_method == "test_module.MyDict.__setitem__"][0]
        assert setitem_override.has_super_call

        append_override = [o for o in method_overrides if o.child_method == "test_module.MyList.append"][0]
        assert append_override.has_super_call

    def test_python_import_resolution(self, parsers_and_queries):
        """Test Python import resolution for inheritance."""
        parsers, queries = parsers_and_queries

        python_code = '''
from collections import OrderedDict
from typing import List
import unittest

class MyOrderedDict(OrderedDict):
    pass

class MyTestCase(unittest.TestCase):
    def test_something(self):
        self.assertEqual(1, 1)
'''

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check imported class inheritance resolution
        ordered_dict_inheritance = [i for i in inheritance_info if i.child_class == "test_module.MyOrderedDict"][0]
        assert ordered_dict_inheritance.parent_class == "collections.OrderedDict"
        assert ordered_dict_inheritance.is_resolved

        testcase_inheritance = [i for i in inheritance_info if i.child_class == "test_module.MyTestCase"][0]
        assert testcase_inheritance.parent_class == "unittest.TestCase"
        assert testcase_inheritance.is_resolved

    def test_javascript_class_inheritance(self, parsers_and_queries):
        """Test JavaScript ES6 class inheritance."""
        parsers, queries = parsers_and_queries

        if "javascript" not in parsers:
            pytest.skip("JavaScript parser not available")

        js_code = '''
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
'''

        analyzer = InheritanceAnalyzer(parsers["javascript"], queries["javascript"], "javascript")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.js", js_code, "test_module")

        # Check inheritance
        assert len(inheritance_info) >= 1
        dog_inheritance = [i for i in inheritance_info if i.child_class == "test_module.Dog"][0]
        assert dog_inheritance.parent_class == "Animal"  # Not fully qualified in JS
        assert dog_inheritance.inheritance_type == "extends"

    def test_class_attributes_extraction(self, parsers_and_queries):
        """Test extraction of class attributes."""
        parsers, queries = parsers_and_queries

        python_code = '''
class Person:
    def __init__(self, name, age):
        self.name = name
        self.age = age
        self._private = "private"

    def set_email(self, email):
        self.email = email

    def update_info(self):
        self.last_updated = "today"
'''

        analyzer = InheritanceAnalyzer(parsers["python"], queries["python"], "python")
        inheritance_info, method_overrides, class_info = analyzer.analyze_file("test.py", python_code, "test_module")

        # Check class attributes were extracted
        person_info = [c for c in class_info if c.name == "Person"][0]
        assert "name" in person_info.attributes
        assert "age" in person_info.attributes
        assert "_private" in person_info.attributes
        assert "email" in person_info.attributes
        assert "last_updated" in person_info.attributes
