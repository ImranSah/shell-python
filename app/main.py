import os
import sys

INVALID_MSG = "command not found"
NOTFOUND = "not found"
BUILTINS_LIST = ["exit", "echo", "type"]

# Split the command line input into command and arguments
def commandIter(commandLineInput):
    if " " in commandLineInput:
        return commandLineInput.split(" ",1)
    else:
        return [commandLineInput,""]

# Evaluate the command and return the result
def evalute(cmd, rest):
    match cmd:
        case "exit":
            sys.exit()
        case "echo":
            return f'{rest}'
        case "type":
            if rest in BUILTINS_LIST:
                return f'{rest} is a shell builtin'
            else:
                for d in os.environ["PATH"].split(os.pathsep):
                    p = os.path.join(d, rest)
                    if os.access(p, os.X_OK):
                        return f"{rest} is {p}"

                # if not found, return not found
                return f'{rest}: {NOTFOUND}'
        case _:
            return f'{rest}: {INVALID_MSG}'

# Main loop for the shell
def replLoop():
    sys.stdout.write("$ ")
    user_input = input().strip()
    cmd, rest = commandIter(user_input)
    result = evalute(cmd, rest)
    print(result)


# Main function to run the shell
def main():
    while(True):
        replLoop()


if __name__ == "__main__":
    main()
