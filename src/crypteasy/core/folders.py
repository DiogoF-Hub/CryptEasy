import os
import shutil
import stat
import zipfile
from pathlib import Path, PurePosixPath

from crypteasy.core.errors import DecryptionError, ExtractionTooLargeError, UnsafeArchiveError

"""
In this file I have everything about folders (TECHNICAL_SPEC.md, section 5.4):
- zip_folder: before encrypting a folder, it is zipped into one file
- extract_folder: after decrypting, that zip is extracted into a brand new folder,
  with every path checked (zip-slip) and the size and number of files capped (zip bomb)

Why it matters: anyone can encrypt a file for me with my public key, including someone
who wants to attack me. So a decrypted zip is NOT trusted: it can be crafted on purpose.
"""

# Limits when extracting a folder (section 5.4, "numbers to tune")
# The zip is made with no compression (see zip_folder), so a real folder is about as big
# once extracted as its zip. 10 times the zip size is a very generous margin
max_files = 100_000
max_ratio = 10
# Small zips get at least 1 MiB, so a tiny zip with an empty file still works
min_limit = 1024 * 1024
# And never more than 20 GiB, whatever the zip size
max_limit = 20 * 1024**3
# Extracted files are copied 1 MiB at a time, never fully loaded in memory
copy_chunk = 1024 * 1024


