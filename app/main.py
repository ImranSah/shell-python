import os
import subprocess
import sys
import shlex

INVALID_MSG = "command not found"
NOTFOUND = "not found"
BUILTINS_LIST = ["exit", "echo", "type"]

# Split the command line input into command and arguments
def commandIter(commandLineInput):
    if " " in commandLineInput:
        split_command, rest = commandLineInput.split(" ",1)
        # split the rest into a list of strings, preserving quotes
        in_quotes = shlex.split(rest)
        return [split_command, in_quotes]
    else:
        return [commandLineInput,[]]

# execute external command
def externalCommand(cmd, rest):
    for d in os.environ["PATH"].split(os.pathsep):
        p = os.path.join(d, cmd)
        if os.access(p, os.X_OK):
            return subprocess.run(f'{cmd} {" ".join(rest)}', shell=True, capture_output=True, text=True).stdout
    return None

# Evaluate the command and return the result
def evalute(cmd, rest):
    match cmd:
        case "exit":
            sys.exit()
        case "echo":
            return f'{" ".join(rest)}'
        case "type":
            if rest in BUILTINS_LIST:
                return f'{" ".join(rest)} is a shell builtin'
            else:
                for d in os.environ["PATH"].split(os.pathsep):
                    p = os.path.join(d, " ".join(rest))
                    if os.access(p, os.X_OK):
                        return f'{" ".join(rest)} is {p}'

                # if not found, return not found
                return f'{" ".join(rest)}: {NOTFOUND}'
        case _:
            result = externalCommand(cmd, rest)
            if result is not None:
                # remove the last newline character
                return result.rstrip('\n')
            else:
                return f'{cmd}: {INVALID_MSG}'

# Main loop for the shell
def replLoop():
    sys.stdout.write("$ ")
    user_input = input().strip()
    # cmd: String, rest: List[String]
    cmd, rest = commandIter(user_input)
    result = evalute(cmd, rest)
    print(result)


# Main function to run the shell
def main():
    while(True):
        replLoop()


if __name__ == "__main__":
    main()
