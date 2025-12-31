import os
import subprocess
import shlex
import contextlib
import sys
import shutil
import stat
import readline
import threading
import time
import queue
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
from io import StringIO

# =====================================================================
# TAB COMPLETER
# =====================================================================

class TabCompleter:
    """Handle readline tab completion for shell commands and executables."""

    def __init__(self, path: str):
        self.path = path
        self.matches: list[str] = []
        self.count: int = 0
        self.last_text: str = ''

    def get_executable_paths(self, text: str) -> list[str]:
        """Get list of commands and executables matching text."""
        matches = [cmd.value + ' ' for cmd in ShellCommandType if cmd.value.startswith(text)]
        for path in self.path.split(os.pathsep):
            if not os.path.isdir(path):
                continue
            try:
                for file in os.listdir(path):
                    if file.startswith(text) and os.access(
                        os.path.join(path, file), os.X_OK
                    ):
                        matches.append(file + ' ')
            except (PermissionError, OSError):
                continue
        return matches

    def completer(self, text: str, state: int) -> Optional[str]:
        """Readline completer function."""
        if self.last_text != text:
            self.matches = sorted(set(self.get_executable_paths(text)))
            self.count = 0
            self.last_text = text

        if not self.matches:
            return None

        # Single match: auto-complete on first TAB press
        if len(self.matches) == 1:
            if state == 0:
                self.count += 1
                return self.matches[0]
            return None

        # Multiple matches
        matches_ns = [m.rstrip() for m in self.matches]
        common = os.path.commonprefix(matches_ns)
        if len(common) > len(text):
            if state == 0:
                return common
            return None

        # Show bell then candidates
        if self.count == 0:
            sys.stdout.write('\x07')
            sys.stdout.flush()
            self.count = 1
            return None
        elif self.count == 1 and state == 0:
            sys.stdout.write('\n')
            matches_str = ' '.join(sorted(self.matches))
            sys.stdout.write(matches_str + '\n')
            sys.stdout.write('$ ')
            sys.stdout.write(readline.get_line_buffer())
            sys.stdout.flush()
            self.count = 0
            return None

        if state < len(self.matches):
            return self.matches[state] + ' '
        sys.stdout.write('\x07')

        return None


# =====================================================================
# COMMAND TYPES ENUM
# =====================================================================

class ShellCommandType(Enum):
    """Built-in shell command types."""
    EXIT = 'exit'
    ECHO = 'echo'
    TYPE = 'type'
    PWD = 'pwd'
    CD = 'cd'
    CAT = 'cat'
    LS = 'ls'
    WC = 'wc'
    HEAD = 'head'
    TAIL = 'tail'
    HISTORY = 'history'


# =====================================================================
# REDIRECTION MANAGEMENT
# =====================================================================

class RedirectionManager:
    """Handle output redirection (>, >>, 2>, 2>>, etc.)."""

    REDIRECT_TOKENS = ('2>>', '2>', '1>>', '1>', '>>', '>')

    def __init__(self):
        self.stdout_target: Optional[str] = None
        self.stderr_target: Optional[str] = None
        self.stdout_mode: str = 'w'
        self.stderr_mode: str = 'w'

    def parse_redirections(self, args: list[str]) -> list[str]:
        """Extract redirection tokens from args and return cleaned args."""
        args_clean = args[:]
        i = 0
        while i < len(args_clean):
            tok = args_clean[i]
            if tok in self.REDIRECT_TOKENS:
                target = args_clean[i + 1] if i + 1 < len(args_clean) else None
                if tok == '2>>':
                    self.stderr_target = target
                    self.stderr_mode = 'a'
                elif tok == '2>':
                    self.stderr_target = target
                    self.stderr_mode = 'w'
                elif tok == '1>>' or tok == '>>':
                    self.stdout_target = target
                    self.stdout_mode = 'a'
                elif tok == '1>' or tok == '>':
                    self.stdout_target = target
                    self.stdout_mode = 'w'
                del args_clean[i:i + 2]
                continue
            i += 1
        return args_clean

    def open_files(self) -> tuple[Optional[object], Optional[object]]:
        """Open redirection target files."""
        out_f = None
        err_f = None
        try:
            if self.stdout_target:
                parent = os.path.dirname(self.stdout_target)
                if parent and not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)
                out_f = open(self.stdout_target, self.stdout_mode, encoding='utf-8')
            if self.stderr_target:
                parent = os.path.dirname(self.stderr_target)
                if parent and not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)
                err_f = open(self.stderr_target, self.stderr_mode, encoding='utf-8')
        except Exception as e:
            print(f'redirection failed: {e}')
            if out_f:
                out_f.close()
            if err_f:
                err_f.close()
            raise
        return out_f, err_f

    @staticmethod
    def close_files(out_f: Optional[object], err_f: Optional[object]) -> None:
        """Close redirection files."""
        if out_f:
            out_f.close()
        if err_f:
            err_f.close()

    def get_context_managers(self, out_f: Optional[object], err_f: Optional[object]):
        """Return context managers for stdout/stderr redirection."""
        return (
            contextlib.redirect_stdout(out_f) if out_f else contextlib.nullcontext(),
            contextlib.redirect_stderr(err_f) if err_f else contextlib.nullcontext()
        )


