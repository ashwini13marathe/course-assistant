# CS 201, HW2: Stacks and queues

Due {{D-7|long}}, 11:59 PM.

Work in `hw2/stack_queue.py` (starter code is in your branch).

## Requirements

1. `ArrayStack` with `push`, `pop`, `peek`, `is_empty` and `__len__`. `pop` and `peek` on an empty stack raise `IndexError`.
2. `TwoStackQueue` with `enqueue`, `dequeue`, `is_empty` and `__len__`, built from two `ArrayStack`s only. `dequeue` must be amortized O(1). `dequeue` on an empty queue raises `IndexError`.
3. `balanced(text)` returns True when every `()`, `[]` and `{}` in `text` is matched and properly nested, using your `ArrayStack`.
4. A comment explaining why `dequeue` is amortized O(1).
