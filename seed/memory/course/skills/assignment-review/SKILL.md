---
name: assignment-review
audience: student
description: Use when a student asks to check, review or get feedback on their assignment work before submitting ("can you check my HW3?"). Reviews against the assignment's checklist with hints, never solutions. Not for getting unstuck without work (hints) or submitting (submit-hw).
---
# Review a student's assignment work

1. Work out which assignment. If unclear, ask.
2. Load its checklist: load_skill("assignment-review/hwN"). If there is none, say the professor hasn't published one yet.
3. **Find the work.** If the student attached files, first copy each into their submission with save_upload to `submission/hwN/` (keep the file name, unless the handout names the file). Then list_files("submission/hwN") and read the files. If the folder is empty or still matches the starter (submission_status tells you), say so and stop.
4. Go through the checklist item by item: pass, fail, or can't tell, each with a one-line reason pointing at the place in their code.
5. For each failure, describe the problem and give a hint toward the fix: a question, an edge case to try, or a concept to revisit. Never write corrected code or the solution, even if asked.
6. End with one line, either "Verdict: pass" or "Verdict: needs work (N items)". On needs work, offer a hint (hints skill) or another review after their changes.