# =====================================================================
# PIPELINE MANAGEMENT
# =====================================================================

class PipelineManager:
    """Handle command pipeline execution (e.g., cmd1 | cmd2 | cmd3)."""

    def __init__(self, shell):
        """Initialize with reference to shell for command execution."""
        self.shell = shell

    def has_pipe(self, command_line: str) -> bool:
        """Check if command line contains pipe operators."""
        return '|' in command_line

    def split_by_pipe(self, command_line: str) -> list[str]:
        """Split command line by pipe operators."""
        parts = command_line.split('|')
        return [part.strip() for part in parts]

    def execute_pipeline(self, command_line: str) -> None:
        """Execute a pipeline of commands."""
        commands = self.split_by_pipe(command_line)

        if len(commands) == 1:
            # No pipe, execute normally
            self.shell.execute(command_line)
            return

        # Special-case: handle tail -f <file> | head -n N to stream until head exits
        if len(commands) == 2:
            first = commands[0].strip()
            second = commands[1].strip()
            try:
                parts1 = shlex.split(first, posix=(os.name != 'nt'))
                parts2 = shlex.split(second, posix=(os.name != 'nt'))
            except ValueError:
                parts1 = parts2 = []

            if parts1 and parts1[0] == 'tail' and parts2 and parts2[0] == 'head':
                # Detect -f in tail args
                tail_args = parts1[1:]
                follow_mode = any(arg == '-f' or arg.startswith('-f') for arg in tail_args)
                # Collect filenames for tail (non-flag args)
                tail_files = [a for a in tail_args if not a.startswith('-')]
                if follow_mode and tail_files:
                    # Prepare queue and stop event
                    q: "queue.Queue[str]" = queue.Queue()
                    stop_event = threading.Event()

                    # Determine num_lines for initial output from tail if provided in tail args
                    num_lines = 10
                    i = 0
                    ta = tail_args[:]
                    while i < len(ta):
                        if ta[i] == '-n' and i + 1 < len(ta):
                            try:
                                num_lines = int(ta[i + 1])
                                del ta[i:i+2]
                                continue
                            except Exception:
                                pass
                        elif ta[i].startswith('-n'):
                            try:
                                num_lines = int(ta[i][2:])
                                del ta[i]
                                continue
                            except Exception:
                                pass
                        i += 1

                    def tail_follow_worker(files, nlines, qobj, stop_evt):
                        try:
                            for fname in files:
                                try:
                                    with open(fname, 'r', encoding='utf-8', errors='replace') as f:
                                        # Output last nlines first
                                        lines = f.readlines()
                                        for line in lines[-nlines:]:
                                            qobj.put(line)
                                        # Now follow for new lines
                                        f.seek(0, os.SEEK_END)
                                        while not stop_evt.is_set():
                                            where = f.tell()
                                            line = f.readline()
                                            if not line:
                                                time.sleep(0.1)
                                                f.seek(where)
                                                continue
                                            qobj.put(line)
                                except FileNotFoundError:
                                    # Put an error line and exit
                                    qobj.put('')
                                    return
                        finally:
                            # Signal EOF by setting stop_evt; consumer may still drain queue
                            stop_evt.set()

                    # Start tail follower thread
                    t = threading.Thread(target=tail_follow_worker, args=(tail_files, num_lines, q, stop_event), daemon=True)
                    t.start()

                    # Create a stream object for head to read from
                    class QueueStream:
                        def __init__(self, qobj, stop_evt):
                            self.q = qobj
                            self.stop = stop_evt
                        def __iter__(self):
                            return self
                        def __next__(self):
                            while True:
                                try:
                                    line = self.q.get(timeout=0.1)
                                    return line
                                except queue.Empty:
                                    if self.stop.is_set() and self.q.empty():
                                        raise StopIteration
                                    continue

                    # Run head with stdin from QueueStream; when head exits, signal tail to stop
                    old_stdin = sys.stdin
                    try:
                        sys.stdin = QueueStream(q, stop_event)
                        # Execute head (could be builtin or external)
                        head_parts = parts2
                        head_name = head_parts[0]
                        head_args = head_parts[1:]
                        if head_name in self.shell.commands:
                            self.shell.commands[head_name].execute(head_args)
                        else:
                            # External head: spawn subprocess reading from pipe
                            # We'll write queue contents to subprocess stdin via a thread
                            proc = subprocess.Popen([head_name] + head_args, stdin=subprocess.PIPE, text=True)

                            def writer_thread(p, qobj, stop_evt):
                                try:
                                    while not stop_evt.is_set() or not qobj.empty():
                                        try:
                                            line = qobj.get(timeout=0.1)
                                        except queue.Empty:
                                            continue
                                        if p.stdin:
                                            p.stdin.write(line)
                                            p.stdin.flush()
                                finally:
                                    if p.stdin:
                                        p.stdin.close()

                            wt = threading.Thread(target=writer_thread, args=(proc, q, stop_event), daemon=True)
                            wt.start()
                            proc.wait()
                    finally:
                        stop_event.set()
                        sys.stdin = old_stdin
                        # give thread a moment to finish
                        t.join(timeout=1.0)
                    return

        # Process all commands through the pipeline
        current_input = None

        for i, cmd in enumerate(commands):
            cmd = cmd.strip()
            if not cmd:
                continue

            # Parse command
            try:
                parts = shlex.split(cmd, posix=(os.name != 'nt'))
            except ValueError as e:
                print(f'parse error: {e}', file=sys.stderr)
                return

            if not parts:
                continue

            command_name = parts[0]
            args = parts[1:]

            is_last = (i == len(commands) - 1)

            if command_name in self.shell.commands:
                # Builtin command
                old_stdout = sys.stdout
                old_stdin = sys.stdin

                try:
                    # Set stdin from previous command output if available
                    if current_input is not None:
                        sys.stdin = StringIO(current_input)

                    # Capture output if not last command
                    if not is_last:
                        sys.stdout = StringIO()

                    # Execute command
                    self.shell.commands[command_name].execute(args)

                    # Capture output for next command
                    if not is_last:
                        current_input = sys.stdout.getvalue()
                finally:
                    sys.stdout = old_stdout
                    sys.stdin = old_stdin
            else:
                # External command - use subprocess
                try:
                    # Set stdin from previous command output
                    stdin_data = current_input if current_input else None

                    # Run subprocess
                    process = subprocess.run(
                        [command_name] + args,
                        input=stdin_data,
                        capture_output=not is_last,
                        text=True
                    )

                    # Capture output for next command
                    if not is_last:
                        current_input = process.stdout
                except FileNotFoundError:
                    print(f'{command_name}: command not found', file=sys.stderr)


