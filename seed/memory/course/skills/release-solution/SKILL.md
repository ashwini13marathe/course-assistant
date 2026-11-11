---
name: release-solution
audience: professor
description: Use when the professor wants students to see a solution or another hidden course file ("release the HW2 solution", "make that visible"). Checks the deadline and late window first. Not for hiding files (call set_student_access with "hidden" directly).
---
# Release a hidden file

1. Identify the file or folder. A solution lives at `memory/course/solutions/hwN`.
2. For a solution, check the assignment's deadline in the index. Students can still submit until the deadline plus 2 days (late policy in COURSE.md).
   - If that window hasn't closed yet, tell the professor exactly when it closes and ask whether to release anyway. Continue only if they confirm.
3. Call set_student_access with the path and `read`. The approval card shows whether the late window has closed.
4. Confirm what students can now see.
