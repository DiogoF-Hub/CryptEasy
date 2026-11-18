# Manual tests

Checklist to run by hand on the exe, based on [TECHNICAL_SPEC.md](TECHNICAL_SPEC.md) (sections 3, 4, 5.4 and 7). Written for #23, run for #24. The results feed the "tests carried out" section of the report.

## How to run it

- On a **Windows PC without Python**, with the exe downloaded from the `v1.0.0rc1` release.
- Go through the tables in order: each part uses what the previous one created (keys, contacts, packages).
- In **Result**, write `OK` or `KO`. For each `KO`: open an issue with the `bug` label (steps to reproduce + a screenshot) and put its number in **Bug**.
- Commands in the appendix are for PowerShell (no install needed).

| Run | |
|---|---|
| Date | |
| Tester | |
| PC / Windows version | |
| Exe version | |

**Files to prepare first** (in a `tests` folder on the Desktop):
- `note.txt`: a few lines of text
- `photo.jpg`: any photo
- `holidays/`: a folder with 2 or 3 files, a subfolder with a file in it, and an **empty** subfolder
- `big.bin`: a file of about 1 GB (appendix, command 1)

---

## A. Launch and window

| ID | What to do | Expected | Result | Bug |
|---|---|---|---|---|
| A1 | Check the exe's SHA-256 against `SHA256SUMS` from the release (command 2) | same value | | |
| A2 | Double-click the exe | a CryptEasy window opens, no browser, no console window | | |
| A3 | First launch, no key yet | Home says to create a key pair first | | |
| A4 | Look at the language on first launch | French if Windows is in French, English otherwise | | |
| A5 | Switch FR ↔ EN in the nav bar, visit every page | all texts change, none empty, no raw key like `encrypt.button` | | |
| A6 | Close the window, start the exe again | the app quits fully (nothing left in Task Manager); the chosen language is kept | | |

## B. My keys (F1, F2, F6)

| ID | What to do | Expected | Result | Bug |
|---|---|---|---|---|
| B1 | Generate "Alice" with the default settings | X25519, level **Strong**, fingerprint shown (16 groups of 4 hex chars) | | |
| B2 | Generate one key for each level: very strong, strong, medium, weak | each key is created, the level shown matches the one picked | | |
| B3 | Generate RSA-2048, RSA-3072 and RSA-4096 keys | all created (RSA-4096 can take a few seconds) | | |
| B4 | Passphrase of 11 characters, then 2 different passphrases in the 2 fields | "The passphrase must be at least 12 characters long.", then "The two passphrases do not match." | | |
| B5 | Level "very strong" with a 12-character passphrase | refused or rated lower: very strong needs 16+ | | |
| B6 | Change one advanced option by hand (e.g. KDF strength) | level becomes "custom", rated by its weakest setting | | |
| B7 | Tick "no passphrase" | a warning must be confirmed, key rated ⛔ no protection | | |
| B8 | Generate "Bob" (strong) | Alice and Bob are both in the list | | |
| B9 | Export Bob's **public** key | a `.pem` file is saved where chosen | | |
| B10 | Export Alice's **private** key | a warning is shown, the file is saved | | |
| B11 | Import a private key `.pem` made with OpenSSL (RSA and X25519) | imported and locked with the new passphrase | | |
| B12 | Change Alice's passphrase | the old one is refused, the new one works (checked in E1) | | |
| B13 | Delete a test key | a confirmation is asked, then the key is gone | | |

## C. Contacts (F3)

| ID | What to do | Expected | Result | Bug |
|---|---|---|---|---|
| C1 | Add contact "Bob" with Bob's `public.pem` (B9) | saved, fingerprint shown with the "check it by phone or in person" hint | | |
| C2 | Compare with Bob's fingerprint in My keys | exactly the same | | |
| C3 | Add a contact with `note.txt` as the key | refused: "This is not a valid public key." | | |
| C4 | Rename then delete a contact | both work, delete asks for confirmation | | |

## D. Encrypt (F4, F6)

| ID | What to do | Expected | Result | Bug |
|---|---|---|---|---|
| D1 | Pick `note.txt`, recipient Alice | size and time estimate shown before starting | | |
| D2 | Open the recipient list | contacts and my own keys are listed | | |
| D3 | Switch AES-256 ↔ AES-128 | default is AES-256, the level indicator updates | | |
| D4 | Encrypt `note.txt` for Alice | "save as" offers a neutral name like `crypteasy_2026-11-20_1432.zip` | | |
| D5 | Encrypt `photo.jpg` for Bob | package saved | | |
| D6 | Encrypt the folder `holidays/` for Alice | package saved, no temp zip left next to it | | |
| D7 | Encrypt `big.bin` for Alice | progress bar moves, the estimate is roughly right | | |

