# CryptEasy: technical spec

---

## 1. In one paragraph

CryptEasy is a desktop app to send files securely. You open it like any program, in its own window. You generate a key pair, share your public key, and save other people's public keys as contacts. To send a file or a folder, you pick it and a contact, and CryptEasy gives you an encrypted `.zip` package that only that contact can open. To open a package someone sent you, you pick it, type your key passphrase, and you get the original file back. Safe defaults in a few clicks. Advanced users can tune the security parameters (key type and size, AES key size, and how strongly the private key is protected on disk: KDF, strength, salt) and the app shows how secure their choice is. The only thing anyone ever shares is their public key: no passphrases travel.

---

## 2. Platforms and delivery

### 2.1 What the user gets

| OS | What the user downloads |
|---|---|
| **Windows** | `crypteasy-<version>-windows-x86_64.exe`, double-click, nothing to install. **main target** |
| Linux | `crypteasy-<version>-linux-x86_64.tar.gz`, standalone binary |
| macOS | `crypteasy-<version>-macos-arm64` standalone binary (Apple Silicon) |

All three are built by **GitHub Actions when we create a release** (version bump on `main`) and attached to the GitHub Release with `SHA256SUMS`. PyInstaller can't cross-compile, so each one is built on its own runner (`windows-latest`, `ubuntu-22.04`, `macos-latest`). Windows + Linux are already in `ci.yml`; **macOS still has to be added**.

Running from source with `uv run` still works on any OS, for devs.

### 2.2 How it runs: a real app window (Flask + pywebview)

Double-click the exe → a normal **CryptEasy window** opens, like any desktop program. No browser, no console window. Closing the window quits the app.

```
   crypteasy.exe
   ┌──────────────────────────────────────────────┐
   │  pywebview: the app window                   │
   │  (uses the web engine already in the OS)     │
   │                                              │
   │      shows our pages (HTML / CSS)            │
   │              ▲                               │
   │              │  only inside the app          │
   │              ▼                               │
   │  Flask: our pages + logic (Python)           │
   │              │                               │
   │              ▼                               │
   │  core/ (crypto) + keystore/ (keys, contacts) │
   └──────────────────────────────────────────────┘
```

- **Flask** builds the pages and runs our Python code, like a website would
- **pywebview** shows those pages in a native window instead of a browser tab. it uses the web engine the OS already has:
  - Windows: Edge **WebView2** (preinstalled on Windows 10 and 11)
  - macOS: the system WebKit (always there)
  - Linux: GTK + WebKit2GTK (installed on most desktop distros; if missing, the user installs one package, e.g. `libwebkit2gtk`)
- **native dialogs**: "pick a file", "pick a folder", "save as" are the real Windows / macOS / Linux dialogs (pywebview provides them). Python then reads and writes the files **directly on disk**, nothing is uploaded or copied first
- **PyInstaller** packs all of it into one file
- risk: pywebview on Linux (GTK backend) is the trickiest combo to pack with PyInstaller. try it in the very first packaging test, not at the end

macOS: our binary isn't signed by Apple (that needs a paid developer account), so the first launch is blocked by Gatekeeper and the user has to right-click → Open once. Intel Macs: see the open question at the end.

---

## 3. What it does

### F1. Generate a key pair
- types: **X25519** (elliptic curve, default) or **RSA** 2048 / 3072 / 4096 (default 3072)
- the user gives it a name ("Diogo laptop") and a **key passphrase** (12+ characters). the passphrase never leaves the PC and is never shared
- **"no passphrase" checkbox**: the private key is then saved unprotected. allowed, but rated ⛔ (section 4.2) and the user has to confirm a warning: anyone who copies the key file can open every file sent to them
- pick a security level (section 4.2), or set the advanced options by hand (KDF, strength, salt)
- private key is saved encrypted with that passphrase (section 6.2), public key saved next to it
- the user can have several key pairs, each with a name (useful for the demo: Alice and Bob on one machine)

