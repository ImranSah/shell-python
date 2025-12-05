import sys

INVALID_MSG = "command not found"

def printMsg(arg):
    print(f'{arg}: {INVALID_MSG}')

def main():
    # TODO: Uncomment the code below to pass the first stage
    sys.stdout.write("$ ")
    cmdInput = input()

    printMsg(cmdInput)

    pass


if __name__ == "__main__":
    main()
