import sys

INVALID_MSG = "command not found"
NOTFOUND = "not found"

BUILTINS = {
    "exit": lambda code=0, *_: sys.exit(),
    "echo": lambda *args: print(" ".join(args)),
    "type" : lambda *args: print(f'{" ".join(args)} is a shell builtin') if len(args)>0 and args[0] in BUILTINS else print(f'{" ".join(args)}: {NOTFOUND}'),
    "invalidCmd":lambda *args: print(f'{" ".join(args)}: {NOTFOUND}')
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
