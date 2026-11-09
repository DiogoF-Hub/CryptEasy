# Risk register

The risks identified in the CDC (Sep 15), plus new ones the team spots during the project. Reviewed at every weekly meeting: did it happen, and what did we do?

**Last updated:** Nov 8 (re-plan)

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
| | | | | | | |
