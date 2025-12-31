# Build Your Own Shell - Python Implementation

## Overview

This project implements a feature-rich custom shell interpreter with advanced capabilities including:

- Parsing and executing shell commands with proper argument handling
- Running external programs with PATH resolution
- Comprehensive builtin command suite (cd, pwd, echo, type, exit, cat, ls, wc, head, tail, history)
- Interactive REPL with readline support and tab completion
- Command pipelines (`|`) for chaining commands
- Output redirection (`>`, `>>`, `2>`, `2>>`) for stdout/stderr
- Command history with persistence (read/write history files)
- Automatic history loading from `$HISTFILE` on startup
- Automatic history saving to `$HISTFILE` on exit

The shell follows POSIX standards and provides a foundation for understanding how command-line shells work under the hood.

## Features

### Builtin Commands

The shell supports the following builtin commands:

#### Core Commands

- **`exit`**: Terminates the shell session (automatically saves history to `$HISTFILE` if set)
- **`echo [options] [args...]`**: Prints arguments to stdout
  - `-n`: Do not output trailing newline
  - `-e`: Enable interpretation of backslash escapes (`\n`, `\t`, `\r`, `\\`)
  - `-E`: Disable interpretation of backslash escapes (default)
- **`type <command>`**: Displays information about whether a command is a builtin or external program, including the full path for external programs

#### Navigation Commands

- **`pwd`**: Prints the current working directory
- **`cd <directory>`**: Changes the current directory
  - Supports `~` for home directory
  - Displays error if directory doesn't exist

#### File Operations

- **`cat [options] [files...]`**: Concatenates and prints file contents
  - `-n`: Number all output lines
  - `-E`: Display `$` at end of lines
  - `-T`: Display TAB characters as `^I`
  - Reads from stdin if no files specified

- **`ls [options] [paths...]`**: Lists directory contents
  - `-l`: Long format (shows permissions and size)
  - `-a`: Show hidden files (starting with `.`)
  - `-S`: Sort by file size (largest first)
  - `-t`: Sort by modification time (newest first)
  - `-R`: Recursive listing

- **`wc [options] [files...]`**: Counts lines, words, and bytes
  - `-l`: Show line count only
  - `-w`: Show word count only
  - `-c`: Show byte count only
  - Default: Shows all three counts
  - Reads from stdin if no files specified

- **`head [options] [files...]`**: Displays first lines of files
  - `-n N`: Number of lines to display (default: 10)
  - `-c N`: Number of bytes to display
  - Reads from stdin if no files specified

- **`tail [options] [files...]`**: Displays last lines of files
  - `-n N`: Number of lines to display (default: 10)
  - `-c N`: Number of bytes to display
  - `-f`: Follow mode (continuously monitor file for new content)
  - Reads from stdin if no files specified

#### History Commands

- **`history [options] [N]`**: Display or manage command history
  - No arguments: Show all history with line numbers
  - `N`: Show last N entries
  - `-n N`: Show last N entries
  - `-c`: Clear all history
  - `-w [file]`: Write history to file (default: `~/.bash_history`)
  - `-r [file]`: Read and append history from file (default: `~/.bash_history`)
  - `-a [file]`: Append new history entries to file (default: `~/.bash_history`)
  - Automatically loads from `$HISTFILE` on startup
  - Automatically saves to `$HISTFILE` on exit

### External Program Execution

The shell can execute external programs by searching through the directories in the `PATH` environment variable. When a command is not a builtin, the shell searches for an executable file with that name in the system PATH.

### Command Pipelines

The shell supports piping command output between multiple commands using the `|` operator:

```bash
$ cat file.txt | grep pattern | wc -l
$ ls -l | head -n 5
$ echo "hello world" | wc -w
```

Pipeline features:
- Connects stdout of one command to stdin of the next
- Supports both builtin and external commands in pipelines
- Special handling for `tail -f | head -n N` to stream output until head exits
- Proper process cleanup and error handling

### Output Redirection

The shell supports comprehensive output redirection:

#### Stdout Redirection
- `>` or `1>`: Redirect stdout to file (overwrite)
- `>>` or `1>>`: Redirect stdout to file (append)

