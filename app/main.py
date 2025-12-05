import sys

INVALID_MSG = "command not found"

def evalute(cmd):
    match cmd:
        case "exit":
            sys.exit()
        case default:
            return f'{cmd}: {INVALID_MSG}'

def replLoop():
    sys.stdout.write("$ ")
    cmd = input().strip()
    result = evalute(cmd)
    print(result)


def main():
    while(True):
        replLoop()


if __name__ == "__main__":
    main()
