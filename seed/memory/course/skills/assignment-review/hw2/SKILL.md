---
name: assignment-review/hw2
description: Review checklist for HW2 (Stacks and queues). Loaded by assignment-review; not used on its own.
audience: student
---
# HW2 review checklist

- [ ] `ArrayStack` has push, pop, peek, is_empty and `__len__`.
- [ ] `pop` and `peek` raise `IndexError` on an empty stack.
- [ ] `TwoStackQueue` uses two `ArrayStack`s and nothing else to hold items.
- [ ] `dequeue` only moves items between stacks when the outgoing stack is empty (amortized O(1)).
- [ ] `dequeue` raises `IndexError` on an empty queue.
- [ ] `balanced` uses `ArrayStack`, handles all three bracket types, rejects wrong nesting like `([)]`, and rejects leftovers like `((`.
- [ ] A comment explains why `dequeue` is amortized O(1).
