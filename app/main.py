import os
import readline
import subprocess
import sys
import glob

EXTERNAL_CACHE = {}
COMMAND_HISTORY = []


def findExec(cmd):
    if cmd in EXTERNAL_CACHE:
        return EXTERNAL_CACHE[cmd]

    path_env = os.environ.get("PATH", "")
    directories = path_env.split(os.pathsep)

    for directory in directories:
        full_path = os.path.join(directory, cmd)
        if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
            EXTERNAL_CACHE[cmd] = full_path
            return full_path

    EXTERNAL_CACHE[cmd] = None
    return None


# ---------------- Builtins ---------------- #


def builtInExit(args):
    raise SystemExit


def builtInEcho(args):
    print(" ".join(args[1:]))


def builtInType(args):
    if len(args) < 2:
        print("type: missing operand")
        return

    cmd = args[1]
    if cmd in BUILTINS:
        print(f"{cmd} is a shell builtin")
    else:
        path = findExec(cmd)
        if path:
            print(f"{cmd} is {path}")
        else:
            print(f"{cmd}: not found")


def builtInPWD(args):
    print(os.getcwd())


def builtInCD(args):
    if len(args) < 2 or args[1] == "~":
        try:
            os.chdir(os.getenv("HOME"))
        except Exception:
            print(f"{args[0]}: could not change directory")
        return
    try:
        os.chdir(args[1])
    except FileNotFoundError:
        print(f"{args[0]}: {args[1]}: No such file or directory")


def builtInHistory(args):
    # Check if a limit argument is provided
    limit = None
    if len(args) > 1:
        try:
            limit = int(args[1])
        except ValueError:
            print(f"history: {args[1]}: numeric argument required", file=sys.stderr)
            return

    # Get the commands to display
    if limit is not None:
        # Show last n commands
        commands_to_show = COMMAND_HISTORY[-limit:] if limit > 0 else []
        start_index = len(COMMAND_HISTORY) - len(commands_to_show) + 1
    else:
        # Show all commands
        commands_to_show = COMMAND_HISTORY
        start_index = 1

    # Print commands with their original indices
    for i, cmd in enumerate(commands_to_show, start=start_index):
        print(f"    {i}  {cmd}")


# ---------------- Pipeline Execution ---------------- #


def execute_pipeline(stages):
    """Execute a pipeline of commands."""
    if len(stages) == 1:
        # No pipeline, execute normally
        args = parse_command(stages[0])
        execute_command(args)
        return

    # Execute pipeline stages
    num_stages = len(stages)
    pipes = []
    pids = []

    for i in range(num_stages - 1):
        r, w = os.pipe()
        pipes.append((r, w))

    for i, stage_cmd in enumerate(stages):
        args = parse_command(stage_cmd)
        if not args:
            continue

        # Determine stdin/stdout for this stage
        stdin_fd = pipes[i-1][0] if i > 0 else None
        stdout_fd = pipes[i][1] if i < num_stages - 1 else None

        # Execute the command
        if args[0] in BUILTINS:
            # Fork for built-in to run in subprocess
            pid = os.fork()
            if pid == 0:  # Child process
                try:
                    # Set up stdin
                    if stdin_fd is not None:
                        os.dup2(stdin_fd, 0)

                    # Set up stdout
                    if stdout_fd is not None:
                        os.dup2(stdout_fd, 1)

                    # Close all pipe fds in child
                    for r, w in pipes:
                        os.close(r)
                        os.close(w)

                    # Execute built-in
                    BUILTINS[args[0]](args)
                    sys.exit(0)
                except SystemExit:
                    sys.exit(0)
                except Exception:
                    sys.exit(1)
            else:  # Parent process
                pids.append(pid)
        else:
            # External command
            exec_path = findExec(args[0])
            if not exec_path:
                print(f"{args[0]}: command not found", file=sys.stderr)
                continue

            pid = os.fork()
            if pid == 0:  # Child process
                # Set up stdin
                if stdin_fd is not None:
                    os.dup2(stdin_fd, 0)

                # Set up stdout
                if stdout_fd is not None:
                    os.dup2(stdout_fd, 1)

                # Close all pipe fds in child
                for r, w in pipes:
                    os.close(r)
                    os.close(w)

                # Execute external command
                os.execv(exec_path, [args[0]] + args[1:])
            else:  # Parent process
                pids.append(pid)

    # Close all pipes in parent
    for r, w in pipes:
        os.close(r)
        os.close(w)

    # Wait for all child processes
    for pid in pids:
        os.waitpid(pid, 0)


