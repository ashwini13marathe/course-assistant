---
name: whats-due
audience: student
description: Use when a student asks what's new, due, open or coming up for assignments ("any new assignment since yesterday?", "what's due?"). Lists open assignments with deadlines and the professor's notes. Not for planning time around them (plan-my-week).
---
# What's new and what's due

1. Turn the period into a timestamp for `published_after`:
   - "since yesterday" or "new" with no period: yesterday at 00:00;
   - "this week": this Monday at 00:00;
   - no mention of "new": leave `published_after` empty.
2. Call list_assignments with that `published_after` and `open_only` true. Assignments past their deadline are left out; mention them only if the student asks.
3. For each assignment, nearest deadline first:
   - number and title;
   - due as weekday, date and time, plus time left;
   - the professor's notes, keeping warnings like "this is a tough one" in substance;
   - hint status (available, or coming);
   - any deadline change from the updates.
4. If nothing is new, say so in one line and list what is still open.
5. Offer one next step if it fits, for example: "Want me to plan your week around HW3?"

Don't open the handout unless the student asks about the content.
