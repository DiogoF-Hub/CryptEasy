import json

import pytest

from crypteasy.keystore import contacts, paths
from crypteasy.keystore.errors import (
    AlreadyExistsError,
    CorruptedStoreError,
    InvalidNameError,
    InvalidPublicKeyError,
    NotFoundError,
)

from .conftest import fake_fingerprint, fake_pem

pytestmark = pytest.mark.usefixtures("fake_core")


def test_empty_book():
    assert contacts.list_contacts() == []


def test_add_list_get():
    pem = fake_pem("rsa-3072")
    added = contacts.add_contact("  Bob ", pem)
    assert added.name == "Bob"
    assert added.key_type == "rsa-3072"
    assert added.fingerprint == fake_fingerprint(pem)
    assert contacts.list_contacts() == [added]
    assert contacts.get_contact(added.fingerprint) == added


def test_list_sorted_by_name():
    for name in ["carol", "Alice", "bob"]:
        contacts.add_contact(name, fake_pem())
    assert [c.name for c in contacts.list_contacts()] == ["Alice", "bob", "carol"]


def test_same_key_twice_rejected():
    pem = fake_pem()
    contacts.add_contact("Bob", pem)
    with pytest.raises(AlreadyExistsError):
        contacts.add_contact("Robert", pem)


@pytest.mark.parametrize(
    "pem",
    [b"", b"not a key", fake_pem().replace(b"x25519", b"dsa-1024"), b"\xff" * 10, b"A" * 20_000],
)
def test_invalid_key_rejected_and_nothing_saved(pem):
    with pytest.raises(InvalidPublicKeyError):
        contacts.add_contact("Bob", pem)
    assert not paths.contacts_file().exists()


def test_invalid_name_rejected():
    with pytest.raises(InvalidNameError):
        contacts.add_contact("", fake_pem())


def test_rename():
    c = contacts.add_contact("Bob", fake_pem())
    renamed = contacts.rename_contact(c.fingerprint, "Robert")
    assert renamed.name == "Robert"
    assert [x.name for x in contacts.list_contacts()] == ["Robert"]


def test_rename_and_remove_unknown():
    with pytest.raises(NotFoundError):
        contacts.rename_contact("0000", "x")
    with pytest.raises(NotFoundError):
        contacts.remove_contact("0000")
    with pytest.raises(NotFoundError):
        contacts.get_contact("0000")


def test_remove():
    a = contacts.add_contact("Alice", fake_pem())
    b = contacts.add_contact("Bob", fake_pem())
    contacts.remove_contact(a.fingerprint)
    assert contacts.list_contacts() == [b]


def _edit_file(change):
    path = paths.contacts_file()
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def test_hand_edited_fingerprint_detected():
    contacts.add_contact("Bob", fake_pem())
    _edit_file(lambda d: d["contacts"][0].update(fingerprint="AAAA " * 15 + "AAAA"))
    with pytest.raises(CorruptedStoreError):
        contacts.list_contacts()


def test_hand_swapped_key_detected():
    """Someone replaces Bob's key with theirs but keeps Bob's fingerprint."""
    contacts.add_contact("Bob", fake_pem())
    _edit_file(lambda d: d["contacts"][0].update(public_pem=fake_pem().decode()))
    with pytest.raises(CorruptedStoreError):
        contacts.list_contacts()


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.update(version=2),
        lambda d: d.update(contacts={}),
        lambda d: d["contacts"].append("Eve"),
        lambda d: d["contacts"][0].pop("added"),
        lambda d: d["contacts"][0].update(name=123),
        lambda d: d["contacts"][0].update(name="Bob‮"),
        lambda d: d["contacts"][0].update(public_pem="clé"),
        lambda d: d["contacts"].append(dict(d["contacts"][0])),
    ],
)
def test_damaged_file_detected(change):
    contacts.add_contact("Bob", fake_pem())
    _edit_file(change)
    with pytest.raises(CorruptedStoreError):
        contacts.list_contacts()


@pytest.mark.parametrize(
    "content", [b"{oops", b"[]", b"\xff\xfe", b"[" * 16_000, b" " * (9 * 1024 * 1024)]
)
def test_unreadable_file_detected(content):
    paths.contacts_file().write_bytes(content)
    with pytest.raises(CorruptedStoreError):
        contacts.list_contacts()


def test_damaged_file_is_not_overwritten_by_add():
    paths.contacts_file().write_bytes(b"{oops")
    with pytest.raises(CorruptedStoreError):
        contacts.add_contact("Bob", fake_pem())
    assert paths.contacts_file().read_bytes() == b"{oops"
