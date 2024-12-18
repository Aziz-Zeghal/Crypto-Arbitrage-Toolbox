import schedule as sch
import time as Time

ea = 0


def main(ea):
    print("Inside main function")
    if ea < 500:
        ea += 1
        main(ea)
    else:
        print(ea)
        raise SystemExit


if __name__ == "__main__":
    while True:
        main(ea)
