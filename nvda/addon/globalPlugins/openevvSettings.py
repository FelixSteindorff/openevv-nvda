"""Optional data management. Speech and secure screens never download files."""
import os
import threading

import globalPluginHandler
import globalVars
import gui
from gui import guiHelper, settingsDialogs
from logHandler import log
import synthDriverHandler
import wx
from wx.lib.scrolledpanel import ScrolledPanel

from synthDrivers import _openevv_dictionaries as dictionaries
from synthDrivers import _openevv_tools as tools
from synthDrivers import _openevv as engine


def currentSynth():
	synth = synthDriverHandler.getSynth()
	if not synth or synth.name != "openevv":
		raise ValueError("Select OpenEVV as the speech synthesizer first.")
	return synth


def showError(parent, error):
	wx.MessageBox(str(error), "OpenEVV", wx.OK | wx.ICON_ERROR, parent)


def preview(text, kind, language):
	synth = currentSynth()
	# Validate before interrupting ongoing reading.
	tools.annotation(text, kind, language)
	import speech
	speech.cancelSpeech()
	synth.previewTool(text, kind, language)


class ToolDialog(wx.Dialog):
	def __init__(self, parent, title):
		super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.content = ScrolledPanel(self)
		self.body = guiHelper.BoxSizerHelper(self.content, orientation=wx.VERTICAL)
		self.sizer.Add(self.content, 1, wx.EXPAND | wx.ALL, 12)

	def finish(self):
		self.content.SetSizer(self.body.sizer)
		self.content.SetupScrolling(scroll_x=False)
		self.sizer.Add(self.CreateButtonSizer(wx.CLOSE), 0, wx.ALIGN_RIGHT | wx.ALL, 12)
		self.SetSizer(self.sizer)
		self.SetMinSize((650, 350))
		self.SetSize((750, min(850, wx.GetDisplaySize().height - 100)))
		self.Bind(wx.EVT_BUTTON, lambda e: self.Close(), id=wx.ID_CLOSE)
		self.Bind(wx.EVT_CLOSE, self.onClose)

	def onClose(self, event):
		if self.IsModal():
			self.EndModal(wx.ID_CLOSE)
		else:
			self.Destroy()

	def button(self, label, action):
		button = self.body.addItem(wx.Button(self.content, label=label))
		button.Bind(wx.EVT_BUTTON, lambda e: self.guarded(action))
		return button

	def guarded(self, action):
		try:
			if globalVars.appArgs.secure:
				raise ValueError("These tools are disabled on secure screens.")
			action()
		except Exception as error:
			showError(self, error)


