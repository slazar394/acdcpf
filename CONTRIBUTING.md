# 🤝 Contributing to ACDCPF

First off, thank you for considering contributing to ACDCPF! 🎉 It's people like you that make ACDCPF such a great tool. Every contribution, no matter how small, is valued and appreciated! 💖

## 📋 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [How Can I Contribute?](#-how-can-i-contribute)
- [Getting Started](#-getting-started)
- [Development Setup](#-development-setup)
- [Pull Request Process](#-pull-request-process)
- [Style Guidelines](#-style-guidelines)
- [Community](#-community)

## 📜 Code of Conduct

This project and everyone participating in it is governed by our commitment to providing a welcoming and inclusive experience for everyone. Please be respectful and constructive in all interactions. 🙏

## 💡 How Can I Contribute?

### 🐛 Reporting Bugs

- Ensure the bug was not already reported by searching on GitHub under [Issues](https://github.com/slazar394/acdcpf/issues)
- If you're unable to find an open issue addressing the problem, [open a new one](https://github.com/slazar394/acdcpf/issues/new)
- Include a **clear title and description**, as much relevant information as possible, and a **code sample** demonstrating the expected behavior that is not occurring

### ✨ Suggesting Enhancements

- Open a new issue with a clear title and detailed description
- Explain **why** this enhancement would be useful to most ACDCPF users
- Provide code examples if applicable

### 🔧 Pull Requests

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Git

### Development Setup

1. **Fork and clone the repository:**

```bash
git clone https://github.com/your-username/acdcpf.git
cd acdcpf
```

2. **Create a virtual environment:**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**

```bash
pip install -e ".[dev]"
```

4. **Run the tests to make sure everything is working:**

```bash
pytest tests/
```

5. **Run the linter to check code quality:**

```bash
flake8 acdcpf/
black --check acdcpf/
```

## 📝 Pull Request Process

1. Update the README.md with details of changes to the interface, if applicable
2. Update the documentation with any new features or changes
3. Ensure all tests pass by running `pytest tests/`
4. Ensure code quality by running the linter
5. The PR will be merged once you have the sign-off of at least one maintainer

### PR Title Convention

Please use the following format for PR titles:

- `feat: Add new feature` for new features
- `fix: Fix bug description` for bug fixes
- `docs: Update documentation` for documentation changes
- `refactor: Refactor code description` for code refactoring
- `test: Add tests for feature` for adding tests
- `chore: Update dependencies` for maintenance tasks

## 🎨 Style Guidelines

### Python Style Guide

- Follow [PEP 8](https://pep8.org/) coding standards
- Use meaningful variable and function names
- Add docstrings to all public functions and classes
- Keep functions small and focused on a single task
- Use type hints where possible

### Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

### Documentation

- Write clear, concise documentation
- Include code examples where appropriate
- Keep documentation up-to-date with code changes

## 🌟 Community

- ⭐ Star the project on GitHub if you find it useful
- 🐛 Report bugs and suggest features through GitHub Issues
- 💬 Join discussions in the Issues section
- 📢 Share the project with others who might find it useful

---

<p align="center">
  Thank you for contributing! 🙏💖
</p>

<p align="center">
  Together, we can make ACDCPF better for everyone! 🚀
</p>
