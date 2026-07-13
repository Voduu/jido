import requests

from jisho_api.word import Word

from jido import Card


class JishoAPIError(Exception):
    pass


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