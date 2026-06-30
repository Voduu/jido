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


class JidoSession:
    def __init__(self, deck_name):
        self.accents_by_expression = {}
        self.accents_by_reading = {}
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
    def __init__(self, user_input, expr, expr_meaning, expr_reading):
        self.user_input = user_input
        self.expr = expr
        self.expr_meaning = expr_meaning
        self.expr_reading = expr_reading
        self.sentence_japanese = ""
        self.sentence_japanese_clean = ""
        self.sentence_english = ""
        self.pitch_accent = ""
        self.pitch_accent_type = "0"
        self.audio = ""
        self.audio_sentence = ""
        self.notes = ""


def fetch_word(user_input):
    # Retrieve data from Jisho API.
    try:
        data = Word.request(user_input).data
    except AttributeError:
        return None
    print(data)

    if len(data) == 0:
        print(f"No match found for {user_input}.")
        return None
    
    expression = ""
    meaning = ""
    reading = ""
    
    # Search for at least one single matching slug.
    match_found = False
    match_count = 0
    readings = []
    matched_indices = []
    for i in range(len(data)):
        parsed_slug = "".join(
            c for c in data[i].slug if c not in "-0123456789")

        # Keep track of the number of matches and skip mismatches.
        if parsed_slug == user_input:
            match_count += 1
            matched_indices.append(i)
            match_found = True
        else:
            continue
        
        # Handle any number of readings.
        slug_readings = []
        for j in range(len(data[i].japanese)):
            # Handle kana only words.
            if data[i].japanese[j].word is None:
                if data[i].japanese[j].reading == user_input:
                    slug_readings.append(data[i].japanese[j].reading)
            
            # Kanji words.
            if data[i].japanese[j].word == user_input:
                slug_readings.append(data[i].japanese[j].reading)
        readings.append("\uff0f".join(slug_readings))
    
    # If a kana-only or kanji match was found.
    if match_found:
        # If there are multiple readings, prompt the user to choose one.
        selected_match = 0
        if match_count > 1:
            for i in range(match_count):
                print(f"{i + 1}. {user_input}\uff08{readings[i]}\uff09")
            
            user_selection = 0
            while user_selection not in range(1, match_count + 1):
                user_selection = input(
                    f"Multiple readings were found for {user_input}. Please "
                    "choose the number of the correct reading (i.e., 1): ")
                try:
                    user_selection = int(user_selection)
                except ValueError:
                    continue
            
            selected_match = user_selection - 1
        
        # If there are multiple senses, prompt the user to choose one.
        senses_count = len(data[matched_indices[selected_match]].senses)
        selected_sense = 0
        if senses_count > 1:
            for i in range(senses_count):
                print(f"{i + 1}. {"; ".join(
                    data[matched_indices[selected_match]]
                    .senses[i].english_definitions)}")
            
            user_selection = 0
            while user_selection not in range(1, senses_count + 1):
                user_selection = input(
                    f"Multiple senses were found for {user_input}. Please "
                    "choose the number of the correct sense (i.e., 1): ")
                try:
                    user_selection = int(user_selection)
                except ValueError:
                    continue
            
            selected_sense = user_selection - 1
        
        expression = "".join(
            c for c in data[matched_indices[selected_match]]
            .slug if c not in "-0123456789")
        meaning = "; ".join(
            data[matched_indices[selected_match]]
            .senses[selected_sense].english_definitions)
        reading = readings[selected_match].split("\uff0f")[0]

    # If no matches found, check for rarely used kanji version.
    if not match_found:
        reading = user_input

        for i in range(len(data)):
            parsed_slug = "".join(
                c for c in data[i].slug if c not in "-0123456789")
            
            reading_match = False
            for j in range(len(data[i].japanese)):
                if data[i].japanese[j].reading == user_input:
                    reading_match = True
                    break
            if reading_match:
                # Check if any senses are usually written using kana alone.
                senses_list = []
                for j in range(len(data[i].senses)):
                    if len(data[i].senses[j].tags) == 0:
                        continue
                    if ("Usually written using kana alone" 
                            in data[i].senses[j].tags):
                        senses_list.append("; ".join(
                                data[i].senses[j].english_definitions))

                senses_count = len(senses_list)
                if senses_count > 1:
                    user_selection = 0
                    while user_selection not in range(1, senses_count + 1):
                        for k in range(senses_count):
                            print(f"{k + 1}. {senses_list[k]}")
                        user_selection = input(
                            f"Multiple senses were found for {user_input}. "
                            "Please choose the number of the correct sense "
                            "(i.e., 1): ")

                        try:
                            user_selection = int(user_selection)
                        except ValueError:
                            continue
                    
                    expression = parsed_slug
                    meaning = senses_list[user_selection - 1]
                    match_found = True
                elif senses_count == 1:
                    expression = parsed_slug
                    meaning = senses_list[0]
                    match_found = True

    # Exit if no matches found.
    if not match_found:
        print(f"No match found for {user_input}.")
        return None

    # Finally, create the card.
    jido_card = Card(
        user_input,
        expression,
        meaning,
        reading
    )

    # NOTE: REMOVE DEBUG
    print(f"JIDO_CARD READING: {jido_card.expr_reading}")

    return jido_card


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
        # print(accent_data)
        for i in range(len(accent_data)):
            if accent_data[i][0] == reading:
                pitch_number = int(accent_data[i][1].split(",")[0])
                reading_found = True
            # Kana only words
            elif accent_data[i][0] == "":
                pitch_number = int(accent_data[i][1].split(",")[0])
                reading_found = True
            
            # NOTE: REMOVE DEBUG
            print(f"Reading found for {expr}: {accent_data[i][0]}.")
            print(f"Pitch accent for {expr}: {pitch_number}.")

    if not reading_found:
        valid_input = False
        while not valid_input:
            try:
                pitch_number = int(input(
                    "No pitch accent data found. Please enter the downstep "
                    f"position for {expr}: "))
                if 0 <= pitch_number <= mora_length:
                    valid_input = True
            except ValueError:
                pass

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
    
    print(f"Pitch Accent Type: {jido_card.pitch_accent_type}.")
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

    # print(svg_full_string)
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

        try:
            sentence_data = json.loads(message.content[0].text)
            print(f"Japanese: {sentence_data["japanese"]}")
            print(f"English: {sentence_data["english"]}")

            jido_card.sentence_japanese = sentence_data["japanese"]
            jido_card.sentence_english = sentence_data["english"]

            # Clean Japanese sentence for Azure TTS.
            jido_card.sentence_japanese_clean = re.sub(
                r"<.*?>", "", sentence_data["japanese"])
            print(f"Clean Japanese string: {jido_card.sentence_japanese_clean}")
            
            # Check for color formatting.
            if ("<span" in jido_card.sentence_japanese
                    and "<span" in jido_card.sentence_english):
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


