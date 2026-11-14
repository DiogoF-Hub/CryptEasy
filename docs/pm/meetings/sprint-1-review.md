# Meeting: sprint 1 review

**Date:** Sat Nov 14, 2026 (Discord, 30 min)
**Attendees:** Diogo · Sam · Yanis · Yani
**Notes by:** Yani

---

## 1. Sprint goal

> The app's core works: a real encrypt → decrypt runs from source.

Reached / partly / not reached: **partly**. Keys and KDF work; #8 (hybrid encryption / decryption) is in progress, Diogo finishes it this weekend.

## 2. Done this sprint

| Issue | Who | Estimate (h) | Actual (h) | Note |
|---|---|---|---|---|
| #2 Re-plan: planning v2 and board | Diogo | 2 | 3 | |
| #3 Set up `docs/pm/` | Diogo | 1 | 1.5 | |
| #4 Sprint 1 kick-off | team | 0.5 | 1 | |
| #6 core: key generation | Diogo | 4 | 3 | |
| #7 core: KDF and security levels | Diogo | 3 | 2 | |
| #9 core: zip a folder, safe extraction | Yani | 3 | 3 | taken over from Diogo on Nov 10, PR #51 waiting for review |
| #14 Interface PR into `main` | Yanis | 0.5 | 1 | |
| #15 Report: Word skeleton | Yani | 2 | 2 | |
| #16 Report: gather the facts | Yani | 2 | 1 |
| #17 Sprint 1 review (this meeting) | team | 0.5 | 0.5 | | |
| **Total** | | **18.5** | **18** | 3 % under the estimate overall |

## 3. Not done (moved to sprint 2)

| Issue | Who | Why |
|---|---|---|
| #8 core: hybrid encryption / decryption | Diogo | in progress, finished this weekend (still sprint 1) |
| #10 core: unit tests | Diogo | **moved to sprint 2**: Diogo had too much this week |
| #11, #12, #13 keystore + tests | Sam | in progress (PR #50), finished this weekend (still sprint 1) |

## 4. Retrospective

- **What went well:** once the work started, it ran smoothly. The organisation is good (sprints, board, PRs): we keep it as it is.
- **What went badly:** the workload was not split evenly between the weeks. Sprint 1 (school week) had more tasks than sprint 2 (company week), so Diogo was overloaded: #9 went to Yani and #10 moved to sprint 2. PRs waiting for review were not seen as a problem: reviews matter for the big steps.
- **What we change for sprint 2:** keep the same organisation; Diogo adds a board view by status to move tasks more easily.

## 5. Decisions

Also add them to [decisions.md](../decisions.md).

- #10 moves to sprint 2 (Diogo)
- #8 (Diogo) and #11 to #13 (Sam) are finished this weekend
- Diogo adds a board view by status (Todo / In Progress / Done)
- next meeting: **Sun Nov 22, 2 pm** (sprint 2 review + code freeze, #27)

## 6. Risks

Anything new, or a risk that happened? Update [risks.md](../risks.md).

- **R6 (new):** #8 is essential for sprint 2 (#21 and the exe depend on it). Not seen as a real risk by the team, as long as everyone does their tasks: Diogo finishes it this weekend

## 7. Sprint 2: who does what

Sprint 2 goal: the Windows exe is built and tested. **Code freeze on Sunday Nov 22.**

| Who | Main tasks |
|---|---|
| Diogo | core unit tests (#10, from sprint 1), README and DEV_README (#26) |
| Sam | Windows exe (#18), CI build and `v1.0.0rc1` release (#19), Linux binary if time (#20) |
| Yanis | plug in the real `core/` and `keystore/` (#21), Info page (#22) |
| Yani | manual tests checklist (#23), test the exe (#24), proofread translations (#25) |
