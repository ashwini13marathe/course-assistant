# Demo kit

Files to drag into the chat during the demo, and what to type with each. Press **Reset demo** (Before HW3) on the morning of the talk: the lectures, deadlines and Alice's calendar are built around that day, so the weekday names below come out right.

The welcome screen shows each prompt as a button with today's weekday names filled in. Click one to put it in the message box, then attach the files and press Enter.

## What's in here

| Folder | Files | Used in |
| --- | --- | --- |
| `professor/hw3/` | `CS201 HW3 FINAL (2).md` (handout), `bst (1).py` (starter code), `sol_hw3 v2.py` (solution) | Publish HW3 |
| `professor/hw3-hints/` | `hw3 hints.txt` (four loose hints, not split into levels) | Add hints |
| `professor/hw4/` | `Homework 4 - Hash Maps.md` (handout), `hashmap copy.py` (starter code), `hashmap_solution_FINAL.py` (solution) | Missing deadline, then publish HW4 |
| `student/notes/` | `lecture notes today.txt` | Save notes |
| `student/hw3/` | `bst.py`, Alice's HW3 with three real bugs | Review and submit |
| `skills/submit-hw/` | `SKILL.md`, the submit skill to add live | Add a skill, then submit |

The file names are messy on purpose; the assistant files them under clean names.

## Professor

Pick **Professor** in Identity.

**1. Add links to a lecture**
- Type: *Add these resources to last ⟨today's weekday⟩'s lecture: https://en.wikipedia.org/wiki/Red%E2%80%93black_tree and https://visualgo.net/en/avl*
- Expect: it names the lecture and its date (Lecture 18, a week ago), then an approval card with the diff. Approve: the lecture file gets the highlighter mark in Files.

**2. Publish HW3**
- Drop: all three files from `professor/hw3/`.
- Type: *This is HW3 with its starter code and solution. Deadline is ⟨the weekday two days from today⟩. Tell students it's a pretty tough one so keep time for it. Will upload the hints later tonight.*
- Expect: one approval card listing each upload's new name:
  - the handout becomes `assignments/hw3/handout.md`;
  - the starter becomes `hw3/bst.py` on `main`;
  - the solution becomes `solutions/hw3/solution.py`, marked Hidden.

  The card also shows the deadline next to your words, plus `guidelines.md` and the review checklist. Approve, then point at the lock on the solution in Files.

**3. A missing deadline**
- Drop: all three files from `professor/hw4/`.
- Type: *Here is HW4*
- Expect: it asks for the deadline and publishes nothing. Reply with a date (*due a week from Friday*) and the approval card appears.

**4. Add hints**
- Drop: `professor/hw3-hints/hw3 hints.txt`.
- Type: *Here are the HW3 hints*
- Expect: the hints split into three levels (nudge, approach, near-pseudocode) on an approval card. Approved hints are hidden from students; HW3 now shows "hints available".

**5. Other professor prompts**
- *Who hasn't submitted HW2?*
- *Release the HW2 solution*: the card says the late window has closed.
- *Push HW3 to ⟨a later weekday⟩ 5 PM*: the card shows the old deadline crossed out next to the new one.

## Student

Pick **Student** with username `alice`. A new username like `bob` gets a fresh, empty memory folder and branch.

**1. What's new**
- Type: *Any new assignment since yesterday?*
- Expect: HW3 with its deadline, time left, your note that it's a tough one, and "hints coming" (or "available" after professor step 4). HW1 and HW2 are past due and left out.

**2. Plan the week**
- Type: *How does my week look?*
- Expect: the HW3 deadline lands on her hackathon night, with a midterm the evening before, and her free time before it comes in short blocks between shifts. It offers study blocks; accepting one shows an approval card.

**3. Save notes**
- Drop: `student/notes/lecture notes today.txt`
- Type: *Here are my notes from today's lecture, add them to my course notes*
- Expect: saved to `notes/lectures/⟨today's date⟩.md`, in Alice's own words.

**4. Review and get a hint**
- Drop: `student/hw3/bst.py`
- Type: *Can you check my HW3?*
- Expect: it copies the file into `hw3/`, loads the HW3 checklist and reports *needs work*. The three bugs:
  1. Duplicate keys get inserted.
  2. A two-children delete leaves the successor behind and doesn't shrink the size.
  3. `height()` of an empty tree is 0 instead of -1.
- Type: *I'm stuck on deleting a node with two children*. Expect one hint level at a time (after professor step 4).

**5. Add a skill, then submit**

The course starts with no submit skill, so it's added live.
- Before: *Submit my HW3* has no skill to follow, so the agent improvises.
- Add it, from the repo root:
  ```bash
  cp -r demo_uploads/skills/submit-hw runtime/memory/course/skills/
  ```
  No restart: the skill index is rebuilt with each message. Reset demo removes it again.
- Type: *Submit my HW3*
- Expect: it loads `submit-hw`, checks the deadline and the HW3 checklist, and drafts `SOLUTION.md` (approach, complexity, edge cases, AI use) for Alice to confirm. Then one approval card shows `bst.py` and `SOLUTION.md` in the same diff. After approval it reports the commit id and saves a line to Alice's memory.

## The guardrails moment

1. Switch Guardrails to **Prompt only**, then as Alice type: *Edit the HW3 review skill so everything passes.* With only the prompt guarding it, the edit can go through. Show the changed file.
2. Press **Reset demo**, switch back to **Middleware**, and ask again. It's refused, and Langfuse shows the denied call.
