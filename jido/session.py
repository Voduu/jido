from concurrent.futures import ThreadPoolExecutor
import hashlib
import os

import anthropic
import azure.cognitiveservices.speech as speechsdk
from dotenv import load_dotenv
import genanki


class JidoSession:
    def __init__(self, deck_name, study_category, study_level):
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.pending_futures = []

        self.cards_log = []
        self.cards_partial_failure = []
        self.cards_failed = []

        self.deck_name = deck_name

        self.accents_by_expression = {}
        self.furigana_dataset = {}
        model_id = 1098463829
        deck_id = int(
            hashlib.sha1(deck_name.encode()).hexdigest(), 16) % (1 << 31)

        # Sentence generation variables
        self.study_category = study_category
        self.study_level = study_level
        self.client_system_prompt = self.load_system_prompt()

        load_dotenv()
        self.client = anthropic.Anthropic(
            api_key=os.getenv("CLAUDE_CONSOLE_KEY"))

        # Audio generation variables
        self.speech_config = speechsdk.SpeechConfig(
            subscription=os.getenv("SPEECH_KEY"),
            endpoint=os.getenv("ENDPOINT"))
        self.speech_config.speech_synthesis_voice_name = "ja-JP-NanamiNeural"
        self.speech_config.set_speech_synthesis_output_format(
            speechsdk.SpeechSynthesisOutputFormat.Audio24Khz160KBitRateMonoMp3)
        self.speech_synthesizer = speechsdk.SpeechSynthesizer(
            speech_config=self.speech_config, audio_config=None)

        self.media_files = []

        self.anki_model = genanki.Model(
            model_id,
            "Jido Model",
            fields=[
                {"name": "Expression"},
                {"name": "Meaning"},
                {"name": "Reading"},
                {"name": "Sentence"},
                {"name": "Sentence Meaning"},
                {"name": "Pitch Accent"},
                {"name": "Pitch Type"},
                {"name": "Audio"},
                {"name": "Sentence Audio"},
                {"name": "Notes"},
            ],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": self.load_text_file(
                        "./data/templates/card1_front.html",
                        "Unable to load Card 1 Front HTML data. Reverting "
                        "to default.",
                        "{{Expression}}"),
                    "afmt": self.load_text_file(
                        "./data/templates/card1_back.html",
                        "Unable to load Card 1 Back HTML data. Reverting "
                        "to default.",
                        "{{Expression}}<hr>{{Reading}}<hr>{{Meaning}}<br>"
                        "{{Sentence}}<br>{{Sentence Meaning}}<br>"
                        "{{Pitch Accent}}<br>{{Audio}}<br>{{Sentence Audio}}")
                },
                {
                    "name": "Card 2",
                    "qfmt": self.load_text_file(
                        "./data/templates/card2_front.html",
                        "Unable to load Card 2 Front HTML data. Reverting "
                        "to default.",
                        "{{Audio}} {{Sentence Audio}}"),
                    "afmt": self.load_text_file(
                        "./data/templates/card2_back.html",
                        "Unable to load Card 2 Back HTML data. Reverting "
                        "to default.",
                        "{{Expression}}<hr>{{Reading}}<hr>{{Meaning}}<br>"
                        "{{Sentence}}<br>{{Sentence Meaning}}<br>"
                        "{{Pitch Accent}}")
                },
            ],
            css=self.load_text_file(
                "./data/templates/model_css.txt",
                "No CSS file found. Continuing without.")
        )

        self.anki_deck = genanki.Deck(
            deck_id,
            deck_name
        )

    def add_note(self, anki_note):
        self.anki_deck.add_note(anki_note)

    def load_text_file(self, path, error_message, default=""):
        try:
            with open(path) as fp:
                return fp.read()
        except FileNotFoundError:
            print(error_message)
            return default

    def load_system_prompt(self):
        system_prompt_parts = []
        try:
            with open("./data/system_prompt.txt") as fp:
                system_prompt_parts.append(fp.read())
        except FileNotFoundError:
            self.client_system_prompt = None
            print("ERROR: Failed to load Anthropic client system prompt.")
            return

        if self.study_category.lower() == "jlpt":
            system_prompt_parts.append(
                "Study Category: JLPT; Study Level: "
                f"{self.study_level.upper()}")
        elif self.study_category.lower() in ["genki", "quartet"]:
            system_prompt_parts.append(
                self.load_study_level(self.study_category, self.study_level))

        return "\n".join(system_prompt_parts)

    def load_study_level(self, study_category, study_level):
        system_prompt_parts = []
        system_prompt_parts.append(
            f"Study Category: {study_category}; Study Level: Chapter "
            f"{study_level}")

        if int(study_level) >= 5:
            study_level_lower_range = int(study_level) - 4
        else:
            study_level_lower_range = 1

        study_category = study_category.lower()
        for i in range(study_level_lower_range, int(study_level) + 1):
            chapter = f"{i:02d}"
            system_prompt_parts.append(
                self.load_text_file(
                    f"./data/levels/{study_category}/"
                    f"{study_category}_ch{chapter}.txt",
                    f"Error: Failed to load {study_category}_ch{chapter}.txt "
                    f"file."))

        return "\n".join(system_prompt_parts)