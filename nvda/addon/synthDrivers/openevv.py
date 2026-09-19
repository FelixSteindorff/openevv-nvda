# The openevv synthesiser driver.
#
# Turns a speech sequence into text with Eloquence annotations in it, and hands
# that to the engine layer beside this file.
#
# Prosody inside a sentence is said as an annotation rather than by setting a
# parameter, and that is the one design decision here worth explaining. A
# parameter is set on the instance and takes effect for everything queued
# behind it, so a pitch change meant for one word arrives too early. An
# annotation travels inside the text and takes effect where it sits. The
# annotations used are in the engine's own test cases and are known to match
# IBM's byte for byte, so this is the path with evidence behind it.

import os
import config
import re
from collections import OrderedDict

from autoSettingsUtils.driverSetting import (
	BooleanDriverSetting,
	DriverSetting,
	NumericDriverSetting,
)
from autoSettingsUtils.utils import StringParameterInfo
from logHandler import log
from speech.commands import (
	BreakCommand,
	CharacterModeCommand,
	IndexCommand,
	LangChangeCommand,
	PitchCommand,
	RateCommand,
	VolumeCommand,
)
from speech.types import SpeechSequence
from synthDriverHandler import (
	SynthDriver,
	VoiceInfo,
	synthDoneSpeaking,
	synthIndexReached,
)

from . import _openevv
from . import _openevv_dictionaries as dictionaries
from . import _openevv_tools as tools

#: What the engine's speed setting is worth at either end of the reader's
#: nought to a hundred. The engine will take nought to two hundred and fifty,
#: but the top of that range is far past intelligible and the bottom is a
#: crawl, so the useful stretch is mapped instead. These two numbers are the
#: ones the IBMTTS driver arrived at by ear on this same engine.
MIN_RATE = 40
MAX_RATE = 156

#: How much further the boost goes, for someone who reads faster than the
#: plain range allows.
RATE_BOOST = 1.6

VOICE_SETTINGS = {
	"pitch": _openevv.VOICE_PITCH,
	"inflection": _openevv.VOICE_FLUCTUATION,
	"volume": _openevv.VOICE_VOLUME,
	"headSize": _openevv.VOICE_HEAD_SIZE,
	"roughness": _openevv.VOICE_ROUGHNESS,
	"breathiness": _openevv.VOICE_BREATHINESS,
}


def _percent(value, default):
	try:
		return max(0, min(100, int(value)))
	except (TypeError, ValueError, OverflowError):
		return default


def _boolean(value):
	if isinstance(value, str):
		return value.lower() in ("true", "yes", "1", "on")
	return value is True or value == 1

#: A break is asked for in milliseconds and the engine's pause annotation is
#: not in milliseconds, so the number has to be scaled -- and by how much
#: depends on the speaking rate, since a pause is counted in something closer
#: to syllables. Measured at these five rates and interpolated between them.
BREAK_FACTORS = {10: 1, 43: 2, 60: 3, 75: 4, 85: 5}

#: How far an unpunctuated stretch may run before it is ended at whitespace.
#:
#: The engine cannot be interrupted -- both of the ways the interface offers
#: fault it, which the engine layer beside this file explains -- so asking for
#: silence means waiting for the utterance in flight to finish synthesising
#: into nothing. That is cheap for a line of a list and is not cheap for a
#: chat message of several thousand characters: measured on this engine, one
#: such message costs 0.83 s, and 560 characters of Arabic, which is spelled
#: out character by character, cost 1.44 s. A reader arrowing down a list
#: every 200 ms has every item that lands inside that wait dropped, which is
#: speech going silent for several objects and then catching up.
#:
#: Sentence ends are the usual boundary because the engine already pauses
#: there: one measured message was 252,010 samples whole and the same 252,010
#: samples in six pieces. This larger fallback is for a stretch with no
#: sentence end, such as the 560-character Arabic case above.
PIECE_CAP = 500

