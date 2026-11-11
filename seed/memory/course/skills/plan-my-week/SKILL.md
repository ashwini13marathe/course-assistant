---
name: plan-my-week
audience: student
description: Use when a student asks how their week or day looks, whether they have time, when to work on something, or about clashes and workload ("how does my week look?"). Combines calendar, deadlines and free time. Not for just listing assignments (whats-due).
---
# Plan the week

1. **Range:** from Now to the end of Sunday, unless the student names another range.
2. **Study hours:** from the student's memory (for example "doesn't study after 10 PM"); otherwise 09:00 to 22:00.
3. Call list_events for the range and list_assignments with `open_only` true.
4. For each deadline in or near the range, call find_free_time from Now to that deadline with the student's study hours. Never add up hours or compare times yourself; use the totals find_free_time returns.
5. Write the week day by day, briefly: events, deadlines (marked clearly), and the free blocks worth using.
6. **Flag clashes:**
   - a deadline on a day that's mostly booked, or on the night of a big event;
   - free time before a deadline that's short or only in small scraps;
   - an exam or big event right before a deadline;
   - the professor saying an assignment is tough.
7. Propose specific study blocks (day and time) from the free time, most useful first, and offer to add them. Call add_event only after the student agrees; each event pauses for their approval.
