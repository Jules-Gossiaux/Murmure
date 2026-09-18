from __future__ import annotations

import logging
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .audio import microphones
from .controller import State
from .models import MODEL_BY_NAME, MODELS
from .shortcut import ShortcutEdit
from .style import apply_theme
from .windows import set_startup

log = logging.getLogger(__name__)


def label(text, name="", wrap=False):
    widget = QLabel(text)
    widget.setObjectName(name)
    widget.setWordWrap(wrap)
    return widget


def button(text, callback, name=""):
    widget = QPushButton(text)
    widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(callback)
    return widget


def card(name="card"):
    widget = QFrame()
    widget.setObjectName(name)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(24, 22, 24, 22)
    layout.setSpacing(13)
    return widget, layout


class NoWheelComboBox(QComboBox):
    """Consume wheel events so Qt can never use them to change the selection."""

    def event(self, event):
        if event.type() == QEvent.Type.Wheel:
            event.accept()
            return True
        return super().event(event)

    def wheelEvent(self, event):
        event.accept()


class MainWindow(QMainWindow):
    def __init__(self, controller, directory: Path):
        super().__init__()
        self.controller, self.directory = controller, directory
        self.hotkey = None
        self.quit_callback = None
        self.allow_close = False
        self.selected = None
        self.history_limit = 100
        self.countdown = 0
        self.latest_id = None
        self.pending_edits = {}
        self.controller.correction_progress.connect(self.show_correction_progress)
        self.controller.correction_finished.connect(self.finish_correction_download)
        self.edit_timer = QTimer(self)
        self.edit_timer.setSingleShot(True)
        self.edit_timer.setInterval(350)
        self.edit_timer.timeout.connect(self.flush_edits)
        self.setWindowTitle("Murmure · Dictée locale")
        self.resize(1080, 760)
        self.setMinimumSize(880, 640)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(205)
        navigation = QVBoxLayout(sidebar)
        navigation.setContentsMargins(20, 31, 20, 23)
        navigation.setSpacing(10)
        navigation.addWidget(label("murmure", "brand"))
        navigation.addWidget(label("LA VOIX, SIMPLEMENT.", "eyebrow"))
        navigation.addSpacing(38)
        self.pages = QStackedWidget()
        self.nav_group = QButtonGroup(self)
        self.nav_buttons = []
        for index, title in enumerate(("Dictée", "Historique", "Vocabulaire", "Paramètres")):
            nav = button(title, lambda checked=False, i=index: self.navigate(i), "nav")
            nav.setCheckable(True)
            self.nav_group.addButton(nav)
            self.nav_buttons.append(nav)
            navigation.addWidget(nav)
        navigation.addStretch()
        navigation.addWidget(label("●  100 % local", "status"))
        navigation.addWidget(label("Votre voix reste\nsur cet ordinateur.", "subtitle"))
        navigation.addSpacing(12)
        navigation.addWidget(label(f"Murmure  /  {__version__}", "subtitle"))
        layout.addWidget(sidebar)
        layout.addWidget(self.pages, 1)
        self._home_page()
        self._history_page()
        self._vocabulary_page()
        self._settings_page()
        self.navigate(0)
        controller.changed.connect(self.update_state)
        controller.history_changed.connect(self.refresh_history)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.refresh_history()

    def _page(self, eyebrow, title, subtitle, scrollable=False):
        page = QWidget()
        page.setObjectName("page")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(36, 30, 36, 28)
        layout.setSpacing(17)
        layout.addWidget(label(eyebrow, "eyebrow"))
        layout.addWidget(label(title, "title"))
        layout.addWidget(label(subtitle, "subtitle", True))
        if scrollable:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.pages.addWidget(scroll)
        else:
            self.pages.addWidget(page)
        return layout

    def _home_page(self):
        layout = self._page(
            "VOTRE ESPACE DE DICTÉE",
            "Les idées viennent en parlant.",
            "Un raccourci. Votre voix. Du texte, là où vous écrivez.",
            scrollable=True,
        )
        hero, content = card("hero")
        content.addWidget(label("Parlez. C’est écrit.", "heroTitle"))
        self.shortcut_hint = label("", "subtitle", True)
        content.addWidget(self.shortcut_hint)
        content.addSpacing(14)
        self.status_label = label("Préparation du moteur…", "status", True)
        content.addWidget(self.status_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        content.addWidget(self.progress)
        row = QHBoxLayout()
        self.record_button = button("Préparation…", self.start_from_ui, "primary")
        self.record_button.setMinimumHeight(44)
        row.addWidget(self.record_button)
        self.cancel_button = button("Annuler · Échap", self.controller.cancel, "danger")
        self.cancel_button.hide()
        row.addWidget(self.cancel_button)
        self.elapsed = label("", "subtitle")
        row.addWidget(self.elapsed)
        row.addStretch()
        content.addLayout(row)
        layout.addWidget(hero)
        self.banner = label("", "banner", True)
        self.banner.hide()
        layout.addWidget(self.banner)
        top = QHBoxLayout()
        top.addWidget(label("Dernière dictée", "section"))
        top.addStretch()
        top.addWidget(button("Tout l’historique  →", lambda: self.navigate(1)))
        layout.addLayout(top)
        recent, recent_layout = card()
        recent.setMinimumHeight(230)
        self.latest_meta = label("Votre première dictée commence ici", "subtitle")
        recent_layout.addWidget(self.latest_meta)
        self.latest_text = QPlainTextEdit()
        self.latest_text.textChanged.connect(lambda: self.transcript_changed("latest"))
        self.latest_text.setPlaceholderText(
            "Ouvrez un champ de texte dans une application, puis utilisez votre raccourci pour dicter."
        )
        self.latest_text.setMinimumHeight(95)
        recent_layout.addWidget(self.latest_text, 1)
        self.copy_latest = button("Copier le texte", lambda: self.copy(self.latest_text.toPlainText()))
        recent_layout.addWidget(self.copy_latest, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(recent, 1)
        layout.addWidget(
            label(
                "Après la première préparation du modèle, aucune connexion n’est nécessaire.",
                "subtitle",
                True,
            )
        )

    def _history_page(self):
        layout = self._page(
            "RETROUVER LE FIL", "Votre historique", "Chaque dictée est enregistrée avant son insertion."
        )
        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher dans vos dictées…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.search_history)
        search_row.addWidget(self.search, 1)
        self.clear_button = button("Tout effacer", self.clear_history, "danger")
        search_row.addWidget(self.clear_button)
        layout.addLayout(search_row)
        splitter = QSplitter()
        self.history_list = QListWidget()
        self.history_list.setWordWrap(True)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_list.currentItemChanged.connect(self.select_entry)
        splitter.addWidget(self.history_list)
        detail, detail_layout = card()
        self.detail_meta = label("Sélectionnez une dictée", "subtitle", True)
        detail_layout.addWidget(self.detail_meta)
        self.detail_text = QPlainTextEdit()
        self.detail_text.textChanged.connect(lambda: self.transcript_changed("detail"))
        self.detail_text.setPlaceholderText(
            "Les transcriptions et les enregistrements à récupérer apparaissent ici."
        )
        detail_layout.addWidget(self.detail_text, 1)
        self.detail_status = label("", "subtitle", True)
        detail_layout.addWidget(self.detail_status)
        self.detail_copy = button("Copier", lambda: self.copy(self.detail_text.toPlainText()), "primary")
        self.recover_button = button("Récupérer l’audio", self.recover_selected)
        self.delete_button = button("Supprimer", self.delete_selected, "danger")
        detail_layout.addWidget(self.detail_copy)
        detail_layout.addWidget(self.recover_button)
        detail_layout.addWidget(self.delete_button)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 5)
        layout.addWidget(splitter, 1)
        self.history_count = label("", "subtitle")
        footer = QHBoxLayout()
        footer.addWidget(self.history_count)
        footer.addStretch()
        self.more_history = button("Afficher davantage", self.load_more_history)
        footer.addWidget(self.more_history)
        layout.addLayout(footer)

    def _vocabulary_page(self):
        layout = self._page(
            "LES MOTS QUI VOUS RESSEMBLENT",
            "Votre vocabulaire",
            "Acronymes, noms propres, termes techniques : donnez des repères au moteur.",
        )
        frame, content = card()
        content.addWidget(label("Mots et expressions à privilégier", "section"))
        content.addWidget(
            label(
                "Un terme par ligne, par exemple FSRS, Anki ou le nom d’un projet.\n"
                "Ces indications aident la reconnaissance ; elles ne garantissent pas une orthographe exacte.",
                "subtitle",
                True,
            )
        )
        self.vocabulary = QPlainTextEdit(self.controller.settings.vocabulary)
        self.vocabulary.setPlaceholderText("FSRS\nAnki\nFaster-Whisper")
        content.addWidget(self.vocabulary, 1)
        self.vocab_count = label("", "subtitle")
        self.vocabulary.textChanged.connect(
            lambda: self.vocab_count.setText(
                f"{len(self.vocabulary.toPlainText())} / 2 000 caractères · privilégiez une liste courte"
            )
        )
        self.vocabulary.textChanged.emit()
        content.addWidget(self.vocab_count)
        self.vocab_save = button("Enregistrer le vocabulaire", self.save_vocabulary, "primary")
        content.addWidget(self.vocab_save, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(frame, 1)

    def _settings_page(self):
        layout = self._page("À VOTRE FAÇON", "Paramètres", "L’essentiel pour une dictée qui s’adapte à vous.")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("page")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(16)
        settings = self.controller.settings
        input_card, content = card()
        content.addWidget(label("Dictée", "section"))
        form = QFormLayout()
        form.setSpacing(14)
        self.key_edit = ShortcutEdit(settings.hotkey_mods, settings.hotkey_vk, settings.hotkey_label)
        self.key_edit.capture_started.connect(self.suspend_shortcut)
        self.key_edit.capture_finished.connect(self.resume_shortcut)
        self.key_edit.setToolTip(
            "Cliquez, puis appuyez sur la combinaison. Appliquez pour l’activer partout."
        )
        form.addRow("Raccourci global", self.key_edit)
        self.microphone = NoWheelComboBox()
        self.microphone.setMinimumContentsLength(22)
        self.microphone.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        microphone_row = QHBoxLayout()
        microphone_row.addWidget(self.microphone, 1)
        microphone_row.addWidget(button("↻", self.refresh_microphones))
        form.addRow("Microphone", microphone_row)
        self.refresh_microphones()
        self.model = NoWheelComboBox()
        for choice in MODELS:
            self.model.addItem(choice.label, choice.name)
        self.model.setCurrentIndex(self.model.findData(settings.model))
        form.addRow("Modèle", self.model)
        self.model_description = label("", "subtitle", True)
        self.model.currentIndexChanged.connect(self.update_model_description)
        self.update_model_description()
        form.addRow("", self.model_description)
        self.correction = QCheckBox("Corriger automatiquement le texte")
        self.correction.setChecked(settings.correction)
        form.addRow("Correction locale", self.correction)
        form.addRow(
            "",
            label(
                "Un petit modèle local corrige l’orthographe, la grammaire et les mots mal transcrits. "
                "Il est téléchargé au premier usage (environ 491 Mo) et fonctionne sans Internet ensuite.",
                "subtitle",
                True,
            ),
        )
        self.correction_download = button(
            "Télécharger le correcteur maintenant", self.download_correction, "primary"
        )
        self.correction_status = label(
            "Préparez-le avant votre première dictée pour éviter un téléchargement pendant l’utilisation.",
            "subtitle",
            True,
        )
        if self.controller.corrector.downloaded:
            self.correction_status.setText("Correcteur local déjà téléchargé et disponible hors ligne.")
            self.correction_download.setText("Correcteur déjà téléchargé")
            self.correction_download.setEnabled(False)
        form.addRow("Préparation", self.correction_download)
        form.addRow("", self.correction_status)
        self.language = NoWheelComboBox()
        for text, value in (
            ("Français", "fr"),
            ("Détection automatique", "auto"),
            ("English", "en"),
            ("Deutsch", "de"),
            ("Español", "es"),
            ("Italiano", "it"),
            ("Nederlands", "nl"),
            ("Português", "pt"),
        ):
            self.language.addItem(text, value)
        self.language.setCurrentIndex(self.language.findData(settings.language))
        form.addRow("Langue", self.language)
        content.addLayout(form)
        content.addWidget(
            label(
                "Le modèle choisi reste chargé entre les dictées. La durée du texte et votre matériel influencent l’attente : 1–2 s ne sont pas garanties pour une longue dictée.\n"
                "Accélération NVIDIA CUDA si disponible, sinon CPU int8. Le temps de transcription est affiché après chaque dictée.",
                "subtitle",
                True,
            )
        )
        body_layout.addWidget(input_card)
        behavior, content = card()
        content.addWidget(label("Au quotidien", "section"))
        self.theme = NoWheelComboBox()
        self.theme.addItem("Clair", "light")
        self.theme.addItem("Sombre", "dark")
        self.theme.setCurrentIndex(self.theme.findData(settings.theme))
        theme_form = QFormLayout()
        theme_form.addRow("Apparence", self.theme)
        content.addLayout(theme_form)
        self.theme.currentIndexChanged.connect(
            lambda: apply_theme(QApplication.instance(), self.theme.currentData())
        )
        self.sounds = QCheckBox("Sons discrets au début et à la fin")
        self.sounds.setChecked(settings.sounds)
        self.close_tray = QCheckBox("Fermer la fenêtre laisse Murmure dans la zone de notification")
        self.close_tray.setChecked(settings.close_to_tray)
        self.startup = QCheckBox("Lancer discrètement à l’ouverture de Windows")
        self.startup.setChecked(settings.startup)
        for widget in (self.sounds, self.close_tray, self.startup):
            content.addWidget(widget)
        body_layout.addWidget(behavior)
        local, content = card()
        content.addWidget(label("Emplacement de l’historique", "section"))
        self.history_path = QLineEdit(str(self.controller.history.directory))
        self.history_path.setReadOnly(True)
        path_row = QHBoxLayout()
        path_row.addWidget(self.history_path, 1)
        path_row.addWidget(button("Choisir un dossier…", self.choose_history_folder))
        content.addLayout(path_row)
        content.addWidget(
            label(
                "Ce dossier contient les textes, dates et durées des dictées. Changer de dossier déplace l’historique existant lorsque vous appliquez les paramètres.",
                "subtitle",
                True,
            )
        )
        content.addWidget(
            button(
                "Ouvrir l’historique actuel",
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.controller.history.directory))),
            ),
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        content.addWidget(label("Audio temporaire, modèles et réglages", "section"))
        content.addWidget(label(str(self.directory), "subtitle", True))
        content.addWidget(
            label(
                "Les audios de récupération restent dans le sous-dossier pending. Ils sont supprimés après transcription ou annulation. Les réglages restent également ici.",
                "subtitle",
                True,
            )
        )
        content.addWidget(label("Dossier des nouveaux modèles", "section"))
        self.models_path = QLineEdit(str(self.controller.engine.cache))
        self.models_path.setReadOnly(True)
        models_row = QHBoxLayout()
        models_row.addWidget(self.models_path, 1)
        models_row.addWidget(button("Choisir un dossier…", self.choose_models_folder))
        content.addLayout(models_row)
        content.addWidget(
            label(
                "Les modèles déjà présents dans le dossier par défaut restent utilisables. Ce choix change l’emplacement des prochains téléchargements, sans déplacer l’historique.",
                "subtitle",
                True,
            )
        )
        content.addWidget(
            button(
                "Ouvrir le dossier de l’application",
                lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.directory))),
            ),
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        body_layout.addWidget(local)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self.apply_button = button("Appliquer les paramètres", self.save_settings, "primary")
        layout.addWidget(self.apply_button, alignment=Qt.AlignmentFlag.AlignRight)

    def update_model_description(self):
        choice = MODEL_BY_NAME.get(self.model.currentData())
        self.model_description.setText(choice.description if choice else "")

    def download_correction(self):
        self.correction_download.setEnabled(False)
        self.correction_download.setText("Téléchargement en cours…")
        self.correction_status.setText("Préparation du correcteur local…")
        self.controller.prepare_correction()

    def show_correction_progress(self, message):
        self.correction_status.setText(message)

    def finish_correction_download(self, success, message):
        self.correction_status.setText(message)
        if success:
            self.correction_download.setText("Correcteur déjà téléchargé")
            self.correction_download.setEnabled(False)
        else:
            self.correction_download.setText("Réessayer le téléchargement")
            self.correction_download.setEnabled(True)

    def navigate(self, index):
        current = self.pages.currentIndex()
        if current == 3 and index != current and not self.confirm_settings():
            self.nav_buttons[current].setChecked(True)
            return False
        if not self.flush_edits():
            self.nav_buttons[current].setChecked(True)
            return False
        self.pages.setCurrentIndex(index)
        self.nav_buttons[index].setChecked(True)
        if index == 1:
            self.refresh_history()
        return True

    def suspend_shortcut(self):
        if self.hotkey:
            self.hotkey.suspend()

    def resume_shortcut(self):
        if self.hotkey:
            try:
                self.hotkey.resume()
            except RuntimeError as error:
                self.controller.notice.emit(str(error), True)

    def choose_history_folder(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Dossier de l’historique", self.history_path.text()
        )
        if directory:
            self.history_path.setText(str(Path(directory).resolve()))

    def choose_models_folder(self):
        directory = QFileDialog.getExistingDirectory(self, "Dossier des modèles", self.models_path.text())
        if directory:
            self.models_path.setText(str(Path(directory).resolve()))

    def show_page(self, index=0):
        self.navigate(index)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def refresh_microphones(self):
        if self.controller.state in (State.STARTING, State.RECORDING, State.TRANSCRIBING, State.INSERTING):
            self.statusBar().showMessage(
                "Attendez la fin de la dictée pour actualiser les microphones.", 3500
            )
            return
        selected = (
            self.microphone.currentData() if self.microphone.count() else self.controller.settings.microphone
        )
        self.microphone.clear()
        self.microphone.addItem("Périphérique Windows par défaut", "")
        try:
            for identity, name in microphones(refresh=True):
                self.microphone.addItem(name, identity)
            index = self.microphone.findData(selected)
            if index == -1 and selected:
                self.microphone.addItem("Débranché · " + selected.split("|", 1)[-1], selected)
                index = self.microphone.count() - 1
            self.microphone.setCurrentIndex(max(0, index))
        except Exception:
            log.exception("Énumération des microphones impossible")
            self.microphone.addItem("Microphones indisponibles · vérifiez les permissions", "")

    def save_vocabulary(self):
        text = self.vocabulary.toPlainText().strip()
        if len(text) > 2000:
            QMessageBox.warning(
                self,
                "Vocabulaire trop long",
                "Gardez au maximum 2 000 caractères pour un contexte pertinent.",
            )
            return
        updated = replace(self.controller.settings, vocabulary=text)
        try:
            updated.save(self.directory)
        except OSError as error:
            QMessageBox.warning(self, "Enregistrement impossible", str(error))
            return
        self.controller.settings = updated
        self.vocab_save.setText("Vocabulaire enregistré ✓")
        QTimer.singleShot(2500, lambda: self.vocab_save.setText("Enregistrer le vocabulaire"))

    def form_settings(self):
        folder = Path(self.history_path.text()).resolve()
        return replace(
            self.controller.settings,
            model=self.model.currentData(),
            correction=self.correction.isChecked(),
            language=self.language.currentData(),
            microphone=self.microphone.currentData(),
            sounds=self.sounds.isChecked(),
            close_to_tray=self.close_tray.isChecked(),
            startup=self.startup.isChecked(),
            hotkey_mods=self.key_edit.modifiers,
            hotkey_vk=self.key_edit.virtual_key,
            hotkey_label=self.key_edit.caption,
            theme=self.theme.currentData(),
            history_folder="" if folder == self.directory.resolve() else str(folder),
            models_folder=""
            if Path(self.models_path.text()).resolve() == (self.directory / "models").resolve()
            else str(Path(self.models_path.text()).resolve()),
        )

    def restore_settings_form(self):
        settings = self.controller.settings
        for widget, value in (
            (self.model, settings.model),
            (self.language, settings.language),
            (self.microphone, settings.microphone),
            (self.theme, settings.theme),
        ):
            widget.setCurrentIndex(widget.findData(value))
        self.key_edit.set_shortcut(settings.hotkey_mods, settings.hotkey_vk, settings.hotkey_label)
        self.correction.setChecked(settings.correction)
        self.sounds.setChecked(settings.sounds)
        self.close_tray.setChecked(settings.close_to_tray)
        self.startup.setChecked(settings.startup)
        self.history_path.setText(str(self.controller.history.directory))
        self.models_path.setText(str(self.controller.engine.cache))

    def confirm_settings(self):
        if self.form_settings() == self.controller.settings:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Appliquer les modifications ?")
        box.setText("Vous avez modifié les paramètres sans les appliquer.")
        box.setInformativeText("Voulez-vous les appliquer avant de quitter cette page ?")
        apply_button = box.addButton("Appliquer", QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton("Ne pas appliquer", QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton("Annuler", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(apply_button)
        box.setEscapeButton(cancel_button)
        box.exec()
        if box.clickedButton() == apply_button:
            return self.save_settings()
        if box.clickedButton() == discard_button:
            self.restore_settings_form()
            return True
        return False

    def prepare_to_leave(self):
        return self.flush_edits() and self.confirm_settings()

    def save_settings(self):
        if self.controller.busy:
            QMessageBox.information(
                self,
                "Moteur occupé",
                "Attendez la fin de la tâche en cours avant de modifier les paramètres.",
            )
            return False
        if not self.flush_edits():
            return False
        previous = self.controller.settings
        updated = self.form_settings()
        try:
            self.hotkey.register(updated.hotkey_mods, updated.hotkey_vk)
            set_startup(updated.startup)
            self.controller.history.relocate(
                Path(updated.history_folder or self.directory), lambda: updated.save(self.directory)
            )
        except Exception as error:
            log.exception("Modification des paramètres impossible")
            try:
                self.hotkey.register(previous.hotkey_mods, previous.hotkey_vk)
                set_startup(previous.startup)
            except Exception:
                log.exception("Restauration des paramètres système impossible")
            QMessageBox.warning(self, "Paramètres non appliqués", str(error))
            return False
        self.controller.settings = updated
        self.controller.engine.cache = Path(updated.models_folder or self.controller.engine.default_cache)
        self.controller.corrector.cache = self.controller.engine.cache
        apply_theme(QApplication.instance(), updated.theme)
        self.shortcut_hint.setText(f"{updated.hotkey_label} pour commencer. Le même raccourci pour terminer.")
        self.banner.hide()
        if previous.model != updated.model or self.controller.engine.model is None:
            self.controller.load()
        self.apply_button.setText("Paramètres appliqués ✓")
        QTimer.singleShot(2500, lambda: self.apply_button.setText("Appliquer les paramètres"))
        return True

    def start_from_ui(self):
        if self.controller.state in (State.RECORDING, State.STARTING):
            self.controller.toggle()
        elif self.controller.state == State.ERROR and self.controller.engine.model is None:
            self.controller.load()
        elif not self.controller.busy and not self.countdown:
            if not self.prepare_to_leave():
                return
            self.countdown = 3
            self.hide()
            self.controller.notice.emit(
                "La dictée démarre dans 3 secondes. Placez le curseur dans votre application.", False
            )
            QTimer.singleShot(3000, self._delayed_start)

    def _delayed_start(self):
        if not self.countdown:
            return
        self.countdown = 0
        if not self.controller.busy:
            self.controller.toggle()

    def update_state(self, state, message):
        if state not in ("idle", "error"):
            self.countdown = 0
        self.status_label.setText(message)
        settings = self.controller.settings
        self.shortcut_hint.setText(
            f"{settings.hotkey_label} pour commencer. Le même raccourci pour terminer."
        )
        self.progress.setVisible(state in ("loading", "starting", "transcribing", "inserting", "closing"))
        self.cancel_button.setVisible(state in ("starting", "recording"))
        self.record_button.setEnabled(state in ("idle", "error", "recording", "starting"))
        self.record_button.setText(
            {
                "recording": "Terminer la dictée",
                "starting": "Terminer la dictée",
                "error": "Réessayer",
                "idle": "Commencer une dictée",
            }.get(state, "Un instant…")
        )
        self.apply_button.setEnabled(not self.controller.busy)
        self.clear_button.setEnabled(not self.controller.busy)
        self.delete_button.setEnabled(not self.controller.busy and self.selected is not None)
        self.recover_button.setEnabled(not self.controller.busy)

    def tick(self):
        if self.controller.state == State.RECORDING:
            elapsed = int(time.monotonic() - self.controller.record_started)
            self.elapsed.setText(f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        else:
            self.elapsed.clear()

    def show_notice(self, text, error):
        self.banner.setText(text)
        self.banner.setVisible(error)

    def refresh_history(self, *args):
        if not self.flush_edits():
            return
        selected_id = self.selected["id"] if self.selected else None
        self.history_list.clear()
        rows = self.controller.history.rows(self.search.text(), limit=self.history_limit + 1)
        self.more_history.setVisible(len(rows) > self.history_limit)
        rows = rows[: self.history_limit]
        selection = 0
        for index, row in enumerate(rows):
            created = datetime.fromisoformat(row["created"])
            preview = row["text"].replace("\n", " ")[:88] or (
                "Audio à récupérer"
                if row["audio"]
                else "Échec de l’enregistrement"
                if row["status"] == "error"
                else "Aucune parole détectée"
            )
            item = QListWidgetItem(f"{created:%d %b · %H:%M}   /   {row['duration']:.0f} s\n{preview}")
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.history_list.addItem(item)
            if row["id"] == selected_id:
                selection = index
        self.history_count.setText(f"{len(rows)} dictée(s) affichée(s)")
        if rows:
            self.history_list.setCurrentRow(selection)
        else:
            self.select_entry(None, None)
        latest = self.controller.history.rows(limit=1)
        if latest:
            row = latest[0]
            self.latest_id = row["id"]
            created = datetime.fromisoformat(row["created"])
            self.latest_meta.setText(f"{created:%d/%m/%Y à %H:%M}  ·  {row['duration']:.1f} secondes")
            self.set_editor_text(self.latest_text, row["text"])
            self.latest_text.setReadOnly(bool(row["audio"]))
        else:
            self.latest_id = None
            self.latest_meta.setText("Votre première dictée commence ici")
            self.set_editor_text(self.latest_text, "")
            self.latest_text.setReadOnly(True)
        self.copy_latest.setEnabled(bool(self.latest_text.toPlainText()))

    def search_history(self):
        self.history_limit = 100
        self.refresh_history()

    def load_more_history(self):
        self.history_limit += 100
        self.refresh_history()

    def select_entry(self, current, previous):
        if not self.flush_edits():
            blocked = self.history_list.blockSignals(True)
            self.history_list.setCurrentItem(previous)
            self.history_list.blockSignals(blocked)
            return
        self.selected = current.data(Qt.ItemDataRole.UserRole) if current else None
        row = self.selected
        self.set_editor_text(self.detail_text, row["text"] if row else "")
        self.detail_text.setReadOnly(not row or bool(row["audio"]))
        self.detail_meta.setText(
            f"{datetime.fromisoformat(row['created']):%d/%m/%Y · %H:%M}\n{row['duration']:.1f} secondes"
            if row
            else "Sélectionnez une dictée"
        )
        self.detail_status.setText(row["detail"] if row else "")
        self.detail_copy.setEnabled(bool(row and row["text"]))
        self.recover_button.setVisible(bool(row and row["audio"] and not row["text"]))
        self.recover_button.setEnabled(not self.controller.busy)
        self.delete_button.setEnabled(bool(row) and not self.controller.busy)

    @staticmethod
    def set_editor_text(editor, text):
        previous = editor.blockSignals(True)
        editor.setPlainText(text)
        editor.blockSignals(previous)

    def transcript_changed(self, source):
        editor = self.latest_text if source == "latest" else self.detail_text
        identifier = (
            self.latest_id if source == "latest" else (self.selected["id"] if self.selected else None)
        )
        if not identifier or editor.isReadOnly():
            return
        text = editor.toPlainText()
        self.pending_edits[identifier] = text
        if source == "latest" and self.selected and self.selected["id"] == identifier:
            self.set_editor_text(self.detail_text, text)
        elif source == "detail" and self.latest_id == identifier:
            self.set_editor_text(self.latest_text, text)
        self.copy_latest.setEnabled(bool(self.latest_text.toPlainText()))
        self.detail_copy.setEnabled(bool(self.detail_text.toPlainText()))
        self.edit_timer.start()

    def flush_edits(self):
        self.edit_timer.stop()
        if not self.pending_edits:
            return True
        try:
            for identifier, text in list(self.pending_edits.items()):
                self.controller.history.edit_text(identifier, text)
                del self.pending_edits[identifier]
                if self.selected and self.selected["id"] == identifier:
                    self.selected["text"] = text
                for index in range(self.history_list.count()):
                    item = self.history_list.item(index)
                    row = item.data(Qt.ItemDataRole.UserRole)
                    if row["id"] == identifier:
                        row["text"] = text
                        item.setData(Qt.ItemDataRole.UserRole, row)
                        created = datetime.fromisoformat(row["created"])
                        preview = text.replace("\n", " ")[:88] or "Texte vide"
                        item.setText(f"{created:%d %b · %H:%M}   /   {row['duration']:.0f} s\n{preview}")
            self.statusBar().showMessage("Modifications du texte enregistrées.", 2200)
            return True
        except Exception:
            log.exception("Impossible d’enregistrer les corrections du texte")
            self.controller.notice.emit(
                "Corrections non enregistrées : vérifiez le dossier de l’historique. Le texte reste dans le champ ; copiez-le avant de quitter.",
                True,
            )
            return False

    def copy(self, text):
        if text:
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage("Texte copié dans le presse-papiers.", 2500)

    def recover_selected(self):
        if self.selected:
            self.controller.recover(self.selected)

    def delete_selected(self):
        if self.selected and not self.controller.busy:
            if (
                QMessageBox.question(
                    self,
                    "Supprimer cette dictée ?",
                    "Le texte et l’éventuel audio de récupération seront supprimés.",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            ):
                self.controller.history.delete(self.selected["id"])
                self.refresh_history()

    def clear_history(self):
        if self.controller.busy:
            return
        if (
            QMessageBox.question(
                self,
                "Effacer l’historique ?",
                "Tous les textes et les audios à récupérer seront définitivement supprimés.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.controller.history.clear()
            self.refresh_history()

    def closeEvent(self, event):
        if self.allow_close:
            event.accept()
        elif not self.prepare_to_leave():
            event.ignore()
        elif self.controller.settings.close_to_tray:
            event.ignore()
            self.hide()
        else:
            event.ignore()
            if self.quit_callback:
                self.quit_callback()
