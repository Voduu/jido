from jisho_api.word import Word
import random
import genanki
import anthropic
import json
import os
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk
import re
from pathlib import Path
import requests
import datetime


class JishoAPIError(Exception):
    pass


class JidoSession:
    def __init__(self, deck_name):
        self.cards_log = []
        self.cards_partial_failure = []
        self.cards_failed = []

        self.deck_name = deck_name

        self.accents_by_expression = {}
        self.furigana_dataset = {}
        model_id = 1098463829
        deck_id = random.randrange(1 << 30, 1 << 31)

        # Sentence generation variables
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
                        "./data/card1_front.html",
                        "Unable to load Card 1 Front HTML data. Reverting "
                        "to default.",
                        "{{Expression}}"),
                    "afmt": self.load_text_file(
                        "./data/card1_back.html",
                        "Unable to load Card 1 Back HTML data. Reverting "
                        "to default.",
                        "{{Expression}}<hr>{{Reading}}<hr>{{Meaning}}<br>"
                        "{{Sentence}}<br>{{Sentence Meaning}}<br>"
                        "{{Pitch Accent}}<br>{{Audio}}<br>{{Sentence Audio}}")
                },
                {
                    "name": "Card 2",
                    "qfmt": self.load_text_file(
                        "./data/card2_front.html",
                        "Unable to load Card 2 Front HTML data. Reverting "
                        "to default.",
                        "{{Audio}} {{Sentence Audio}}"),
                    "afmt": self.load_text_file(
                        "./data/card2_back.html",
                        "Unable to load Card 2 Back HTML data. Reverting "
                        "to default.",
                        "{{Expression}}<hr>{{Reading}}<hr>{{Meaning}}<br>"
                        "{{Sentence}}<br>{{Sentence Meaning}}<br>"
                        "{{Pitch Accent}}")
                },
            ],
            css=self.load_text_file(
                "./data/model_css.txt",
                "No CSS file found. Continuing without.")
        )

        self.anki_deck = genanki.Deck(
            deck_id,
            deck_name
        )

        self.load_system_prompt()

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
        try:
            with open("./data/system_prompt.txt") as fp:
                self.client_system_prompt = fp.read()
        except FileNotFoundError:
            self.client_system_prompt = None
            print("ERROR: Failed to load Anthropic client system prompt.")
    

class Card:
    def __init__(
            self, user_input, expr, expr_meaning, expr_reading,
            expr_reading_furigana, expr_notes):
        self.user_input = user_input
        self.expr = expr
        self.expr_meaning = expr_meaning
        self.expr_reading = expr_reading
        self.expr_reading_furigana = expr_reading_furigana
        self.sentence_japanese = ""
        self.sentence_japanese_clean = ""
        self.sentence_english = ""
        self.pitch_accent = ""
        self.pitch_accent_type = "0"
        self.audio = ""
        self.audio_sentence = ""
        self.notes = expr_notes

        self.status_jisho = None
        self.status_furigana = None
        self.status_pitch_accent = None
        self.status_sentence = None
        self.status_audio_expr = None
        self.status_audio_sentence = None


