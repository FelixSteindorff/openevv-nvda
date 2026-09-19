"""Optional pronunciation data, kept in NVDA's config (also on secure screens).

No network access occurs while loading/speaking. Normal mode prepares cache
files; secure mode only reads. Updates publish atomic snapshots; custom files
are separate.
"""
import io
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request
import uuid
import zipfile

PROFILES = {
	"builtin": "Original (no additional dictionaries)",
	"alternative": "Alternative (English/Spanish)",
	"community": "Community (German/English)",
	"custom": "Custom dictionaries",
	"alternative_custom": "Alternative + custom corrections",
	"community_custom": "Community + custom corrections",
}
PROVIDERS = {
	"alternative": "https://github.com/mohamed00/AltIBMTTSDictionaries/archive/refs/heads/master.zip",
	"community": "https://github.com/eigencrow/IBMTTSDictionaries/archive/refs/heads/master.zip",
}
PREFIXES = {0x10000: "enu", 0x10001: "eng", 0x20000: "esp", 0x20001: "esm",
	0x30000: "fra", 0x30001: "frc", 0x40000: "deu", 0x50000: "ita"}
VOLUMES = {"main": 0, "root": 1, "abbr": 2}
FILENAME = re.compile(r"^([a-z]{3})(main|root|abbr)\.dic$", re.I)
MAX_BYTES = 16 * 1024 * 1024


def root():
	try:
		from config import WritePaths
		path = WritePaths.configDir
	except ImportError:  # NVDA before WritePaths
		import globalVars
		path = globalVars.appArgs.configPath
	return Path(path) / "openevvDictionaries"


def directory(profile, base=None):
	base = Path(base) if base is not None else root()
	if profile == "custom":
		return base / "custom"
	if profile not in PROVIDERS:
		return None
	try:
		name = json.loads((base / profile / "current.json").read_text(encoding="utf-8"))["snapshot"]
		if not re.fullmatch(r"[0-9a-f]{32}", name):
			return None
		path = base / profile / name
		return path if path.is_dir() else None
	except (OSError, ValueError, KeyError, TypeError):
		return None