### F2. Export / import keys
- export my **public** key as `.pem` to send to people ("save as" dialog)
- export my **private** key file, still locked with my key passphrase (backup / move to another PC). warning shown
- import an existing private key `.pem` (e.g. made with OpenSSL), RSA or X25519. it gets re-locked with a key passphrase and the chosen settings
- change the key passphrase / protection settings of a key pair (re-locks the private key)

### F3. Contacts book
- add a contact: name + their public key `.pem` → the key is validated before saving
- show each contact's **fingerprint** (short hash of the key), with a hint: "check it with them by phone or in person"
- list, rename, delete contacts
- encrypting a file means picking a contact, so you don't re-import keys each time

### F4. Encrypt a file or a folder
1. pick a file **or a folder** (native dialog). a folder is zipped automatically by the app first (temp zip, deleted right after), then encrypted like any file. the user doesn't have to zip it themselves
2. the app shows the **total size and an estimated time** before anything starts, e.g. "2.3 GB, about 25 s" (section 5.5)
3. pick a recipient (a contact, or one of my own keys)
4. security settings: default = recommended. "advanced" panel for the options in section 4
5. click Encrypt → "save as" dialog, with a neutral default name like `crypteasy_2026-10-18_1432.zip` that reveals nothing about the content. the user can rename it to anything, it still decrypts

### F5. Decrypt a file
The package is just a bundle of 2 files:
- `key.enc`: the random symmetric key (AES), encrypted with the recipient's public key
- `file.enc`: the file, encrypted with that symmetric key

(+ `signature.sig` if the sender signed it, see F9)

Steps:
1. pick the `.zip` package (native dialog)
2. the app **finds the right key by itself**: it reads the recipient fingerprint in the package and picks the matching key pair among mine. if none matches, it says so (and I can still import a key file: `private.key` exported from CryptEasy, or a `.pem`)
3. enter my key passphrase (the one I chose when generating the key, nothing from the sender). skipped if the key has no passphrase
4. click Decrypt → the app decrypts `key.enc` with the private key to get the symmetric key back, then decrypts `file.enc` with it
5. a single file → "save as" dialog, prefilled with its original name
6. a folder → the app **asks**: "keep it as a `.zip`" or "extract it into a new folder" (section 5.4)

### F6. Security level indicator
- on the encrypt and key generation screens, the current settings are rated **very strong / strong / medium / weak / no protection** (section 4.2) with a one-line why

### F7. Clear error messages
| Situation | What the user sees |
|---|---|
| wrong key passphrase | "Wrong passphrase for this key." |
| package not encrypted for any of my keys | "This file wasn't encrypted for any of your keys." |
| package modified / corrupted / truncated | "This file is damaged or was modified. Nothing was decrypted." |
| not a CryptEasy package / unknown version | "This isn't a CryptEasy file, or it was made by a newer version." |
| invalid key file | "This isn't a valid public / private key." |
| folder too big / too many files when extracting | "This folder is unusually large once extracted, extraction stopped. The extracted part was deleted." |
| *(stretch)* signature doesn't match | "The signature is wrong: this file may be forged or modified. Nothing was decrypted." |
| Windows without WebView2 (very rare) | "CryptEasy needs Microsoft WebView2" + link to install it |