def fetch_word(user_input, jido_session):
    # Retrieve data from Jisho API.
    try:
        data = Word.request(user_input).data
    except AttributeError:
        return None
    except requests.exceptions.JSONDecodeError:
        raise JishoAPIError
    except Exception:
        raise JishoAPIError
    # print(data)

    # Cycle through the data to find slug matches or 'usually kana' matches.
    match_list = [None] * len(data)
    k_matches = []
    s_matches = []
    for i in range(len(data)):
        parsed_slug = "".join(
            c for c in data[i].slug if c not in "-0123456789")

        # If parsed slug matches, mark as slug match.
        if parsed_slug == user_input:
            match_list[i] = "s"
            s_matches.append(i)
            continue

        # If parsed slug does not match, check for reading match
        # (rarely-used kanji).
        usually_kana_match = False
        for j in range(len(data[i].japanese)):
            if data[i].japanese[j].reading == user_input:
                usually_kana_match = True
                break

        # If there is a reading match, check the tags to see if it is usually
        # written in kana.
        if usually_kana_match:
            for j in range(len(data[i].senses)):
                if len(data[i].senses[j].tags) == 0:
                    continue
                if ("Usually written using kana alone"
                        in data[i].senses[j].tags):
                    match_list[i] = "k"
                    k_matches.append(i)
                    break

        if match_list[i] is None:
            match_list[i] = "n"

    # Determine which kind of match the word is.
    if "s" in match_list:
        match_type = "kanji_kana"
    elif "k" in match_list:
        match_type = "rare_kanji"
    else:
        return None

    # Handle multiple readings (kanji match only).
    readings = []
    if match_type == "kanji_kana":
        for i in range(len(s_matches)):
            # NOTE: Removed previous kana only word handling.
            # See here for history:
            # https://github.com/Voduu/jido/blob/e2649759daa46f10faa76d6fcf68c50cb92fdc72/main.py

            slug_readings = []
            for j in range(len(data[s_matches[i]].japanese)):
                if data[s_matches[i]].japanese[j].word == user_input:
                    slug_readings.append(
                        data[s_matches[i]].japanese[j].reading)

            # Create string of readings.
            readings.append("\uff0f".join(slug_readings))

        # Prompt the user to choose the reading.
        selected_match = 0
        if (len(s_matches) > 1):
            for i in range(len(s_matches)):
                print(f"{i + 1}. {user_input}\uff08{readings[i]}\uff09")

                user_selection = 0
            while user_selection not in range(1, len(s_matches) + 1):
                user_selection = input(
                    f"Multiple readings were found for {user_input}. Please "
                    "choose the number of the correct reading (i.e., 1): ")

                try:
                    user_selection = int(user_selection)
                except ValueError:
                    continue

            selected_match = user_selection - 1

    # Identify the user's selection in match_list.
    word_index = -1
    if match_type == "kanji_kana":
        word_index = s_matches[selected_match]
    elif match_type == "rare_kanji" and len(k_matches) == 1:
        word_index = k_matches[0]

    # Check for multiple senses
    # The values are the actual indices of the senses, the index is the 
    # displayed number to the user.
    senses_list = [] 
    sense_index = -1

    # If a WordConfig has already been selected.
    if word_index > -1:
        # Check if there are more than one valid senses.
        if match_type == "rare_kanji":
            for i in range(len(data[word_index].senses)):
                if ("Usually written using kana alone"
                        in data[word_index].senses[i].tags and
                        "Wikipedia definition" not in
                        data[word_index].senses[i].parts_of_speech):
                    senses_list.append(i)
        else:
            for i in range(len(data[word_index].senses)):
                if ("Wikipedia definition" not in
                        data[word_index].senses[i].parts_of_speech):
                    senses_list.append(i)

        # If there are multiple senses, prompt the user to choose one.
        if len(senses_list) > 1:
            for i in range(len(senses_list)):
                print(f"{i + 1}. {"; ".join(
                    data[word_index].senses[senses_list[i]]
                    .english_definitions)}")

            user_selection = 0
            while user_selection not in range (1, len(senses_list) + 1):
                user_selection = input(
                    f"Multiple senses were found for {user_input}. Please "
                    "choose the number of the correct sense (i.e., 1): ")
                try:
                    user_selection = int(user_selection)
                except ValueError:
                    continue

            sense_index = senses_list[user_selection - 1]

        # If there is only a single matching sense.
        else:
            sense_index = senses_list[0]

    # If a WordConfig has not been selected
    # ("usually kana" word matching to multiple WordConfigs)
    else:
        # First number is the WordConfig index, second is sense index.
        word_sense_index_tuple = []

        for i in range(len(k_matches)):
            for j in range(len(data[k_matches[i]].senses)):
                if ("Usually written using kana alone"
                        in data[k_matches[i]].senses[j].tags and
                        "Wikipedia definition" not in
                        data[k_matches[i]].senses[j].parts_of_speech):
                    word_sense_index_tuple.append((k_matches[i], j))

        # Prompt the user to choose the desired sense.
        for i in range(len(word_sense_index_tuple)):
            print(f"{i + 1}. {"; ".join(
                data[word_sense_index_tuple[i][0]]
                .senses[word_sense_index_tuple[i][1]]
                .english_definitions)}")

        user_selection = 0
        while user_selection not in range (1, len(word_sense_index_tuple) + 1):
            user_selection = input(
                f"Multiple senses were found for {user_input}. Please "
                "choose the number of the correct sense (i.e., 1): ")
            try:
                user_selection = int(user_selection)
            except ValueError:
                continue

        # Finally, set word_index and sense_index.
        word_index = word_sense_index_tuple[user_selection - 1][0]
        sense_index = word_sense_index_tuple[user_selection - 1][1]

    # Save parts of the word.
    expression = "".join(
        c for c in data[word_index].slug if c not in "-0123456789")
    meaning = "; ".join(
        data[word_index].senses[sense_index].english_definitions)
    sense_notes = data[word_index].senses[sense_index].parts_of_speech
    if match_type == "kanji_kana":
        reading = readings[selected_match].split("\uff0f")[0]
    else:
        reading = user_input

    # Retrieve the furigana reading for the expression.
    furigana_found = False
    expression_match = False
    if expression in jido_session.furigana_dataset:
        furigana_entries = jido_session.furigana_dataset[expression]
        reading_furigana = ""
        expression_match = True

        for i in range(len(furigana_entries)):
            if furigana_entries[i][0] == reading:
                for j in range(len(furigana_entries[i][1])):
                    if "rt" in furigana_entries[i][1][j]:
                        # Add a space if the previous character is not a 
                        # bracket (or the string is not empty) for formatting.
                        if (reading_furigana != "" 
                                and reading_furigana[-1] != "]"):
                            reading_furigana += " "

                        reading_furigana += (
                            furigana_entries[i][1][j]["ruby"] + "[" 
                            + furigana_entries[i][1][j]["rt"] + "]")
                    else:
                        reading_furigana += furigana_entries[i][1][j]["ruby"]
                furigana_found = True
                break

    furigana_status = ""
    if not furigana_found:
        # If a match is found but no furigana (mismatched reading, etc.).
        if expression_match:
            print(
                f"Furigana data found for {user_input} but none matched the "
                f"reading {reading}. Defaulting to {reading} without "
                 "furigana.")
            reading_furigana = reading
            furigana_status = "mismatched reading"
        # If a match is not found.
        else:
            print(
                f"Furigana data not found for {user_input}. Defaulting to "
                f"{reading} without furigana.")
            reading_furigana = reading
            furigana_status = "no data found"

    # Create the notes section.
    expr_notes = format_speech_parts(sense_notes)

    # Finally, create the card.
    jido_card = Card(
        user_input,
        expression,
        meaning,
        reading,
        reading_furigana,
        expr_notes
    )

    # Update Jisho and furigana statuses.
    jido_card.status_jisho = ("success", "")

    if furigana_status == "":
        jido_card.status_furigana = ("success", "")
    else:
        jido_card.status_furigana = ("failure", furigana_status)
        jido_session.cards_partial_failure.append(jido_card)

    return jido_card


