import sys

INVALID_MSG = "command not found"

BUILTINS = {
    "exit": lambda code=0, *_: sys.exit(code),
    "echo": lambda *args: print(" ".join(args))
}

def commandIter(commandLineInput):
    if " " in commandLineInput:
        return commandLineInput.split(" ",1)
    else:
        return [commandLineInput,""]

def evalute(cmd, rest):
    match cmd:
        case default:
            return f'{cmd}: {INVALID_MSG}'

def replLoop():
    sys.stdout.write("$ ")
    commandLineInput = input().strip()
    cmd, rest = commandIter(commandLineInput)
    if cmd in BUILTINS:
        BUILTINS[cmd](rest)
    else:
        result = evalute(cmd, rest)
        print(result)


def main():
    while(True):
        replLoop()


if __name__ == "__main__":
    main()