## E. Decrypt (F5, section 5.4)

| ID | What to do | Expected | Result | Bug |
|---|---|---|---|---|
| E1 | Decrypt the `note.txt` package (D4) | Alice's key picked by itself, passphrase asked, "save as" prefilled with `note.txt` | | |
| E2 | Compare the decrypted file with the original (command 3) | same SHA-256 | | |
| E3 | Rename a package to `anything.zip`, decrypt it | still decrypts | | |
| E4 | Decrypt with a key that has no passphrase (B7) | no passphrase field | | |
| E5 | Decrypt the folder package (D6) | asks: keep as `.zip` or extract into a new folder | | |
| E6 | Choose "extract" | a new `holidays/` folder with every file, the subfolder **and** the empty subfolder | | |
| E7 | Extract the same package again in the same place | a new `holidays (2)/`, the first one untouched | | |
| E8 | Click "Open folder" | Explorer opens on the extracted folder | | |
| E9 | Decrypt it again, choose "keep as .zip" | a normal `.zip` that opens in Windows | | |
| E10 | Decrypt `big.bin` (D7), compare (command 3) | same SHA-256 | | |

## F. Errors (F7)

The messages below are the English ones (`en.json`); in French, check the matching text of `fr.json`. After each error, check that **no half file or folder** was left where it would have been saved.

| ID | What to do | Expected | Result | Bug |
|---|---|---|---|---|
| F1 | Decrypt with a wrong passphrase | "Wrong passphrase for this key." | | |
| F2 | Delete Bob's key pair, then decrypt the photo package (D5) | "This file was not encrypted for any of your keys." | | |
| F3 | Change one byte of a package (command 4), decrypt it | "This file is damaged or was modified. Nothing was decrypted." | | |
| F4 | Cut a package in half (command 5), decrypt it | same message as F3 | | |
| F5 | Decrypt a normal `.zip` that isn't a CryptEasy package | "This is not a CryptEasy file, or it was made by a newer version." | | |
| F6 | Import `note.txt` as a private key | "This is not a valid private key." | | |
| F7 | Decrypt `note.txt` again and save it under the name of a file that already exists | "… already exists: CryptEasy never overwrites a file. Choose another name." | | |

## G. Info page (F8)

| ID | What to do | Expected | Result | Bug |
|---|---|---|---|---|
| G1 | Open Info, in FR then in EN | explains hybrid encryption, the security levels, the package format and the safety tips | | |
| G2 | Read the format part | describes the `.zip` package (`key.enc` + `file.enc`), not the old `.ceasy` format (#22) | | |

---

## Summary

| Part | Tests | OK | KO |
|---|---|---|---|
| A. Launch and window | 6 | | |
| B. My keys | 13 | | |
| C. Contacts | 4 | | |
| D. Encrypt | 7 | | |
| E. Decrypt | 10 | | |
| F. Errors | 7 | | |
| G. Info page | 2 | | |
| **Total** | **49** | | |

## Appendix: PowerShell commands

Open PowerShell in the `tests` folder (Shift + right-click in the folder → "Open PowerShell window here").

```powershell
# 1. Create big.bin, about 1 GB
$f = [IO.File]::Create("$PWD\big.bin"); $f.SetLength(1GB); $f.Close()

# 2. SHA-256 of the exe (compare with the SHA256SUMS file of the release)
Get-FileHash .\crypteasy-1.0.0rc1-windows-x86_64.exe -Algorithm SHA256

# 3. Compare an original and its decrypted copy (the 2 hashes must be equal)
Get-FileHash .\note.txt, .\decrypted\note.txt -Algorithm SHA256

# 4. Change one byte in the middle of a package -> modified.zip
$b = [IO.File]::ReadAllBytes("$PWD\package.zip"); $i = [int]($b.Length / 2); $b[$i] = $b[$i] -bxor 1
[IO.File]::WriteAllBytes("$PWD\modified.zip", $b)

# 5. Keep only the first half of a package -> truncated.zip
$b = [IO.File]::ReadAllBytes("$PWD\package.zip")
[IO.File]::WriteAllBytes("$PWD\truncated.zip", $b[0..([int]($b.Length / 2))])
```
