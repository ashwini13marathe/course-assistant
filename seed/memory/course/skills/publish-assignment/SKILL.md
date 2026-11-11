---
name: publish-assignment
audience: professor
description: Use when the professor uploads, posts or announces a NEW assignment or homework, with or without files ("here is HW3 and its solution"). Files the uploads by convention and publishes with a deadline. Not for changing an existing assignment (update-assignment) or adding hints (add-hints).
---
# Publish an assignment

## Required before publishing

1. **Assignment number** (hw1, hw2, ...), from the message or the files.
2. **Deadline**: a date, ideally with a time.

If either is missing, or the deadline is vague ("next week", "soon"), ask one short question and do nothing else this turn. Never guess or default the date.

## Steps

1. Check the assignment index. If this number already exists, follow update-assignment instead.
2. Read every attachment (read_file on `uploads/<name>`). Classify each by its content, not its file name:
   - `handout`: the instructions students read.
   - `starter`: code students start from and fill in (stubs, TODOs).
   - `solution`: a complete working answer, or anything the professor calls a solution.
   If a file's role is genuinely unclear, ask.
3. Resolve the deadline against Now. A date with no time means 11:59 PM that day. Put the ISO value in `due` (`YYYY-MM-DDTHH:MM`) and copy the professor's exact words for the deadline into `due_quote` (for example `Thu Dec 3`).
4. `title`: the handout's heading topic, or the professor's words.
5. `overview`: one or two sentences on what the assignment asks, from the handout.
6. `professor_notes`: what the professor wants students to know, in their own words, lightly tidied (for example "This is a pretty tough one, so keep time to work on it. Hints will be uploaded tonight."). Add no advice of your own.
7. `hints_status`: `coming` if the professor says hints will follow, otherwise `none`.
8. `review_checklist`: a Markdown checklist of what a correct submission must do, from the handout's requirements. Use the solution only to understand them. Requirements only: no solution code and no key trick.
9. Call publish_assignment once with all of the above. The professor approves it on a card showing the new file names, so don't ask "shall I?" first.

## After publishing

Reply in two or three lines: where each file went, the deadline used, and that students can see it now while the solution stays hidden.
