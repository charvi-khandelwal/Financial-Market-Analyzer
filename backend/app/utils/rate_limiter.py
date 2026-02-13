import time
from collections import deque

class MinuteRateLimiter:
    def __init__(self, max_calls_per_minute: int):
        self.max_calls = max_calls_per_minute
        self.calls = deque()

    def acquire(self):
        now = time.time()
        while self.calls and (now - self.calls[0]) > 60:
            self.calls.popleft()
        if len(self.calls) >= self.max_calls:
            sleep_for = 60 - (now - self.calls[0])
            if sleep_for > 0:
                time.sleep(sleep_for)
        self.calls.append(time.time())