#### Stderr Redirection
- `2>`: Redirect stderr to file (overwrite)
- `2>>`: Redirect stderr to file (append)

Examples:
```bash
$ echo "Hello" > output.txt
$ ls nonexistent 2> error.log
$ cat file.txt >> combined.txt 2>> error.txt
```

Redirection features:
- Automatically creates parent directories if needed
- Supports redirection with both builtin and external commands
- Can redirect stdout and stderr to different files simultaneously

### Tab Completion

The shell provides intelligent tab completion for:
- Builtin commands
- External executables in PATH
- Shows common prefix on first TAB
- Displays all matches on second TAB
- Auto-completes when only one match exists

### Command History

The shell maintains a persistent command history with:
- Arrow key navigation (↑/↓) through previous commands
- Automatic loading from `$HISTFILE` environment variable on startup
- Automatic saving to `$HISTFILE` on exit
- Manual history management with `history` command options
- Avoids consecutive duplicate entries

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

$ ls -la
drwxr-xr-x    128 file1.txt
-rw-r--r--     256 file2.txt
-rw-r--r--    1024 README.md

$ cat file1.txt | wc -l
42

$ echo "test" > output.txt

$ history 5
    1  type echo
    2  type ls
    3  ls -la
    4  cat file1.txt | wc -l
    5  echo "test" > output.txt

$ exit
```

### Using History Persistence

Set the `HISTFILE` environment variable to enable automatic history persistence:

```bash
$ export HISTFILE=~/.my_shell_history
$ ./your_program.sh
# Commands are automatically loaded from ~/.my_shell_history on startup
# New commands are automatically saved on exit
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

1. **Shell Engine** (`Shell` class)
   - Main shell execution engine and state management
   - Command history tracking with persistence support
   - Tab completion integration
   - Automatic history loading from `$HISTFILE` on startup
   - Automatic history saving to `$HISTFILE` on exit
   - Builtin command registry and routing

2. **Tab Completer** (`TabCompleter` class)
   - Handles readline tab completion for shell commands
   - Searches builtin commands and PATH executables
   - Provides intelligent auto-completion with common prefix detection
   - Shows all matches on repeated TAB presses

3. **Command Types** (`ShellCommandType` enum)
   - Defines all supported builtin command types
   - Used for command routing and type checking

4. **Redirection Manager** (`RedirectionManager` class)
   - Parses and handles output redirection tokens (`>`, `>>`, `2>`, `2>>`)
   - Opens and manages redirection target files
   - Provides context managers for stdout/stderr redirection
   - Automatically creates parent directories

5. **Pipeline Manager** (`PipelineManager` class)
   - Handles command pipeline execution (`cmd1 | cmd2 | cmd3`)
   - Connects stdout of one command to stdin of next
   - Special handling for `tail -f | head` streaming scenarios
   - Supports both builtin and external commands in pipelines

6. **Command Classes** (Abstract base: `Command`)
   - Each builtin command implemented as separate class
   - Consistent interface: `can_handle()` and `execute()`
   - Individual option parsing and error handling
   - Support for stdin/stdout redirection in pipelines

7. **External Command Executor** (`ExternalCommand` class)
   - Executes non-builtin commands via subprocess
   - Searches PATH for executable resolution
   - Handles output redirection for external programs

### Current Implementation Status

The shell currently implements:

- ✅ Basic REPL loop with interactive command prompt
- ✅ Comprehensive builtin command suite (exit, echo, type, pwd, cd, cat, ls, wc, head, tail, history)
- ✅ Advanced command parsing with proper quoting and escaping
- ✅ External program execution via PATH searching
- ✅ Command pipelines (`|`) connecting multiple commands
- ✅ Output redirection (`>`, `>>`, `2>`, `2>>`) for stdout/stderr
- ✅ Tab completion for commands and executables
- ✅ Command history with arrow key navigation
- ✅ History persistence (read/write history files)
- ✅ Automatic history loading from `$HISTFILE` on startup
- ✅ Automatic history saving to `$HISTFILE` on exit
- ✅ Error handling for invalid commands and file operations
- ✅ Special pipeline handling for streaming scenarios (`tail -f | head`)

