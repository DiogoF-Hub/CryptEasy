# Meeting: sprint 2 review + code freeze

**Date:** Sun Nov 22, 2026, 2 pm (Discord, 30 min)
**Attendees:** Diogo · Sam · Yanis · Yani
**Notes by:** Yani

---

## 1. Sprint goal

> The Windows exe is built and tested. Code freeze at the end of this meeting.

Reached / partly / not reached: **partly**. The exe is built (pre-release `v1.0.0rc1`), and all the other sprint 2 tasks are done. It is tested this afternoon (#24) on Windows without Python, which shows whether it really works.

## 2. Done this sprint

| Issue | Who | Estimate (h) | Actual (h) | Note |
|---|---|---|---|---|
| #10 core: unit tests | Diogo | 4 | 3 | moved from sprint 1, PR #57 (Nov 18) |
| #18 Windows exe (PyInstaller) | Sam | 6 | 3 | PR #63 (Nov 22) |
| #19 CI build and `v1.0.0rc1` release | Sam | 3 | 1 | PR #63 (Nov 22), pre-release `v1.0.0rc1` published |
| #20 Linux binary (optional) | Sam | 2 | 1 | PR #63 (Nov 22) |
| #21 Plug the real `core/` and `keystore/` into the interface | Yanis | 6 | 8 | PR #59 (Nov 19) |
| #22 Info page | Yanis | 1 | 1 | PR #59 (Nov 19) |
| #23 Manual tests checklist | Yani | 2 | 2 | PR #58 (Nov 20) |
| #25 Proofread the translations | Yani | 1 | 1 | PR #58 (Nov 20) |
| #26 README and DEV_README | Diogo | 2 | 1 | PR #64 (Nov 22) |
| #27 Sprint 2 review (this meeting) | team | 0.5 | 0.5 | |
| **Not planned, added during the sprint** | | | | |
| #55 core: refuse crafted private key files | Diogo | 1.5 | 2.5 | PR #56 (Nov 18) |
| #60 core: clear errors for crafted packages and folder zips | Diogo, Yani | 1.5 | 3 | found while reviewing PR #59; PR #61 (Diogo, Nov 20), PR #62 (Yani, Nov 22) |
| **Total** | | **30.5** | **27** | actual times completed from the board on Nov 24. Not in this table: #24 (3 h estimated, 5 h actual, finished on Nov 23). Whole sprint on the board, #24 included: 33.5 h estimated, 32 h actual (−4 %) |

Sprint 1 leftovers, finished on Nov 14 as decided at the sprint 1 review: #8 hybrid encryption (Diogo, PR #52) and #11 to #13 keystore (Sam, PR #50).

## 3. Not done (moved to sprint 3)

| Issue | Who | Why |
|---|---|---|
| #24 Test the exe | Yani | the exe was only available on Nov 22 and Yani wasn't available then: done this afternoon (still sprint 2), on Windows without Python, and the Linux binary in VMs on Ubuntu 22.04, Ubuntu 26.04 and Debian |

## 4. Bugs

Open bugs found by the manual tests, and which ones get fixed before the archive (bug fixes only after the code freeze).

| Issue | Severity | Fix before the archive? |
|---|---|---|
| | | |

The manual tests on the exe (#24) are run this afternoon: bugs found are added here.

## 5. Retrospective

- **What went well:** the work moved forward well, every task is done except #24. The week was lighter (company week). The PR reviews caught security problems before merging (#55, #60).
- **What went badly:** the team started its tasks on Wednesday instead of Monday, because of other ongoing projects. The exe came late, so it couldn't be tested before this meeting.
- **What we change for sprint 3:** we try to start our tasks on Monday. The sprint 3 split stays the same.

## 6. Decisions

Also add them to [decisions.md](../decisions.md).

- code freeze from now (Nov 22): after it, only bug fixes go into `main`
- a bug found after the freeze is fixed by the member who was in charge of that part, unless Yani can fix it himself
- #24 also tests the Linux binary in VMs on Ubuntu 22.04, Ubuntu 26.04 and Debian
- next week (sprint 3), everyone gets familiar with the whole code, to understand how it all works

## 7. Risks

Anything new, or a risk that happened? Update [risks.md](../risks.md).

- **R6** (#8 finished late): did **not** happen, #8 was merged on Nov 14 as planned
- **R7 (new):** the CI builds the Linux binary on Ubuntu 22.04 but only starts it without its window (the CI has no screen), and the window was only tested on Sam's Arch Linux. #24 tests it in VMs on Ubuntu 22.04, Ubuntu 26.04 and Debian
- **R8 (new):** the exe is tested after the code freeze, so bugs can still show up in sprint 3. Whoever was in charge of the part fixes them

## 8. Sprint 3: who does what

Sprint 3 goal: report, slides, demo. **Final archive on Arche on Saturday Nov 28.**

| Who | Main tasks |
|---|---|
| Diogo | report: final state of `core/` (#32), slides: technical part (#36), final archive on Arche (#38) |
| Sam | report: packaging, CI and tests (#31), slides: packaging and tests (#37) |
| Yanis | user guide with screenshots (#28), report: interface (#29), demo and backup video (#30) |
| Yani | report: organisation and planned vs actual (#33), sections 6 and 9 (#46), assembly and pdf (#34), slides template (#35), meeting notes (#5) |
| team | final review (#39, Sat Nov 28), timed rehearsal (#40, Mon Nov 30) |