def format_speech_parts(sense_notes):
    note_entries = []

    if "Suru verb" in sense_notes:
        note_entries.append("する動詞")
    
    if "Ichidan verb" in sense_notes:
        note_entries.append("一段動詞")
    
    if any(note.startswith("Godan verb") for note in sense_notes):
        note_entries.append("五段動詞")
    
    if "Transitive verb" in sense_notes:
        note_entries.append("他動詞")
    
    if "Intransitive verb" in sense_notes:
        note_entries.append("自動詞")
    
    if "Na-adjective (keiyodoshi)" in sense_notes:
        note_entries.append("な形容詞")
    
    if "I-adjective (keiyoushi)" in sense_notes:
        note_entries.append("い形容詞")
    
    if "Adverb (fukushi)" in sense_notes:
        note_entries.append("副詞")

    if "Counter" in sense_notes:
        note_entries.append("助数詞")
    
    if "Prefix" in sense_notes:
        note_entries.append("接頭語")
    
    if "Noun, used as a suffix" in sense_notes:
        note_entries.append("接尾語")
    
    if "Expressions (phrases, clauses, etc.)" in sense_notes:
        note_entries.append("表現")
    
    if len(note_entries) > 0:
        return "\uff0f".join(note_entries)
    else:
        return ""


def fetch_pitch_accent(jido_session, jido_card):
    expr = jido_card.expr
    reading = jido_card.expr_reading
    small_kana = [
        "ぁ", "ぃ", "ぅ", "ぇ", "ぉ", "ゃ", "ゅ", "ょ", "ゎ", "ァ", "ィ", "ゥ", 
        "ェ", "ォ", "ャ", "ュ", "ョ", "ヮ", "ヵ", "ヶ"]
    mora_string = "".join(c for c in reading if c not in small_kana)
    mora_length = len(mora_string)
    reading_length = len(reading)
    reading_found = False
    pitch_number = 0

    # Find the expression in one of the dictionaries.
    if expr in jido_session.accents_by_expression:
        accent_data = jido_session.accents_by_expression[expr]
        for i in range(len(accent_data)):
            if accent_data[i][0] == reading:
                pitch_number = int(accent_data[i][1].split(",")[0])
                reading_found = True
            # Kana only words
            elif accent_data[i][0] == "":
                pitch_number = int(accent_data[i][1].split(",")[0])
                reading_found = True

    if not reading_found:
        valid_input = False
        while not valid_input:
            try:
                pitch_number = int(input(
                    "No pitch accent data found. Please enter the downstep "
                    f"position for {jido_card.user_input}: "))
                if 0 <= pitch_number <= mora_length:
                    valid_input = True
            except ValueError:
                pass
        jido_card.status_pitch_accent = ("failed", "manual entry")
        jido_session.cards_partial_failure.append(jido_card)
    else:
        jido_card.status_pitch_accent = ("success", "")

    # Heiban
    if pitch_number == 0:
        jido_card.pitch_accent_type = "1"
        for i in range(mora_length + 1):
            if i == 0:
                pitch_string = "L"
            elif i > 0:
                pitch_string += "H"
    # Atamadaka
    elif pitch_number == 1:
        jido_card.pitch_accent_type = "2"
        for i in range(mora_length + 1):
            if i == 0:
                pitch_string = "H"
            elif i > 0:
                pitch_string += "L"
    # Nakadaka
    elif 1 < pitch_number < mora_length:
        jido_card.pitch_accent_type = "3"
        for i in range(mora_length + 1):
            if i == 0:
                pitch_string = "L"
            elif 0 < i <= pitch_number - 1:
                pitch_string += "H"
            elif i > pitch_number - 1:
                pitch_string += "L"
    # Odakagata
    elif pitch_number == mora_length:
        jido_card.pitch_accent_type = "4"
        for i in range(mora_length + 1):
            if i == 0:
                pitch_string = "L"
            elif 0 < i <= pitch_number - 1:
                pitch_string += "H"
            elif i > pitch_number - 1:
                pitch_string += "L"
    
    # Develop the SVG based on the pitch_string.
    ## First, kana characters along the bottom.
    kana_str = ""
    kana_pos = 5
    svg_kana_1 = '<text x="'
    svg_kana_2_normal_kana = (
        '" y="67.5" style="font-size:20px;'
        'font-family:sans-serif;fill:#000;">'
    )
    svg_kana_2_small_kana = (
        '" y="67.5" style="font-size:14px;'
        'font-family:sans-serif;fill:#000;">'
    )
    svg_kana_3 = '</text>'

    count = 1
    while count <= reading_length:
        # If this is not the last kana, check for a small kana next
        if (count != reading_length and reading[count] in small_kana):
            kana_pos -= 5
            kana_str += (
                svg_kana_1 + str(kana_pos) + svg_kana_2_normal_kana 
                + reading[count - 1] + svg_kana_3)
            kana_pos += 17
            kana_str += (
                svg_kana_1 + str(kana_pos) + svg_kana_2_small_kana 
                + reading[count] + svg_kana_3)
            kana_pos += 23
            count += 1
        else:
            kana_str += (
                svg_kana_1 + str(kana_pos) + svg_kana_2_normal_kana 
                + reading[count - 1] + svg_kana_3)
            kana_pos += 35
        count += 1

    ## Next, create the lines.
    line_str = ""
    line_x_pos = 16
    line_low_pos = ',30 '
    line_high_pos = ',5 '
    line_low_to_high = '35,-25"'
    line_high_to_low = '35,25"'
    line_no_height_change = '35,0"'

    svg_line_1 = '<path d="m '
    svg_line_2 = ' style="fill:none;stroke:#000;stroke-width:1.5;"></path>'

    count = 1
    while count < len(pitch_string):
        line_change = ""
        if pitch_string[count - 1] == "H":
            if pitch_string[count] == "H":
                line_change = line_no_height_change
            elif pitch_string[count] == "L":
                line_change = line_high_to_low
            line_str += (
                svg_line_1 + str(line_x_pos) + line_high_pos + line_change 
                + svg_line_2)
        elif pitch_string[count - 1] == "L":
            if pitch_string[count] == "H":
                line_change = line_low_to_high
            elif pitch_string[count] == "L":
                line_change = line_no_height_change
            line_str += (
                svg_line_1 + str(line_x_pos) + line_low_pos + line_change 
                + svg_line_2)

        line_x_pos += 35
        count += 1

    ## Add the dots.
    dot_str = ""
    dot_x_pos = 16
    dot_low_pos = "30"
    dot_high_pos = "5"

    svg_dot_1 = '<circle r="5" cx="'
    svg_dot_1_hollow = '<circle r="3.25" cx="'
    svg_dot_2 = '" cy="'
    svg_dot_3 = '" style="opacity:1;fill:#000;"></circle>'
    svg_dot_3_hollow = '" style="opacity:1;fill:#fff;"></circle>'

    for i in range(len(pitch_string)):
        if pitch_string[i] == "H":
            dot_str += (
                svg_dot_1 + str(dot_x_pos) + svg_dot_2 + dot_high_pos 
                + svg_dot_3)

            if i == len(pitch_string) - 1:
                dot_str += (
                    svg_dot_1_hollow + str(dot_x_pos) + svg_dot_2 
                    + dot_high_pos + svg_dot_3_hollow)
        elif pitch_string[i] == "L":
            dot_str += (
                svg_dot_1 + str(dot_x_pos) + svg_dot_2 + dot_low_pos 
                + svg_dot_3)

            if i == len(pitch_string) - 1:
                dot_str += (
                    svg_dot_1_hollow + str(dot_x_pos) + svg_dot_2 
                    + dot_low_pos + svg_dot_3_hollow)

        dot_x_pos += 35


    ## Finally, add the outer SVG takes and data.
    svg_width = dot_x_pos - 19

    svg_str_1 = '<svg class="pitch" width="'
    svg_str_2 = 'px" height="75px" viewBox="0 0 '
    svg_str_3 = ' 75">'
    svg_str_4 = '</svg>'

    svg_full_string = (
        svg_str_1 + str(svg_width) + svg_str_2 + str(svg_width) + svg_str_3 
        + kana_str + line_str + dot_str + svg_str_4)

    jido_card.pitch_accent = svg_full_string
    

