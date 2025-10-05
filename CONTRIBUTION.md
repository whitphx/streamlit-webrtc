# Contributing to streamlit-webrtc

Thank you for your interest in contributing to streamlit-webrtc! This guide will help you set up your development environment and understand our contribution process.

## Overview

streamlit-webrtc is a Python library that enables real-time video and audio processing in Streamlit applications using WebRTC technology. The project consists of:

- **Backend (Python)**: Core WebRTC functionality and Streamlit integration
- **Frontend (TypeScript/React)**: WebRTC UI components and browser-side processing
- **Examples**: Demonstration applications showcasing various features

## Prerequisites

### Required Software

- **Python 3.9 or higher** (Python 3.9.7 is excluded due to compatibility issues)
- **Node.js 18 or higher** (for frontend development)
- **Git** for version control

### Platform-Specific Requirements

#### Windows

```bash
# Install Python from https://python.org or use Windows Package Manager
winget install Python.Python.3.11

# Install Node.js from https://nodejs.org or use chocolatey
choco install nodejs

# Install Git
winget install Git.Git
```

#### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install Python 3.9+
sudo apt install python3.11 python3.11-venv python3-pip

# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Install Git
sudo apt install git

# Install build essentials for Python packages
sudo apt install build-essential
```

#### Linux (CentOS/RHEL/Fedora)

```bash
# Install Python 3.9+
sudo dnf install python3.11 python3-pip

# Install Node.js 18+
sudo dnf install nodejs npm

# Install Git
sudo dnf install git

# Install development tools
sudo dnf groupinstall "Development Tools"
```

## Development Setup

### 1. Fork and Clone the Repository

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/streamlit-webrtc.git
cd streamlit-webrtc

# Add the upstream repository
git remote add upstream https://github.com/whitphx/streamlit-webrtc.git
```

### 2. Install uv Package Manager

uv is the modern Python package manager used by this project:

```bash
# On Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# On Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### 3. Set Up Python Environment

```bash
# Install Python dependencies
uv sync

# Install development dependencies (includes testing and linting tools)
uv sync --dev

# Install pre-commit hooks for code quality
uv run pre-commit install
```

### 4. Set Up Frontend Environment

```bash
# Navigate to frontend directory
cd streamlit_webrtc/frontend

# Install pnpm if not already available
npm install -g pnpm

# Install frontend dependencies
pnpm install

# Return to project root
cd ../..
```

## Development Workflow

### Running the Application

#### For Frontend Development

1. **Enable Development Mode**

   ```bash
   # Edit streamlit_webrtc/component.py
   # Set _RELEASE = False (IMPORTANT: Do not commit this change)
   ```

2. **Start Frontend Development Server**

   ```bash
   cd streamlit_webrtc/frontend
   pnpm dev
   ```

3. **Start Streamlit Application** (in a new terminal)
   ```bash
   uv run streamlit run home.py
   ```

The application will be available at http://localhost:8501

#### For Backend-Only Development

```bash
# Ensure _RELEASE = True in streamlit_webrtc/component.py
uv run streamlit run home.py
```

### Building the Project

#### Build Frontend

```bash
cd streamlit_webrtc/frontend
pnpm run build
```

#### Build Complete Package

```bash
# This builds both frontend and Python package
make build
```

## Code Quality and Testing

### Running Tests

#### Python Tests

```bash
# Run all Python tests
uv run pytest

# Run specific test file
uv run pytest tests/test_specific.py

# Run with coverage
uv run pytest --cov=streamlit_webrtc
```

#### Frontend Tests

```bash
cd streamlit_webrtc/frontend

# Run tests once
pnpm test

# Run tests in watch mode
pnpm test --watch

# Run tests with coverage
pnpm test --coverage
```

### Code Formatting and Linting

#### Backend (Python)

```bash
# Format Python code with ruff
uv run ruff format .

# Check and fix linting issues
uv run ruff check . --fix

# Type checking with mypy
uv run mypy .

# Format all backend code (shortcut)
make format/backend
```

#### Frontend (TypeScript/React)

```bash
cd streamlit_webrtc/frontend

