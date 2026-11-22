# CryptEasy

Send files securely, without being a cryptographer.

CryptEasy is a desktop app that opens in its own window, like any program. You generate a key pair, share your public key, and save other people's public keys as contacts. To send a file or a folder, you pick it and a contact, and CryptEasy gives you an encrypted `.zip` package that only that contact can open. To open a package someone sent you, you pick it, type your key passphrase, and you get the original back.

Safe defaults in a few clicks. Advanced users can tune every setting, and the app shows how secure their choice is. The only thing anyone ever shares is their public key: no passphrase ever travels.

It's shipped as a single executable: nothing to install, no Python needed.

> SAE 5.02 project, autumn 2026. Full technical reference: [docs/TECHNICAL_SPEC.md](docs/TECHNICAL_SPEC.md).

## Features

- **Key pairs**: X25519 (default) or RSA 2048 / 3072 / 4096. On disk, the private key is locked with your key passphrase.
- **Contacts book**: save your contacts' public keys once, with a fingerprint you check with them by phone or in person.
- **Encrypt** a file or a whole folder for a contact (or for yourself). Hybrid encryption: the file is encrypted with a new random AES-GCM key, and that key is locked with the recipient's public key.
- **Decrypt** a package sent to you. The right key is picked by itself, you only type its passphrase.
- **Import / export**: share your public key as a `.pem` file, back up your private key, import keys made with OpenSSL.
- **Security levels**: pick one in a list, or tune each setting yourself; the indicator always rates your weakest setting.
- **Clear error messages**: wrong passphrase, not for you, damaged or modified file, not a CryptEasy file.
- **French and English** interface, plus an Info page that explains how it all works.

## Security levels

| Level | Key type | File cipher | Key passphrase protection | Passphrase |
|---|---|---|---|---|
| 🟢🟢 **Very strong** | X25519 or RSA-4096 | AES-256-GCM | Argon2id (max), 32-byte salt | 16+ chars |
| 🟢 **Strong** *(default)* | X25519 or RSA-3072 | AES-256-GCM | Argon2id (normal), 16-byte salt | 12+ chars |
| 🟡 **Medium** | RSA-2048 | AES-128-GCM | PBKDF2-SHA256, 16-byte salt | 12+ chars |
| 🔴 **Weak** *(learning only)* | RSA-2048 | AES-128-GCM | PBKDF2-SHA256, **no salt** | 12+ chars |
| ⛔ **No protection** | any | any | none, the key is in clear on the disk | none |

The levels and what they protect against are explained in [docs/TECHNICAL_SPEC.md, section 4](docs/TECHNICAL_SPEC.md#4-security-options).

## Security design

- Only the [`cryptography`](https://cryptography.io/) library is used. No cryptographic primitive is written by hand.
- Authenticated encryption only (AES-GCM), in chunks of 64 KiB. Any change, cut, reordering or extra data in a package is detected, and big files never have to fit in RAM.
- The original file name is encrypted inside the package, and cleaned on decryption (no `../` path tricks, no Windows device names, no invisible characters).
- The decrypted file gets its real name only once **every** chunk is checked. A failed decryption leaves nothing behind. Nothing is ever overwritten.
- Folders are zipped by the app; on extraction, dangerous paths and zip bombs are refused.
- Key files, packages and folder zips come from other people, so they are all checked before use: a crafted file can't freeze the app (huge KDF costs, huge sizes) or crash it.
- The window shows pages served by Flask on `127.0.0.1` only, with a random token at each launch, CSRF protection and `Host` header checks.

Public-key encryption is only as safe as the public key you use: always compare a contact's fingerprint with them, through another channel, before trusting it.

## What it doesn't do

It doesn't **send** files (you send the package yourself: email, USB stick...), doesn't encrypt for several people at once, doesn't do password-only encryption, and can't recover anything if you lose your private key or its passphrase. Full list: [docs/TECHNICAL_SPEC.md, section 9](docs/TECHNICAL_SPEC.md#9-what-it-does-not-do).

## Download

Get the latest version from the repository's **Releases** page:

| OS | File | How to run |
|---|---|---|
| **Windows** 10 / 11 | `crypteasy-<version>-windows-x86_64.exe` | double-click it |
| Linux | `crypteasy-<version>-linux-x86_64.tar.gz` | `tar -xzf crypteasy-*.tar.gz && ./crypteasy` |

The Linux binary uses the window engine of your system: it needs glibc 2.35+ and WebKit2GTK 4.1. On Debian / Ubuntu that's 2 packages (the second one is easy to miss):

```bash
sudo apt install libwebkit2gtk-4.1-0 gir1.2-webkit2-4.1
```

macOS isn't built for now (see [docs/pm/decisions.md](docs/pm/decisions.md)); from source it runs with `uv run`.

To check a download, compare it with the release's `SHA256SUMS`:
- Windows (PowerShell): `Get-FileHash .\crypteasy-<version>-windows-x86_64.exe -Algorithm SHA256`
- Linux: `sha256sum -c SHA256SUMS --ignore-missing`

Your keys, contacts and settings are kept in `%APPDATA%\CryptEasy` on Windows and `~/.local/share/CryptEasy` on Linux.

## Development

Quick start (needs [uv](https://docs.astral.sh/uv/) and GNU Make):

```bash
git clone https://github.com/DiogoF-Hub/CryptEasy.git
cd CryptEasy
make install && make lint && make test && make run
```

Everything else is in **[DEV_README.md](DEV_README.md)**: uv, Makefile targets, linting, tests, branches and pull requests, versioning and releases, CI.

## Project layout

```
src/crypteasy/
  __main__.py  # starts Flask and opens the app window (pywebview)
  core/        # crypto engine: keys, KDF, package format, hybrid encryption, folders
  keystore/    # my key pairs, contacts book, settings
  ui/          # Flask pages, templates, translations (fr / en), native dialogs
packaging/     # PyInstaller spec, launcher, smoke test of the built exe
tests/         # core/, keystore/, ui/
docs/          # technical spec, CDC, project management (planning, decisions, risks, meetings)
```

## Project management

- Tasks, owners, estimates and time spent: [GitHub board](https://github.com/users/DiogoF-Hub/projects/1)
- Planning: [initial plan](docs/pm/planning-v1.md), then the [re-plan of Nov 8](docs/pm/planning-v2.md) into 3 one-week sprints
- [Decisions](docs/pm/decisions.md), [risks](docs/pm/risks.md), [meeting notes](docs/pm/meetings/)

The first milestones (MS0 to MS3, weeks 5 to 8) were replaced by the 3 sprints on Nov 8; the reasons are in planning v2.

## Team

SAE 5.02, BUT Réseaux & Télécommunications, *Parcours Cybersécurité*, IUT Nancy-Brabois.

Diogo CARVALHO · Sam KAFAI · Yanis DISCOURS · Yani SAI
