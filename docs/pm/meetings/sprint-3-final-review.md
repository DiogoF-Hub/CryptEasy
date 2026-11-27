# Meeting: sprint 3 + final project review

**Date:** Friday Nov 27, 20:30 (on Discord)
**Attendees:** Diogo · Sam · Yanis · Yani
**Notes by:** Yani

---

## 1. Sprint goal

> Report, slides and demo ready. Final archive uploaded to Arche.

Reached / partly / not reached: **reached**. Report: 20-page body + annexes A to F. Slides: all parts on `main` (#74, #76), slide 18 filled. Archive: uploaded by Diogo on Sat Nov 28.

## 2. Done this sprint

Times from the board on Nov 27, after the meeting.

| Issue | Who | Estimate (h) | Actual (h) | Note |
|---|---|---|---|---|
| #33 Report: organisation, planned vs actual (2 to 5) | Yani | 6 | 4 | |
| #46 Report: CDC choices and improvements (6, 9) | Yani | 3 | 2 | |
| #32 Report: final state of `core/` (7.1) | Diogo | 1 | 1 | |
| #31 Report: keystore, packaging, CI and tests (7.2, 7.4, 8.1) | Sam | 3.5 | 1 | |
| #29 Report: interface (7.3) | Yanis | 2 | 1 | |
| #28 User guide with screenshots | Yanis | 3 | 3 | |
| #34 Report: assembly, layout and pdf | Yani | 3 | 2 | section 7 cut from 7.5 to 4.5 pages to fit 20 pages |
| #35 Slides: template and assembly | Yani | 3 | 1.5 | |
| #36 Slides: technical part | Diogo | 2 | 0.75 | |
| #37 Slides: packaging and tests | Sam | 2 | 1 | |
| #5 Meeting notes | Yani | 1.5 | 2 | |
| #39 Final review (this meeting) | team | 1 | 1 | held on Nov 27 instead of Nov 28 |
| **Total (tasks done on Nov 27)** | | **31** | **20.25** | **−35 %** |
| #30 Demo and backup video | Yanis | 3 | in progress | |
| #38 Archive on Arche | Diogo | 1 | Sat Nov 28 | |
| #40 Timed rehearsal | team | 1 | Mon Nov 30 | |

Sprint 3 took about a third less time than planned: the report and slides went faster because their sources already existed (board, Git history, decision log, meeting notes), and part of the writing was done with an AI assistant (report annex F).

## 3. Final archive

Everything is on the repo; **Diogo builds the zip and sends it to the teacher** (upload on Arche, Sat Nov 28).

- [x] project (source + exe): on the repo and in release `v1.0.0rc1`
- [x] documentation: README, DEV_README, user guide, technical spec, on the repo
- [x] report pdf (10 to 20 pages): 20-page body + annexes, sent to Diogo tonight
- [ ] uploaded to Arche, confirmation received: Diogo, Sat Nov 28

## 4. Whole project review

Confirmed at the meeting.

- **Goals met:** everything the CDC asked for: key pairs (RSA / X25519), hybrid encryption, private key protected by a passphrase, contacts, standalone Windows exe.
- **Goals dropped, and why:** file signing (F9), not enough time after the Nov 8 re-planning (the Ed25519 key is already generated, so it can be added later). macOS build: last priority, not done.
- **Goals added:** folders, security levels, FR / EN interface, Linux binary, checks against crafted files (#55, #60).
- **Biggest gaps between estimated and actual time, and what they taught us:** organisation tasks and unplanned fixes took longer than planned, technical tasks shorter (the spec was detailed). The totals look right (−4 % on sprints 1 and 2) but hide gaps in both directions.

## 5. Retrospective on the whole project

Validated at the meeting (matches sections 9 and 10 of the report).

- **What went well:**
  - the organisation in one-week sprints, with a meeting at the end of each one
  - running the project on GitHub with Git, with every decision written down (`decisions.md`)
  - a review on every PR, which also found real security flaws before they reached the exe
  - the split of roles by skill
  - the finished application: everything the CDC asked for, plus folders, security levels and FR / EN
- **What went badly:** spreading the work across the sprints around our weeks at work (apprenticeship); overall it still worked out.
- **What we would do differently next time:** start earlier, with short sprints right after the CDC.

## 6. Presentation

Split taken from the slides (18 slides, ~20 min + ~5 min questions). No change asked at the meeting.

| Who | Part | ~ minutes |
|---|---|---|
| Diogo | 6 meetings, 8 difficulties, 10 hybrid encryption, 11 security by default | ~4 |
| Sam | 7 estimated vs actual, 12 keys and contacts, 15 exe and CI, 16 tests (with Yani) | ~4 |
| Yanis | 3 the project, 13 interface, 14 interface choices | ~3 |
| Yani | 2 outline, 4 planned vs actual, 5 who did what, 9 CDC vs result, 16 tests (with Sam) | ~5 |
| Everyone | 17 demo (led by Yanis, #30), 18 thanks and next steps | ~4 + 1 |
| | questions | ~5 |

Rehearsal date: Monday Nov 30 (#40)
