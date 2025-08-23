# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## RFS Framework Overview

RFS Framework v4 is a comprehensive Python framework for modern enterprise applications featuring:
- **Core Pattern**: Result/Either/Maybe monads for functional error handling
- **Reactive Programming**: Mono/Flux reactive streams with Result integration
- **State Machine**: Functional state management with transitions and actions
- **Event System**: Event-driven architecture with CQRS and Event Sourcing
- **Cloud Native**: Optimized for Google Cloud Run with auto-scaling and monitoring
- **Production Ready**: Built-in validation, optimization, and security scanning

## Common Development Commands

### Project Setup & Development
```bash
# Install dependencies with all features
pip install -e ".[all]"

# Install specific feature sets
pip install -e ".[web,database,test]"

# Run development server
rfs-cli dev --reload --port 8000

# Run a single test
pytest tests/test_result.py::TestResult::test_success_creation -v

# Run tests with coverage
pytest --cov=rfs --cov-report=term-missing

# Run specific test markers
pytest -m "not slow"
pytest -m integration
```

### Code Quality & Linting
```bash
# Format code with black
black src/rfs

# Sort imports
isort src/rfs

# Type checking
mypy src/rfs

# Security scanning
bandit -r src/rfs

# All linting/validation via CLI
rfs-cli dev lint
rfs-cli dev security-scan
```

### Documentation & Building
```bash
# Generate documentation
rfs-cli docs --all

# Build for production
rfs-cli build --platform cloud-run

# Create distribution packages
python -m build
```

### Deployment
```bash
# Deploy to Cloud Run
rfs-cli deploy cloud-run --region asia-northeast3

# Check deployment status
rfs-cli deploy status

# View logs
rfs-cli deploy logs --follow
```

## Architecture & Code Structure

### Core Module Organization

The framework uses a modular architecture with clear separation of concerns:

1. **Core Pattern (`src/rfs/core/`)**: Result monad pattern is central to error handling. All functions return `Result[T, E]` for explicit success/failure handling. The registry pattern manages service dependencies.

2. **Configuration System**: Uses Pydantic v2 for type-safe configuration with environment profiles (development, production, cloud_run). Configuration validation happens at startup.

3. **Reactive Streams (`src/rfs/reactive/`)**: Implements Project Reactor patterns with `Mono` (single value) and `Flux` (stream of values). All reactive operations integrate with the Result pattern.

4. **State Machine (`src/rfs/state_machine/`)**: Functional state management with immutable states. Transitions are defined declaratively with optional actions and guards.

5. **Event System (`src/rfs/events/`)**: Event-driven architecture supporting CQRS (Command Query Responsibility Segregation) and Event Sourcing patterns. Saga pattern for distributed transactions.

### Key Design Patterns

- **Railway Oriented Programming**: All operations use Result type for error handling without exceptions
- **Dependency Injection**: Registry-based service management with `@stateless` decorator
- **Functional Composition**: Heavy use of map, bind (flatMap), and pipe operations
- **Type Safety**: Full type hints with Python 3.10+ features (match/case, union types)

### Module Dependencies

```
Core (Result, Config, Registry)
    ↓
Reactive (Mono, Flux)
    ↓
State Machine & Events
    ↓
Cloud Run Integration (Service Discovery, Task Queue, Monitoring)
    ↓
Production Framework (Validation, Optimization, Security)
```

### Testing Strategy

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test module interactions
- **Markers**: Use pytest markers for test categorization (slow, integration, unit, security, performance)
- **Coverage Target**: Maintain >80% code coverage

### Error Handling Philosophy

Never throw exceptions in business logic. Always return Result types:
```python
def divide(a: int, b: int) -> Result[float, str]:
    if b == 0:
        return Failure("Division by zero")
    return Success(a / b)
```

### Async/Await Integration

The framework supports both sync and async operations:
- `Result` for synchronous operations
- `ResultAsync` for asynchronous operations
- Reactive streams handle async naturally

### CLI Tool Architecture

The CLI (`rfs-cli`) is built with Typer and Rich for an enhanced developer experience. Commands are organized into subcommands:
- `project`: Project management
- `dev`: Development tools
- `deploy`: Deployment operations
- `debug`: Debugging utilities