import os
import readline
import subprocess
import sys

EXTERNAL_CACHE = {}


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
        print(f"{args[0]}: not found", file=sys.stderr)


# ---------------- Command Parsing ---------------- #


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
}

# ---------------- Autocompletion --------------#
# Variables to track completion state
last_tab_text = ""
last_tab_matches = []
last_tab_count = 0


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
    matches = [command + " " for command in BUILTINS.keys()
               if command.startswith(text)]
    # custom executables autocompletion
    for path in os.environ["PATH"].split(os.pathsep):
        if os.path.isdir(path):
            for file in os.listdir(path):
                if file.startswith(text) and os.access(
                    os.path.join(path, file), os.X_OK
                ):
                    matches.append(file + " ")

    # Multiple matches
    if last_tab_count == 0:
        # First tab press - increment counter, ring bell, return the text
        last_tab_count += 1
        if state == 0:
            sys.stdout.write('\a')  # Ring bell
            sys.stdout.flush()
            return text
        return None
    else:
        # Second tab press - display all matches
        if state == 0:
            print()  # New line
            print("  ".join(last_tab_matches))
            sys.stdout.write(f"$ {text}")
            sys.stdout.flush()
            return text

        # Complete to longest common prefix
        longest_prefix = get_longest_common_prefix(last_tab_matches)
        if len(longest_prefix) > len(text) and state == 0:
            return longest_prefix

    return matches[state] if state < len(matches) else None


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

        args = parse_command(command)
        execute_command(args)


if __name__ == "__main__":
    main()
