---
name: add-hints
audience: professor
description: Use when the professor provides hints for an assignment, typed or attached ("here are the hints for HW3"). Stores them as three levels students unlock one at a time. Not for publishing or reviewing.
---
# Add hints for an assignment

1. Identify the assignment; it must already be published. If unclear, ask.
2. Get the hints from the message or the attachment (read_file on `uploads/<name>`).
3. If the professor marked levels, keep them as given. Otherwise split them into exactly three levels:
   - **Level 1, nudge:** a question or pointer that gets the student thinking; no method.
   - **Level 2, approach:** the method or structure to use; no code.
   - **Level 3, near-pseudocode:** the steps in order; still not runnable code.
   Use only the professor's content. Don't invent hints.
4. Call save_hints with the three levels. The professor sees them on an approval card before they're saved.
5. Confirm: the hints are stored hidden, the assignment now shows "hints available", and students unlock one level at a time.
