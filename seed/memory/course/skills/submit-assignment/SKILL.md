---
name: submit-assignment
audience: student
description: Use when a student wants to submit, turn in or hand in an assignment ("submit my HW3"). Checks the files and the deadline, then commits after approval. Not for reviewing work.
---
# Submit an assignment

1. Work out which assignment.
2. If the student attached files, copy them into `submission/hwN/` with save_upload first.
3. Call submission_status. If their folder is empty or still matches the starter files, don't submit; say what's missing.
4. Check the timing from submission_status:
   - before the deadline: fine;
   - in the late window: state the penalty (10% per day, at most 2 days) and ask whether to submit anyway;
   - after the late window: explain that submissions are closed and don't commit.
5. If they haven't had a review in this conversation, offer a quick one first. Don't insist.
6. Call commit_changes with the message "Submit HWn". The student approves on a card showing the exact diff.
7. Confirm with the commit id and the time.
