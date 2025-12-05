import sys

INVALID_MSG = "command not found"

def commandIter(commandLineInput):
    if " " in commandLineInput:
        return commandLineInput.split(" ",1)
    else:
        return [commandLineInput,""]

def evalute(commandLineInput):
    cmd, rest = commandIter(commandLineInput)
    match cmd:
        case "echo":
            return rest
        case "exit":
            sys.exit()
        case default:
            return f'{cmd}: {INVALID_MSG}'

def replLoop():
    sys.stdout.write("$ ")
    commandLineInput = input().strip()
    result = evalute(commandLineInput)
    print(result)


def main():
    while(True):
        replLoop()


if __name__ == "__main__":
    main()
