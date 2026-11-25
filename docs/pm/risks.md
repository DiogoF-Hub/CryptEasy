# Risk register

The risks identified in the CDC (Sep 15), plus new ones the team spots during the project. Reviewed at every weekly meeting: did it happen, and what did we do?

**Last updated:** Nov 24 (after the manual tests, #24)

---

## Risks from the CDC

| # | Risk | Impact | Planned mitigation (CDC) | Happened? | What we actually did |
|---|---|---|---|---|---|
| R1 | bad split of time between the 4 members | schedule delay | short weekly progress meetings, tasks clearly assigned from the start | ✅ **yes**: on Nov 8 the development had started about 5 weeks late | re-planned into 3 one-week sprints with a goal and a review every Sunday ([planning v2](planning-v2.md)) |
| R2 | gap in cryptography skills between members | slows down the core module | pair work on sensitive parts, shared internal documentation | ✅ **yes**: the gap is in Python and git in general, not only cryptography | roles re-split by skill on Nov 8: everyone works where they're most useful |
| R3 | scope creep (features added along the way) | deadlines missed | minimal scope (MVP) frozen after the CDC | ⚠️ **partly**: the technical spec added features (folders, security levels, FR / EN, Linux and macOS builds) | on Nov 8: Linux binary made optional, macOS build only if time is left, file signing (already optional in the CDC) left out of the sprints |
| R4 | mistakes in key handling (loss, wrong manipulation) | loss of test data, blocked demo | systematic tests, dummy data for demos | ❌ no (so far) | |
| R5 | late start with the chosen GUI library | interface delay | simple interface prototype during design | ❌ **no** | the interface was built early (Oct 15), on a fake backend |

## New risks

Risks the team spots during the project (something that *could* go wrong, not something that already did). Added at the weekly meetings.

| # | Risk | Impact | Mitigation | Spotted on | Happened? | What we actually did |
|---|---|---|---|---|---|---|
| R6 | #8 (hybrid encryption) finished late | sprint 2 is blocked: plugging the real core into the interface (#21) and the exe (#18) both need it | Diogo finishes #8 this weekend (Nov 14 to 15); the team sees no other risk as long as everyone does their tasks | Nov 14 | ❌ **no** | Diogo merged #8 on Nov 14 (PR #52), as decided at the sprint 1 review |
| R7 | the Linux binary's window doesn't open on Ubuntu or Debian | the optional Linux build (#20) can't be shown or used | the CI builds it on Ubuntu 22.04 but only starts it without its window (no screen in the CI), and the window was only tested on Sam's Arch Linux: #24 tests it in VMs on Ubuntu 22.04, Ubuntu 26.04 and Debian. The Linux binary is optional anyway | Nov 22 | ❌ **no** | #24: the window opened normally on Debian 13, Ubuntu 22.04 and Ubuntu 26.04, 16/16 tests OK on each ([manual-tests-linux.md](../manual-tests-linux.md)) |
| R8 | bugs found after the code freeze | less time left for the report and the slides in sprint 3 | the member who was in charge of the part fixes it, unless Yani can fix it himself | Nov 22 | ⚠️ **partly** | one minor visual issue, found by Diogo after the freeze: some cards touch on the Info page (#67). Nothing is broken, so it isn't fixed (code freeze) and goes to the improvements in the report. No blocking bug in the manual tests |