#: Where a piece may end: after a run of whitespace, so nothing is split
#: inside a word and no annotation is separated from what it applies to.
_BOUNDARY = re.compile(r"(\s+)")

#: Closing marks which may follow sentence-final punctuation.
_CLOSERS = "\"')]}\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"

# Declining a possible sentence boundary keeps the engine's own prosody.
# Splitting these common abbreviations introduced audible clause pauses.
_ABBREVIATIONS = frozenset((
	"prof", "bzw", "ca", "usw", "etc", "ggf", "inkl", "zzgl", "vgl",
	"abb", "tel", "str", "abs", "nr", "vs", "approx", "dept",
))


def _endsSentence(text):
	"""Whether a word ends a sentence rather than a dotted number.

	A dot is the doubtful one and the doubt is not symmetrical. A boundary the
	engine would not have made costs an audible pause -- it ends a clause there,
	and that is 0.40 s of gap -- while a boundary declined costs only a longer
	wait on the next cancel. So a dot has to argue for itself.

	An abbreviation and an initial are what it fails on. "Mr. Jones" split after
	the dot measured 0.70 s longer than the same sentence whole, and "J. R. R.
	Tolkien" split at every initial measured 1.48 s longer than 3.72, which is
	nearly half again. Two tests are enough for both, in any of the nine
	languages: a word carrying a dot inside it is an abbreviation rather than a
	sentence -- "e.g.", "i.e.", "U.S." -- and so is a short word that starts with
	a capital, which is every initial and every "Mr.", "Mrs.", "Dr.", "St." and
	"Nr." there is. What that turns down as well is a short capitalised sentence
	end such as "Yes.", and turning one of those down costs nothing but a piece
	that runs to the next sentence.
	"""
	tail = text.rstrip(_CLOSERS)
	if not tail:
		return False
	if tail.endswith(("?", "!", "\N{HORIZONTAL ELLIPSIS}", "\N{IDEOGRAPHIC FULL STOP}", "\N{FULLWIDTH EXCLAMATION MARK}", "\N{FULLWIDTH QUESTION MARK}")):
		return True
	if not tail.endswith(".") or len(tail) < 2 or tail[-2].isdigit():
		return False
	word = tail[:-1]
	if word.casefold() in _ABBREVIATIONS or (len(word) == 1 and word.isalpha()):
		return False
	return "." not in word and not (len(word) <= 3 and word[:1].isupper())


