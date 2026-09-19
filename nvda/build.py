#!/usr/bin/env python3
"""Package the NVDA add-on.

An .nvda-addon file is a zip with the manifest at its root, so the packing
itself is four lines. The rest of this is the check worth having: every entry
point the driver asks the library for by name is looked up in the library's own
export table first, and a name that is not there stops the build.

That check exists because of how the failure would otherwise look. ctypes
resolves a name the moment it is used, not when the library is loaded, so a
misspelling or an entry point that was never wrapped shows up as speech simply
not happening, in a screen reader, with the log the only way to find out why.
Here it is a message before anything is shipped.

usage: build.py [--version V] [--tested V] [--out DIR]
"""

import argparse
import os
import re
import struct
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ADDON = os.path.join(HERE, "addon")

# Engine payloads are supplied explicitly with --dll; none are fetched.

#: Where the libraries go inside the add-on. Not "openevv", because that is
#: the driver module's name and a directory of the same name beside it would be
#: a package competing with it.
ENGINE_DIR = "synthDrivers/openevv_engine"

DEFAULT_TESTED = "2026.2.0"


def say(what):
    print("build: " + what)


def die(what):
    sys.stderr.write("build: " + what + "\n")
    raise SystemExit(1)


# ---- reading a library's export table --------------------------------------


def _rva_to_offset(sections, rva):
    for start, size, raw in sections:
        if start <= rva < start + size:
            return raw + (rva - start)
    return None


def exported_names(path):
    """Every name a PE exports, read out of the file itself.

    Done here rather than with objdump so that packaging needs nothing but
    Python; the add-on is built on machines that have no cross toolchain.
    """
    with open(path, "rb") as f:
        image = f.read()

    if image[:2] != b"MZ":
        die("%s is not a PE file at all" % path)
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    if image[pe : pe + 4] != b"PE\0\0":
        die("%s has no PE header" % path)

    sections_count = struct.unpack_from("<H", image, pe + 6)[0]
    optional_size = struct.unpack_from("<H", image, pe + 20)[0]
    optional = pe + 24
    magic = struct.unpack_from("<H", image, optional)[0]
    if magic == 0x10B:
        directories = optional + 96
    elif magic == 0x20B:
        directories = optional + 112
    else:
        die("%s has an optional header this does not know (%#x)" % (path, magic))

    export_rva, export_size = struct.unpack_from("<II", image, directories)
    if export_rva == 0 or export_size == 0:
        die("%s exports nothing" % path)

    sections = []
    at = optional + optional_size
    for _ in range(sections_count):
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from(
            "<IIII", image, at + 8
        )
        # A section whose raw size is short still covers its virtual size in
        # memory, so take whichever is larger for the lookup.
        sections.append((virtual_address, max(virtual_size, raw_size), raw_pointer))
        at += 40

    table = _rva_to_offset(sections, export_rva)
    if table is None:
        die("%s puts its export table outside every section" % path)

    count = struct.unpack_from("<I", image, table + 0x18)[0]
    names_rva = struct.unpack_from("<I", image, table + 0x20)[0]
    names = _rva_to_offset(sections, names_rva)
    if names is None:
        die("%s puts its name table outside every section" % path)

    out = set()
    for i in range(count):
        one = struct.unpack_from("<I", image, names + i * 4)[0]
        where = _rva_to_offset(sections, one)
        if where is None:
            continue
        end = image.index(b"\0", where)
        out.add(image[where:end].decode("ascii", "replace"))
    return out


# ---- what the driver asks for ----------------------------------------------


def wanted_names():
    """Every eci entry point the engine layer names."""
    source = open(os.path.join(ADDON, "synthDrivers", "_openevv.py"), encoding="utf-8").read()
    return set(re.findall(r"\bdll\.(eci\w+)", source))


# ---- the version -----------------------------------------------------------


def described():
    try:
        out = subprocess.run(
            ["git", "describe", "--tags", "--always", "--dirty"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "0.0"
    return out[1:] if out.startswith("v") else out


# ---- packing ---------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version")
    ap.add_argument("--tested", default=DEFAULT_TESTED)
    ap.add_argument("--out", default=os.path.join(ROOT, "build"))
    ap.add_argument("--dll", required=True, help="separately supplied, compatible OpenEVV x64 library")
    ap.add_argument("--engine-notice", help="optional additional engine license/provenance text to include")
    args = ap.parse_args()

    version = args.version or described()

    have = []
    if args.engine_notice and not os.path.isfile(args.engine_notice):
        die("the supplied engine notice does not exist")
    libraries = [(args.dll, "eci.dll", True)]
    for path, name, required in libraries:
        if os.path.isfile(path):
            have.append((path, name))
        elif required:
            die(
                "there is no %s; supply your own compatible OpenEVV x64 library with --dll"
                % os.path.relpath(path, ROOT)
            )
        else:
            say("no %s, so the add-on is sixty-four bit only" % name)

    wants = wanted_names()
    if not wants:
        die("the engine layer names no entry points, which cannot be right")
    for path, name in have:
        with open(path, "rb") as f:
            image = f.read()
        if len(image) < 64 or image[:2] != b"MZ":
            die("%s is not a Windows PE library" % path)
        pe = struct.unpack_from("<I", image, 0x3c)[0]
        if pe + 6 > len(image) or image[pe:pe+4] != b"PE\0\0" or struct.unpack_from("<H", image, pe+4)[0] != 0x8664:
            die("%s is not an x64 PE library" % path)
        has = exported_names(path)
        missing = sorted(wants - has)
        if missing:
            die(
                "%s does not export %s, which the driver calls"
                % (name, ", ".join(missing))
            )
        say("%s exports all %d names the driver calls" % (name, len(wants)))

    manifest = open(os.path.join(HERE, "manifest.ini.in"), encoding="utf-8").read()
    manifest = manifest.replace("@VERSION@", version).replace("@TESTED@", args.tested)

    os.makedirs(args.out, exist_ok=True)
    target = os.path.join(args.out, "openevv-%s.nvda-addon" % version)

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.ini", manifest)
        z.write(os.path.join(ROOT, "LICENSE"), "LICENSE")
        z.write(os.path.join(ROOT, "NOTICE.md"), "NOTICE.md")
        if args.engine_notice:
            z.write(args.engine_notice, "ENGINE-NOTICE.txt")
        for leaf in ("openevv.py", "_openevv.py", "_openevv_dictionaries.py", "_openevv_tools.py"):
            z.write(os.path.join(ADDON, "synthDrivers", leaf), "synthDrivers/" + leaf)
        z.write(os.path.join(ADDON, "globalPlugins", "openevvSettings.py"), "globalPlugins/openevvSettings.py")
        z.write(os.path.join(ADDON, "doc", "en", "readme.html"), "doc/en/readme.html")
        for path, name in have:
            z.write(path, ENGINE_DIR + "/" + name)

    say("wrote %s, %d bytes" % (target, os.path.getsize(target)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
