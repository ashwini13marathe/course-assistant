"""CS 201 HW2: stacks and queues. Fill in every method marked TODO."""


class ArrayStack:
    def __init__(self):
        self._data = []

    def push(self, item):
        raise NotImplementedError  # TODO

    def pop(self):
        raise NotImplementedError  # TODO

    def peek(self):
        raise NotImplementedError  # TODO

    def is_empty(self):
        raise NotImplementedError  # TODO

    def __len__(self):
        raise NotImplementedError  # TODO


class TwoStackQueue:
    # TODO: explain why dequeue is amortized O(1)
    def __init__(self):
        self._inbox = ArrayStack()
        self._outbox = ArrayStack()

    def enqueue(self, item):
        raise NotImplementedError  # TODO

    def dequeue(self):
        raise NotImplementedError  # TODO

    def is_empty(self):
        raise NotImplementedError  # TODO

    def __len__(self):
        raise NotImplementedError  # TODO


def balanced(text):
    raise NotImplementedError  # TODO