class SynthDriver(SynthDriver):
	name = "openevv"
	description = "Eloquence (openevv)"

	supportedSettings = (
		SynthDriver.LanguageSetting(),
		SynthDriver.VoiceSetting(),
		SynthDriver.RateSetting(),
		SynthDriver.PitchSetting(),
		SynthDriver.InflectionSetting(),
		SynthDriver.VolumeSetting(),
		SynthDriver.RateBoostSetting(),
		# Translators: Label for a setting in voice settings dialog.
		NumericDriverSetting("headSize", _("Hea&d size"), False),
		# Translators: Label for a setting in voice settings dialog.
		NumericDriverSetting("roughness", _("Rou&ghness"), False),
		# Translators: Label for a setting in voice settings dialog.
		NumericDriverSetting("breathiness", _("Breathi&ness"), False),
		# Translators: Label for a setting in voice settings dialog.
		BooleanDriverSetting("abbreviations", _("Expand a&bbreviations"), False),
		# Translators: Label for a setting in voice settings dialog.
		BooleanDriverSetting("voiceTags", _("Allow backquote voice &tags"), False),
		DriverSetting("dictionaryProfile", "Pronunciation &dictionary", False, defaultVal="builtin"),
		# Translators: Label for a setting in voice settings dialog.
		DriverSetting("samplerate", _("Sa&mple rate"), False, defaultVal="11025"),
	)

	supportedCommands = {
		IndexCommand,
		CharacterModeCommand,
		LangChangeCommand,
		BreakCommand,
		PitchCommand,
		RateCommand,
		VolumeCommand,
	}
	supportedNotifications = {synthIndexReached, synthDoneSpeaking}

	@classmethod
	def check(cls):
		return os.path.isfile(_openevv.libraryPath())

	def __init__(self):
		self._rateBoost = False
		self._abbreviations = False
		self._voiceTags = False
		self._dictionaryProfile = "builtin"
		self._engine = _openevv.Engine(self._onIndexReached)
		self._engine.open()
		self._language = self._engine.language
		self._voice = str(_openevv.VOICE_FIRST)
		self._samplerate = str(self._engine.sampleRate)
		# Selected settings belong to the UI/config, not to the worker's
		# last completed operation. Saving must also work with queued speech.
		self._voiceParams = dict(self._engine.voiceParams)
		self._rate = _percent(self._paramToPercent(
			self._voiceParams[_openevv.VOICE_SPEED], MIN_RATE, MAX_RATE), 50)
		log.debug("openevv: engine version %s" % self._engine.version)

	def terminate(self):
		self._engine.close()

	# ---- speaking ----------------------------------------------------

	def speak(self, speechSequence: SpeechSequence):
		engine = self._engine
		#: The pieces to hand over, in order. Nearly every utterance a screen
		#: reader says is one piece; a long one is several, so that asking for
		#: silence waits out a piece and not the whole of it.
		pieces = []
		batch = [(engine.selectLanguage, (self._language, self._presetNow()))]
		text = []
		spelling = False
		#: Prosody annotations which have not yet been restored to the reader's
		#: configured value. An opening and its restore have to stay in one queue
		#: item, or a cancel between them leaks the change into later speech.
		prosody = set()
		#: Which language the text being built is in, since a sequence may
		#: change it more than once and each change is against the last.
		speaking = self._language
		usedLanguageSwitch = False
		#: Whether anything in this sequence is meant to make a sound. A
		#: sequence of nothing but commands is silent because it should be, and
		#: the engine layer is told so rather than complaining about it.
		words = False

		#: What this piece has to say, and how much has gathered in it. A piece
		#: is what a cancel waits for, so it is closed at the first boundary
		#: past the limit rather than at the limit exactly.
		saying = False
		gathered = 0
		sentence = False

		def flush():
			if text:
				joined = _openevv.encodeText("".join(text), speaking)
				batch.append((engine.addText, (joined,)))
				del text[:]

		def endPiece():
			"""Close the piece being gathered, if it has anything in it."""
			nonlocal batch, saying, gathered
			flush()
			if batch:
				pieces.append((batch, saying))
				batch = []
			saying = False
			gathered = 0

		def mayEndPiece():
			# Voice tags are arbitrary annotations supplied inside the text; when
			# enabled their state cannot be inferred here, so retain the old single
			# queue item just as for a command whose state is visibly open.
			return not spelling and not prosody and not self._voiceTags

		for item in speechSequence:
			if isinstance(item, str):
				said = self._processText(item, speaking)
				words = words or said.strip() != ""
				# Sentence ends are free boundaries because the engine already pauses
				# there. Whitespace after the much larger cap bounds a sentence which
				# has no end of its own.
				for part in _BOUNDARY.split(said):
					if not part:
						continue
					text.append(part)
					gathered += len(part)
					if part.strip():
						saying = True
						sentence = _endsSentence(part)
					else:
						if mayEndPiece() and (sentence or gathered >= PIECE_CAP):
							endPiece()
						sentence = False
			elif isinstance(item, IndexCommand):
				# An index has to sit between stretches of text rather than
				# inside one, so what has been gathered goes first.
				flush()
				batch.append((engine.index, (item.index,)))
			elif isinstance(item, CharacterModeCommand):
				# What the last such command asked for, so that spelling left
				# open at the end of the sequence is closed once and spelling
				# already closed is not closed again.
				spelling = item.state
				# On its own, not on the end of a stretch of text. An
				# annotation with nothing after it in the same call does not
				# take effect, which is how spelling used to leak out of one
				# utterance and into every one after it.
				flush()
				batch.append((engine.addText, (b"`ts1 " if item.state else b"`ts0 ",)))
			elif isinstance(item, BreakCommand):
				text.append(" `p%d " % self._breakToPause(item.time))
			elif isinstance(item, PitchCommand):
				if item.isDefault:
					prosody.discard(PitchCommand)
				else:
					prosody.add(PitchCommand)
				text.append("`vb%d " % self._pitchToParam(item.newValue))
			elif isinstance(item, RateCommand):
				if item.isDefault:
					prosody.discard(RateCommand)
				else:
					prosody.add(RateCommand)
				text.append("`vs%d " % self._rateToParam(item.newValue))
			elif isinstance(item, VolumeCommand):
				if item.isDefault:
					prosody.discard(VolumeCommand)
				else:
					prosody.add(VolumeCommand)
				text.append("`vv%d " % self._volumeToParam(item.newValue))
			elif isinstance(item, LangChangeCommand):
				# A document saying part of itself is in another language.
				# Where the library has that language it is switched to, in
				# the order the sequence asks for it, so a German quotation
				# in an English page is read as German rather than as
				# English with German spelling.
				#
				# The switch has to be flushed first: it is a call and not an
				# annotation, so text already handed over would otherwise be
				# spoken in the language that came after it. The preset is
				# copied again because a language change replaces all eight
				# of its settings.
				language = self._languageFor(item.lang) if item.lang else self._language
				if language is not None and language != speaking:
					usedLanguageSwitch = True
					if text or saying or len(batch) > 1:
						endPiece()
					batch.append((engine.selectLanguage, (language, self._presetNow())))
					speaking = language
			else:
				log.error("openevv: unknown speech: %s" % item)

		flush()
		if spelling:
			batch.append((engine.addText, (b"`ts0 ",)))
		if batch or not pieces:
			pieces.append((batch, saying or not pieces and words))

		# One queue item per piece, so that a cancel drops the pieces that
		# have not started rather than having to wait for them. Only the last
		# reports the utterance finished.
		for position, (piece, expectAudio) in enumerate(pieces):
			last = position == len(pieces) - 1
			piece.append((engine.synthesize if last else engine.synthesizePart, (expectAudio,)))
			engine.post(piece)
		if usedLanguageSwitch:
			# A control survives cancellation of the speech tail. This restores
			# the default even without a trailing LangChangeCommand(None).
			engine.control([(engine.selectLanguage, (self._language, self._presetNow()))])

	def _processText(self, text, language=None):
		# Normalize before choosing sentence boundaries so typographic variants
		# get the same pauses as their ordinary spelling. Filter tags afterwards.
		text = _openevv.normalizeText(text, self._language if language is None else language)
		# Native Japanese crashes on some raw backquote forms (including `0
		# and an escaped literal backquote). Keep raw text tags disabled for
		# Japanese, including temporary switches; NVDA commands are separate.
		if not self._voiceTags or (self._language if language is None else language) == 0x80000:
			# A backtick starts an annotation, so ordinary text carrying one
			# would be read as a command rather than spoken. Unless the reader
			# has asked for tags to go through, it becomes a space.
			text = text.replace("`", " ")
		return text

	def cancel(self):
		self._engine.cancel()

	def pause(self, switch):
		self._engine.pause(switch)

	def previewTool(self, text, kind="text", language=None):
		"""A user-requested preview; never enables raw voice tags in normal text."""
		language = self._language if language is None else language
		if language not in self._engine.languages:
			raise ValueError("This language is not available in the DLL.")
		marked = tools.annotation(text, kind, language)
		payload = _openevv.encodeText(marked, language)
		engine = self._engine
		self.cancel()
		engine.post([(engine.selectLanguage, (language, self._presetNow())),
			(engine.addText, (payload,)), (engine.synthesize, (True,))])
		# The existing control queue survives cancellation of the preview.
		engine.control([(engine.selectLanguage, (self._language, self._presetNow()))])

	def requestPhonemes(self, text, language, callback):
		def analyse():
			try:
				result, error = tools.phonemeBody(self._engine.phonemes(text, language)), None
			except Exception as exc:
				result, error = None, str(exc)
			callback(result, error)
		self._engine.control([(analyse, ())])

	def _onIndexReached(self, index):
		if index is None:
			synthDoneSpeaking.notify(synth=self)
		else:
			synthIndexReached.notify(synth=self, index=index)

	# ---- turning the reader's numbers into the engine's --------------

	def _rateToParam(self, percent):
		value = self._percentToParam(percent, MIN_RATE, MAX_RATE)
		if self._rateBoost:
			value = int(round(value * RATE_BOOST))
		return min(value, _openevv.VOICE_RANGE[_openevv.VOICE_SPEED][1])

	def _pitchToParam(self, percent):
		return int(percent)

	def _volumeToParam(self, percent):
		return int(percent)

	def _breakToPause(self, milliseconds):
		rates = sorted(BREAK_FACTORS)
		rate = self.rate
		if rate <= rates[0]:
			factor = BREAK_FACTORS[rates[0]]
		elif rate >= rates[-1]:
			factor = BREAK_FACTORS[rates[-1]]
		elif rate in BREAK_FACTORS:
			factor = BREAK_FACTORS[rate]
		else:
			below = [i for i, r in enumerate(rates) if r < rate][-1]
			lo, hi = rates[below], rates[below + 1]
			factor = BREAK_FACTORS[lo] + (BREAK_FACTORS[hi] - BREAK_FACTORS[lo]) * (
				rate - lo
			) / (hi - lo)
		return max(0, int(factor * milliseconds))

	# ---- the settings ------------------------------------------------

	def _get_rate(self):
		return self._rate

	def _set_rate(self, percent):
		self._rate = _percent(percent, self._rate)
		self._post(_openevv.VOICE_SPEED, self._rateToParam(self._rate))

	def _get_rateBoost(self):
		return self._rateBoost

	def _set_rateBoost(self, enable):
		enable = _boolean(enable)
		if enable != self._rateBoost:
			rate = self.rate
			self._rateBoost = enable
			self.rate = rate

	def _get_pitch(self):
		return self._voiceParams[_openevv.VOICE_PITCH]

	def _set_pitch(self, value):
		self._post(_openevv.VOICE_PITCH, value)

	def _get_volume(self):
		return self._voiceParams[_openevv.VOICE_VOLUME]

	def _set_volume(self, value):
		self._post(_openevv.VOICE_VOLUME, value)

	def _get_inflection(self):
		return self._voiceParams[_openevv.VOICE_FLUCTUATION]

	def _set_inflection(self, value):
		self._post(_openevv.VOICE_FLUCTUATION, value)

	def _get_headSize(self):
		return self._voiceParams[_openevv.VOICE_HEAD_SIZE]

	def _set_headSize(self, value):
		self._post(_openevv.VOICE_HEAD_SIZE, value)

	def _get_roughness(self):
		return self._voiceParams[_openevv.VOICE_ROUGHNESS]

	def _set_roughness(self, value):
		self._post(_openevv.VOICE_ROUGHNESS, value)

	def _get_breathiness(self):
		return self._voiceParams[_openevv.VOICE_BREATHINESS]

	def _set_breathiness(self, value):
		self._post(_openevv.VOICE_BREATHINESS, value)

	def _get_abbreviations(self):
		return self._abbreviations

	def _set_abbreviations(self, enable):
		enable = _boolean(enable)
		self._abbreviations = enable
		# Nought turns the abbreviation dictionary on, which is the engine's
		# own sense of the setting and not a mistake here.
		self._engine.control(
			[(self._engine.setParam, (_openevv.PARAM_DICTIONARY, 0 if enable else 1))],
		)

	def _get_voiceTags(self):
		return self._voiceTags

	def _set_voiceTags(self, enable):
		self._voiceTags = _boolean(enable)

	def _get_availableSamplerates(self):
		# Classic is the recommended default; native 22 kHz is experimental.
		labels = {8000: "8 kHz", 11025: "11 kHz (Classic)",
			22050: "22 kHz (Experimental)"}
		return OrderedDict(
			(str(hz), StringParameterInfo(str(hz),
				labels.get(hz, "%.3g kHz (Resampled)" % (hz / 1000.0))))
			for _number, hz in sorted(_openevv.SAMPLE_RATES, key=lambda item: item[1])
		)

	def _get_availableDictionaryprofiles(self):
		return OrderedDict((key, StringParameterInfo(key, label)) for key, label in dictionaries.PROFILES.items())

	def _get_dictionaryProfile(self):
		return self._dictionaryProfile

	def _set_dictionaryProfile(self, profile):
		profile = profile if isinstance(profile, str) and profile in dictionaries.PROFILES else "builtin"
		if profile == self._dictionaryProfile:
			return
		self._dictionaryProfile = profile
		self._engine.control([(self._applyDictionaryProfile, (profile,))])

	def _applyDictionaryProfile(self, profile):
		if not self._engine.setDictionaryProfile(profile) and self._dictionaryProfile == profile:
			self._dictionaryProfile = self._engine.dictionaryProfile

	def reloadDictionaries(self):
		self._engine.control([(self._applyDictionaryProfile, (self._dictionaryProfile,))])

	def _get_samplerate(self):
		return self._samplerate

	def _applySampleRate(self, hz):
		if not self._engine.setSampleRate(hz) and self._samplerate == str(hz):
			self._samplerate = str(self._engine.sampleRate)

	def _set_samplerate(self, value):
		value = str(value)
		if value not in self.availableSamplerates:
			value = str(_openevv.SAMPLE_RATE)
		self._samplerate = value
		self._engine.control([(self._applySampleRate, (int(value),))])

	def _get_availableLanguages(self):
		return OrderedDict(
			(_openevv.localeOf(lang) or "x-eci-%x" % lang,
			 StringParameterInfo(_openevv.localeOf(lang) or "x-eci-%x" % lang,
				_openevv.nameOf(lang)))
			for lang in self._engine.languages
		)

	def _get_availableVoices(self):
		# The eight identities and display names are stable across languages.
		# NVDA's generic language control does not rebuild the voice combo.
		# Enumerate only this language, never a language/preset Cartesian product.
		return OrderedDict(
			(str(number), VoiceInfo(str(number), _openevv.VOICE_NAMES.get(number, name)))
			for number, name in self._engine.voiceNamesFor(self._language).items()
		)

	def _languageFor(self, locale):
		"""Which of the library's languages a document's locale means.

		A document says `de' or `de_DE' or `de-AT'; the library has one
		German. So the whole locale is tried first, and then just the
		language part of it, and anything the library does not have answers
		nothing, which leaves the voice where it was.
		"""
		if not locale:
			return None
		want = str(locale).replace("-", "_")
		short = want.split("_")[0].lower()
		loose = None
		for language in self._engine.languages:
			have = _openevv.localeOf(language)
			if have is None:
				continue
			if have.lower() == want.lower():
				return language
			if loose is None and have.split("_")[0].lower() == short:
				loose = language
		return loose

	def _presetNow(self):
		return int(self._voice)

	def _get_voice(self):
		return self._voice

	def _set_voice(self, value):
		# Migrate the first test build's language:preset IDs as well as old
		# single-language configurations. Persist only the new independent ID.
		value = str(value)
		if ":" in value:
			lang, value = value.split(":", 1)
			try:
				lang = int(lang)
				if lang in self._engine.languages:
					self.language = _openevv.localeOf(lang) or "x-eci-%x" % lang
			except ValueError:
				pass
		if value not in self.availableVoices:
			value = next(iter(self.availableVoices))
		self._voice = value
		self._voiceParams = self._engine.voiceParamsFor(self._language, int(value))
		speed = self._voiceParams[_openevv.VOICE_SPEED]
		if self._rateBoost:
			speed = int(round(speed / RATE_BOOST))
		self._rate = _percent(self._paramToPercent(speed, MIN_RATE, MAX_RATE), 50)
		self._engine.control([
			(self._engine.selectLanguage, (self._language, int(value))),
			(self._engine.copyVoice, (int(value),)),
		])
		if self._rateToParam(self._rate) != self._voiceParams[_openevv.VOICE_SPEED]:
			self.rate = self._rate

	def _get_language(self):
		return _openevv.localeOf(self._language) or "x-eci-%x" % self._language

	def _set_language(self, value):
		languages = list(self.availableLanguages)
		if value not in languages:
			value = languages[0]
		self._language = self._engine.languages[languages.index(value)]
		if self._voice not in self.availableVoices:
			self._voice = next(iter(self.availableVoices))
		self._engine.control([
			(self._engine.selectLanguage, (self._language, self._presetNow())),
		])

	def loadSettings(self, onlyChanged=False):
		# NVDA loads voice before the other settings. Normalise legacy IDs and
		# unavailable choices before that happens; language must precede voice.
		c = config.conf[self._configSection][self.name]
		voice = str(c.get("voice") or self.voice)
		language = c.get("language")
		if ":" in voice:
			oldLanguage, voice = voice.split(":", 1)
			if not language:
				try:
					language = _openevv.localeOf(int(oldLanguage))
				except ValueError:
					pass
		language = language if isinstance(language, str) and language in self.availableLanguages else next(iter(self.availableLanguages))
		if not onlyChanged or self.language != language:
			self.language = language
		c["language"] = self.language
		c["voice"] = voice if voice in self.availableVoices else next(iter(self.availableVoices))
		rate = str(c.get("samplerate") or _openevv.SAMPLE_RATE)
		c["samplerate"] = rate if rate in self.availableSamplerates else str(_openevv.SAMPLE_RATE)
		profile = c.get("dictionaryProfile", "builtin")
		c["dictionaryProfile"] = profile if isinstance(profile, str) and profile in dictionaries.PROFILES else "builtin"
		for setting in ("rateBoost", "abbreviations", "voiceTags"):
			c[setting] = _boolean(c.get(setting, False))
		# NVDA loads rate before rateBoost in the displayed order. Establish
		# boost first so the saved percentage maps to the right ECI speed.
		self.rateBoost = c["rateBoost"]
		preset = self._engine.voiceParamsFor(self._language, int(c["voice"]))
		defaults = {name: preset[which] for name, which in VOICE_SETTINGS.items()}
		speed = preset[_openevv.VOICE_SPEED]
		if self._rateBoost:
			speed = int(round(speed / RATE_BOOST))
		defaults["rate"] = _percent(self._paramToPercent(speed, MIN_RATE, MAX_RATE), 50)
		for name, default in defaults.items():
			c[name] = _percent(c.get(name), default)
		super().loadSettings(onlyChanged)

	def _post(self, which, value):
		if which != _openevv.VOICE_SPEED:
			value = _percent(value, self._voiceParams[which])
		if self._voiceParams.get(which) == value:
			return
		self._voiceParams[which] = value
		# As a control step, not as speech: a setting asked for while speech is
		# being cancelled -- which every keystroke does -- would otherwise be
		# thrown away with the utterances, and the reader's choice would not
		# take.
		self._engine.control([(self._engine.setVoiceParam, (which, value))])
