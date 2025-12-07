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
        return [split_command, rest]
    else:
        return [commandLineInput,""]

# execute external command
def externalCommand(cmd, rest):
    for d in os.environ["PATH"].split(os.pathsep):
        p = os.path.join(d, cmd)
        if os.access(p, os.X_OK):
            return subprocess.run(f'{cmd} {rest}', shell=True, capture_output=True, text=True).stdout
    return None

# Evaluate the command and return the result
def evalute(cmd, rest):
    match cmd:
        case "exit":
            sys.exit()
        case "echo":
            in_quotes = shlex.split(rest)
            return f'{" ".join(in_quotes)}'
        case "type":
            if rest in BUILTINS_LIST:
                return f'{rest} is a shell builtin'
            else:
                for d in os.environ["PATH"].split(os.pathsep):
                    p = os.path.join(d, rest)
                    if os.access(p, os.X_OK):
                        return f'{rest} is {p}'

                # if not found, return not found
                return f'{rest}: {NOTFOUND}'
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