### F8. Info page
How it works (hybrid encryption explained simply), what each security level means, the package format, safety tips (verify fingerprints, don't lose your private key).

### F9 *(stretch, only if everything else is done)*. Sign files

**The problem.** Alice's public key is public: anyone can encrypt a file for her. So encryption alone doesn't prove who sent a package. Mallory could make a fake `invoice.pdf`, encrypt it for Alice, and email it pretending to be Bob.

**The fix.** Bob signs the package with a key only he has. Alice's app checks the signature with Bob's public key, which she already has in her contacts.

**Keys.** A signature needs a key that can *sign*, and X25519 can only encrypt. So each identity gets a second, signing-only key: **Ed25519** (always Ed25519, whatever the encryption key type, so there's only one signing algorithm to code). From the user's side nothing changes:
- generating a key pair creates both at once, in a few milliseconds. the user sees **one** key pair with one name
- the signing key is generated **from day 1**, even while the signing screens don't exist yet. so adding signing later changes nothing for existing keys and contacts
- both private keys are locked together in the same `private.key`, with the same passphrase
- both public keys are in the same exported `public.pem`, so contacts get both automatically
- this is exactly how GPG works: one "key" for the user is really a signing key + an encryption subkey

**Signing is optional.** On the Encrypt page:
```
   ☑ Sign as "Bob laptop"     (default: on, if I have a key pair)
```
- checked → the app asks Bob's passphrase (it needs his private signing key), and the package gets a 3rd file, `signature.sig`
- unchecked → no passphrase needed, no signature, the package has just 2 files

**What's in the package when it's signed:**
```
   📦 package.zip
   ├── key.enc
   ├── file.enc
   └── signature.sig     ← new, only when signed
```
`signature.sig` is a small JSON file:
```json
{
  "signer_fingerprint": "7C1E 04AB ...",
  "algorithm": "ed25519",
  "signature": "base64..."
}
```

**How it's made (Bob's side):**
```
   key.enc ──► SHA-256 ──┐
                         ├──► "CryptEasy v1 signature" + both hashes ──► sign with 🖊️ Bob's
   file.enc ─► SHA-256 ──┘                                                   private signing key
                                                                                    │
                                                                                    ▼
                                                                             signature.sig
```
The signature covers both files, so changing even one byte of either one breaks it.

**How it's checked (Alice's side), before anything is decrypted:**
```
   signature.sig ──► signer_fingerprint ──► look it up in Alice's contacts
                                                   │
                   ┌───────────────────────────────┼─────────────────────────────┐
                   ▼                               ▼                             ▼
         found: "Bob", check the           not in contacts                no signature.sig
         signature with his public key           │                              │
             │                 │                 ▼                              ▼
          valid             invalid      ⚠️ "Signed by an unknown key       ⚠️ "Not signed: we can't
             │                 │            (7C1E 04AB ...)."               tell who sent it."
             ▼                 ▼            + "add as contact" button       (decrypt still allowed)
   ✅ "Sent by Bob,      ❌ "The signature is wrong:
      verified."             forged or modified."
                             nothing is decrypted
```

**Why it proves it's Bob:** only Bob's private signing key can make a signature that checks out with Bob's public key. Mallory doesn't have it, so a fake package either has no signature (⚠️) or a wrong one (❌).

---

## 4. Security options

There's only **one secret the user types** in the whole app: the key passphrase that locks their private key on their own disk. Nobody else ever needs it.

### 4.1 The settings

**Key generation screen** (the key pair, and how its private key is locked):

| Setting | Options | What it changes |
|---|---|---|
| Key type | X25519, RSA-2048, RSA-3072, RSA-4096 | how hard it is to break the public-key encryption of `key.enc` |
| KDF (turns the passphrase into the lock) | Argon2id, PBKDF2-SHA256 | how expensive each passphrase guess is. Argon2id is memory-hard, so GPUs don't help much |
| KDF strength | normal / strong / max | stronger = slower to unlock, and slower to brute-force |
| Salt | 32 / 16 bytes, or **none** (PBKDF2 only) | stops precomputed guesses. Argon2id always needs a salt |
| Key passphrase | 12+ characters (16+ for very strong), no forced symbols, strength hint. or the **"no passphrase"** checkbox | the thing the attacker has to guess. no passphrase = nothing to guess |

**Encrypt screen:**

| Setting | Options | What it changes |
|---|---|---|
| File cipher | AES-256-GCM, AES-128-GCM | size of the random file key. GCM only: it detects tampering. no CBC |

KDF strength presets, timed on Nov 10 on a recent laptop (Intel Core Ultra X7) and set to about half the target there, to land near the target on an average laptop. Argon2id never uses more than 1 GiB, so a laptop with little RAM doesn't crash.

