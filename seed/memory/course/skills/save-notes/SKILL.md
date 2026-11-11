---
name: save-notes
audience: student
description: Use when a student shares, pastes or attaches notes and wants them saved, filed or added to their notes ("add my notes from today's lecture"). Files them by the naming convention. Not for course materials.
---
# Save the student's notes

## Where notes go (inside memory/me/notes/)

- Lecture notes: `lectures/YYYY-MM-DD.md`, using the lecture's date.
- Notes about one assignment: `assignments/hwN.md`.
- Anything else: `general/<short-topic>.md`, lowercase with hyphens.

## Steps

1. Work out the kind and the date. "Today's lecture" is today's date; check the lecture index for a lecture on that day. If there is none, say so and ask which lecture.
2. Get the content: the pasted text, or read the attachment (`uploads/<name>`). If the attachment is binary (a PDF or an image), save it with save_upload next to where the Markdown file would go, using the same base name and its own extension.
3. If the file doesn't exist yet, create it with write_file in this layout:

   ```
   ---
   lecture: memory/course/lectures/YYYY-MM-DD.md
   title: Lecture N, <lecture title>
   ---
   # Lecture N: <lecture title> (<Weekday Mon D>)

   ## Notes (added <h:mm AM/PM>)

   <the student's notes>
   ```

   Leave out the `lecture:` line for notes that aren't about a lecture.
4. If the file exists, add a new `## Notes (added <time>)` section at the end with append_to_file (no under_heading; put the heading in the text).
5. Keep the student's words. Fix only the Markdown (bullets, line breaks). Don't add, summarize or correct content unless asked.
6. Confirm with the path.
