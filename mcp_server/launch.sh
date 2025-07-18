#!/bin/bash
# Launch script for Graph-Code RAG MCP Server

# Set default environment variables if not already set
export MEMGRAPH_HOST=${MEMGRAPH_HOST:-localhost}
export MEMGRAPH_PORT=${MEMGRAPH_PORT:-7687}

# Check if Memgraph is running
echo "Checking Memgraph connection..."
nc -z $MEMGRAPH_HOST $MEMGRAPH_PORT
if [ $? -ne 0 ]; then
    echo "Error: Memgraph is not running on $MEMGRAPH_HOST:$MEMGRAPH_PORT"
    echo "Please start Memgraph with: docker-compose up -d"
    exit 1
fi

echo "Starting Graph-Code RAG MCP Server..."
echo "Memgraph: $MEMGRAPH_HOST:$MEMGRAPH_PORT"
echo "----------------------------------------"

# Launch the server
python -m mcp_server.server
