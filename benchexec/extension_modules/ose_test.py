import ose
import signal


def child() -> int:
    print("Child says hi!")
    return 1


with ose.Stack(size=1024 * 1024) as stack:
    pid = ose.clone(func=child, stack=stack, flags=signal.SIGCHLD)

print("Clone returned", pid)