# Format code with prettier and eslint
pnpm format

# Check formatting
pnpm lint

# Format all frontend code (shortcut from root)
make format/frontend
```

#### Format Everything

```bash
# Format both backend and frontend
make format
```

### Pre-commit Hooks

Pre-commit hooks run automatically on each commit to ensure code quality:

```bash
# Install hooks (if not done during setup)
uv run pre-commit install

# Run hooks manually on all files
uv run pre-commit run --all-files

# Skip hooks for a specific commit (use sparingly)
git commit --no-verify -m "Your commit message"
```

## Project Structure

```
streamlit-webrtc/
├── streamlit_webrtc/           # Main Python package
│   ├── __init__.py            # Package initialization
│   ├── component.py           # Main Streamlit component
│   ├── webrtc.py             # WebRTC core functionality
│   ├── config.py             # Configuration handling
│   ├── credentials.py        # STUN/TURN server management
│   └── frontend/             # React/TypeScript frontend
│       ├── src/              # Frontend source code
│       ├── package.json      # Node.js dependencies
│       └── dist/             # Built frontend assets
├── pages/                    # Example applications
├── tests/                    # Python test suite
├── docs/                     # Documentation
├── scripts/                  # Build and utility scripts
├── pyproject.toml           # Python project configuration
├── Makefile                 # Build automation
└── DEVELOPMENT.md           # Development guidelines
```

## Making Changes

### Creating a Feature Branch

```bash
# Update your fork
git checkout main
git pull upstream main

# Create a new feature branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/issue-description
```

### Implementing Changes

1. **Make your changes** following the coding standards
2. **Add tests** for new functionality
3. **Update documentation** if needed
4. **Test your changes** thoroughly

### Example Development Workflow

```bash
# 1. Make changes to Python code
# Edit streamlit_webrtc/component.py or other files

# 2. Test changes
uv run pytest tests/

# 3. Format code
make format/backend

# 4. If making frontend changes
cd streamlit_webrtc/frontend
# Edit src/ files
pnpm test
pnpm format
pnpm run build

# 5. Test the complete application
cd ../..
uv run streamlit run home.py
```

### Testing Your Changes

#### Manual Testing

1. Run the example applications in `pages/`
2. Test camera and microphone functionality
3. Verify WebRTC connections work properly
4. Test on different browsers if possible

#### Automated Testing

```bash
# Run full test suite
uv run pytest
cd streamlit_webrtc/frontend && pnpm test

# Test with different Python versions (if available)
uv run --python 3.9 pytest
uv run --python 3.11 pytest
```

## Submitting Changes

### Commit Guidelines

Follow conventional commit format:

```bash
# Feature commits
git commit -m "feat: add new video filter functionality"

# Bug fix commits
git commit -m "fix: resolve camera permission issue on Firefox"

# Documentation commits
git commit -m "docs: update installation instructions"

# Refactoring commits
git commit -m "refactor: simplify WebRTC connection logic"
```

### Pull Request Process

1. **Push your branch**

   ```bash
   git push origin feature/your-feature-name
   ```

2. **Create Pull Request** on GitHub with:

   - Clear title and description
   - Reference any related issues
   - Include screenshots/videos for UI changes
   - List breaking changes if any

3. **Address Review Feedback**

   - Make requested changes
   - Push updates to your branch
   - Respond to reviewer comments

4. **CI/CD Checks**
   - Ensure all tests pass
   - Verify formatting is correct
   - Check that the build succeeds

## Getting Help

- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share ideas
- **Documentation**: Check docs/ directory and README.md
- **Examples**: Look at pages/ for usage patterns

## Contributing Guidelines

### What We Welcome

- Bug fixes and improvements
- New WebRTC features and capabilities
- Documentation improvements
- Example applications
- Performance optimizations
- Cross-platform compatibility fixes

### What We Don't Accept

- Breaking changes without discussion
- Features that significantly increase bundle size
- Code without tests
- Changes that break existing functionality
- Non-inclusive language or behavior

Thank you for contributing to streamlit-webrtc! ❤️ Your contributions help make real-time video and audio processing accessible to the Streamlit community.