# This func zips a folder into dst_zip, keeping the paths relative to the folder
# e.g. holidays/beach/sun.jpg is stored as "beach/sun.jpg"
# The zip is written straight to the disk file by file, so a big folder never sits in RAM
def zip_folder(folder, dst_zip):
    folder = Path(folder)

    # ZIP_STORED = no compression. The zip is encrypted right after, and encrypted data
    # can't be compressed anyway. It also keeps the zip bomb guard simple: a real folder
    # is never 10 times bigger than its zip
    # allowZip64 lets the zip go past 4 GiB
    with zipfile.ZipFile(dst_zip, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
        # os.walk goes through every subfolder, one at a time
        # for each one it gives: its path, the names of its subfolders, the names of its files
        for root, dirs, files in os.walk(folder):
            here = Path(root)
            rel = here.relative_to(folder)

            # A symlink can point anywhere on the disk (e.g. to C:\Windows),
            # so symlinked folders are skipped (section 5.4)
            # dirs[:] changes the list in place, so os.walk doesn't go into them
            dirs[:] = sorted(d for d in dirs if not (here / d).is_symlink())

            # An empty folder has no file to carry its path, so it is stored on its own
            # In a zip, a name ending with "/" means "this is a folder"
            if rel != Path(".") and not dirs and not files:
                zf.writestr(rel.as_posix() + "/", b"")

            for name in sorted(files):
                path = here / name
                # Only normal files: no symlinks, and no special files (sockets, pipes, ...)
                if path.is_symlink() or not path.is_file():
                    continue
                # as_posix() writes the path with "/", the separator zips always use
                zf.write(path, (rel / name).as_posix())


# This func extracts zip_path into a NEW folder created inside parent, and returns it
# The new folder is named after the zip: holidays.zip gives holidays/,
# or "holidays (2)/" if that name is already taken. So nothing of the user's is overwritten
# If anything goes wrong, the new folder is deleted, so nothing half extracted stays behind
def extract_folder(zip_path, parent):
    zip_path = Path(zip_path)
    folder = new_folder(Path(parent), zip_path.stem or "folder")
    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()
            limit = size_limit(zip_path.stat().st_size)

            # 1. Check everything that can be checked before writing anything
            if len(infos) > max_files:
                raise ExtractionTooLargeError(f"{len(infos)} files, the limit is {max_files}")
            # file_size is the size the zip CLAIMS for each file. It can lie, so the real
            # bytes are counted again while extracting (step 2). But if even the claimed
            # total is too big, there's no need to start
            if sum(info.file_size for info in infos) > limit:
                raise ExtractionTooLargeError("the files announced by the zip are too big")
            # Every path is checked first, so a bad path at the end of the zip
            # stops the extraction before the first file is written
            targets = [safe_target(folder, info) for info in infos]

            # 2. Extract, counting the real bytes that come out
            written = 0
            for info, target in zip(infos, targets, strict=True):
                if target is None:  # the entry is the folder itself, nothing to do
                    continue
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                # "xb" = create a new file, and fail if it already exists. That happens
                # when the zip holds the same name twice (or "A.txt" and "a.txt" on
                # Windows, where case doesn't count): never overwrite a file silently
                with zf.open(info) as src, open(target, "xb") as dst:
                    while chunk := src.read(copy_chunk):
                        written += len(chunk)
                        if written > limit:
                            raise ExtractionTooLargeError(f"more than {limit} bytes extracted")
                        dst.write(chunk)

    # FileExistsError: the same name twice. NotADirectoryError: a path goes "through" a
    # file, e.g. "a" is a file and then "a/b.txt". A zip made by zip_folder never does that
    except (FileExistsError, NotADirectoryError) as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise UnsafeArchiveError("the zip holds the same path twice") from exc
    except (zipfile.BadZipFile, zipfile.LargeZipFile, EOFError) as exc:
        shutil.rmtree(folder, ignore_errors=True)
        raise DecryptionError("the decrypted folder is not a valid zip") from exc
    # BaseException catches everything, even Ctrl+C: the folder is deleted, then
    # "raise" alone sends the same error on, unchanged
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    return folder


# This func gives the size limit of the extracted folder for a zip of zip_size bytes:
# 10 times the zip size, but at least 1 MiB and at most 20 GiB
def size_limit(zip_size):
    return min(max(max_ratio * zip_size, min_limit), max_limit)


# This func creates parent/name, or "name (2)", "name (3)"... if the name is taken
# mkdir() (with no exist_ok) fails if the folder already exists, so even if another
# program creates the same folder at the same moment, we never reuse an existing one
def new_folder(parent, name):
    n = 1
    while True:
        candidate = parent / (name if n == 1 else f"{name} ({n})")
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            n += 1


# This func checks one path of the zip and gives where it will be written in folder
# It gives None for an entry that is the folder itself (e.g. "./")
# It raises UnsafeArchiveError for any path that could end up outside the folder
# Examples of what an attacker can put in a zip (that's the "zip-slip" attack):
#   "../../Startup/virus.exe"  goes up out of the folder
#   "/etc/passwd"  or  "C:/Windows/x.dll"  absolute paths
#   "..\\x.exe"  same thing with Windows separators
#   "report.txt:hidden"  on Windows, writes into a hidden part of a file (NTFS stream)
#   a symlink entry, which could then send the next files anywhere
def safe_target(folder, info):
    # Zips should use "/", but some tools write "\", so both are treated as separators
    raw = info.filename.replace("\\", "/")
    parts = [p for p in PurePosixPath(raw).parts if p != "."]

    # A symlink is recognised by its file type, stored in the top 16 bits of
    # external_attr (the same "mode" as a Unix file)
    is_symlink = stat.S_ISLNK(info.external_attr >> 16)
    if raw.startswith("/") or is_symlink:
        raise UnsafeArchiveError(f"unsafe path in the zip: {info.filename!r}")
    for part in parts:
        # ":" catches "C:" (a drive) and "name:stream", "\0" is never valid in a name
        if part == ".." or ":" in part or "\0" in part:
            raise UnsafeArchiveError(f"unsafe path in the zip: {info.filename!r}")
    if not parts:
        return None

    # Last check, on the real final path: resolve() follows "..", symlinks already on
    # the disk, etc. The result must still be inside the folder
    root = folder.resolve()
    target = folder.joinpath(*parts).resolve()
    if target == root or not target.is_relative_to(root):
        raise UnsafeArchiveError(f"unsafe path in the zip: {info.filename!r}")
    return target
