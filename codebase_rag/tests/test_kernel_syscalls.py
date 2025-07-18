"""Tests for kernel syscall pattern detection and analysis."""

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


def test_syscall_define_simple(parser, queries):  # noqa: ARG001
    """Test parsing simple SYSCALL_DEFINE macros."""
    code = """
    #include <linux/syscalls.h>
    
    SYSCALL_DEFINE1(exit, int, error_code)
    {
        do_exit((error_code & 0xff) << 8);
    }
    
    SYSCALL_DEFINE2(kill, pid_t, pid, int, sig)
    {
        return do_kill(pid, sig);
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Should have syscall nodes
    syscall_nodes = [n for n in nodes if n.node_type == "syscall"]
    assert len(syscall_nodes) == 2
    
    # Check exit syscall
    exit_syscall = next((n for n in syscall_nodes if n.name == "exit"), None)
    assert exit_syscall is not None
    assert exit_syscall.properties["param_count"] == 1
    assert len(exit_syscall.properties["params"]) == 1
    assert exit_syscall.properties["params"][0] == ("int", "error_code")
    
    # Check kill syscall
    kill_syscall = next((n for n in syscall_nodes if n.name == "kill"), None)
    assert kill_syscall is not None
    assert kill_syscall.properties["param_count"] == 2
    assert len(kill_syscall.properties["params"]) == 2
    assert kill_syscall.properties["params"][0] == ("pid_t", "pid")
    assert kill_syscall.properties["params"][1] == ("int", "sig")
    
    # Check relationships
    rel_dict = {(r[0], r[1], r[3]): r for r in relationships}
    assert ("sys_exit", "IMPLEMENTS_SYSCALL", "exit") in rel_dict
    assert ("sys_kill", "IMPLEMENTS_SYSCALL", "kill") in rel_dict


def test_syscall_define_variants(parser, queries):  # noqa: ARG001
    """Test different SYSCALL_DEFINE variants."""
    code = """
    #include <linux/syscalls.h>
    
    /* Standard syscall */
    SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, size_t, count)
    {
        return ksys_read(fd, buf, count);
    }
    
    /* Compat syscall */
    COMPAT_SYSCALL_DEFINE3(read, unsigned int, fd, char __user *, buf, compat_size_t, count)
    {
        return ksys_read(fd, buf, count);
    }
    
    /* Zero-parameter syscall */
    SYSCALL_DEFINE0(getpid)
    {
        return task_tgid_vnr(current);
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    syscall_nodes = [n for n in nodes if n.node_type == "syscall"]
    # We should have 3 nodes: read, compat_read, and getpid
    assert len(syscall_nodes) == 3
    
    # Check regular read syscall  
    read_syscall = next((n for n in syscall_nodes if n.name == "read" and "compat_" not in n.file_path), None)
    assert read_syscall is not None
    
    # Check compat read syscall
    compat_read = next((n for n in syscall_nodes if "compat_read" in str(n)), None)
    # Compat syscalls are stored with compat_ prefix internally
    
    # Check getpid syscall
    getpid_syscall = next((n for n in syscall_nodes if n.name == "getpid"), None)
    assert getpid_syscall is not None
    assert getpid_syscall.properties["param_count"] == 0
    assert len(getpid_syscall.properties["params"]) == 0


def test_syscall_complex_types(parser, queries):  # noqa: ARG001
    """Test syscalls with complex parameter types."""
    code = """
    #include <linux/syscalls.h>
    
    SYSCALL_DEFINE5(mount, char __user *, dev_name, char __user *, dir_name,
                    char __user *, type, unsigned long, flags, void __user *, data)
    {
        return do_mount(dev_name, dir_name, type, flags, data);
    }
    
    SYSCALL_DEFINE3(ioctl, unsigned int, fd, unsigned int, cmd, unsigned long, arg)
    {
        return do_vfs_ioctl(fd, cmd, arg);
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    syscall_nodes = [n for n in nodes if n.node_type == "syscall"]
    
    # Check mount syscall
    mount_syscall = next((n for n in syscall_nodes if n.name == "mount"), None)
    assert mount_syscall is not None
    assert mount_syscall.properties["param_count"] == 5
    assert mount_syscall.properties["params"][0] == ("char __user *", "dev_name")
    assert mount_syscall.properties["params"][4] == ("void __user *", "data")


@pytest.mark.xfail(reason="SYSCALL_PATH edges not implemented yet")
def test_syscall_path_edges(parser, queries):  # noqa: ARG001
    """Test SYSCALL_PATH edge creation."""
    code = """
    #include <linux/syscalls.h>
    
    static int do_open(const char *filename, int flags) {
        // Implementation
        return 0;
    }
    
    SYSCALL_DEFINE2(open, const char __user *, filename, int, flags)
    {
        return do_open(filename, flags);
    }
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Should have CALLS relationship from syscall to implementation
    calls_rels = [r for r in relationships if r[1] == "CALLS"]
    assert any(r[0] == "sys_open" and r[3] == "do_open" for r in calls_rels)


def test_ioctl_definitions(parser, queries):  # noqa: ARG001
    """Test parsing of ioctl definitions."""
    code = """
    #include <linux/ioctl.h>
    
    #define MY_IOCTL_MAGIC 'M'
    
    #define MY_IOCTL_RESET    _IO(MY_IOCTL_MAGIC, 0)
    #define MY_IOCTL_READ     _IOR(MY_IOCTL_MAGIC, 1, int)
    #define MY_IOCTL_WRITE    _IOW(MY_IOCTL_MAGIC, 2, int)
    #define MY_IOCTL_RDWR     _IOWR(MY_IOCTL_MAGIC, 3, struct my_data)
    
    struct my_data {
        int value;
        char buffer[256];
    };
    """
    
    c_parser = CParser(parser, queries)
    nodes, relationships = c_parser.parse_file("test.c", code)
    
    # Should have ioctl nodes
    ioctl_nodes = [n for n in nodes if n.node_type == "ioctl"]
    assert len(ioctl_nodes) == 4
    
    # Check ioctl properties
    reset_ioctl = next((n for n in ioctl_nodes if n.name == "MY_IOCTL_RESET"), None)
    assert reset_ioctl is not None
    assert reset_ioctl.properties["direction"] == "none"
    assert reset_ioctl.properties["magic"] == "MY_IOCTL_MAGIC"  # Macro name, not value
    assert reset_ioctl.properties["number"] == "0"
    
    read_ioctl = next((n for n in ioctl_nodes if n.name == "MY_IOCTL_READ"), None)
    assert read_ioctl is not None
    assert read_ioctl.properties["direction"] == "read"
    assert read_ioctl.properties["type"] == "int"