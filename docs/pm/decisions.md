# Decision log

One line per decision or change of scope, written when it's made. This is what the report uses for "changes to the project goals" and "choices made to clarify vague points in the CDC".

| Date | Decision | Why | Proposed by |
|---|---|---|---|
| Sep 15 | Topic: CryptEasy, a file encryption tool with a graphical interface, hybrid encryption (AES + RSA / elliptic curve), packaged as a standalone executable | see the CDC | team |
| Oct 15 | GUI with **Flask**, not Streamlit (the CDC left the choice open) | the standalone executable is required, and Streamlit can't be packaged reliably with PyInstaller | team |
| Oct 15 | One long-lived branch per member (`*-dev`), changes reach `main` only through pull requests, CI on every push | work in parallel without breaking `main`, keep a clear history of who did what | Sam |
| Oct 18 | The app runs in its **own window (pywebview)**, not in the browser | it should feel like a normal desktop program | Diogo |
| Oct 15 to 18 | Encrypted output is **one `.zip` package** with `key.enc` + `file.enc` | one file to send, and the encryption settings travel with it | Diogo |
| Oct 15 to 18 | The passphrase, KDF and salt protect the **private key on disk**; no per-file password | a per-file password would have to be sent through a safe channel, which is exactly the problem public keys solve | Diogo |
| Oct 15 to 18 | **Security levels** (very strong → no protection) to choose the settings in one click | safe defaults for beginners, tunable for advanced users (CDC) | Diogo |
| Oct 15 to 18 | Folders can be encrypted (zipped automatically by the app) | the user shouldn't have to zip a folder by hand | Diogo |
| Oct 18 | Interface in **French and English**, one translation file per language | adding a language later is just adding a file | Diogo |
| Oct 18 | An Ed25519 signing key is generated with every key pair from day 1; file signing itself stays a stretch goal | adding signing later then changes nothing for existing keys and contacts | Diogo |
| Oct 18 | `main` is protected on GitHub: only the repository owner merges, after reviewing the PR | nothing reaches `main` without being checked | Diogo |
| Nov 8 | **Re-plan:** 3 one-week sprints instead of the CDC's mostly sequential phases ([planning v2](planning-v2.md)) | the development started about 5 weeks late, 3 weeks left: a mostly sequential plan can't absorb the delay | Diogo |
| Nov 8 | **Roles split by skill** instead of by component (Yani moves to report, testing and slides) | the component split didn't match who could do what (CDC risk R2) | Diogo |
| Nov 8 | **Scope:** file signing not planned (stretch only), Linux binary optional, macOS build not a priority (only if time is left) | not enough time; keep the effort on the Windows exe | Diogo |
| Nov 8 | Tasks tracked on a **GitHub board**: one issue per task, estimate and actual time | needed for the planned vs actual and estimated vs actual parts of the report | Diogo |
| Nov 10 | #9 (zip a folder + safe extraction) **moved from Diogo to Yani**, still in sprint 1. Diogo reviews the PR | Diogo had 26 h planned in sprint 1, the most of the team; folders are independent from the crypto, so Yani can work on it in parallel. Agreed together in class | team |
| Nov 10 | **Report:** each section is written by the member who worked on that part; Yani assembles the whole document (#34). The skeleton (#15) was checked together by the 4 members in class | the person who did the work is the one who can explain it and justify the choices | team |
| Nov 10 | The report is written in a **shared online Word document**, everyone edits it at the same time; at the end of each sprint Yani commits the current version to `docs/report/` | git can't merge two versions of a .docx, so editing it on separate branches would lose someone's work; the snapshot at each sprint still keeps the history on GitHub | team |
| Nov 10 | **Report sections re-split:** sections 6 (choices made to clarify the CDC) and 9 (improvements) move to Yani (new issue #46); #32 now only covers the final state of `core/` (Diogo); the final state of `keystore/` moves to Sam (#31). Estimates follow the work: #32 4 h → 1 h, #46 3 h, #31 3 h → 3.5 h | same rule as above, whoever built a part writes about it: Sam built `keystore/` (#11, #12), Diogo built `core/`; sections 6 and 9 cover the whole project, so they go to Yani, who leads the report | Yani, Diogo |
| Nov 14 | #10 (core unit tests) **moved to sprint 2** (Diogo). #8 (Diogo) and #11 to #13 (Sam) are finished this weekend, still in sprint 1 | the school week of sprint 1 was the busiest one, Diogo already gave #9 to Yani; the company week of sprint 2 is lighter | Diogo |
| Nov 14 | The team uses the existing **Board view** of the GitHub project ([by status](https://github.com/users/DiogoF-Hub/projects/1/views/2): Todo / In Progress / Done) to move tasks | asked at the sprint 1 review | Diogo |