# ---------------- Command Execution ---------------- #


def execute_command(args):
    if not args:
        return

    # ----- Handle redirection ----- #
    stdout_file = None
    stdout_mode = "w"
    stderr_file = None
    stderr_mode = "w"
    cleaned_args = []

    i = 0
    while i < len(args):
        token = args[i]
        if token in (">", "1>"):
            if i + 1 < len(args):
                stdout_file = args[i + 1]
                stdout_mode = "w"
                i += 2
            else:
                print("syntax error: expected file after >", file=sys.stderr)
                return
        elif token in (">>", "1>>"):
            if i + 1 < len(args):
                stdout_file = args[i + 1]
                stdout_mode = "a"
                i += 2
            else:
                print("syntax error: expected file after >>", file=sys.stderr)
                return
        elif token == "2>":
            if i + 1 < len(args):
                stderr_file = args[i + 1]
                stderr_mode = "w"
                i += 2
            else:
                print("syntax error: expected file after 2>", file=sys.stderr)
                return
        elif token == "2>>":
            if i + 1 < len(args):
                stderr_file = args[i + 1]
                stderr_mode = "a"
                i += 2
            else:
                print("syntax error: expected file after 2>>", file=sys.stderr)
                return
        else:
            cleaned_args.append(token)
            i += 1

    args = cleaned_args
    if not args:
        return

    # ----- Builtins ----- #
    if args[0] in BUILTINS:
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        f_stdout = f_stderr = None
        try:
            if stdout_file:
                f_stdout = open(stdout_file, stdout_mode)
                sys.stdout = f_stdout
            if stderr_file:
                f_stderr = open(stderr_file, stderr_mode)
                sys.stderr = f_stderr

            BUILTINS[args[0]](args)

        finally:
            if f_stdout:
                f_stdout.close()
                sys.stdout = old_stdout
            if f_stderr:
                f_stderr.close()
                sys.stderr = old_stderr
        return

    # ----- External commands ----- #
    exec_path = findExec(args[0])
    if exec_path:
        try:
            f_stdout = open(stdout_file, stdout_mode) if stdout_file else None
            f_stderr = open(stderr_file, stderr_mode) if stderr_file else None

            subprocess.run(
                [args[0]] + args[1:],
                executable=exec_path,
                stdout=f_stdout,
                stderr=f_stderr,
            )
        except Exception as e:
            print(f"Error running {args[0]}: {e}", file=sys.stderr)
        finally:
            if f_stdout:
                f_stdout.close()
            if f_stderr:
                f_stderr.close()
    else:
        print(f"{args[0]}: command not found", file=sys.stderr)


# ---------------- Command Parsing ---------------- #


def parse_pipeline(command):
    """Split command into pipeline stages by '|' (respecting quotes)."""
    stages = []
    current = []

    in_single_quote = False
    in_double_quote = False

    i = 0
    while i < len(command):
        ch = command[i]

        # Backslash handling
        if ch == "\\" and not in_single_quote:
            current.append(ch)
            i += 1
            if i < len(command):
                current.append(command[i])
            i += 1
            continue

        # Quote toggles
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            current.append(ch)
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            current.append(ch)
        # Pipe separator (only outside quotes)
        elif ch == '|' and not in_single_quote and not in_double_quote:
            if current:
                stages.append(''.join(current).strip())
                current = []
        else:
            current.append(ch)

        i += 1

    if current:
        stages.append(''.join(current).strip())

    return stages


def parse_command(command):
    args = []
    current = []

    in_single_quote = False
    in_double_quote = False

    i = 0
    while i < len(command):
        ch = command[i]

        # Backslash outside quotes
        if ch == "\\" and not in_single_quote and not in_double_quote:
            i += 1
            if i < len(command):
                current.append(command[i])

        # Backslash inside double quotes (only escapes " and \)
        elif ch == "\\" and in_double_quote:
            if i + 1 < len(command) and command[i + 1] in ['"', "\\"]:
                i += 1
                current.append(command[i])
            else:
                current.append(ch)

        # Single quote toggle
        elif ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote

        # Double quote toggle
        elif ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote

        # Whitespace separator (only outside quotes)
        elif ch.isspace() and not in_single_quote and not in_double_quote:
            if current:
                args.append("".join(current))
                current = []

        # Normal character
        else:
            current.append(ch)

        i += 1

    if current:
        args.append("".join(current))

    return args


