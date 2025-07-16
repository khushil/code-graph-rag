# Complete Setup Guide for Graph-Code RAG

This guide walks you through setting up Graph-Code RAG from scratch to a fully functional system.

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Prerequisites Installation](#prerequisites-installation)
3. [Project Setup](#project-setup)
4. [Database Setup](#database-setup)
5. [Environment Configuration](#environment-configuration)
6. [First Run](#first-run)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)
9. [Next Steps](#next-steps)

## System Requirements

### Minimum Requirements
- **CPU**: 4 cores (8+ cores recommended for parallel processing)
- **RAM**: 8GB (16GB+ recommended for large codebases)
- **Storage**: 10GB free space (more for large repos)
- **OS**: Linux, macOS, or Windows with WSL2

### Software Requirements
- Python 3.12 or higher
- Docker and Docker Compose
- Git
- Internet connection (for API access and dependencies)

## Prerequisites Installation

### Step 1: Install Python 3.12+

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev
```

**macOS (using Homebrew):**
```bash
brew install python@3.12
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) or use WSL2

### Step 2: Install UV Package Manager

UV is a fast Python package manager used by this project:

```bash
# Install using the official installer
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv

# Verify installation
uv --version
```

### Step 3: Install Docker

**Ubuntu/Debian:**
```bash
# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**macOS:**
Download and install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

**Windows:**
Install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) with WSL2 backend

### Step 4: Verify Prerequisites

```bash
# Check Python
python3.12 --version  # Should show 3.12.x

# Check UV
uv --version  # Should show uv version

# Check Docker
docker --version  # Should show Docker version
docker compose version  # Should show Docker Compose version
```

## Project Setup

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/vitali87/code-graph-rag.git
cd code-graph-rag

# Or if you're using a fork
git clone https://github.com/YOUR_USERNAME/code-graph-rag.git
cd code-graph-rag
```

### Step 2: Create Virtual Environment and Install Dependencies

```bash
# Let UV create and manage the virtual environment
uv venv

# Install with full language support (recommended)
uv sync --extra treesitter-full

# Or for development (includes test dependencies)
make dev
```

### Step 3: Verify Installation

```bash
# Activate virtual environment (UV does this automatically)
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate  # On Windows

# Test the installation
python -m codebase_rag.main --help
```

## Database Setup

### Step 1: Start Memgraph Database

```bash
# Start Memgraph using Docker Compose
docker compose up -d

# Verify it's running
docker compose ps

# You should see:
# - memgraph running on port 7687
# - memgraph-lab running on port 3000
```

### Step 2: Verify Database Connection

```bash
# Check logs
docker compose logs memgraph

# Test connection (optional)
docker exec -it memgraph mgconsole
# Type: MATCH (n) RETURN count(n);
# Should return 0
# Type: :quit to exit
```

### Step 3: Access Memgraph Lab (Optional)

Open your browser and go to:
- URL: http://localhost:3000
- Connect to: `memgraph:7687`
- No authentication required by default

## Environment Configuration

### Step 1: Create Environment File

```bash
# Copy the example environment file
cp .env.example .env
```

### Step 2: Configure AI Provider

Edit `.env` file and configure one or more AI providers:

#### Option A: Google Gemini (Recommended for best results)
```bash
# Get free API key from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL_ID=gemini-2.5-pro
MODEL_CYPHER_ID=gemini-2.5-flash-lite-preview-06-17
```

#### Option B: OpenAI
```bash
# Get API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ORCHESTRATOR_MODEL_ID=gpt-4o-mini
OPENAI_CYPHER_MODEL_ID=gpt-4o-mini
```

#### Option C: Anthropic Claude
```bash
# Get API key from: https://console.anthropic.com/
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_ORCHESTRATOR_MODEL_ID=claude-3-5-sonnet-20241022
ANTHROPIC_CYPHER_MODEL_ID=claude-3-5-haiku-20241022
```

#### Option D: Local Models with Ollama
```bash
# First, install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull llama3

# Configure in .env
LOCAL_MODEL_ENDPOINT=http://localhost:11434/v1
LOCAL_ORCHESTRATOR_MODEL_ID=llama3
LOCAL_CYPHER_MODEL_ID=llama3
LOCAL_MODEL_API_KEY=ollama
```

### Step 3: Verify Configuration

```bash
# Check environment variables are loaded
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('API Key configured:', bool(os.getenv('GEMINI_API_KEY') or os.getenv('OPENAI_API_KEY') or os.getenv('LOCAL_MODEL_ENDPOINT')))"
```

## First Run

### Step 1: Prepare a Test Repository

```bash
# Option 1: Use the current repository
export TEST_REPO_PATH=$(pwd)

# Option 2: Clone a sample repository
git clone https://github.com/pallets/flask.git /tmp/flask-test
export TEST_REPO_PATH=/tmp/flask-test
```

### Step 2: Ingest Your First Repository

```bash
# Basic ingestion
python -m codebase_rag.main start \
  --repo-path $TEST_REPO_PATH \
  --update-graph \
  --clean

# With progress monitoring (for larger repos)
python -m codebase_rag.main start \
  --repo-path $TEST_REPO_PATH \
  --update-graph \
  --clean \
  --parallel
```

### Step 3: Start Interactive Mode

```bash
# Start the RAG CLI
python -m codebase_rag.main start --repo-path $TEST_REPO_PATH

# You should see:
# "Welcome to the Codebase RAG CLI!..."
```

### Step 4: Try Your First Queries

In the interactive prompt, try:
```
> What functions are defined in this codebase?
> Show me all classes that contain 'user' in their name
> Find the main entry point of the application
> What test files exist in this project?
```

## Verification

### Step 1: Check Database Content

```bash
# Export graph to verify ingestion
python -m codebase_rag.main export -o test_graph.json

# Analyze the export
python examples/graph_export_example.py test_graph.json
```

### Step 2: Test Parallel Processing

```bash
# Re-ingest with parallel processing
python -m codebase_rag.main start \
  --repo-path $TEST_REPO_PATH \
  --update-graph \
  --clean \
  --parallel \
  --workers 4
```

### Step 3: Test C Language Support (if applicable)

```bash
# If you have a C project
git clone https://github.com/torvalds/linux.git /tmp/linux-sample --depth=1
python -m codebase_rag.main start \
  --repo-path /tmp/linux-sample \
  --update-graph \
  --clean \
  --parallel \
  --folder-filter "init,kernel/sched"
```

## Troubleshooting

### Common Issues and Solutions

#### 1. **Import Errors / Module Not Found**
```bash
# Ensure you're in the virtual environment
source .venv/bin/activate

# Reinstall dependencies
uv sync --extra treesitter-full
```

#### 2. **Memgraph Connection Refused**
```bash
# Check if Memgraph is running
docker compose ps

# Restart Memgraph
docker compose down
docker compose up -d

# Check logs
docker compose logs memgraph
```

#### 3. **API Key Errors**
```bash
# Verify .env file exists and has correct keys
cat .env | grep -E "API_KEY|MODEL_ID"

# Test API key (for Gemini)
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('Key starts with:', os.getenv('GEMINI_API_KEY', 'NOT SET')[:10] + '...')"
```

#### 4. **Out of Memory During Processing**
```bash
# Use fewer workers
python -m codebase_rag.main start \
  --repo-path $TEST_REPO_PATH \
  --update-graph \
  --parallel \
  --workers 2

# Or process specific folders
python -m codebase_rag.main start \
  --repo-path $TEST_REPO_PATH \
  --update-graph \
  --folder-filter "src,lib"
```

#### 5. **Tree-sitter Build Errors**
```bash
# Install build dependencies
# Ubuntu/Debian:
sudo apt install build-essential

# macOS:
xcode-select --install

# Reinstall tree-sitter packages
uv pip install --force-reinstall tree-sitter tree-sitter-c==0.21.3
```

### Getting Help

1. **Check Logs:**
   ```bash
   # Application logs are shown in terminal
   # Database logs:
   docker compose logs memgraph
   ```

2. **Enable Debug Mode:**
   ```bash
   export LOGURU_LEVEL=DEBUG
   python -m codebase_rag.main start --repo-path $TEST_REPO_PATH
   ```

3. **Community Support:**
   - Open an issue on [GitHub](https://github.com/vitali87/code-graph-rag/issues)
   - Include error messages and steps to reproduce

## Next Steps

### 1. Process Your Own Codebase
```bash
python -m codebase_rag.main start \
  --repo-path /path/to/your/project \
  --update-graph \
  --clean \
  --parallel
```

### 2. Explore Advanced Features
- Try code optimization: `python -m codebase_rag.main optimize python --repo-path /path/to/project`
- Export and analyze graphs: `python -m codebase_rag.main export -o my_analysis.json`
- Run example scripts in the `examples/` directory

### 3. Configure for Production
- Set up proper API key management
- Configure memory limits for large codebases
- Set up monitoring for long-running ingestions

### 4. Integrate with Your Workflow
- Add to CI/CD pipelines
- Create custom analysis scripts
- Build dashboards using exported graph data

## Performance Tips

### For Large Codebases (>100K LOC)
1. **Start with parallel processing:**
   ```bash
   --parallel --workers 16
   ```

2. **Process incrementally:**
   ```bash
   # Process core modules first
   --folder-filter "core,lib"
   
   # Then add other modules
   --folder-filter "tests,docs"
   ```

3. **Skip non-essential files:**
   ```bash
   --skip-tests  # During initial analysis
   ```

### For C/Kernel Code
1. **Use subsystem filtering:**
   ```bash
   --folder-filter "drivers/net,drivers/usb"
   ```

2. **Increase workers for header-heavy code:**
   ```bash
   --parallel --workers 32
   ```

### Memory Optimization
1. **Monitor system resources:**
   ```bash
   # In another terminal
   htop  # or top
   ```

2. **Adjust worker count based on RAM:**
   - 8GB RAM: 2-4 workers
   - 16GB RAM: 4-8 workers
   - 32GB+ RAM: 8-16 workers

## Congratulations! 🎉

You now have a fully functional Graph-Code RAG system. Start exploring your codebase with natural language queries and leverage the power of knowledge graphs for code understanding!

For more information:
- See [README.md](README.md) for feature overview
- Check [CHANGELOG.md](CHANGELOG.md) for latest updates
- Read [CONTRIBUTING.md](CONTRIBUTING.md) to contribute