# CryptEasy

File encryption for people who are not cryptographers.

CryptEasy is a desktop application that encrypts a file for a recipient using their public key, and decrypts files sent to you with your own password-protected private key. It aims for safe defaults in a few clicks, while still letting advanced users choose the algorithm and key size. It is shipped as a single self-contained executable: nothing to install, no Python needed.

> **Status:** in development (SAE 5.02, autumn 2026). The features below are the planned scope; see the milestones further down.

## Features

- **Key pairs**: generate an elliptic-curve (X25519, default) or RSA (2048 / 3072 / 4096-bit) key pair. The private key is stored encrypted with your password.
- **Encrypt for a recipient**: hybrid encryption. The file is encrypted with a fresh AES-256-GCM key, and that key is protected with the recipient's public key.
- **Decrypt**: open files sent to you with your private key and password.
- **Contacts book**: save your contacts' public keys once, with fingerprints you can verify in person or by phone.
- **Import / export**: share your public key as a `.pem` file and import others'.
- *Stretch goal:* sign files and verify signatures.

## Security design

- Uses only the [`cryptography`](https://cryptography.io/) library (pyca). No cryptographic primitive is re-implemented.
- Authenticated encryption only (AES-256-GCM), in authenticated chunks. Any modification, truncation, or reordering of an encrypted file is detected, and large files are processed without loading them into memory.
- The original filename is stored inside the encrypted data, and it is sanitized on decryption (no path traversal).
- Decryption output is written only once every chunk has been verified. A failed decryption leaves no partial plaintext.
- The interface is a local web app bound to `127.0.0.1` only, with CSRF protection, a per-launch access token, and `Host` header checks against DNS rebinding.

The security of public-key encryption depends on using the *right* public key. Always compare a contact's fingerprint with them through another channel before trusting it.

## Download

Get the latest executable from the repository's **Releases** page:

- Windows: `crypteasy-<version>-windows-x86_64.exe`. Run it directly.
- Linux: `crypteasy-<version>-linux-x86_64.tar.gz`. Run `tar -xzf crypteasy-*.tar.gz && ./crypteasy`.

Check a download against the published checksums: `sha256sum -c SHA256SUMS --ignore-missing`.

## Development

Quick start (needs [uv](https://docs.astral.sh/uv/) and GNU Make):

```bash
make install && make lint && make test && make run
```

Everything else is in **[DEV_README.md](DEV_README.md)**: uv usage, Makefile targets, linting, tests, branching and PRs, versioning and releases, and CI.

## Project layout

```
src/crypteasy/
  core/        # crypto engine: keys, file format, hybrid encryption
  keystore/    # own identity storage, contacts book
  ui/          # Flask web interface
packaging/     # PyInstaller spec, launcher, smoke test
tests/         # core/, keystore/, ui/, e2e/
```

## Milestones

| Milestone | Target | Content |
|---|---|---|
| MS0 Foundations | week 5 | Scaffold, CI, interfaces, packaging spike |
| MS1 Components | week 6 | Crypto engine, key storage, GUI skeleton |
| MS2 MVP complete | week 7 | Full encrypt → decrypt flow in the executable |
| MS3 Release candidate | week 8 | Tested on clean machines, release `v1.0.0rc1` |

## Contributing

See [DEV_README.md, section 6: Branches and pull requests](DEV_README.md#6-branches-and-pull-requests).

## Team

SAE 5.02, BUT Réseaux & Télécommunications, *Parcours Cybersécurité*, IUT Nancy-Brabois.

Diogo CARVALHO · Sam KAFAI · Yanis DISCOURS · YS
