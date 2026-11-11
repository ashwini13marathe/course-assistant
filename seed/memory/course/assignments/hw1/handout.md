# CS 201, HW1: Linked lists

Due {{D-21|long}}, 11:59 PM.

Implement `SinglyLinkedList` in `hw1/linked_list.py` (starter code is in your branch).

## Requirements

1. `append(value)` adds to the end in O(1) time (keep a tail reference).
2. `prepend(value)` adds to the front in O(1) time.
3. `find(value)` returns True if the value is in the list.
4. `remove(value)` removes the first node holding `value`; raises `ValueError` if absent. Keep `head`, `tail` and the length correct, including when removing the only node.
5. `__len__` runs in O(1) time.
6. `__iter__` yields values from head to tail.
7. `reverse()` reverses the list in place in O(n) time and O(1) extra space.

## Notes

- Don't use Python lists to store the values.
- Test the edge cases: an empty list, a one-node list, and removing the head or the tail.
