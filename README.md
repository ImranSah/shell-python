# Build Your Own Shell - Python Implementation

## Overview

This project implements a custom shell interpreter capable of:

- Parsing and executing shell commands
- Running external programs
- Supporting builtin commands (cd, pwd, echo, type, exit, etc.)
- Providing an interactive REPL (Read-Eval-Print Loop) interface

The shell follows POSIX standards and provides a foundation for understanding how command-line shells work under the hood.

## Features

### Builtin Commands

The shell currently supports the following builtin commands:

- **`exit`**: Terminates the shell session
- **`echo`**: Prints arguments to stdout
- **`type`**: Displays information about whether a command is a builtin or external program, including the full path for external programs

### External Program Execution

The shell can execute external programs by searching through the directories in the `PATH` environment variable. When a command is not a builtin, the shell searches for an executable file with that name in the system PATH.

### Interactive REPL

The shell provides an interactive command-line interface with:

- Command prompt (`$`)
- Command parsing and execution
- Error handling for invalid commands

## Requirements

- Python 3.14 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer and resolver

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd shell-python
   ```

2. **Install uv** (if not already installed):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Install dependencies:**

   ```bash
   uv sync
   ```

## Usage

### Running Locally

To run the shell locally, use the provided script:

```bash
./your_program.sh
```

This will start an interactive shell session. You can then enter commands:

```bash
$ echo Hello, World!
Hello, World!
$ type echo
echo is a shell builtin
$ type ls
ls is /usr/bin/ls
$ ls
file1.txt  file2.txt  README.md
$ exit
```

### Running with Python

Alternatively, you can run the shell directly using Python:

```bash
uv run --quiet -m app.main
```

Or using Python directly:

```bash
python -m app.main
```

## Project Structure

```
shell-python/
├── app/
│   ├── __pycache__/      # Python bytecode cache
│   └── main.py           # Main shell implementation
├── pyproject.toml        # Python project configuration
├── README.md             # This file
├── uv.lock               # Dependency lock file
└── your_program.sh       # Local execution script
```

## Implementation Details

### Core Components

1. **REPL Loop** (`replLoop()`)
   - Displays the command prompt (`$`)
   - Reads user input
   - Parses and executes commands
   - Prints command results

2. **Command Iterator** (`commandIter()`)
   - Splits command line input into command and arguments
   - Handles commands with or without arguments
   - Returns a list with command and remaining arguments

3. **Command Evaluator** (`evalute()`)
   - Uses pattern matching to handle builtin commands (exit, echo, type)
   - Executes external commands via `externalCommand()`
   - Returns appropriate error messages for invalid commands
   - Handles command output formatting

4. **External Command Executor** (`externalCommand()`)
   - Searches for executables in directories listed in the `PATH` environment variable
   - Executes external programs using `subprocess`
   - Returns command output or `None` if command not found

### Current Implementation Status

The shell currently implements:

- ✅ Basic REPL loop with interactive command prompt
- ✅ Builtin command support (exit, echo, type)
- ✅ Command parsing and argument handling
- ✅ External program execution via PATH searching
- ✅ Error handling for invalid commands
- ✅ Command type detection (builtin vs external)
- ✅ Output formatting and newline handling

Future enhancements may include:

- Additional builtin commands (cd, pwd, etc.)
- Piping and redirection (`|`, `>`, `>>`, `<`)
- Environment variable expansion
- Command history
- Background process execution
- Signal handling

## Development Workflow

### Making Changes

1. Edit `app/main.py` to implement new features
2. Test locally using `./your_program.sh`
3. Commit your changes:

   ```bash
   git commit -am "your commit message"
   ```

4. Push your changes:

   ```bash
   git push origin master
   ```

### Testing

Test your implementation locally by running the shell and executing various commands. Make sure to test:

- Builtin commands (exit, echo, type)
- External program execution (ls, cat, pwd, etc.)
- Invalid command handling
- Command parsing with and without arguments
- The `type` command with both builtin and external commands

## Configuration

### Python Project Configuration (`pyproject.toml`)

- **Project name**: `shell-python`
- **Version**: `0.1.0`
- **Python requirement**: `>=3.14`
- **Dependencies**: Uses Python standard library modules (`os`, `subprocess`, `sys`)

## Contributing

Contributions are welcome! Feel free to fork the repository, make improvements, and submit pull requests.

## Resources

- [POSIX Shell Specification](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html)
- [Python Documentation](https://docs.python.org/3/)
- [uv Documentation](https://github.com/astral-sh/uv)