def fetch_sentences(jido_session, jido_card):
    for i in range(2):
        content_message = (
            f"Expression: {jido_card.user_input}; Meaning: "
            f"{jido_card.expr_meaning}; Level: JLPT N4; Pitch Formatting Number: "
            f"{jido_card.pitch_accent_type}")
        message = jido_session.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=jido_session.client_system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": content_message
                }
            ]
        )

        for block in message.content:
            if block.type == "text":
                message_content = block

        try:
            sentence_data = json.loads(message_content.text)

            jido_card.sentence_japanese = sentence_data["japanese"]
            jido_card.sentence_english = sentence_data["english"]

            # Clean Japanese sentence for Azure TTS.
            jido_card.sentence_japanese_clean = re.sub(
                r"<.*?>", "", sentence_data["japanese"])
            
            # Check for color formatting.
            if ("<span" in jido_card.sentence_japanese
                    and "<span" in jido_card.sentence_english):
                jido_card.status_sentence = ("success", "")
                break
            else:
                if i == 0:
                    print(
                         "Error including <span> formatting in the generated"
                        f" sentence for {jido_card.user_input}. Retrying once"
                         "...")
                else:
                    print(
                         "Failed to include <span> formatting in the generated"
                        f" sentence for {jido_card.user_input}. Continuing "
                         "with an unformated sentence.")
                    jido_card.status_sentence = ("failed", "formatting")
                    jido_session.cards_partial_failure.append(jido_card)
        except (json.JSONDecodeError, KeyError):
            if i == 0:
                print(
                    f"Error generating sentences for {jido_card.user_input}. "
                        "Retrying once...")
            else:
                print(
                    f"Failed to generate sentences for {jido_card.user_input}."
                    " Continuing without sentences.")
                jido_card.sentence_japanese = ""
                jido_card.sentence_english = ""
                jido_card.status_sentence = ("failed", "failed to generate")
                jido_session.cards_partial_failure.append(jido_card)