# ---------------- Builtins Map ---------------- #
BUILTINS = {
    "exit": builtInExit,
    "echo": builtInEcho,
    "type": builtInType,
    "pwd": builtInPWD,
    "cd": builtInCD,
    "history": builtInHistory,
}

# ---------------- Autocompletion --------------#
# Variables to track completion state
last_tab_text = ""
last_tab_matches = []
last_tab_count = 0


def get_executable_matches(text):
    """Find all executables in PATH that match the given prefix."""
    matches = []

    # First, check builtins
    for cmd in BUILTINS.keys():
        if cmd.startswith(text):
            matches.append(cmd)

    # Then check executables in PATH
    path_dirs = os.environ.get("PATH", "").split(":")
    for dir_path in path_dirs:
        if not dir_path:
            continue

        # Use glob to find all files in the directory
        try:
            for file_path in glob.glob(os.path.join(dir_path, "*")):
                if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                    cmd_name = os.path.basename(file_path)
                    if cmd_name.startswith(text) and cmd_name not in matches:
                        matches.append(cmd_name)
        except Exception:
            # Skip directories we can't access
            pass

    return sorted(matches)


def get_longest_common_prefix(strings):
    """Get the longest common prefix of a list of strings."""
    if not strings:
        return ""
    if len(strings) == 1:
        return strings[0]

    prefix = strings[0]
    for string in strings[1:]:
        # Find the length of common prefix
        length = 0
        for i, (c1, c2) in enumerate(zip(prefix, string)):
            if c1 != c2:
                break
            length = i + 1

        # Update prefix to common part
        prefix = prefix[:length]
        if not prefix:
            break

    return prefix


def auto_complete(text, state):
    """Custom tab completion function for readline."""
    global last_tab_text, last_tab_matches, last_tab_count

    # Split the line to get the current command/args
    line = readline.get_line_buffer()

    # First word (command) completion
    if not line.strip() or " " not in line.lstrip():
        # New completion attempt or different text
        if text != last_tab_text:
            last_tab_text = text
            last_tab_matches = get_executable_matches(text)
            last_tab_count = 0

        # No matches
        if not last_tab_matches:
            last_tab_count = 0
            return None

        # Single match - complete with trailing space
        if len(last_tab_matches) == 1:
            if state == 0:
                return last_tab_matches[0] + " "
            return None

        # Multiple matches - try to complete to longest common prefix immediately
        longest_prefix = get_longest_common_prefix(last_tab_matches)
        if len(longest_prefix) > len(text):
            # If completing yields a single exact match, add trailing space
            # (e.g., when only one candidate remains after completion)
            remaining = [m for m in last_tab_matches if m.startswith(longest_prefix)]
            if len(remaining) == 1 and state == 0:
                return remaining[0] + " "
            if state == 0:
                return longest_prefix
            return None

        # If LCP doesn't extend the text, fall back to bell/list behavior
        if last_tab_count == 0:
            last_tab_count += 1
            if state == 0:
                sys.stdout.write("\a")  # Ring bell
                sys.stdout.flush()
                return text
            return None

        # Second tab press - display all matches
        if last_tab_count == 1:
            if state == 0:
                print()  # New line
                print("  ".join(last_tab_matches))
                # Reprint prompt and current text (include leading "$ ")
                sys.stdout.write(f"$ {text}")
                sys.stdout.flush()
                last_tab_count = 2
                return text
            return None

        # Subsequent tabs: try to cycle through matches
        return last_tab_matches[state] if state < len(last_tab_matches) else None

    # Multiple word completion (not implemented yet)
    if state == 0:
        return text
    return None


# ---------------- Main Loop ---------------- #


def main():
    readline.set_completer(auto_complete)
    readline.parse_and_bind("tab: complete")
    while True:
        try:
            sys.stdout.write("$ ")
            sys.stdout.flush()
            command = input().strip()
        except EOFError:
            break

        if not command:
            continue

        # Add command to history
        COMMAND_HISTORY.append(command)
        readline.add_history(command)

        # Check if command contains pipeline
        stages = parse_pipeline(command)
        if len(stages) > 1:
            execute_pipeline(stages)
        else:
            args = parse_command(command)
            execute_command(args)


if __name__ == "__main__":
    main()
