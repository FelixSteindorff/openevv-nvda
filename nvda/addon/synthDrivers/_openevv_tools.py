"""Explicit pronunciation tools and portable named settings, with no NVDA UI."""
import datetime
import json
import math
import re

from . import _openevv_dictionaries as dictionaries

KINDS = {
	"text": "Normaler Text",
	"phonemes": "Lautfolge (ECI-Phoneme, fortgeschritten)",
	"ordinal": "Ordnungszahl",
	"telephone": "Telefonnummer",
	"currency": "Geldbetrag",
	"date_dmy": "Datum: Tag/Monat/Jahr",
	"date_mdy": "Datum: Monat/Tag/Jahr",
	"date_ymd": "Datum: Jahr/Monat/Tag",
}


def annotation(text, kind, language):
	text = text.strip()
	if not text or len(text) > 500 or any(ord(c) < 32 for c in text):
		raise ValueError("Bitte 1 bis 500 Zeichen ohne Zeilenumbrüche eingeben.")
	if kind == "text":
		return text.replace("`", " ")
	if language not in dictionaries.PREFIXES:
		raise ValueError("Diese Aussprachehilfe ist nur für die acht westlichen Sprachvarianten freigegeben.")
	if kind == "phonemes":
		if not re.fullmatch(r"[A-Za-z0-9 .,:;?!'~^=+*/_#%()<>|@&$-]+", text):
			raise ValueError("ECI-Lautfolge ohne Backticks oder eckige Klammern eingeben.")
		return "`[" + text + "]"
	if kind == "ordinal":
		valid, tag = re.fullmatch(r"[0-9]{1,12}", text), "ord"
	elif kind == "telephone":
		valid, tag = re.fullmatch(r"[+0-9() ./-]{1,40}", text), "tel"
		valid = valid and any(c.isdigit() for c in text)
	elif kind == "currency":
		valid, tag = re.fullmatch(r"(?:[$£€] ?)?-?[0-9]{1,12}(?:[.,][0-9]{1,2})?(?: ?(?:USD|EUR|GBP))?", text), "cur"
	elif kind in ("date_dmy", "date_mdy", "date_ymd"):
		parts = re.split(r"[./-]", text)
		valid = len(parts) == 3 and all(re.fullmatch(r"[0-9]{1,4}", p) for p in parts)
		tag = {"date_dmy": "datedmy", "date_mdy": "datemdy", "date_ymd": "dateymd"}[kind]
		if valid:
			values = [int(p) for p in parts]
			y, m, d = {"date_dmy": (values[2], values[1], values[0]),
				"date_mdy": (values[2], values[0], values[1]), "date_ymd": tuple(values)}[kind]
			try:
				datetime.date(y, m, d)
			except ValueError:
				valid = False
			if valid and language == 0x30001:
				# Canadian French's native DMY tag can leave synthesis silent.
				# Preserve the explicitly selected date through its working YMD
				# route; never infer the order of an unlabelled date.
				tag, text = "dateymd", "%04d/%02d/%02d" % (y,m,d)
	else:
		raise ValueError("Unbekannte Aussprachehilfe.")
	if not valid:
		raise ValueError("Die Eingabe passt nicht zum gewählten Format.")
	return "`" + tag + "[" + text + "]"


def phonemeBody(output):
	# The ECI buffer contains terminal-style backspaces as well as annotations.
	chars = []
	for char in output:
		if char == "\b":
			if chars:
				chars.pop()
		else:
			chars.append(char)
	blocks = re.findall(r"`\[([^\]]+)\]", "".join(chars))
	if not blocks:
		raise ValueError("Die Engine hat keine verwendbare ECI-Lautfolge geliefert.")
	return " ".join(blocks)


def rawToWpm(raw):
	# Exact integer curve from src/eci/api/eci_convert.c; not measured speech speed.
	raw = max(0, min(250, int(raw)))
	return (14 * raw * raw + 1406 * raw + 70250 + 500) // 1000


def wpmChoice(driver, wanted):
	try:
		wanted = float(wanted)
		if not math.isfinite(wanted):
			raise ValueError()
	except (TypeError, ValueError):
		raise ValueError("Eine gültige Geschwindigkeit eingeben.")
	choices = []
	for boost in (False, True):
		for percent in range(101):
			raw = driver._percentToParam(percent, 40, 156)
			if boost:
				raw = int(round(raw * 1.6))
			wpm = rawToWpm(raw)
			choices.append((abs(wpm-wanted), boost != driver.rateBoost, wpm, percent, boost))
	_, _, actual, percent, boost = min(choices)
	return percent, boost, actual


def snapshot(driver):
	return {setting.id: getattr(driver, setting.id) for setting in driver.supportedSettings if setting.useConfig}


def readPresets():
	path = dictionaries.root() / "voice-presets.json"
	if not path.exists():
		return {}
	if path.stat().st_size > 1024 * 1024:
		raise ValueError("Die Preset-Datei ist zu groß.")
	data = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(data, dict) or any(not isinstance(k, str) or not isinstance(v, dict) for k, v in data.items()):
		raise ValueError("Ungültige Preset-Datei; sie wurde nicht verändert.")
	return data


def savePreset(name, driver):
	name = name.strip()
	if not name or len(name) > 80 or any(ord(c) < 32 for c in name):
		raise ValueError("Einen Namen mit 1 bis 80 Zeichen eingeben.")
	data = readPresets()
	data[name] = snapshot(driver)
	_writePresets(data)


def deletePreset(name):
	data = readPresets()
	del data[name]
	_writePresets(data)


def _writePresets(data):
	dictionaries.ensureWritable()
	raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
	if len(raw) > 1024 * 1024:
		raise ValueError("Zu viele Presets; die bisherigen bleiben erhalten.")
	dictionaries.atomicWrite(dictionaries.root() / "voice-presets.json", raw)


def applyPreset(driver, name):
	data = readPresets()[name]
	# Apply through validated setters; never flatten NVDA's layered config
	# sections or implicitly write the currently active configuration profile.
	driver.language = data.get("language", next(iter(driver.availableLanguages)))
	driver.voice = data.get("voice", "1")
	driver.rateBoost = data.get("rateBoost", False)
	for setting in driver.supportedSettings:
		if setting.useConfig and setting.id not in ("language", "voice", "rateBoost"):
			if setting.id in data:
				setattr(driver, setting.id, data[setting.id])