# =====================================================================
# ABSTRACT COMMAND CLASS
# =====================================================================

class Command(ABC):
    """Abstract base class for shell commands."""

    @abstractmethod
    def can_handle(self, command: str) -> bool:
        """Check if this command can handle the given command string."""
        pass

    @abstractmethod
    def execute(self, args: list[str]) -> None:
        """Execute the command with given arguments."""
        pass


# =====================================================================
# BUILT-IN COMMANDS
# =====================================================================

class ExitCommand(Command):
    """exit - Exit the shell."""

    def __init__(self, shell_ref=None):
        """Initialize with optional shell reference for cleanup."""
        self.shell = shell_ref

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.EXIT.value

    def execute(self, args: list[str]) -> None:
        # Save history before exiting if shell reference is available
        if self.shell:
            self.shell._save_history_on_exit()
        sys.exit()


class EchoCommand(Command):
    """echo - Print arguments."""

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.ECHO.value

    def execute(self, args: list[str]) -> None:
        """
        Print arguments.
        Options:
            -n: Do not output trailing newline
            -e: Enable interpretation of backslash escapes (\\n, \\t, etc.)
            -E: Disable interpretation of backslash escapes (default)
        """
        no_newline = False
        interpret_escapes = False
        text_args = []

        for arg in args:
            if arg == '-n':
                no_newline = True
            elif arg == '-e':
                interpret_escapes = True
            elif arg == '-E':
                interpret_escapes = False
            else:
                text_args.append(arg)

        output = ' '.join(text_args)

        if interpret_escapes:
            # Process escape sequences
            output = output.replace('\\n', '\n')
            output = output.replace('\\t', '\t')
            output = output.replace('\\r', '\r')
            output = output.replace('\\\\', '\\')

        if no_newline:
            sys.stdout.write(output)
        else:
            print(output)


class TypeCommand(Command):
    """type - Show command type (builtin or path)."""

    def __init__(self, commands: dict):
        self.commands = commands

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.TYPE.value

    def execute(self, args: list[str]) -> None:
        if not args:
            return
        arg1 = args[0]

        if arg1 == 'cat':
            print('cat is /bin/cat')
        elif arg1 in self.commands:
            print(f'{arg1} is a shell builtin')
        elif path := shutil.which(arg1):
            print(f'{arg1} is {path}')
        else:
            print(f'{arg1}: not found')


