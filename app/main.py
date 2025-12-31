import os
import shlex
import subprocess
import sys


def handle_echo(args):
    return " ".join(args)


def handle_type(args):
    if not args:
        return "type: missing argument"

    cmd = args[0]
    if cmd in ["echo", "type", "exit", "pwd"]:
        return f"{cmd} is a shell builtin"
    else:
        found_path = find_executable(cmd)
        if found_path:
            return f"{cmd} is {found_path}"
        else:
            return f"{cmd}: not found"


def handle_exit(args):
    sys.exit(0)


def handle_pwd(args):
    return os.getcwd()


def handle_cd(args):
    if not args:
        target_dir = os.path.expanduser("~")
    else:
        target_dir = os.path.expanduser(args[0])

    try:
        os.chdir(target_dir)
    except FileNotFoundError:
        return f"cd: {target_dir}: No such file or directory"
    except NotADirectoryError:
        return f"cd: {target_dir}: Not a directory"
    except PermissionError:
        return f"cd: {target_dir}: Permission denied"
    return None


def find_executable(filename):
    """Find executable file in PATH directories and current directory."""
    if os.path.isfile(filename) and os.access(filename, os.X_OK):
        return os.path.abspath(filename)

    # check in PATH directories
    path_dirs = os.getenv("PATH", "").split(os.pathsep)
    for directory in path_dirs:
        potential_path = os.path.join(directory, filename)
        if os.path.isfile(potential_path) and os.access(potential_path, os.X_OK):
            return potential_path
    return None


# def parse_command(command_line):
#     parts = shlex.split(command_line)
#     if not parts:
#         return None, []
#     return parts[0], parts[1:]


def parse_command(command_line):
    parts = []
    current_token = []
    i = 0

    while i < len(command_line):
        char = command_line[i]

        # Skip whitespace between tokens
        if char in " \t" and not current_token:
            i += 1
            continue

        # Whitespace ends current token (if not in quotes)
        if char in " \t":
            if current_token:
                parts.append("".join(current_token))
                current_token = []
            i += 1
            continue

        # Single quote: everything literal until closing quote
        if char == "'":
            i += 1
            while i < len(command_line) and command_line[i] != "'":
                current_token.append(command_line[i])
                i += 1
            if i >= len(command_line):
                raise ValueError("No closing quotation")
            i += 1  # Skip closing quote
            continue

        # Double quote: backslash escapes special chars
        if char == '"':
            i += 1
            while i < len(command_line) and command_line[i] != '"':
                if command_line[i] == "\\" and i + 1 < len(command_line):
                    next_char = command_line[i + 1]
                    # In double quotes, backslash escapes: \ " and also newline/tab
                    if next_char in '\\"':
                        current_token.append(next_char)
                        i += 2
                    else:
                        # Backslash is literal if not escaping special char
                        current_token.append("\\")
                        i += 1
                else:
                    current_token.append(command_line[i])
                    i += 1
            if i >= len(command_line):
                raise ValueError("No closing quotation")
            i += 1  # Skip closing quote
            continue

        # Backslash outside quotes: escapes next character
        if char == "\\":
            if i + 1 < len(command_line):
                current_token.append(command_line[i + 1])
                i += 2
            else:
                # Trailing backslash - treat as literal
                current_token.append("\\")
                i += 1
            continue

        # Regular character
        current_token.append(char)
        i += 1

    # Add final token if any
    if current_token:
        parts.append("".join(current_token))

    if not parts:
        return None, []
    return parts[0], parts[1:]


BUILTINS = {
    "echo": handle_echo,
    "type": handle_type,
    "exit": handle_exit,
    "quit": handle_exit,
    "pwd": handle_pwd,
    "cd": handle_cd,
}


def execute_command(command_line):
    cmd_name, args = parse_command(command_line)
    if cmd_name is None:
        return None

    if ">" in command_line or "1>" in command_line:
        return os.system(command_line)

    if cmd_name in BUILTINS:
        return BUILTINS[cmd_name](args)

    # Execute external command
    found_path = find_executable(cmd_name)
    if found_path:
        try:
            subprocess.run([cmd_name] + args,
                           executable=found_path, check=True)
        except subprocess.CalledProcessError as e:
            return f"Error executing command: {e}"
    else:
        return f"{cmd_name}: command not found"


def main():
    while True:
        try:
            sys.stdout.write("$ ")
            sys.stdout.flush()

            command = input()

            output = execute_command(command)

            if output is not None:
                sys.stdout.write(output + "\n")
        except EOFError:
            print("\nExiting (EOF)")
            sys.exit(0)

        except KeyboardInterrupt:
            print("\n^C")
            sys.exit(0)

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            continue


if __name__ == "__main__":
    main()