| Preset | Argon2id (4 lanes) | PBKDF2-SHA256 | Measured | Unlock time target (average laptop) |
|---|---|---|---|---|
| normal | 256 MiB memory, 4 passes | 1 200 000 iterations | ~0.25 s | ~0.5 s |
| strong | 512 MiB memory, 4 passes | 2 500 000 iterations | ~0.5 s | ~1 s |
| max | 1 GiB memory, 6 passes | 7 500 000 iterations | ~1.3 to 1.5 s | ~3 s |

### 4.2 Security levels

The user can pick a level from a dropdown instead of setting each option. The level fills in the options; changing any option by hand switches to "custom" and the indicator rates it by its **weakest setting**.

| Level | Key type | File cipher | KDF | KDF strength | Salt | Passphrase |
|---|---|---|---|---|---|---|
| 🟢🟢 **Very strong** | X25519 or RSA-4096 | AES-256-GCM | Argon2id | max | 32 bytes | 16+ chars |
| 🟢 **Strong** *(default)* | X25519 or RSA-3072 | AES-256-GCM | Argon2id | normal | 16 bytes | 12+ chars |
| 🟡 **Medium** | RSA-2048 | AES-128-GCM | PBKDF2-SHA256 | normal | 16 bytes | 12+ chars |
| 🔴 **Weak** *(learning only)* | RSA-2048 | AES-128-GCM | PBKDF2-SHA256 | normal | **none** | 12+ chars |
| ⛔ **No protection** | any | any | none | none | none | **none** (checkbox) |

What each level means, in plain words (for the Info page):
- **Very strong**: overkill on purpose. unlocking your key takes a few seconds and uses a lot of RAM, which makes guessing your passphrase extremely slow
- **Strong**: what we recommend. no known attack, unlocks in under a second
- **Medium**: still safe today, but with smaller margins: RSA-2048 is the minimum still accepted, and PBKDF2 is easier to attack with GPUs than Argon2id
- **Weak**: there to show why salt matters. without a salt, the same passphrase always gives the same lock, so an attacker can precompute guesses once and reuse them against everyone (rainbow tables)
- **No protection**: the private key sits on the disk in clear. the encryption of the files themselves is still fine, but anyone who gets a copy of your key file can read everything sent to you. shown to compare, never recommended

Notes:
- X25519 is about as strong as RSA-3072 (both ~128-bit security), with much smaller and faster keys. that's why it's in the top two levels
- the key type and KDF are picked at **key generation**, the file cipher at **encrypt** time. so a key generated as "strong" can still be used to encrypt with AES-128, and the encrypt screen indicator shows the result

### 4.3 What these settings protect against

Someone steals your laptop or copies your private key file. They then have to guess your key passphrase. The KDF makes every guess slow, and the salt makes every guess work against your key only.

---

## 5. Encrypted package format (`.zip`)

### 5.1 Contents

A plain zip (stored, not compressed: compressing ciphertext is useless) that's just a bundle of exactly 2 files (3 when signed, see F9). The package's own name doesn't matter: the app only looks at what's inside, so a renamed package (`for_alice.zip`, `stuff.zip`...) decrypts exactly the same.

```
package.zip
├── key.enc         # the random symmetric key, encrypted with the recipient's public key
├── file.enc        # header (public settings) + the file encrypted with that symmetric key
└── signature.sig   # (stretch, optional) the sender's signature over the 2 files above
```

`file.enc` layout:
```
[ "CRYPTEZ" magic + format version ] [ header length ] [ header JSON ] [ encrypted chunks ... ]
```

The header is what the decryptor needs to know *how* the file was encrypted (algorithms, chunk size). It holds **no secrets**. The original filename is not in the header, it's inside the encrypted chunks.

Header JSON example:
```json
{
  "format": "crypteasy",
  "version": 1,
  "key_type": "rsa-3072",
  "key_wrap": "rsa-oaep-sha256",
  "recipient_fingerprint": "3F2A 91C0 ...",
  "cipher": "aes-256-gcm",
  "chunk_size": 65536,
  "is_folder": false
}
```
- `is_folder` is `true` when the app zipped a folder before encrypting
- `recipient_fingerprint` lets the decrypting app find the right key by itself and say "not for you" right away

