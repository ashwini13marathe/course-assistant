"""CS 201 HW1, alice: singly linked list."""


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
        node = _Node(value)
        if self.tail is None:
            self.head = self.tail = node
        else:
            self.tail.next = node
            self.tail = node
        self._size += 1

    def prepend(self, value):
        self.head = _Node(value, self.head)
        if self.tail is None:
            self.tail = self.head
        self._size += 1

    def find(self, value):
        node = self.head
        while node:
            if node.value == value:
                return True
            node = node.next
        return False

    def remove(self, value):
        prev, node = None, self.head
        while node:
            if node.value == value:
                if prev is None:
                    self.head = node.next
                else:
                    prev.next = node.next
                if node is self.tail:
                    self.tail = prev
                self._size -= 1
                return
            prev, node = node, node.next
        raise ValueError(f"{value!r} not in list")

    def __len__(self):
        return self._size

    def __iter__(self):
        node = self.head
        while node:
            yield node.value
            node = node.next

    def reverse(self):
        prev, node = None, self.head
        self.tail = self.head
        while node:
            node.next, prev, node = prev, node, node.next
        self.head = prev
