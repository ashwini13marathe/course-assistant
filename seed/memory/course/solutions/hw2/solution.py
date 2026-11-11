"""CS 201 HW2 reference solution: stacks and queues."""


class ArrayStack:
    def __init__(self):
        self._data = []

    def push(self, item):
        self._data.append(item)

    def pop(self):
        if not self._data:
            raise IndexError("pop from empty stack")
        return self._data.pop()

    def peek(self):
        if not self._data:
            raise IndexError("peek at empty stack")
        return self._data[-1]

    def is_empty(self):
        return not self._data

    def __len__(self):
        return len(self._data)


class TwoStackQueue:
    # Each item is pushed onto `inbox` once, moved to `outbox` at most once and
    # popped once, so n operations cost O(n) in total: amortized O(1) each.
    def __init__(self):
        self._inbox = ArrayStack()
        self._outbox = ArrayStack()

    def enqueue(self, item):
        self._inbox.push(item)

    def dequeue(self):
        if self._outbox.is_empty():
            while not self._inbox.is_empty():
                self._outbox.push(self._inbox.pop())
        if self._outbox.is_empty():
            raise IndexError("dequeue from empty queue")
        return self._outbox.pop()

    def is_empty(self):
        return self._inbox.is_empty() and self._outbox.is_empty()

    def __len__(self):
        return len(self._inbox) + len(self._outbox)


PAIRS = {")": "(", "]": "[", "}": "{"}


def balanced(text):
    stack = ArrayStack()
    for ch in text:
        if ch in "([{":
            stack.push(ch)
        elif ch in PAIRS:
            if stack.is_empty() or stack.pop() != PAIRS[ch]:
                return False
    return stack.is_empty()