### Architecture Highlights

**Object-Oriented Design:**
- Each builtin command is a separate class implementing the `Command` interface
- Manager classes handle specific concerns (pipelines, redirection, completion)
- Clean separation of concerns and single responsibility principle

**Advanced Features:**
- Smart history tracking prevents duplicate saves with `-a` option
- Pipeline support for both builtin and external commands
- Proper stdin/stdout/stderr handling in complex pipelines
- Thread-based streaming for `tail -f | head` scenarios

**POSIX Compliance:**
- Follows standard shell behavior for command parsing
- Compatible with common shell scripting patterns
- Standard exit codes and error messages

Future enhancements may include:

- Job control and background process execution (`&`, `fg`, `bg`)
- Environment variable expansion (`$VAR`, `${VAR}`)
- Command substitution (`` `command` `` or `$(command)`)
- Conditional execution (`&&`, `||`)
- Input redirection (`<`)
- Globbing and wildcards (`*`, `?`, `[...]`)
- Shell scripting support (execute `.sh` files)
- Signal handling (SIGINT, SIGTERM, etc.)
- Aliases and functions

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

#### Builtin Commands
- `exit` - Exit the shell
- `echo` with options (`-n`, `-e`)
- `type` with builtins and external commands
- `pwd` and `cd` with various paths
- `cat` with files and stdin
- `ls` with various options (`-l`, `-a`, `-S`, `-t`, `-R`)
- `wc` with files and stdin
- `head` and `tail` with various options
- `history` with all options (`-n`, `-c`, `-w`, `-r`, `-a`)

#### Advanced Features
- **Pipelines**:
  - `echo "hello" | wc -w`
  - `cat file.txt | grep pattern | wc -l`
  - `ls -l | head -n 5`
  - `tail -f file.txt | head -n 10` (streaming)

- **Redirection**:
  - `echo "test" > output.txt`
  - `echo "more" >> output.txt`
  - `ls nonexistent 2> error.log`
  - `cat file.txt > out.txt 2> err.txt`

- **History**:
  - Use arrow keys to navigate history
  - `export HISTFILE=/tmp/test_history`
  - Restart shell and verify history persistence
  - Test `history -w`, `history -r`, `history -a`

- **Tab Completion**:
  - Type partial command and press TAB
  - Verify common prefix completion
  - Verify match listing on second TAB

#### Error Handling
- Invalid command execution
- File not found errors
- Permission errors
- Malformed redirection syntax

## Configuration

### Python Project Configuration (`pyproject.toml`)

- **Project name**: `shell-python`
- **Version**: `0.1.0`
- **Python requirement**: `>=3.14`
- **Dependencies**: Uses Python standard library modules:
  - `os`, `sys`: System operations and environment
  - `subprocess`: External command execution
  - `shlex`: Shell-like syntax parsing
  - `contextlib`: Context manager utilities
  - `shutil`: High-level file operations
  - `stat`: File status operations
  - `readline`: Command-line editing and history
  - `threading`, `time`, `queue`: Threading for `tail -f` support
  - `abc`: Abstract base classes for command interface
  - `enum`: Enum types for command definitions
  - `typing`: Type hints for better code quality
  - `io`: String I/O for pipeline handling

### Environment Variables

The shell recognizes and uses the following environment variables:

- **`PATH`**: Colon-separated list of directories to search for executables
- **`HOME`** / **`HOMEPATH`** / **`USERPROFILE`**: User's home directory for `cd ~`
- **`HISTFILE`**: Path to history file for automatic persistence (e.g., `~/.bash_history`)

## Contributing

Contributions are welcome! Feel free to fork the repository, make improvements, and submit pull requests.

## Resources

- [POSIX Shell Specification](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html)
- [Bash Reference Manual](https://www.gnu.org/software/bash/manual/bash.html)
- [Python Documentation](https://docs.python.org/3/)
- [uv Documentation](https://github.com/astral-sh/uv)
- [Python subprocess Module](https://docs.python.org/3/library/subprocess.html)
- [Python readline Module](https://docs.python.org/3/library/readline.html)

## License

This project is part of a learning exercise to understand shell implementation fundamentals.
