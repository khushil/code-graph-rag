"""Tests for kernel concurrency primitive detection and analysis."""

import pytest

from codebase_rag.parser_loader import load_parsers
from codebase_rag.parsers.c_parser import CParser


@pytest.fixture
def parser_and_queries():
    """Create a C parser and queries."""
    parsers, queries = load_parsers()
    return parsers["c"], queries["c"]


@pytest.fixture
def parser(parser_and_queries):
    """Get just the parser."""
    return parser_and_queries[0]


@pytest.fixture
def queries(parser_and_queries):
    """Get just the queries."""
    return parser_and_queries[1]


def test_spinlock_detection(parser, queries):  # noqa: ARG001
    """Test detection of spinlock definitions and operations."""
    code = """
    #include <linux/spinlock.h>
    
    static DEFINE_SPINLOCK(my_lock);
    spinlock_t another_lock;
    
    void critical_function(void) {
        unsigned long flags;
        
        spin_lock_init(&another_lock);
        
        spin_lock_irqsave(&my_lock, flags);
        /* Critical section */
        spin_unlock_irqrestore(&my_lock, flags);
        
        spin_lock(&another_lock);
        /* Another critical section */
        spin_unlock(&another_lock);
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Should have concurrency primitive nodes
    lock_nodes = [n for n in nodes if n.node_type == "concurrency_primitive"]
    assert len(lock_nodes) >= 2  # my_lock and another_lock
    
    # Check spinlock properties
    my_lock = next((n for n in lock_nodes if n.name == "my_lock"), None)
    assert my_lock is not None
    assert my_lock.properties["primitive_type"] == "spinlock"
    assert my_lock.properties["is_static"] is True
    
    # Check LOCKS/UNLOCKS relationships
    lock_rels = [r for r in relationships if r[1] in ["LOCKS", "UNLOCKS"]]
    assert len(lock_rels) >= 4  # Two lock and two unlock operations
    
    # Verify lock operations
    assert any(r[0] == "critical_function" and r[1] == "LOCKS" and r[3] == "my_lock" for r in lock_rels)
    assert any(r[0] == "critical_function" and r[1] == "UNLOCKS" and r[3] == "my_lock" for r in lock_rels)


def test_mutex_detection(parser, queries):  # noqa: ARG001
    """Test detection of mutex definitions and operations."""
    code = """
    #include <linux/mutex.h>
    
    static DEFINE_MUTEX(my_mutex);
    struct mutex dynamic_mutex;
    
    int protected_operation(void) {
        int ret = 0;
        
        mutex_init(&dynamic_mutex);
        
        if (mutex_lock_interruptible(&my_mutex))
            return -EINTR;
            
        /* Protected code */
        ret = do_something();
        
        mutex_unlock(&my_mutex);
        
        mutex_lock(&dynamic_mutex);
        /* More protected code */
        mutex_unlock(&dynamic_mutex);
        
        return ret;
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Should have mutex nodes
    mutex_nodes = [n for n in nodes if n.node_type == "concurrency_primitive" 
                   and n.properties["primitive_type"] == "mutex"]
    assert len(mutex_nodes) >= 2
    
    # Check mutex properties
    my_mutex = next((n for n in nodes if n.node_type == "concurrency_primitive" and n.name == "my_mutex"), None)
    assert my_mutex is not None
    assert my_mutex.properties["primitive_type"] == "mutex"
    
    # Check lock/unlock relationships
    lock_rels = [r for r in relationships if r[1] in ["LOCKS", "UNLOCKS"]]
    assert any(r[0] == "protected_operation" and r[1] == "LOCKS" and r[3] == "my_mutex" for r in lock_rels)


def test_rwlock_detection(parser, queries):  # noqa: ARG001
    """Test detection of read-write lock operations."""
    code = """
    #include <linux/rwlock.h>
    
    static DEFINE_RWLOCK(data_lock);
    
    void reader_function(void) {
        read_lock(&data_lock);
        /* Read data */
        read_unlock(&data_lock);
    }
    
    void writer_function(void) {
        write_lock(&data_lock);
        /* Modify data */
        write_unlock(&data_lock);
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Check rwlock node
    data_lock = next((n for n in nodes if n.node_type == "concurrency_primitive" and n.name == "data_lock"), None)
    assert data_lock is not None
    assert data_lock.properties["primitive_type"] == "rwlock"
    
    # Check read/write lock operations
    lock_rels = [r for r in relationships if r[1] in ["LOCKS", "UNLOCKS"]]
    
    # Should have both read and write operations
    assert any(r[0] == "reader_function" and r[1] == "LOCKS" for r in lock_rels)
    assert any(r[0] == "writer_function" and r[1] == "LOCKS" for r in lock_rels)


def test_critical_section_tracking(parser, queries):  # noqa: ARG001
    """Test tracking of critical sections between lock/unlock pairs."""
    code = """
    #include <linux/spinlock.h>
    
    spinlock_t lock;
    int shared_data = 0;
    
    void update_data(int value) {
        spin_lock(&lock);
        shared_data = value;  /* Critical section */
        if (value > 100) {
            shared_data *= 2;
        }
        spin_unlock(&lock);
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Check for critical section information
    lock_ops = [(r[0], r[1], r[3]) for r in relationships if r[1] in ["LOCKS", "UNLOCKS"]]
    
    # Should have matching lock/unlock pairs
    locks = [op for op in lock_ops if op[1] == "LOCKS"]
    unlocks = [op for op in lock_ops if op[1] == "UNLOCKS"]
    
    assert len(locks) == 1
    assert len(unlocks) == 1
    assert locks[0][2] == unlocks[0][2]  # Same lock


def test_nested_locks(parser, queries):  # noqa: ARG001
    """Test detection of nested lock acquisitions."""
    code = """
    #include <linux/spinlock.h>
    #include <linux/mutex.h>
    
    spinlock_t outer_lock;
    struct mutex inner_mutex;
    
    void nested_locks_function(void) {
        spin_lock(&outer_lock);
        
        mutex_lock(&inner_mutex);
        /* Nested critical section */
        mutex_unlock(&inner_mutex);
        
        spin_unlock(&outer_lock);
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Check lock operations are in correct order
    lock_rels = [(r[1], r[3]) for r in relationships 
                 if r[0] == "nested_locks_function" and r[1] in ["LOCKS", "UNLOCKS"]]
    
    # Verify nesting order
    assert len(lock_rels) == 4
    assert lock_rels[0] == ("LOCKS", "outer_lock")
    assert lock_rels[1] == ("LOCKS", "inner_mutex")
    assert lock_rels[2] == ("UNLOCKS", "inner_mutex")
    assert lock_rels[3] == ("UNLOCKS", "outer_lock")


def test_trylock_operations(parser, queries):  # noqa: ARG001
    """Test detection of trylock operations."""
    code = """
    #include <linux/spinlock.h>
    #include <linux/mutex.h>
    
    spinlock_t slock;
    struct mutex mlock;
    
    int try_operations(void) {
        if (spin_trylock(&slock)) {
            /* Got spinlock */
            spin_unlock(&slock);
            return 1;
        }
        
        if (mutex_trylock(&mlock)) {
            /* Got mutex */
            mutex_unlock(&mlock);
            return 2;
        }
        
        return 0;
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Check for trylock operations
    trylock_rels = [r for r in relationships if r[1] == "TRIES_LOCK"]
    assert len(trylock_rels) >= 2
    
    # Verify trylock targets
    assert any(r[3] == "slock" for r in trylock_rels)
    assert any(r[3] == "mlock" for r in trylock_rels)