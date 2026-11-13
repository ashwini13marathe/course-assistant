---
name: submit-hw
audience: student
description: Use when a student wants to submit, turn in or hand in an assignment ("submit my HW3"). Checks the work against the requirements, writes a SOLUTION.md explaining the approach, then commits after approval. Not for a review without submitting (assignment-review).
---
# Submit homework

1. Work out which assignment (hwN). If files are attached, copy them into `submission/hwN/` with save_upload.
2. Call submission_status. Stop if the folder is empty or still matches the starter; say what's missing.
3. Check the timing from submission_status:
   - before the deadline: fine;
   - in the late window: state the penalty (10% per day, at most 2 days) and ask whether to submit anyway;
   - after the late window: explain that submissions are closed and stop.
4. Load `assignment-review/hwN` and walk its checklist against the code. List anything unmet, one line each. Don't fix code; ask whether to submit anyway.
5. Draft `submission/hwN/SOLUTION.md` from the student's code:
   - **Approach**: the idea in 3–5 sentences;
   - **Complexity**: time and space for each main operation;
   - **Edge cases handled** and **known limitations**;
   - **AI use**: what the assistant helped with in this conversation (review, hints, this write-up).

   Show the draft and ask the student to confirm or correct it: it must reflect their understanding. Then save it with write_file.
6. Call commit_changes with the message "Submit hwN". The student approves on a card showing the exact diff: code and SOLUTION.md together.
7. Confirm with the commit id and the time, then remember "Submitted hwN on <date>" in their memory.
