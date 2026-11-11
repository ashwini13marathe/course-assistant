---
name: assignment-review/hw1
description: Review checklist for HW1 (Linked lists). Loaded by assignment-review; not used on its own.
audience: student
---
# HW1 review checklist

- [ ] `append` is O(1): uses a tail reference, no walk to the end.
- [ ] `prepend` is O(1) and sets `tail` when the list was empty.
- [ ] `find` returns True/False and handles an empty list.
- [ ] `remove` deletes only the first match and raises `ValueError` when absent.
- [ ] `remove` keeps `head`, `tail` and the length right when removing the head, the tail, or the only node.
- [ ] `__len__` is O(1) (a counter, not a walk).
- [ ] `__iter__` yields values from head to tail.
- [ ] `reverse` works in place, O(n) time, O(1) extra space, and updates `tail`.
- [ ] No Python list is used to store the values.
