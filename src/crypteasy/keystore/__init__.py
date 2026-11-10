"""Key storage: my key pairs, the contacts book and the app settings (TECHNICAL_SPEC section 6).

Public modules: `paths` (data folder, settings.json), `identities` (my key pairs),
`contacts` (contacts.json), `errors`. Everything that needs the crypto engine goes
through `_core`, the only module that imports `crypteasy.core`.
"""
