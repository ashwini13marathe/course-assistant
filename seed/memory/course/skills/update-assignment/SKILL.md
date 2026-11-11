---
name: update-assignment
audience: professor
description: Use when the professor changes an EXISTING assignment - moves or extends the deadline, adds a note or clarification, or replaces a file ("push HW3 to Friday"). Not for publishing a new assignment.
---
# Update an assignment

## Required

- Which assignment. If unclear, ask.
- For a deadline change: the new date and time in the professor's words. If vague, ask.

## Steps

1. Find the assignment in the index. If it doesn't exist, say so and offer to publish it.
2. Resolve a new deadline against Now; a date with no time means 11:59 PM. Put the ISO value in `due` and the professor's exact words in `due_quote`.
3. A note or clarification goes in `note`, in the professor's words.
4. Call update_assignment. The approval card shows the old and new deadline.
5. Confirm in one line, and mention that students see the change when they check what's due.

## Replacing a file

For a corrected handout: save_upload the attachment over the existing file in `memory/course/assignments/hwN/`, then call update_assignment with a note saying what changed.