def fetch_audio(jido_session, jido_card):
    for i in range(2):
        try:
            synthesizer = jido_session.speech_synthesizer
            audio_result = synthesizer.speak_text_async(jido_card.expr)

            expression_audio = audio_result.get()
            expression_stream = speechsdk.AudioDataStream(expression_audio)
            expression_audio_path = (
                "./output/audio/" + jido_card.expr + "_expr.mp3")
            expression_stream.save_to_wav_file(expression_audio_path)
            jido_card.audio = "[sound:" + jido_card.expr + "_expr.mp3]"
            jido_session.media_files.append(
                "./output/audio/" + jido_card.expr + "_expr.mp3")
            
            jido_card.status_audio_expr = ("success", "")
            break
        except Exception:
            if i == 0:
                print(
                    f"Error obtaining expression audio for {jido_card.expr}. "
                    "Retrying once...")
            else:
                print(
                    f"Failed to obtain expression audio for {jido_card.expr}. "
                    "Continuing without audio.")
                jido_card.audio = ""
                jido_card.status_audio_expr = ("failed", "failed to generate")
                jido_session.cards_partial_failure.append(jido_card)

    for i in range(2):
        try:
            synthesizer = jido_session.speech_synthesizer
            audio_result = synthesizer.speak_text_async(
                jido_card.sentence_japanese_clean)

            sentence_audio = audio_result.get()
            sentence_stream = speechsdk.AudioDataStream(sentence_audio)
            sentence_audio_path = (
                "./output/audio/" + jido_card.expr + "_sentence.mp3")
            sentence_stream.save_to_wav_file(sentence_audio_path)
            jido_card.audio_sentence = (
                "[sound:" + jido_card.expr + "_sentence.mp3]")
            jido_session.media_files.append(
                "./output/audio/" + jido_card.expr + "_sentence.mp3")
            
            jido_card.status_audio_sentence = ("success", "")
            break
        except Exception:
            if i == 0:
                print(
                    f"Error obtaining sentence audio for {jido_card.expr}. "
                    "Retrying once...")
            else:
                print(
                    f"Failed to obtain sentence audio for {jido_card.expr}. "
                    "Continuing without audio.")
                jido_card.audio_sentence = ""
                jido_card.status_audio_sentence = (
                    "failed", "failed to generate")
                jido_session.cards_partial_failure.append(jido_card)


