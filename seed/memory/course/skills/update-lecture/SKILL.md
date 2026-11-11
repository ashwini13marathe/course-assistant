---
name: update-lecture
audience: professor
description: Use when the professor adds or changes lecture material (links, readings, slides, a summary) for a lecture named by date, weekday or number ("last Tuesday's lecture", "lecture 14"). Not for assignments.
---
# Add material to a lecture

1. **Find the lecture.** Resolve the date against Now:
   - "today's lecture" is today's date;
   - "last Tuesday" is the most recent Tuesday before today (if today is Tuesday, the one 7 days ago);
   - "Thursday's lecture" with no qualifier is the most recent past Thursday;
   - a number maps through the lecture index.
2. Look it up in the lecture index (`memory/course/lectures/YYYY-MM-DD.md`). If there is no lecture on that date, say so, name the nearest lectures before and after, and ask which one. Don't create a new lecture file unless asked.
3. Read the lecture file.
4. **Links:** one bullet each, `- [Title](url)`, under the `Resources` heading. Use the professor's title if given, otherwise a short descriptive title from the URL. Skip any URL already listed.
5. **Summary or notes:** append under `Summary` unless the professor asks to replace it.
6. Call append_to_file with `under_heading` set to `Resources` (or `Summary`). Put all the new bullets in one call. The professor approves the change on a card.
7. Confirm with the lecture's number and absolute date, what you added, and anything skipped as a duplicate.