def import_csv(jido_session):
    # Add message about how this process may take a while and requires
    # human input.
    print(
        "Please note that this process is not entirely automatic.\nIt may "
        "take some time to complete depending on the number of words in the "
        "file and will likely require your input.")

    # Prompt the user to place the file in the correct directory and identify
    # it.
    input_file_name = ""
    while input_file_name == "":
        input_file_name = input(
            "Please place your .csv or .txt file in the ./input/ directory, "
            "and provide the name here, including the extension. To cancel, "
            "type 'cancel': ")
    
    if input_file_name == "cancel":
        return

    delimiter = ""
    while delimiter == "":
        delimiter = input(
            "Please enter the character used to delimit each word in the "
            "file. Use \\n for new line and \\t for tab:")
    
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
            print(word_list)
    except FileNotFoundError:
        print(
            f"File {input_file_name} not found. Please ensure it is placed in "
             "the ./input/ directory.")
        return

    for word in word_list:
        if len(word.strip()) > 0:
            process_word(word, jido_session)

    
def process_word(user_input, jido_session):
    # Retrieve Jisho data.
    jido_card = fetch_word(user_input)
    if jido_card is None:
        return

    # Retrieve pitch accent data.
    fetch_pitch_accent(jido_session, jido_card)

    # Retrieve sentence data.
    fetch_sentences(jido_session, jido_card)

    # Retrieve audio data.
    fetch_audio(jido_session, jido_card)

    # Create note.
    create_note(jido_session, jido_card)



def create_note(jido_session, jido_card):
    anki_note = genanki.Note(
        model=jido_session.anki_model,
        fields=[
            jido_card.user_input,
            jido_card.expr_meaning,
            jido_card.expr_reading,
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


def export_deck(output_name, jido_session):

    print(jido_session.media_files)
    for item in jido_session.media_files:
        print(os.path.exists(item))

    jido_package = genanki.Package(jido_session.anki_deck)
    jido_package.media_files = jido_session.media_files
    jido_package.write_to_file("./output/packages/" + output_name + ".apkg")


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
                
                if reading in jido_session.accents_by_reading:
                    jido_session.accents_by_reading[reading].append(
                        [expression, pitch_number.rstrip()])
                else:
                    jido_session.accents_by_reading[reading] = [
                        [expression, pitch_number.rstrip()]]
    except FileNotFoundError:
        print("accents.txt not found.")
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

        process_word(user_input, jido_session)


if __name__ == "__main__":
    main()