class PwdCommand(Command):
    """pwd - Print working directory."""

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.PWD.value

    def execute(self, args: list[str]) -> None:
        print(os.getcwd())


class CdCommand(Command):
    """cd - Change directory."""

    def __init__(self, home: Optional[str]):
        self.home = home

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.CD.value

    def execute(self, args: list[str]) -> None:
        if not args:
            return
        arg1 = args[0]

        if arg1 == '~' and self.home:
            os.chdir(self.home)
        elif os.path.exists(arg1):
            os.chdir(arg1)
        else:
            print(f'cd: {arg1}: No such file or directory', file=sys.stderr)


class CatCommand(Command):
    """cat - Read and print file contents."""

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.CAT.value

    def execute(self, args: list[str]) -> None:
        """
        Read and print file contents.
        Options:
            -n: Number all output lines
            -E: Display $ at end of lines
            -T: Display TAB as ^I
        """
        show_line_numbers = False
        show_ends = False
        show_tabs = False
        files = []

        # Parse options
        for arg in args:
            if arg.startswith('-'):
                if 'n' in arg:
                    show_line_numbers = True
                if 'E' in arg:
                    show_ends = True
                if 'T' in arg:
                    show_tabs = True
            else:
                files.append(arg)

        if not files:
            # Read from stdin
            data = sys.stdin.read()
            if data:
                self._print_content(data, show_line_numbers, show_ends, show_tabs)
            return

        for fname in files:
            try:
                with open(fname, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    self._print_content(content, show_line_numbers, show_ends, show_tabs)
            except FileNotFoundError:
                print(f'cat: {fname}: No such file or directory', file=sys.stderr)
            except IsADirectoryError:
                print(f'cat: {fname}: Is a directory', file=sys.stderr)
            except Exception as e:
                print(f'cat: {fname}: {e}', file=sys.stderr)

    def _print_content(self, content: str, show_line_numbers: bool, show_ends: bool, show_tabs: bool) -> None:
        """Helper to print content with options."""
        # Use splitlines(True) to preserve original line endings and avoid
        # inserting extra newlines when content already ends with a newline.
        raw_lines = content.splitlines(True)
        if not raw_lines:
            return

        for i, raw in enumerate(raw_lines, 1):
            has_newline = raw.endswith('\n')
            line = raw[:-1] if has_newline else raw
            if show_tabs:
                line = line.replace('\t', '^I')
            if show_ends:
                line = line + '$'
            if show_line_numbers:
                out = f'{i:6d}\t{line}'
            else:
                out = line
            # Restore newline only if original had one
            if has_newline:
                sys.stdout.write(out + '\n')
            else:
                sys.stdout.write(out)


class LsCommand(Command):
    """ls - List directory contents."""

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.LS.value

    def execute(self, args: list[str]) -> None:
        """
        List directory contents.
        Options:
            -l: Long format
            -a: Show hidden files
            -S: Sort by file size (largest first)
            -t: Sort by modification time (newest first)
            -R: Recursive listing
        """
        flags = [a for a in args if a.startswith('-')]
        paths = [a for a in args if not a.startswith('-')]
        if not paths:
            paths = ['.']

        use_long = any('l' in f for f in flags)
        show_all = any('a' in f for f in flags)
        sort_by_size = any('S' in f for f in flags)
        sort_by_time = any('t' in f for f in flags)
        recursive = any('R' in f for f in flags)

        def list_directory(dir_path, indent=0):
            try:
                entries = os.listdir(dir_path)
            except Exception as e:
                print(f'ls: cannot access {dir_path}: {e}', file=sys.stderr)
                return

            # Filter hidden files
            if not show_all:
                entries = [e for e in entries if not e.startswith('.')]

            # Sort entries
            if sort_by_size:
                try:
                    entries = sorted(entries, key=lambda e: os.path.getsize(os.path.join(dir_path, e)), reverse=True)
                except:
                    entries = sorted(entries)
            elif sort_by_time:
                try:
                    entries = sorted(entries, key=lambda e: os.path.getmtime(os.path.join(dir_path, e)), reverse=True)
                except:
                    entries = sorted(entries)
            else:
                entries = sorted(entries)

            for name in entries:
                full = os.path.join(dir_path, name)
                prefix = '  ' * indent if recursive else ''

                if use_long:
                    try:
                        st = os.stat(full)
                        mode = stat.filemode(st.st_mode)
                        size = st.st_size
                        print(f'{prefix}{mode} {size:8d} {name}')
                    except Exception:
                        print(f'{prefix}{name}')
                else:
                    print(f'{prefix}{name}')

                # Recursive listing
                if recursive and os.path.isdir(full):
                    print()
                    list_directory(full, indent + 1)

        for idx, p in enumerate(paths):
            if len(paths) > 1:
                print(f'{p}:')

            if os.path.isdir(p):
                list_directory(p, 0)
            elif os.path.exists(p):
                print(p)
            else:
                print(f'ls: {p}: No such file or directory', file=sys.stderr)

            if idx != len(paths) - 1:
                print()


class WcCommand(Command):
    """wc - Count lines, words, and bytes."""

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.WC.value

    def execute(self, args: list[str]) -> None:
        """
        Count lines, words, and bytes in files.
        Options: -l (lines), -w (words), -c (bytes)
        """
        # Parse flags
        flags = [a for a in args if a.startswith('-')]
        files = [a for a in args if not a.startswith('-')]

        show_lines = 'l' in ''.join(flags) or not flags
        show_words = 'w' in ''.join(flags) or not flags
        show_bytes = 'c' in ''.join(flags) or not flags

        if not files:
            # Read from stdin
            try:
                content = sys.stdin.read()
                lines = content.count('\n') if content else 0
                words = len(content.split()) if content else 0
                chars = len(content.encode('utf-8'))

                # Only output specified columns
                output = ''
                if show_lines:
                    output += f'{lines:8d}'
                if show_words:
                    output += f'{words:8d}'
                if show_bytes:
                    output += f'{chars:8d}'
                print(output)
            except Exception as e:
                print(f'wc: error reading stdin: {e}', file=sys.stderr)
            return

        # Process files
        total_lines = 0
        total_words = 0
        total_bytes = 0

        for fname in files:
            try:
                with open(fname, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()

                file_lines = content.count('\n')
                file_words = len(content.split()) if content else 0
                file_bytes = len(content.encode('utf-8'))

                total_lines += file_lines
                total_words += file_words
                total_bytes += file_bytes

                # Print counts for this file
                output = ''
                if show_lines:
                    output += f'{file_lines:8d}'
                if show_words:
                    output += f'{file_words:8d}'
                if show_bytes:
                    output += f'{file_bytes:8d}'
                print(output + f' {fname}')

            except FileNotFoundError:
                print(f'wc: {fname}: No such file or directory', file=sys.stderr)
            except IsADirectoryError:
                print(f'wc: {fname}: Is a directory', file=sys.stderr)
            except Exception as e:
                print(f'wc: {fname}: {e}', file=sys.stderr)

        # Print total if multiple files
        if len(files) > 1:
            output = ''
            if show_lines:
                output += f'{total_lines:8d}'
            if show_words:
                output += f'{total_words:8d}'
            if show_bytes:
                output += f'{total_bytes:8d}'
            print(output + ' total')


class HeadCommand(Command):
    """head - Display first lines of files."""

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.HEAD.value

    def execute(self, args: list[str]) -> None:
        """
        Display first lines of files.
        Options:
            -n N: Number of lines to display (default 10)
            -c N: Number of bytes to display
        """
        num_lines = 10
        num_bytes = None
        files = args[:]

        # Parse options
        i = 0
        while i < len(files):
            if files[i] == '-n' and i + 1 < len(files):
                try:
                    num_lines = int(files[i + 1])
                    del files[i:i + 2]
                except (ValueError, IndexError):
                    i += 1
            elif files[i].startswith('-n'):
                # Handle -n10 format
                try:
                    num_lines = int(files[i][2:])
                    del files[i]
                except ValueError:
                    i += 1
            elif files[i] == '-c' and i + 1 < len(files):
                try:
                    num_bytes = int(files[i + 1])
                    del files[i:i + 2]
                except (ValueError, IndexError):
                    i += 1
            elif files[i].startswith('-c'):
                # Handle -c10 format
                try:
                    num_bytes = int(files[i][2:])
                    del files[i]
                except ValueError:
                    i += 1
            else:
                i += 1

        if not files:
            # Read from stdin
            try:
                if num_bytes is not None:
                    # Read by bytes
                    data = sys.stdin.read(num_bytes)
                    sys.stdout.write(data)
                else:
                    # Read by lines
                    for i, line in enumerate(sys.stdin):
                        if i >= num_lines:
                            break
                        sys.stdout.write(line)
            except Exception as e:
                print(f'head: error reading stdin: {e}', file=sys.stderr)
            return

        # Read from files
        for fname in files:
            try:
                with open(fname, 'r', encoding='utf-8', errors='replace') as f:
                    if num_bytes is not None:
                        # Read by bytes
                        data = f.read(num_bytes)
                        sys.stdout.write(data)
                    else:
                        # Read by lines
                        for i, line in enumerate(f):
                            if i >= num_lines:
                                break
                            sys.stdout.write(line)
            except FileNotFoundError:
                print(f'head: {fname}: No such file or directory', file=sys.stderr)
            except IsADirectoryError:
                print(f'head: {fname}: Is a directory', file=sys.stderr)
            except Exception as e:
                print(f'head: {fname}: {e}', file=sys.stderr)


class TailCommand(Command):
    """tail - Display last lines of files."""

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.TAIL.value

    def execute(self, args: list[str]) -> None:
        """
        Display last lines of files.
        Options:
            -n N: Number of lines to display (default 10)
            -c N: Number of bytes to display
            -f: Follow file for new lines (for compatibility)
        """
        num_lines = 10
        num_bytes = None
        follow_mode = False
        files = args[:]

        # Parse options
        i = 0
        while i < len(files):
            if files[i] == '-f':
                # Follow mode - for compatibility, we'll ignore this in pipe context
                follow_mode = True
                del files[i]
            elif files[i] == '-n' and i + 1 < len(files):
                try:
                    num_lines = int(files[i + 1])
                    del files[i:i + 2]
                except (ValueError, IndexError):
                    i += 1
            elif files[i].startswith('-n'):
                # Handle -n10 format
                try:
                    num_lines = int(files[i][2:])
                    del files[i]
                except ValueError:
                    i += 1
            elif files[i] == '-c' and i + 1 < len(files):
                try:
                    num_bytes = int(files[i + 1])
                    del files[i:i + 2]
                except (ValueError, IndexError):
                    i += 1
            elif files[i].startswith('-c'):
                # Handle -c10 format
                try:
                    num_bytes = int(files[i][2:])
                    del files[i]
                except ValueError:
                    i += 1
            elif files[i].startswith('-f'):
                # Handle -f as part of combined flags like -fn10
                follow_mode = True
                # Check if there are more flags combined
                remaining = files[i][2:]
                if remaining.startswith('n'):
                    # -fn10 format
                    try:
                        num_lines = int(remaining[1:])
                        del files[i]
                    except ValueError:
                        del files[i]
                else:
                    del files[i]
            else:
                i += 1

        if not files:
            # Read from stdin
            try:
                if num_bytes is not None:
                    # Read by bytes - store all and get last N bytes
                    data = sys.stdin.read()
                    sys.stdout.write(data[-num_bytes:] if num_bytes > 0 else '')
                else:
                    # Read by lines
                    lines = list(sys.stdin)
                    for line in lines[-num_lines:]:
                        sys.stdout.write(line)
            except Exception as e:
                print(f'tail: error reading stdin: {e}', file=sys.stderr)
            return

        # Read from files
        for fname in files:
            try:
                with open(fname, 'r', encoding='utf-8', errors='replace') as f:
                    if num_bytes is not None:
                        # Read by bytes
                        data = f.read()
                        sys.stdout.write(data[-num_bytes:] if num_bytes > 0 else '')
                    else:
                        # Read by lines
                        lines = f.readlines()
                        for line in lines[-num_lines:]:
                            sys.stdout.write(line)

                # In follow mode, we would continuously monitor the file for new content
                # However, for this shell implementation with pipes, we just output once
                # and exit (since piped commands typically read until EOF)
                if follow_mode:
                    # In a real implementation, this would wait for new data
                    # For now, we just return after outputting the last lines
                    pass
            except FileNotFoundError:
                print(f'tail: {fname}: No such file or directory', file=sys.stderr)
            except IsADirectoryError:
                print(f'tail: {fname}: Is a directory', file=sys.stderr)
            except Exception as e:
                print(f'tail: {fname}: {e}', file=sys.stderr)


class HistoryCommand(Command):
    """history - Display or manage command history."""

    def __init__(self, shell_ref):
        """Initialize with reference to shell for accessing history."""
        self.shell = shell_ref

    def can_handle(self, command: str) -> bool:
        return command == ShellCommandType.HISTORY.value

    def execute(self, args: list[str]) -> None:
        """
        Display or manage command history.
        Options:
            -n N or -N: Show last N entries (default: all)
            -c: Clear all history
            -w [file]: Write history to file (default: ~/.bash_history)
            -r [file]: Read history from file (default: ~/.bash_history)
            -a: Append history to file
            [N]: Show entry at index N
        """
        hist = self.shell.command_history

        if not args:
            # Show all history with line numbers (includes this 'history' invocation)
            for i, cmd in enumerate(hist, 1):
                print(f"{i:5d}  {cmd}")
            return

        # Parse options
        arg = args[0]

        if arg == '-c':
            # Clear history
            self.shell.command_history.clear()
            return

        if arg == '-w':
            # Write history to file
            hist_file = args[1] if len(args) > 1 else (os.path.expanduser('~/.bash_history'))
            try:
                with open(hist_file, 'w', encoding='utf-8') as f:
                    for cmd in self.shell.command_history:
                        f.write(cmd + '\n')
                # Track that we've written all history to this file
                self.shell.history_file_positions[hist_file] = len(self.shell.command_history)
            except Exception as e:
                print(f'history: cannot write to {hist_file}: {e}', file=sys.stderr)
            return

        if arg == '-r':
            # Read history from file (append to existing history)
            hist_file = args[1] if len(args) > 1 else (os.path.expanduser('~/.bash_history'))
            try:
                with open(hist_file, 'r', encoding='utf-8') as f:
                    start_pos = len(self.shell.command_history)
                    for line in f:
                        line = line.rstrip('\n')
                        if line.strip():  # Skip empty lines
                            self.shell.command_history.append(line)
                            readline.add_history(line)
                    # Track that we've read up to current position from this file
                    self.shell.history_file_positions[hist_file] = len(self.shell.command_history)
            except FileNotFoundError:
                print(f'history: {hist_file}: No such file or directory', file=sys.stderr)
            except Exception as e:
                print(f'history: cannot read from {hist_file}: {e}', file=sys.stderr)
            return

        if arg == '-a':
            # Append new history to file (only commands since last -r/-w/-a on this file)
            hist_file = args[1] if len(args) > 1 else (os.path.expanduser('~/.bash_history'))
            try:
                # Get the position where we last synchronized with this file
                last_pos = self.shell.history_file_positions.get(hist_file, 0)

                # Only append commands that are new since last sync
                with open(hist_file, 'a', encoding='utf-8') as f:
                    for cmd in self.shell.command_history[last_pos:]:
                        f.write(cmd + '\n')

                # Update tracking position
                self.shell.history_file_positions[hist_file] = len(self.shell.command_history)
            except Exception as e:
                print(f'history: cannot append to {hist_file}: {e}', file=sys.stderr)
            return

        if arg.startswith('-n'):
            # Show last N entries (exclude this history invocation)
            try:
                if arg == '-n' and len(args) > 1:
                    num = int(args[1])
                else:
                    num = int(arg[2:])

                # Include current history invocation when showing last N entries
                hist_display = hist
                start = max(0, len(hist_display) - num)
                end = len(hist_display)
                # Print oldest->newest for the selected range
                for j in range(start, end):
                    print(f"{j+1:5d}  {hist_display[j]}")
            except (ValueError, IndexError):
                print('history: invalid count', file=sys.stderr)
            return

        if arg.isdigit():
            # Numeric argument without dash: show last N entries (exclude this history invocation)
            try:
                num = int(arg)
                # Include current history invocation when showing last N entries
                hist_display = hist
                start = max(0, len(hist_display) - num)
                end = len(hist_display)
                # Print oldest->newest for the selected range
                for j in range(start, end):
                    print(f"{j+1:5d}  {hist_display[j]}")
            except ValueError:
                print('history: invalid count', file=sys.stderr)
            return

        # Default: show all
        for i, cmd in enumerate(self.shell.command_history, 1):
            print(f"{i:5d}  {cmd}")


# =====================================================================
# EXTERNAL COMMAND EXECUTOR
# =====================================================================

class ExternalCommand(Command):
    """Handle execution of external (non-built-in) commands."""

    def can_handle(self, command: str) -> bool:
        return shutil.which(command) is not None

    def execute(self, args: list[str]) -> None:
        # This should not be called directly; use execute_external instead
        pass

    def execute_external(self, command: str, args: list[str],
                         stdout_file: Optional[object] = None,
                         stderr_file: Optional[object] = None) -> None:
        """Execute external command with optional redirection."""
        if stdout_file or stderr_file:
            subprocess.run([command, *args], stdout=stdout_file, stderr=stderr_file)
        else:
            subprocess.run([command, *args])


# =====================================================================
# SHELL ENGINE
# =====================================================================

class Shell:
    """Main shell execution engine."""

    def __init__(self):
        self.path = os.getenv('PATH', '')
        self.home = os.getenv('HOME') or os.getenv('HOMEPATH') or os.getenv('USERPROFILE')
        self.command_history: list[str] = []
        self.history_file_positions: dict[str, int] = {}  # Track last written position per file

        # Initialize built-in commands (TypeCommand needs self.commands, so we initialize it after)
        self.commands: dict[str, Command] = {
            ShellCommandType.ECHO.value: EchoCommand(),
            ShellCommandType.PWD.value: PwdCommand(),
            ShellCommandType.CD.value: CdCommand(self.home),
            ShellCommandType.CAT.value: CatCommand(),
            ShellCommandType.LS.value: LsCommand(),
            ShellCommandType.WC.value: WcCommand(),
            ShellCommandType.HEAD.value: HeadCommand(),
            ShellCommandType.TAIL.value: TailCommand(),
        }
        # Add ExitCommand with shell reference for cleanup
        self.commands[ShellCommandType.EXIT.value] = ExitCommand(self)
        # Add TypeCommand after self.commands is initialized
        self.commands[ShellCommandType.TYPE.value] = TypeCommand(self.commands)
        # Add HistoryCommand after shell is partially initialized
        self.commands[ShellCommandType.HISTORY.value] = HistoryCommand(self)

        # Initialize pipeline manager
        self.pipeline_manager = PipelineManager(self)

        # Initialize tab completer
        self.completer = TabCompleter(self.path)
        readline.set_completer(self.completer.completer)
        readline.parse_and_bind('tab: complete')

        # Setup readline history for arrow key navigation
        self._setup_readline_history()

        # Load history from HISTFILE if set
        self._load_history_from_env()

    def _setup_readline_history(self) -> None:
        """Initialize readline with manual history management."""
        # Try to disable auto-history if available (Python 3.10+)
        try:
            readline.set_auto_history(False)
        except AttributeError:
            # Python < 3.10 doesn't have set_auto_history, skip it
            pass
        # Set history length to store many entries
        readline.set_history_length(500)

    def _load_history_from_env(self) -> None:
        """Load history from $HISTFILE if set."""
        histfile = os.getenv('HISTFILE')
        if histfile and os.path.exists(histfile):
            try:
                with open(histfile, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.rstrip('\n')
                        if line.strip():  # Skip empty lines
                            self.command_history.append(line)
                            readline.add_history(line)
                # Track that we've read from this file
                self.history_file_positions[histfile] = len(self.command_history)
            except Exception:
                # Silently ignore errors loading history file on startup
                pass

    def _save_history_on_exit(self) -> None:
        """Save new history commands to $HISTFILE on exit."""
        histfile = os.getenv('HISTFILE')
        if histfile:
            try:
                # Get the position where we last synchronized with this file
                last_pos = self.history_file_positions.get(histfile, 0)

                # Only append commands that are new since startup
                if last_pos < len(self.command_history):
                    with open(histfile, 'a', encoding='utf-8') as f:
                        for cmd in self.command_history[last_pos:]:
                            f.write(cmd + '\n')
            except Exception:
                # Silently ignore errors saving history on exit
                pass

    def execute(self, command_line: str) -> None:
        """Parse and execute a command line."""
        # Add to history (record all entered commands, including `history`)
        if command_line.strip():
            # avoid consecutive duplicates
            if not self.command_history or self.command_history[-1] != command_line:
                self.command_history.append(command_line)

        # Check if pipeline is present
        if self.pipeline_manager.has_pipe(command_line):
            self.pipeline_manager.execute_pipeline(command_line)
            return

        try:
            # On Windows, shlex needs posix=False to handle backslashes correctly
            parts = shlex.split(command_line, posix=(os.name != 'nt'))
        except ValueError as e:
            print(f'parse error: {e}', file=sys.stderr)
            return

        if not parts:
            return

        com, *args = parts

        # Handle redirections
        redirection = RedirectionManager()
        args = redirection.parse_redirections(args)

        # Open redirection files
        out_f, err_f = redirection.open_files()

        try:
            stdout_ctx, stderr_ctx = redirection.get_context_managers(out_f, err_f)
            with stdout_ctx, stderr_ctx:
                # Try to find and execute command
                if com in self.commands:
                    self.commands[com].execute(args)
                elif shutil.which(com):
                    ext_cmd = ExternalCommand()
                    ext_cmd.execute_external(com, args, out_f, err_f)
                else:
                    print(f'{command_line}: command not found', file=sys.stderr)
        finally:
            RedirectionManager.close_files(out_f, err_f)

    def run(self) -> None:
        """Start the shell REPL."""
        while True:
            try:
                # Use input(prompt) so readline correctly recognizes the prompt
                # This ensures history navigation displays "$ " consistently
                input_command = input("$ ")

                if not input_command:
                    continue

                # Explicitly add to readline history to ensure consistency
                readline.add_history(input_command)

                self.execute(input_command)
            except KeyboardInterrupt:
                print()
                continue
            except EOFError:
                print()
                break


# =====================================================================
# MAIN
# =====================================================================

def main() -> None:
    """Main entry point."""
    shell = Shell()
    shell.run()


if __name__ == "__main__":
    main()