---
name: hints/hw1
description: Three hint levels for HW1 (Linked lists). Served one level at a time by get_hint; never shown whole to students.
audience: student
---
# HW1 hints

## Level 1 (nudge)

Draw a three-node list on paper. For `reverse`, what does each node's `next` need to point at when you're done, and what would you lose if you changed it too early?

## Level 2 (approach)

Walk the list once with three references: the previous node, the current node and the next node. Save the next node before you redirect the current node's `next`.

## Level 3 (near-pseudocode)

Set previous to nothing and current to the head; remember the old head as the new tail. While current exists: save current's next, point current's next at previous, move previous to current, move current to the saved next. Finally, the head is previous.