class DictionaryDialog(ToolDialog):
	def __init__(self, parent):
		super().__init__(parent, "OpenEVV – custom dictionary entries")
		synth = currentSynth()
		self.languages = [lang for lang in synth._engine.languages if lang in dictionaries.PREFIXES]
		self.language = self.body.addLabeledControl("&Language:", wx.Choice,
			choices=[engine.nameOf(lang) for lang in self.languages])
		self.language.SetSelection(self.languages.index(synth._language) if synth._language in self.languages else 0)
		self.volume = self.body.addLabeledControl("Dictionary &type:", wx.Choice,
			choices=["Whole words", "Word stems", "Abbreviations"])
		self.volume.SetSelection(0)
		self.search = self.body.addLabeledControl("Sea&rch:", wx.TextCtrl)
		self.list = self.body.addLabeledControl("&Entries:", wx.ListCtrl,
			style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(620, 180))
		self.list.InsertColumn(0, "Word", width=210)
		self.list.InsertColumn(1, "Pronunciation", width=380)
		self.word = self.body.addLabeledControl("&Word:", wx.TextCtrl)
		self.kind = self.body.addLabeledControl("Entry &format:", wx.Choice,
			choices=["Replacement text", "ECI phonemes (advanced)"])
		self.kind.SetSelection(0)
		self.value = self.body.addLabeledControl("Repla&cement:", wx.TextCtrl)
		self.button("&Apply entry", self.put)
		self.button("&Delete selected entry", self.remove)
		self.button("&Preview pronunciation", self.hear)
		self.analyseButton = self.button("Anal&yze original word phonemes", self.analyse)
		self.button("&Save file and reload", self.save)
		self.status = self.body.addLabeledControl("Status:", wx.TextCtrl, style=wx.TE_READONLY)
		self.body.addItem(wx.StaticText(self.content, label=("Enable custom entries in Speech settings by selecting Custom dictionaries\n"
			"or Alternative/Community + custom corrections. Japanese and Polish\n"
			"are not supported by this .dic editor. Apply entries before saving.")))
		self.rows, self.visible, self.dirty, self.editing = [], [], False, None
		self.lastSelection = (self.language.GetSelection(), 0)
		self.load()
		self.draftDirty = False
		self.word.Bind(wx.EVT_TEXT, self.draftChanged)
		self.value.Bind(wx.EVT_TEXT, self.draftChanged)
		self.kind.Bind(wx.EVT_CHOICE, self.draftChanged)
		self.search.Bind(wx.EVT_TEXT, lambda e: self.refresh())
		self.list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.select)
		self.language.Bind(wx.EVT_CHOICE, self.change)
		self.volume.Bind(wx.EVT_CHOICE, self.change)
		self.finish()

	def lang(self):
		return self.languages[self.language.GetSelection()]

	def draftChanged(self, event):
		self.draftDirty = True

	def load(self):
		self.rows, self.revision = dictionaries.readCustom(self.lang(), self.volume.GetSelection())
		self.editing, self.dirty = None, False
		self.word.ChangeValue("")
		self.value.ChangeValue("")
		self.draftDirty = False
		self.refresh()

	def refresh(self):
		query = self.search.GetValue().casefold()
		self.list.DeleteAllItems()
		self.visible = [i for i,(k,v) in enumerate(self.rows) if query in (k+" "+v).casefold()]
		for index in self.visible:
			key, value = self.rows[index]
			row = self.list.InsertItem(self.list.GetItemCount(), key)
			self.list.SetItem(row, 1, value)
		self.status.SetValue("%d entries%s" % (len(self.rows), " – not yet saved" if self.dirty else ""))

	def select(self, event):
		row = event.GetIndex()
		if row < 0 or row >= len(self.visible):
			return
		self.editing = self.visible[row]
		key, value = self.rows[self.editing]
		self.word.ChangeValue(key)
		phonemes = value.startswith("`[") and value.endswith("]")
		self.kind.SetSelection(1 if phonemes else 0)
		self.value.ChangeValue(value[2:-1] if phonemes else value)
		self.draftDirty = False

	def discard(self):
		return not (self.dirty or self.draftDirty) or wx.MessageBox("Discard unsaved changes?", "OpenEVV",
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self) == wx.YES

	def change(self, event):
		if not self.discard():
			self.language.SetSelection(self.lastSelection[0])
			self.volume.SetSelection(self.lastSelection[1])
			return
		try:
			self.load()
			self.lastSelection = (self.language.GetSelection(), self.volume.GetSelection())
		except Exception as error:
			self.language.SetSelection(self.lastSelection[0])
			self.volume.SetSelection(self.lastSelection[1])
			showError(self, error)

	def put(self):
		key = self.word.GetValue().strip()
		kind = "phonemes" if self.kind.GetSelection() == 1 else "text"
		value = tools.annotation(self.value.GetValue(), kind, self.lang())
		if any(c in key for c in "\t\n\r\x00") or not key:
			raise ValueError("Enter a valid word without control characters.")
		dictionaries.parse((key+"\t"+value).encode("cp1252"))
		rows = list(self.rows)
		if self.editing is not None:
			rows.pop(self.editing)
		rows = [(k,v) for k,v in rows if k != key]
		rows.append((key,value))
		self.rows = sorted(rows, key=lambda item: item[0].casefold())
		self.editing, self.dirty = None, True
		self.draftDirty = False
		self.refresh()

	def remove(self):
		index = self.list.GetFirstSelected()
		if index < 0:
			raise ValueError("Select an entry first.")
		self.rows.pop(self.visible[index])
		self.editing, self.dirty = None, True
		self.refresh()

	def hear(self):
		preview(self.value.GetValue(), "phonemes" if self.kind.GetSelection() == 1 else "text", self.lang())

	def analyse(self):
		word = self.word.GetValue()
		language = self.lang()
		self.analyseButton.Disable()
		def done(value, error):
			if not self:
				return
			self.analyseButton.Enable()
			if error:
				showError(self, error)
			elif word == self.word.GetValue() and language == self.lang():
				self.kind.SetSelection(1)
				self.value.SetValue(value)
		currentSynth().requestPhonemes(word, language, lambda value,error: wx.CallAfter(done, value, error))

	def save(self):
		if self.draftDirty:
			raise ValueError("The input fields have changed. Please choose Apply entry first.")
		self.revision = dictionaries.saveCustom(self.lang(), self.volume.GetSelection(), self.rows, self.revision)
		self.dirty = False
		self.refresh()
		currentSynth().reloadDictionaries()
		self.status.SetValue("File saved; reload of the active profile requested.")

	def onClose(self, event):
		if self.discard():
			super().onClose(event)


