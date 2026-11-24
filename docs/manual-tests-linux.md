# Manual tests: Linux runs

Short version of [manual-tests.md](manual-tests.md) for the Linux binary (#24). The full checklist was run on Windows ([manual-tests-windows.md](manual-tests-windows.md), 49/49 OK). The crypto, the keys, the contacts and the error messages are the same Python code on every system, and the CI runs the automated tests on Ubuntu and Windows. So on Linux, only what depends on the system is tested again:

- the install written in the README (WebKit2GTK packages) and the window (GTK / WebKit2GTK), which was only tested on Sam's Arch Linux: the CI builds the binary on Ubuntu 22.04 but only starts it without its window;
- the "open" and "save as" windows, the data folder (`~/.local/share/CryptEasy`), "Open folder", the language and quitting.

The IDs in brackets are the matching tests of the full checklist.

| Run | Debian | Ubuntu 22.04 | Ubuntu 26.04 |
|---|---|---|---|
| Date | Sun Nov 22, 2026 | Mon Nov 23, 2026 | Mon Nov 23, 2026 |
| Tester | Yani (c0mpr0mized) | Yani (c0mpr0mized) | Yani (c0mpr0mized) |
| Machine (PC or VM) | PC | VM (VirtualBox) | VM (VirtualBox) |
| Exact version (`grep PRETTY /etc/os-release`) | Debian GNU/Linux 13 (trixie) | Ubuntu 22.04.5 LTS | Ubuntu 26.04.1 LTS |
| Exe version | 1.0.0rc1 | 1.0.0rc1 | 1.0.0rc1 |

**Files to prepare first** (in a `tests` folder in the home folder): the `.tar.gz` and `SHA256SUMS` from the `v1.0.0rc1` release, `note.txt` (a few lines of text) and the folder `holidays/` (2 files, a subfolder with a file in it, and an **empty** subfolder).

## Tests

| ID | What to do | Expected | Debian | Ubuntu 22.04 | Ubuntu 26.04 | Bug |
|---|---|---|---|---|---|---|
| L1 (A1) | Check the download (command 1) | `crypteasy-1.0.0rc1-linux-x86_64.tar.gz: OK` | OK | OK | OK | |
| L2 | Install the 2 packages given in the README (command 2), extract and start the binary (command 3) | the install works as written, a CryptEasy window opens (no browser) | OK | OK | OK | |
| L3 (A3, A4) | Look at the first launch | Home says to create a key pair first; French if the system is in French, English otherwise | OK | OK | OK | |
| L4 (A5) | Switch FR ↔ EN, visit every page | all texts change, none empty, no raw key like `encrypt.button` | OK | OK | OK | |
| L5 (B1) | Generate "Alice" with the default settings | X25519, level **Strong**, fingerprint shown | OK | OK | OK | |
| L6 (B9) | Export Alice's public key | the "save as" window opens, the `.pem` file is saved | OK | OK | OK | |
| L7 (C1) | Add a contact "Alice-contact" with that `.pem` | the "open" window opens, the contact is saved | OK | OK | OK | |
| L8 (D4) | Encrypt `note.txt` for Alice | "save as" offers a neutral name like `crypteasy_2026-11-23_1432.zip` | OK | OK | OK | |
| L9 (D6) | Encrypt the folder `holidays/` for Alice | package saved, no temp zip left next to it | OK | OK | OK | |
| L10 (E1, E2) | Decrypt the `note.txt` package into `decrypted/`, compare (command 4) | "save as" prefilled with `note.txt`, same SHA-256 | OK | OK | OK | |
| L11 (E6) | Decrypt the folder package, choose "extract" | a new `holidays/` folder with every file, the subfolder **and** the empty subfolder | OK | OK | OK | |
| L12 (E8) | Click "Open folder" | the file manager opens on the extracted folder | OK | OK | OK | |
| L13 (F1) | Decrypt with a wrong passphrase | "Wrong passphrase for this key." | OK | OK | OK | |
| L14 (F7) | Decrypt `note.txt` again, save it under the same name in `decrypted/` | "… already exists: CryptEasy never overwrites a file. Choose another name." | OK | OK | OK | |
| L15 | Check the data folder (command 5) | the folder is only readable by you (`drwx------`), and so are the files in it (`-rw-------`) | OK | OK | OK | |
| L16 (A6) | Close the window, check (command 6), start the binary again | nothing left running; Alice is still there, the chosen language is kept | OK | OK | OK | |

## Summary

**Notes on these runs:**
- In the VirtualBox VMs, set the graphics controller to VBoxSVGA: with the default (VMSVGA), Ubuntu 26.04 shows a `vmwgfx` error at boot. This is a VirtualBox setting, not a CryptEasy problem.
- On Ubuntu 22.04 installed by VirtualBox's unattended install, the terminal didn't open until the system language (locale) was set again. Also a VM setup problem, not a CryptEasy one.
- The CryptEasy window opened normally on the 3 systems, with no extra option.


| System | Tests | OK | KO |
|---|---|---|---|
| Debian | 16 | 16 | 0 |
| Ubuntu 22.04 | 16 | 16 | 0 |
| Ubuntu 26.04 | 16 | 16 | 0 |

## Commands (terminal, in the `tests` folder)

```bash
# 1. Check the download
sha256sum -c SHA256SUMS --ignore-missing

# 2. The 2 packages the Linux binary needs (from the README)
sudo apt install libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1

# 3. Extract and start
tar -xzf crypteasy-1.0.0rc1-linux-x86_64.tar.gz && ./crypteasy

# 4. Compare an original and its decrypted copy (the 2 hashes must be equal)
sha256sum note.txt decrypted/note.txt

# 5. Data folder: keys, contacts and settings
ls -ld ~/.local/share/CryptEasy && ls -lR ~/.local/share/CryptEasy

# 6. After closing the window: nothing must be printed
pgrep -a crypteasy
```