def import_csv(jido_session):
    print(
        "\nPlease note that this process is not entirely automatic.\nIt may "
        "take some time to complete depending on the number of words in the "
        "file and will likely require your input.\nYou will be given the "
        "opportunity to stop early every 25 words. You can then export what "
        "has been completed.\nYour position in the file will not be saved and "
        "it will start from the beginning the next time.\n")

    # Prompt the user to place the file in the correct directory and identify
    # it.
    input_file_name = ""
    while input_file_name == "":
        input_file_name = input(
            "Please place your .csv or .txt file in the \"/input\" directory, "
            "and provide the name here, including the extension. To cancel, "
            "type 'cancel': ")
    
    if input_file_name == "cancel":
        return

    delimiter = ""
    while delimiter == "":
        delimiter = input(
            "Please enter the character used to delimit each word in the "
            "file. Use \\n for new line and \\t for tab: ")
    
    # Fix escape delimiters.
    if delimiter == "\\n":
        delimiter = "\n"
    elif delimiter == "\\t":
        delimiter = "\t"
    
    # Attempt to load the file.
    word_list = []
    try:
        with open(f"./input/{input_file_name}") as input_file:
            data = input_file.read().rstrip()

            word_list = data.split(delimiter)
    except FileNotFoundError:
        print(
            f"File {input_file_name} not found. Please ensure it is placed in "
             "the ./input/ directory.")
        return

    print()
    count = 0
    for word in word_list:
        if count != 0 and count % 25 == 0:
            user_input = "invalid"
            while user_input.lower() not in ["y", "n", ""]:
                user_input = input(
                    f"{count} words have been processed. Would you like to "
                    "continue? [Y/n] ")

            print()
            if user_input.lower() == "n":
                break
        
        if len(word.strip()) > 0:
            process_word(word, jido_session)
        count += 1

    
