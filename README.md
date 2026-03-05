# Smartloop

An SLM framework for inference and fine-tuning models on edge devices.

<img width="1076" height="963" alt="Screenshot 2026-03-04 at 4 18 39 PM" src="https://github.com/user-attachments/assets/0d725cf6-5b92-4561-b782-6f1be2b318fd" />

## Installation

```bash
curl -fsSL https://smartloop.ai/install | bash
```

Or install via Homebrew:

```bash
brew tap smartloop-ai/smartloop
brew install smartloop
```

### Upgrading

```bash
# via Homebrew
brew update && brew upgrade smartloop
```

## Usage

```bash
# View available commands
slp --help

# Initialize a new project
slp init -t <developer_token>

# Add a document for training
slp add document.pdf

# Run interactive chat
slp run
```

### Project Management

```bash
slp projects create <name>
slp projects list
slp projects switch <name>
slp status
```

### Server Management

SLP includes a background API server compatible with OpenAI's chat completion format:

```bash
slp server start
slp server stop
slp server status
```

On macOS, the server can also be managed via `brew services` (if install using homebrew):

```bash
brew services start smartloop
brew services stop smartloop
```

On Linux/WSL, the installer creates a systemd user service:

```bash
systemctl --user start smartloop
systemctl --user stop smartloop
systemctl --user status smartloop
```

### Supported Models

| Model | Base Model | Size |
|-------|-----------|------|
| `gemma3-1b` | google/gemma-3-1b-it | 1B |
| `gemma3-4b` | google/gemma-3-4b-it | 4B |
| `llama3-1b` | meta-llama/Llama-3.2-1B-Instruct | 1B |
| `llama3-3b` | meta-llama/Llama-3.2-3B-Instruct | 3B |
| `phi4-mini` | microsoft/phi-4-mini | 4B |

## Requirements

- macOS (Apple Silicon) or Linux (x86_64)
- Python 3.11 or later (installed automatically via Homebrew)
- CMake (installed automatically via Homebrew)

## License

Smartloop is distributed under the MIT License.