def parse(data, encoding="cp1252"):
	# Legacy .dic is CP1252. UTF-8 is accepted explicitly with a BOM,
	# avoiding ambiguous guessing that turns German umlauts into mojibake.
	text = data.decode("utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else encoding)
	entries = []
	for number, line in enumerate(text.splitlines(), 1):
		if not line.strip() or line.lstrip().startswith(("#", ";")):
			continue
		key, sep, value = line.partition("\t")
		key, value = key.strip(), value.strip()
		if not sep or not key or not value or "\x00" in line:
			raise ValueError("Invalid dictionary entry on line %d" % number)
		key, value = key.encode(encoding), value.encode(encoding)
		if len(key) > 128 or len(value) > 512:
			raise ValueError("Dictionary entry too long on line %d" % number)
		entries.append((key, value))
	return entries


def entries(profile, language, base=None):
	path = directory(profile, base)
	prefix = PREFIXES.get(language)
	if path is None or not path.is_dir() or prefix is None:
		return []
	result = []
	seen = set()
	for file in sorted(path.iterdir()):
		match = FILENAME.fullmatch(file.name)
		if not match or match[1].lower() != prefix or not file.is_file():
			continue
		volume = VOLUMES[match[2].lower()]
		if volume in seen or file.stat().st_size > MAX_BYTES:
			raise ValueError("Duplicate or oversized dictionary: " + file.name)
		seen.add(volume)
		result.extend((volume, key, value) for key, value in parse(file.read_bytes()))
	return result


def prepared(profile, languages, base=None):
	"""Normalise once for ECI's bulk loader; secure mode only reads the cache."""
	base = Path(base) if base is not None else root()
	if profile in ("alternative_custom", "community_custom"):
		original = prepared(profile.removesuffix("_custom"), languages, base)
		custom = prepared("custom", languages, base)
		result = {}
		for language in languages:
			volumes = dict(original.get(language, ()))
			for volume, own in custom.get(language, ()):
				if volume not in volumes:
					volumes[volume] = own
					continue
				raw, overrides = volumes[volume].read_bytes(), own.read_bytes()
				target = base / "prepared" / (hashlib.sha256(b"overlay-v1\0" + raw + b"\0" + overrides).hexdigest() + ".dic")
				if not target.exists():
					ensureWritable()
					# ECI keys are exact byte strings. Own identical keys win in
					# the same volume; other original entries remain untouched.
					merged = dict(parse(raw))
					merged.update(parse(overrides))
					atomicWrite(target, b"\n".join(k+b"\t"+v for k,v in merged.items()) + b"\n\n")
				volumes[volume] = target
			if volumes:
				result[language] = sorted(volumes.items())
		return result
	path = directory(profile, base)
	if path is None or not path.is_dir():
		return {}
	try:
		import globalVars
		secure = globalVars.appArgs.secure
	except ImportError:  # standalone test runner
		secure = False
	result = {}
	for language in languages:
		prefix = PREFIXES.get(language)
		if not prefix:
			continue
		seen = set()
		for file in sorted(path.iterdir()):
			match = FILENAME.fullmatch(file.name)
			if not match or match[1].lower() != prefix or not file.is_file():
				continue
			volume = VOLUMES[match[2].lower()]
			if volume in seen or file.stat().st_size > MAX_BYTES:
				raise ValueError("Duplicate or oversized dictionary: " + file.name)
			seen.add(volume)
			raw = file.read_bytes()
			# Content-addressed: original files stay untouched, including custom
			# UTF-8 files. A final blank line avoids ECI dropping its last entry.
			target = base / "prepared" / (hashlib.sha256(raw).hexdigest() + ".dic")
			if not target.is_file():
				if secure:
					raise ValueError("Load the dictionary in normal NVDA first, then copy the settings for sign-in again")
				normal = b"\n".join(key+b"\t"+value for key, value in parse(raw)) + b"\n\n"
				target.parent.mkdir(parents=True, exist_ok=True)
				temp = target.with_suffix("." + uuid.uuid4().hex + ".tmp")
				temp.write_bytes(normal)
				os.replace(temp, target)
			result.setdefault(language, []).append((volume, target))
	return result


def install(profile, archive, base=None):
	ensureWritable()
	if profile not in PROVIDERS:
		raise ValueError("This profile cannot be downloaded")
	if len(archive) > MAX_BYTES:
		raise ValueError("Dictionary download too large")
	files = {}
	with zipfile.ZipFile(io.BytesIO(archive)) as z:
		for info in z.infolist():
			parts = info.filename.split("/")
			# Only repository-root files; do not accidentally pick IBMTTS 6.7
			# variants or extract paths supplied by an archive.
			if len(parts) != 2 or not FILENAME.fullmatch(parts[1]):
				continue
			name = parts[1].lower()
			if name in files or info.file_size > MAX_BYTES or sum(map(len, files.values())) + info.file_size > MAX_BYTES:
				raise ValueError("Invalid dictionary download")
			data = z.read(info)
			parse(data)
			files[name] = data
	if not files:
		raise ValueError("The download contains no dictionaries")
	base = Path(base) if base is not None else root()
	name = uuid.uuid4().hex
	path = base / profile / name
	path.mkdir(parents=True)
	for filename, data in files.items():
		(path / filename).write_bytes(data)
	metadata = dict(snapshot=name, source=PROVIDERS[profile], files=sorted(files))
	(path / "source.json").write_text(json.dumps(metadata), encoding="utf-8")
	temp = path.parent / (name + ".json")
	temp.write_text(json.dumps(metadata), encoding="utf-8")
	os.replace(temp, path.parent / "current.json")
	return sorted(files)


def download(profile, base=None):
	ensureWritable()
	request = urllib.request.Request(PROVIDERS[profile], headers={"User-Agent": "OpenEVV-NVDA"})
	with urllib.request.urlopen(request, timeout=30) as response:
		data = response.read(MAX_BYTES + 1)
	return install(profile, data, base)


def ensureWritable():
	try:
		import globalVars
		if globalVars.appArgs.secure:
			raise ValueError("OpenEVV data is read-only on secure screens.")
	except ImportError:
		pass


def atomicWrite(path, data):
	ensureWritable()
	path.parent.mkdir(parents=True, exist_ok=True)
	temp = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
	try:
		temp.write_bytes(data)
		os.replace(temp, path)
	finally:
		temp.unlink(missing_ok=True)


def customFile(language, volume):
	if language not in PREFIXES or volume not in VOLUMES.values():
		raise ValueError("Custom .dic files are not supported for this language.")
	stem = PREFIXES[language] + next(k for k,v in VOLUMES.items() if v == volume)
	path = directory("custom")
	found = [p for p in path.iterdir() if p.name.lower() == stem + ".dic"] if path.exists() else []
	if len(found) > 1:
		raise ValueError("Multiple files exist for the same dictionary.")
	return found[0] if found else path / (stem + ".dic")


def readCustom(language, volume):
	path = customFile(language, volume)
	if path.exists() and path.stat().st_size > MAX_BYTES:
		raise ValueError("The dictionary file is too large.")
	raw = path.read_bytes() if path.exists() else b""
	return [(k.decode("cp1252"),v.decode("cp1252")) for k,v in parse(raw)], hashlib.sha256(raw).hexdigest()


def saveCustom(language, volume, rows, revision):
	ensureWritable()
	path = customFile(language, volume)
	raw = path.read_bytes() if path.exists() else b""
	if hashlib.sha256(raw).hexdigest() != revision:
		raise ValueError("The file was changed outside the editor. Please close and reopen it.")
	encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "cp1252"
	comments = [line for line in raw.decode(encoding).splitlines() if line.lstrip().startswith(("#", ";"))]
	keys = set()
	for key, value in rows:
		if not key or not value or key.lstrip().startswith(("#", ";")) or any(c in key+value for c in "\t\r\n\x00"):
			raise ValueError("Word and pronunciation are required and must not contain control characters.")
		if key in keys:
			raise ValueError("Duplicate dictionary key: " + key)
		keys.add(key)
	content = "\n".join(comments + [k+"\t"+v for k,v in rows]) + "\n"
	data = content.encode(encoding)
	parse(data)  # Enforce ECI's byte limits and CP1252 representability.
	if len(data) > MAX_BYTES:
		raise ValueError("The dictionary file is too large.")
	atomicWrite(path, data)
	return hashlib.sha256(data).hexdigest()