def process_word(user_input, jido_session):
    print(f"=== {user_input} ===")
    # Retrieve Jisho data.
    try:
        jido_card = fetch_word(user_input, jido_session)
    except JishoAPIError:
        print(f"Unable to retrieve data for {user_input}. Please try again.")

        failed_card = Card(user_input, "", "", "", "", "")
        failed_card.status_jisho = ("failed", "Jisho API error")
        jido_session.card_failed.append(failed_card)
        jido_session.cards_log.append(failed_card)
        return

    # If no result, check if the word was entered as a する verb or な adj.
    if jido_card is None:
        # な adjective
        if user_input[-1] == "な":
            adjusted_user_input = user_input[:-1]
            jido_card = fetch_word(adjusted_user_input, jido_session)
        # する verb
        elif user_input[-2:] == "する":
            adjusted_user_input = user_input[:-2]
            jido_card = fetch_word(adjusted_user_input, jido_session)
        # No match.
        else:
            print(f"No match found for {user_input}.\n")

            failed_card = Card(user_input, "", "", "", "", "")
            failed_card.status_jisho = ("failed", "no match found")
            jido_session.cards_failed.append(failed_card)
            jido_session.cards_log.append(failed_card)
            return

    # Retrieve pitch accent data.
    fetch_pitch_accent(jido_session, jido_card)

    # Retrieve sentence data.
    fetch_sentences(jido_session, jido_card)

    # Retrieve audio data.
    fetch_audio(jido_session, jido_card)

    # Create note.
    create_note(jido_session, jido_card)

    # Add card to cards log.
    jido_session.cards_log.append(jido_card)


def create_note(jido_session, jido_card):
    anki_note = genanki.Note(
        model=jido_session.anki_model,
        fields=[
            jido_card.user_input,
            jido_card.expr_meaning,
            jido_card.expr_reading_furigana,
            jido_card.sentence_japanese,
            jido_card.sentence_english,
            jido_card.pitch_accent,
            jido_card.pitch_accent_type,
            jido_card.audio,
            jido_card.audio_sentence,
            jido_card.notes
        ]
    )

    jido_session.add_note(anki_note)
    print()


def export_deck(output_name, jido_session):
    jido_package = genanki.Package(jido_session.anki_deck)
    jido_package.media_files = jido_session.media_files
    jido_package.write_to_file("./output/packages/" + output_name + ".apkg")
    export_datetime = datetime.datetime.now().strftime(
        f"%Y-%m-%d %I:%M %p")

    # Generate partially failed cards.
    failure_string = ""
    
    for card in jido_session.cards_partial_failure:
        need_comma = False
        failure_string += "    ✗ " + card.user_input + ": "

        # Furigana
        if card.status_furigana[0] != "success":
            failure_string += f"furigana ({card.status_furigana[1]})"
            need_comma = True

        # Pitch Accent
        if card.status_pitch_accent[0] != "success":
            if need_comma:
                failure_string += ", "
            
            failure_string += f"pitch accent ({card.status_pitch_accent[1]})"
            need_comma = True
        
        # Sentences
        if card.status_sentence[0] != "success":
            if need_comma:
                failure_string += ", "
            
            failure_string += f"sentences ({card.status_sentence[1]})"
            need_comma = True
        
        # Expression Audio
        if card.status_audio_expr[0] != "success":
            if need_comma:
                failure_string += ", "
            
            failure_string += f"expression audio ({card.status_audio_expr[1]})"
            need_comma = True
        
        # Sentence Audio
        if card.status_audio_sentence[0] != "success":
            if need_comma:
                failure_string += ", "
            
            failure_string += (
                f"sentence audio ({card.status_audio_sentence[1]})")
            need_comma = True
        
        failure_string += "\n"
    
    # Generate skipped cards.
    skipped_string = ""

    if len(jido_session.cards_failed) == 0:
        skipped_string = ""
    
    for card in jido_session.cards_failed:
        skipped_string += f"    ✗ {card.user_input}: {card.status_jisho[1]}\n"
        
    # Generate detailed log.
    detailed_log = ""
    
    for i in range(len(jido_session.cards_log)):
        card = jido_session.cards_log[i]
        detailed_log += f"{i + 1}. {card.user_input}\n"

        # Jisho API 
        if card.status_jisho[0] == "success":
            detailed_log += "    ✓ Jisho lookup\n"
        else:
            detailed_log += (
                f"    ✗ Jisho lookup ({card.status_jisho[1]})\n"
                "    ✗ Furigana\n"
                "    ✗ Pitch accent\n"
                "    ✗ Sentence generation\n"
                "    ✗ Expression audio\n"
                "    ✗ Sentence audio\n")
            
            continue

        # Furigana
        if card.status_furigana[0] == "success":
            detailed_log += "    ✓ Furigana\n"
        else:
            detailed_log += f"    ✗ Furigana ({card.status_furigana[1]})\n"
        
        # Pitch Accent
        if card.status_pitch_accent[0] == "success":
            detailed_log += "    ✓ Pitch accent\n"
        else:
            detailed_log += (
                f"    ✗ Pitch accent ({card.status_pitch_accent[1]})\n")
        
        # Sentences
        if card.status_sentence[0] == "success":
            detailed_log += "    ✓ Sentence generation\n"
        else:
            detailed_log += (
                f"    ✗ Sentence generation ({card.status_sentence[1]})\n")
        
        # Expression Audio
        if card.status_audio_expr[0] == "success":
            detailed_log += "    ✓ Expression audio\n"
        else:
            detailed_log += (
                f"    ✗ Expression audio ({card.status_audio_expr[1]})\n")
        
        # Sentence Audio
        if card.status_audio_sentence[0] == "success":
            detailed_log += "    ✓ Sentence audio\n"
        else:
            detailed_log += (
                f"    ✗ Sentence audio ({card.status_audio_sentence[1]})\n")

    output_string = (
        "=== Jido Import Log ===\n"
        f"Deck: {jido_session.deck_name}\n"
        f"Date: {export_datetime}\n"
        f"Words processed: {len(jido_session.cards_log)}\n"
        f"Fully successful: {(len(jido_session.cards_log)
                              - (len(jido_session.cards_partial_failure)
                                 + len(jido_session.cards_failed)))}\n"
        f"Partial failures: {len(jido_session.cards_partial_failure)}\n"
        f"{failure_string}"
        f"Skipped: {len(jido_session.cards_failed)}\n"
        f"{skipped_string}"
        "\n\n"
        "=== Detailed Log ===\n"\
        f"{detailed_log}")
        
    # Save File
    Path("./output/logs").mkdir(parents=True, exist_ok=True)
    export_file_path = datetime.datetime.now().strftime(
        f"./output/logs/%Y%m%d_%H%M_{output_name}.log")
    with open(export_file_path, "w") as fp:
        fp.write(output_string)