class PresetDialog(ToolDialog):
	def __init__(self, parent):
		super().__init__(parent, "OpenEVV – named voice presets")
		self.choices = self.body.addLabeledControl("Sa&ved presets:", wx.Choice)
		self.name = self.body.addLabeledControl("&Name:", wx.TextCtrl)
		self.button("&Save current settings", self.save)
		self.button("&Apply selected preset", self.apply)
		self.button("&Delete selected preset", self.remove)
		self.status = self.body.addLabeledControl("Status:", wx.TextCtrl, style=wx.TE_READONLY)
		self.body.addItem(wx.StaticText(self.content, label=("Includes language, voice, rate, voice parameters, dictionary profile\n"
			"and sample rate. You can save the NVDA configuration after applying a preset.\n"
			"Use NVDA configuration profiles for automatic switching between applications.")))
		self.refresh()
		self.choices.Bind(wx.EVT_CHOICE, lambda e: self.name.SetValue(self.choices.GetStringSelection()))
		self.finish()

	def refresh(self, select=None):
		names = sorted(tools.readPresets(), key=str.casefold)
		self.choices.SetItems(names)
		if names:
			self.choices.SetSelection(names.index(select) if select in names else 0)

	def chosen(self):
		name = self.choices.GetStringSelection()
		if not name:
			raise ValueError("Select a saved preset first.")
		return name

	def save(self):
		name = self.name.GetValue().strip()
		if name in tools.readPresets() and wx.MessageBox("Overwrite the existing preset?", "OpenEVV",
			wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
			return
		tools.savePreset(name, currentSynth())
		self.refresh(name)
		self.status.SetValue("Preset saved: " + name)

	def apply(self):
		name = self.chosen()
		tools.applyPreset(currentSynth(), name)
		self.status.SetValue("Preset applied: " + name)

	def remove(self):
		name = self.chosen()
		if wx.MessageBox("Delete preset: " + name + "?", "OpenEVV", wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
			return
		tools.deletePreset(name)
		self.refresh()
		self.status.SetValue("Preset deleted.")


class WpmDialog(ToolDialog):
	def __init__(self, parent):
		super().__init__(parent, "OpenEVV – words per minute")
		current = tools.rawToWpm(currentSynth()._voiceParams[engine.VOICE_SPEED])
		self.value = self.body.addLabeledControl("Desired &words per minute:", wx.SpinCtrl,
			min=149, max=1297, initial=max(149, min(1297, current)))
		self.button("&Apply rate", self.apply)
		self.status = self.body.addLabeledControl("Status:", wx.TextCtrl, style=wx.TE_READONLY,
			value="Current engine setting: %d WPM" % current)
		self.body.addItem(wx.StaticText(self.content, label=("The closest available NVDA speech rate is selected.\n"
			"Rate boost is enabled if needed. The resulting value is displayed.\n"
			"WPM is the engine setting; the actual word count depends on the text.")))
		self.finish()

	def apply(self):
		synth = currentSynth()
		percent, boost, actual = tools.wpmChoice(synth, self.value.GetValue())
		synth.rateBoost, synth.rate = boost, percent
		self.status.SetValue("Applied: %d WPM; rate %d %%; boost %s" % (
			actual, percent, "on" if boost else "off"))


class PronunciationDialog(ToolDialog):
	def __init__(self, parent):
		super().__init__(parent, "OpenEVV – pronunciation and number preview")
		synth = currentSynth()
		self.languages = list(synth._engine.languages)
		self.language = self.body.addLabeledControl("&Language:", wx.Choice,
			choices=[engine.nameOf(lang) for lang in self.languages])
		self.language.SetSelection(self.languages.index(synth._language))
		self.kinds = list(tools.KINDS)
		self.kind = self.body.addLabeledControl("Reading &format:", wx.Choice, choices=list(tools.KINDS.values()))
		self.kind.SetSelection(0)
		self.text = self.body.addLabeledControl("&Text or value:", wx.TextCtrl)
		self.button("&Preview", self.hear)
		self.body.addItem(wx.StaticText(self.content, label=("Examples: ordinal 12; telephone +49 30 123456; currency amount 12.50;\n"
			"Date 19/09/2026 (day/month/year). Enter ECI phonemes without outer brackets.\n"
			"This format applies only to the preview. Ordinary NVDA speech is unchanged.\n"
			"Special formats support the eight Western language variants.")))
		self.finish()

	def hear(self):
		preview(self.text.GetValue(), self.kinds[self.kind.GetSelection()], self.languages[self.language.GetSelection()])


class OpenEvvPanel(settingsDialogs.SettingsPanel):
	title = "OpenEVV"

	def makeSettings(self, sizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=sizer)
		helper.addItem(wx.StaticText(self, label=(
			"Select the pronunciation dictionary in Speech settings.\n"
			"Original is the default. Downloads are optional; custom files are preserved.")))
		self.providers = list(dictionaries.PROVIDERS)
		self.provider = helper.addLabeledControl("Dictionary so&urce:", wx.Choice,
			choices=[dictionaries.PROFILES[p] for p in self.providers])
		self.provider.SetSelection(0)
		self.downloadButton = helper.addItem(wx.Button(self, label="&Download / update"))
		self.downloadButton.Bind(wx.EVT_BUTTON, self.onDownload)
		self.customButton = helper.addItem(wx.Button(self, label="&Open custom dictionary folder"))
		self.customButton.Bind(wx.EVT_BUTTON, self.onCustom)
		self.reloadButton = helper.addItem(wx.Button(self, label="&Reload active dictionary"))
		self.reloadButton.Bind(wx.EVT_BUTTON, self.onReload)
		self.toolButtons = []
		for label, cls in (("Open dictionary &editor", DictionaryDialog),
			("Manage voice &presets", PresetDialog), ("Set words per &minute", WpmDialog),
			("Pre&view pronunciation and numbers", PronunciationDialog)):
			button = helper.addItem(wx.Button(self, label=label))
			button.Bind(wx.EVT_BUTTON, lambda event, cls=cls: self.openTool(cls))
			self.toolButtons.append(button)
		self.status = helper.addLabeledControl("&Status:", wx.TextCtrl, style=wx.TE_READONLY | wx.TE_MULTILINE)
		self.status.SetValue(self.statusText())
		helper.addItem(wx.StaticText(self, label=(
			"Windows sign-in: select OpenEVV, save settings, then open General settings\n"
			"and enable NVDA during sign-in. Copy the saved settings and select\n"
			"OpenEVV in the copy dialog. Repeat the copy after updates.\n"
			"Requires an installed copy of NVDA and administrator privileges.")))
		self.logonButton = helper.addItem(wx.Button(self, label="Open sign-in setup (&General)"))
		self.logonButton.Bind(wx.EVT_BUTTON, self.onLogon)
		self.busy = False
		if globalVars.appArgs.secure:
			for button in (self.downloadButton, self.customButton, self.reloadButton, self.logonButton, *self.toolButtons):
				button.Disable()

	def openTool(self, cls):
		if globalVars.appArgs.secure:
			return
		try:
			currentSynth()
			dialog = cls(self)
			try:
				dialog.ShowModal()
			finally:
				dialog.Destroy()
		except Exception as error:
			showError(self, error)

	def statusText(self):
		lines = []
		for profile in dictionaries.PROVIDERS:
			path = dictionaries.directory(profile)
			files = sorted(p.name for p in path.glob("*.dic")) if path else []
			lines.append(dictionaries.PROFILES[profile] + ": " + (", ".join(files) or "not downloaded"))
		synth = synthDriverHandler.getSynth()
		if synth and synth.name == "openevv":
			lines.append("Active: " + dictionaries.PROFILES[synth.dictionaryProfile])
			if synth._engine.dictionaryError:
				lines.append("Loading error: " + synth._engine.dictionaryError)
		return "\n".join(lines)

	def onDownload(self, event):
		if globalVars.appArgs.secure or self.busy:
			return
		profile = self.providers[self.provider.GetSelection()]
		self.busy = True
		self.downloadButton.Disable()
		self.status.SetValue("Downloading dictionary …")
		def work():
			success = False
			try:
				files = dictionaries.download(profile)
				success = True
				message = "Downloaded: " + ", ".join(files)
			except Exception as error:
				log.error("openevv: dictionary download failed", exc_info=True)
				message = "Download failed; existing files have been preserved. " + str(error)
			wx.CallAfter(done, message, success)
		def done(message, success):
			if not self:
				return
			self.busy = False
			self.downloadButton.Enable()
			self.status.SetValue(message + "\n" + self.statusText())
			if success:
				self.onReload(None)
		threading.Thread(target=work, name="openevv.dictionaryDownload", daemon=True).start()

	def onCustom(self, event):
		if globalVars.appArgs.secure:
			return
		path = dictionaries.directory("custom")
		path.mkdir(parents=True, exist_ok=True)
		os.startfile(str(path))

	def onReload(self, event):
		if globalVars.appArgs.secure:
			return
		synth = synthDriverHandler.getSynth()
		if not synth or synth.name != "openevv":
			return
		synth.reloadDictionaries()
		def finished():
			if not self:
				return
			if synth._engine._work.unfinished_tasks:
				wx.CallLater(100, finished)
			else:
				self.status.SetValue(self.statusText())
		wx.CallLater(100, finished)

	def onLogon(self, event):
		if globalVars.appArgs.secure:
			return
		# Navigate the existing settings dialog. NVDA owns elevation, selection
		# of add-ons and copying; never replace systemConfig behind its back.
		dialog = self.GetTopLevelParent()
		index = dialog.categoryClasses.index(settingsDialogs.GeneralSettingsPanel)
		dialog.catListCtrl.Select(index)
		dialog.catListCtrl.Focus(index)
		dialog.catListCtrl.SetFocus()

	def onSave(self):
		pass  # The synth's persisted choice lives in its own settings panel.


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self):
		super().__init__()
		self.registered = not globalVars.appArgs.secure
		if self.registered:
			settingsDialogs.NVDASettingsDialog.categoryClasses.append(OpenEvvPanel)

	def terminate(self):
		if self.registered and OpenEvvPanel in settingsDialogs.NVDASettingsDialog.categoryClasses:
			settingsDialogs.NVDASettingsDialog.categoryClasses.remove(OpenEvvPanel)
		super().terminate()
