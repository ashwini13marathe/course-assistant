---
name: hints/hw2
description: Three hint levels for HW2 (Stacks and queues). Served one level at a time by get_hint; never shown whole to students.
audience: student
---
# HW2 hints

## Level 1 (nudge)

A stack reverses order. What happens to the order of items if you reverse them twice?

## Level 2 (approach)

Use one stack for arriving items and one for leaving items. Only move items across when the leaving stack is empty, and move all of them at once.

## Level 3 (near-pseudocode)

Enqueue pushes onto the inbox. Dequeue: if the outbox is empty, pop every item from the inbox and push it onto the outbox; then, if the outbox is still empty, raise IndexError; otherwise pop from the outbox.