def main():
    deck_name = ""
    output_name = ""
    valid_output_name = False

    while deck_name == "":
        deck_name = input("Enter your deck name: ")

    while not valid_output_name:
        output_name = input("Enter your output name (excluding .apkg): ")
        output_name = output_name.lower().strip(" .").replace(" ", "-")
        output_name = "".join(c for c in output_name if c not in '<>:"/\\|?*')

        if len(output_name) > 0:
            valid_output_name = True
    
    jido_session = JidoSession(deck_name)
    # Create accent data dictionary
    try:
        with open("./data/accents.txt") as accents_file:
            for line in accents_file:
                expression, reading, pitch_number = line.split("\t")
                pitch_number = "".join(
                    c for c in pitch_number if c in "0123456789,")
                
                if expression in jido_session.accents_by_expression:
                    jido_session.accents_by_expression[expression].append(
                        [reading, pitch_number.rstrip()])
                else:
                    jido_session.accents_by_expression[expression] = [
                        [reading, pitch_number.rstrip()]]
    except FileNotFoundError:
        print("accents.txt not found.")
        return
    
    # Create a furigana data dictionary.
    try:
        with open(
                "./data/furigana.json", encoding="utf-8-sig") as furigana_file:
            data = json.load(furigana_file)

            for entry in data:
                if entry["text"] in jido_session.furigana_dataset:
                    jido_session.furigana_dataset[entry["text"]].append(
                        [entry["reading"], entry["furigana"]])
                else:
                    jido_session.furigana_dataset[entry["text"]] = [
                        [entry["reading"], entry["furigana"]]]
                 
    except FileNotFoundError:
        print("File \"./data/furigana.json\" not found.")
        return
    
    # Ensure required directories exist.
    Path("./output/audio/").mkdir(parents=True, exist_ok=True)
    Path("./output/packages/").mkdir(parents=True, exist_ok=True)
    Path("./input/").mkdir(parents=True, exist_ok=True)

    while True:
        user_input = input(
            "Enter a word ('exit' to exit, 'export' to create .apkg "
            "package, 'csv' to import a csv file): ")

        if user_input == "exit":
            break

        if user_input == "export":
            export_deck(output_name, jido_session)
            break

        if user_input == "csv":
            import_csv(jido_session)
            continue

        print()
        process_word(user_input, jido_session)


if __name__ == "__main__":
    main()