### 5.2 Encrypt, step by step

Example used all the way through: Bob sends his `holidays/` folder (2 photos) to Alice.

**Step 0. If it's a folder, zip it first** (section 5.4). From here on, that zip is "the file". (a single file skips this step)
```
   📁 holidays/                         🗜️ holidays.zip  (temp, deleted at the end)
   ├── beach.jpg       ── zip ──►
   └── sunset.jpg
```

**Step 1. Make a random file key.** A brand new one for every file, 32 bytes for AES-256 (16 for AES-128). It's never saved anywhere in clear.
```
   os.urandom(32)  ───►  🔑 file key   e.g. 9f3a…c71e  (random, used once)
```

**Step 2. Encrypt the file with the file key (AES-GCM), in 64 KiB chunks.** Chunk 0 holds the original filename (so it's hidden). Each chunk gets a tag that detects any change, and each tag also covers the header, so nobody can swap a setting in the header either. Chunks mean huge files never have to fit in RAM.
```
   holidays.zip  (from step 0)
       │  split
       ▼
   [ name ] [ chunk 1 ] [ chunk 2 ] ... [ last chunk ]
       │         │           │                │
       └─────────┴─── AES-GCM with 🔑 file key ───┘   (header checked in every tag)
                             │
                             ▼
   [ enc 0 + tag ] [ enc 1 + tag ] [ enc 2 + tag ] ... [ enc N + tag ]   → body of file.enc
```
The file is now locked, but the 🔑 file key is still sitting in memory in clear. Alice needs it to open the file, and it can't be sent as is. That's step 3.

**Step 3. Lock the file key with Alice's public key → `key.enc`.** Only Alice's private key can open it.
```
   🔑 file key ─────────────┐
                            ├──►  RSA-OAEP-SHA256  (or X25519 + HKDF)  ───►  📄 key.enc
   Alice's public key 🔓 ───┘
```
- RSA: RSA-OAEP with SHA-256
- X25519: make a throwaway key pair, ECDH with Alice's public key, HKDF-SHA256 → wrapping key, AES-GCM-encrypt the file key. `key.enc` = throwaway public key + wrapped file key
- after this, the file key in clear isn't kept or saved anywhere (only `key.enc` leaves)

**Step 4. Bundle everything into the zip** (+ `signature.sig` if "sign" is checked, F9). Delete the temp folder zip if there was one.
```
   📦 package.zip
   ├── key.enc     ← step 3
   └── file.enc    = [ header ] + [ encrypted chunks from step 2 ]
```
Bob sends `package.zip` to Alice however he wants (email, USB, Teams). No passphrase to share. (`package.zip` is the encrypted package; `holidays.zip` is hidden inside `file.enc`)

### 5.3 Decrypt, step by step

Example: Alice opens the `package.zip` from Bob.

**Step 1. Open the zip and check it.** Exactly `key.enc` + `file.enc` (+ optionally `signature.sig`), sane sizes. Files are read directly, **never extracted** with `extractall` (zip-slip).
```
   📦 package.zip ──► only the expected files?  ── no ──►  ❌ "This isn't a CryptEasy file"
                              │ yes
                              ▼
```
*(stretch: if `signature.sig` is there, it's checked right here, before anything else, see F9)*

**Step 2. Read the header** at the start of `file.enc`: known format, version, algorithms, sane values (e.g. chunk size ≤ 16 MiB).
```
   file.enc ──► [ header ] ──► version 1? known algorithms? ── no ──►  ❌ "made by a newer version"
                                       │ yes
                                       ▼
```

**Step 3. Which of my keys is it for?** The app compares the fingerprint in the header with the fingerprints of all of Alice's key pairs, and picks the matching one by itself.
```
   header: recipient_fingerprint = 3F2A 91C0 ...
                     │
                     ▼  compare with each of Alice's keys
   ┌───────────────────────────────────┐
   │  "Alice laptop"   3F2A 91C0 ...  ✅ │ ──► picked automatically
   │  "Alice work"     88B1 0D4E ...    │
   └───────────────────────────────────┘
                     │
             no match at all ──► ❌ "This file wasn't encrypted for any of your keys."
                                    (Alice can still import a key file by hand)
```

**Step 4. Unlock Alice's private key with her passphrase** (section 6.2). Skipped if the key was saved with "no passphrase".
```
   Alice types her passphrase 🗝️
          │
          ▼
   passphrase + salt (from private.key) ──► Argon2id / PBKDF2 ──► lock key
                                                                     │
   private.key (locked) ──────────── AES-GCM decrypt ◄──────────────┘
          │                                │
          │                     wrong ─────┴───── right
          │                       │                 │
          │   ❌ "Wrong passphrase           🔐 Alice's private key (only in memory)
          │       for this key."
```

**Step 5. Open `key.enc` with the private key → get the file key back.**
```
   📄 key.enc ──► decrypt with 🔐 Alice's private key ──► 🔑 file key
```

**Step 6. Decrypt the chunks one by one into a temp file.** Every tag is checked. One bad tag, a missing last chunk, or extra data at the end = stop, delete the temp file, nothing is given to the user.
```
   [ enc 0 + tag ] [ enc 1 + tag ] ... [ enc N + tag ]
          │
          ▼  AES-GCM with 🔑 file key, check each tag (and the header)
          │
     tag OK? ── no ──► 🗑️ delete temp file ──► ❌ "This file is damaged or was modified.
          │ yes                                     Nothing was decrypted."
          ▼
   temp file  +  original name from chunk 0
```

**Step 7. Only once everything checked out:** clean up the filename (section 8).
```
   original name "holidays.zip"  ──► sanitize ("../../evil.exe" would become "evil.exe")
                                         │
   temp file ──── rename ────────────────┴──►  ✅ holidays.zip
```

**Step 8. A folder? Ask Alice what she wants** (`is_folder: true` in the header; a single file just goes to the "save as" dialog).
```
                          ✅ holidays.zip
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
   "Keep it as a .zip"                    "Extract it into a new folder"
            │                                         │
            ▼                                         ▼
   "save as" dialog → holidays.zip        Alice picks where (e.g. Desktop), the app creates
                                          a NEW folder there:
                                          📁 Desktop/holidays/
                                          ├── beach.jpg
                                          └── sunset.jpg
                                          + "Open folder" button
```

### 5.4 Folders

**On encrypt:**
- the user picks the folder with the native "pick a folder" dialog
- the app walks that folder directly on disk and zips it into a temp file (`zipfile`, streamed to disk, not in memory), keeping the relative paths. folder name = zip name
- skipped: symlinks (they could point outside the folder)
- the zip is then encrypted like any normal file, with `is_folder: true` in the header

**On decrypt, "extract it into a new folder":**
- the user picks a location, and the app always extracts into a **brand new folder it creates there** (`holidays/`, or `holidays (2)/` if that name is taken). never into an existing folder, so nothing of the user's gets overwritten, and if something goes wrong the user just deletes that one folder
- every path is checked before writing: it must stay inside the new folder (no `../`, no absolute paths, no symlinks). that's the zip-slip protection
- **zip bomb guard**: extraction stops and the new folder is deleted if the extracted total goes past a limit (e.g. 10× the zip size or 20 GB) or there are too many files (e.g. 100 000). numbers to tune
- at the end: an "Open folder" button (opens Explorer / Finder / the file manager)

### 5.5 Size and time estimate

- as soon as a file or folder is picked, Python reads its size from the disk (a folder: walks it and adds up every file) and shows e.g. "📦 2.3 GB, 412 files"
- the app measures how fast this PC encrypts: at startup it encrypts ~50 MB of random data once (≈ 0.1 to 0.5 s) and keeps the speed (MB/s)
- estimate = size ÷ speed, plus a margin for zipping folders. shown as "about 25 s" (rounded, it's an estimate)
- same thing on the Decrypt page, from the package size
- a progress bar while it runs (the page asks the app for the progress every half second)
- above ~4 GB, an extra line: "large file, this may take a few minutes"
- no hard size limit. we test up to 4 GB

---

## 6. Keys

### 6.1 Storage
- per-user app data folder (Windows `%APPDATA%\CryptEasy`, Linux `~/.local/share/CryptEasy`, macOS `~/Library/Application Support/CryptEasy`), overridable with `CRYPTEASY_HOME` for tests
```
CryptEasy/
├── keys/<id>/private.key     # both private keys (encryption + signing), locked with the key passphrase (section 6.2)
├── keys/<id>/public.pem      # both public keys, one after the other. this is the file you share
├── keys/<id>/info.json       # name, type, level, created date, fingerprint
├── contacts.json             # name, public key PEM, fingerprint, added date
└── settings.json             # app settings, e.g. { "language": "fr" }
```
- nothing else is stored. no copies of encrypted or decrypted files, no passphrases

### 6.2 Private key protection
Since the user picks the KDF, strength and salt, we can't use the standard encrypted PEM (`BestAvailableEncryption` picks its own KDF and settings). So `private.key` is our own small JSON file:

```json
{
  "format": "crypteasy-private-key",
  "version": 1,
  "kdf": "argon2id",
  "salt": "base64...",
  "params": { "memory_kib": 65536, "iterations": 3, "parallelism": 4 },
  "nonce": "base64...",
  "ciphertext": "base64..."
}
```

- lock: `lock_key = KDF(key passphrase, salt, params)` → AES-256-GCM encrypt the private keys (PKCS#8 DER) with `lock_key` → `ciphertext`
- unlock: same KDF with the stored salt and params → decrypt. wrong passphrase = GCM tag fails = "Wrong passphrase for this key."
- **no passphrase**: `"kdf": "none"`, no salt, no nonce, and the private keys are stored as-is in a `"plaintext"` field
- the salt and params aren't secret, they just have to be stored to redo the same derivation
- both KDFs come from `cryptography` (`PBKDF2HMAC` and `Argon2id`), no extra crypto lib
- on load, refuse silly params (e.g. Argon2 memory > 1 GiB) so a crafted key file can't freeze the app
- export = this same file. import also accepts a standard PEM (encrypted or not), which is then re-locked in this format

### 6.3 Fingerprint
SHA-256 of the public key (DER), shown as groups of 4 hex chars, first 16 groups. Same key always gives the same fingerprint on every machine.

---

## 7. Screens

All screens live inside the CryptEasy window.

| Page | Contains |
|---|---|
| **Home** | short intro, 4 big buttons (Encrypt, Decrypt, My keys, Contacts). first launch with no key → "create your key pair first" |
| **My keys** | list of my key pairs (name, type, level, fingerprint). generate new (level dropdown + advanced + "no passphrase" checkbox). export public / private, import private, change passphrase, delete (with confirmation) |
| **Contacts** | list (name, fingerprint). add (name + `.pem` file), rename, delete |
| **Encrypt** | pick file / pick folder buttons, size + time estimate, recipient picker, AES choice, security level indicator, *(stretch)* "sign as" checkbox, Encrypt button, progress bar, "save as" |
| **Decrypt** | pick package button, size + time estimate, key auto-picked (or import a key file), key passphrase field, *(stretch)* sender status, Decrypt button, progress bar, then "save as" / "keep zip or extract" for folders |
| **Info** | how it works, security levels explained, format, tips |

Common: nav bar with a **language switch (FR / EN)**, errors shown inline in plain language. Closing the window quits the app.

### 7.1 Languages

The app is in **French and English**.
- every text the user can see (buttons, labels, error messages, Info page) lives in **one translation file per language**, never written directly in the templates or the Python code:
```
src/crypteasy/ui/translations/
├── fr.json     # { "encrypt.button": "Chiffrer", "error.wrong_passphrase": "Phrase secrète incorrecte pour cette clé.", ... }
└── en.json     # { "encrypt.button": "Encrypt",  "error.wrong_passphrase": "Wrong passphrase for this key.", ... }
```
- pages and code only use the **key** (`encrypt.button`); a small helper looks it up in the current language
- first launch: the app picks the OS language (French if the OS is in French, English otherwise). the user can switch at any time from the nav bar, and the choice is saved in `settings.json`
- a missing text in one language falls back to English, so the app never shows an empty button
- **adding a language** = copy `en.json` to e.g. `pt.json`, translate the values, done. the app lists every file in `translations/` in the language switch
- a test checks that every file has the same keys as `en.json`, so nobody forgets a translation

---

## 8. Safety rules for the code itself

- crypto only from the **`cryptography`** library. no homemade crypto, no pycryptodome
- random only from `os.urandom` / `secrets`
- original filename from the package: keep only the base name, reject empty, `.`, `..`, NUL, path separators → falls back to `decrypted_file`
- never overwrite an existing file or folder
- extracting a decrypted folder: only into a new folder made by the app, every path checked, size and file count capped (section 5.4)
- the only temp files are the folder zip (encrypt) and the half-decrypted file (decrypt). both are deleted after each action, also on errors, and at startup
- **the local server**: pywebview talks to Flask through a small server on `127.0.0.1` only, on a random port. while the app is open, other programs on the PC (or a malicious website open in the user's normal browser) could try to call it. so: a random secret token per launch that every request must carry, CSRF tokens on every action, and a `Host` header check. this matters even more because our routes take real file paths
- no passphrases, keys or file contents in logs

---

## 9. What it does NOT do

- ❌ **send** files. the user sends the zip themselves (email, USB, Teams...)
- ❌ password-only encryption (no keys at all)
- ❌ per-file passwords. the sender would have to send the password to the recipient through a safe channel, which is exactly the problem public keys solve
- ❌ encrypt for several recipients at once
- ❌ compress files
- ❌ weak modes: no AES-CBC / ECB, no unauthenticated encryption
- ❌ recover anything if you lose your private key or its passphrase. no backdoor
- ❌ key servers, revocation, expiry dates, certificates, web of trust
- ❌ accounts, cloud, sync, network features
- ❌ protect you if your PC already has malware (it can read the key while it's unlocked)
- ❌ securely wipe memory or deleted files (Python can't guarantee it)
- ❌ mobile app, auto-update, installer, Apple / Microsoft code signing
- ❌ open GPG / age / 7-zip encrypted files (only our own format)

---

## 10. Tech stack and structure

| | |
|---|---|
| Language | Python 3.13 |
| Crypto | `cryptography` |
| Pages + logic | Flask |
| App window | **pywebview** (native window, native file dialogs, uses the OS web engine) |
| Packaging | PyInstaller one-file, no console window, built per OS by GitHub Actions on each release |
| Tests | pytest, run in CI on Windows + Linux (+ macOS once added) |

CI machines have no screen, so tests never open the window: they call `core/` and `keystore/` directly, and the pages through Flask's test client. The exe gets a `--no-window` mode (starts Flask only) so CI can smoke-test the built exe.

```
src/crypteasy/
  __main__.py      # start Flask + open the pywebview window
  core/            # keys.py, package.py (zip format), hybrid.py (encrypt/decrypt), kdf.py, levels.py,
                   # folders.py (zip / safe extract), speed.py (estimate), signing.py (stretch), errors.py
  keystore/        # paths.py, identities.py (my keys), contacts.py
  ui/              # Flask routes, templates/, static/, dialogs.py (pywebview native dialogs),
                   # i18n.py (translation helper), translations/ (fr.json, en.json)
packaging/         # PyInstaller spec + smoke test
tests/
```

---

## 11. Open question

| Question | Explanation | Recommendation |
|---|---|---|
| macOS: Apple Silicon only, or also Intel Macs? | `macos-latest` builds for Apple Silicon (M1 and newer). Intel Macs (before ~2021) need a separate runner, which GitHub is phasing out | Apple Silicon only |
