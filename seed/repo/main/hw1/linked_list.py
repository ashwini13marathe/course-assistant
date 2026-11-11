"""CS 201 HW1: singly linked list. Fill in every method marked TODO."""


class _Node:
    __slots__ = ("value", "next")

    def __init__(self, value, next=None):
        self.value = value
        self.next = next


class SinglyLinkedList:
    def __init__(self):
        self.head = None
        self.tail = None
        self._size = 0

    def append(self, value):
        raise NotImplementedError  # TODO

    def prepend(self, value):
        raise NotImplementedError  # TODO

    def find(self, value):
        raise NotImplementedError  # TODO

    def remove(self, value):
        raise NotImplementedError  # TODO

    def __len__(self):
        raise NotImplementedError  # TODO

    def __iter__(self):
        raise NotImplementedError  # TODO

    def reverse(self):
        raise NotImplementedError  # TODO
