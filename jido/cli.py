from dotenv import load_dotenv
import json
from pathlib import Path
import requests

from .audio import fetch_audio
from .card import Card, create_note
from .export import export_deck
from .jisho import fetch_furigana_data, fetch_word, JishoAPIError
from .pitch import fetch_pitch_accent
from .sentences import fetch_sentences
from .session import JidoSession


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

    # print()
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
    jido_card, status = resolve_word(user_input, jido_session)

    # If no card was created, exit.
    if status == "failed":
        return
    # If data loaded from database.
    elif status == "fetched from database":
        # Create note.
        create_note(jido_session, jido_card)
    
        # Add card to cards log.
        jido_session.cards_log.append(jido_card)
    # If data not loaded from database, enter the pipeline.
    else:
        jido_session.pending_futures.append(
            jido_session.executor.submit(
                generate_card, jido_session, jido_card))


def resolve_word(user_input, jido_session):
    print(f"\n=== {user_input} ===")
    # Retrieve Jisho data.
    try:
        jido_card = fetch_word(user_input)
    except JishoAPIError:
        print(f"Unable to retrieve data for {user_input}. Please try again.")

        failed_card = Card(user_input, "", "", "", "")
        failed_card.status_jisho = ("failed", "Jisho API error")
        jido_session.card_failed.append(failed_card)
        jido_session.cards_log.append(failed_card)
        return (failed_card, "failed")

    # If no result, check if the word was entered as a する verb or な adj.
    if jido_card is None:
        # な adjective
        if user_input[-1] == "な":
            adjusted_user_input = user_input[:-1]
            jido_card = fetch_word(adjusted_user_input)
        # する verb
        elif user_input[-2:] == "する":
            adjusted_user_input = user_input[:-2]
            jido_card = fetch_word(adjusted_user_input)
        # No match.
        else:
            print(f"No match found for {user_input}.")

            failed_card = Card(user_input, "", "", "", "")
            failed_card.status_jisho = ("failed", "no match found")
            jido_session.cards_failed.append(failed_card)
            jido_session.cards_log.append(failed_card)
            return (failed_card, "failed")

    # Check if the card already exists in the database.
    fetched_from_database = False
    try:
        card = {
            "user_input": jido_card.user_input,
            "reading": jido_card.expr_reading,
            "meaning": jido_card.expr_meaning,
            "user_level": (
                jido_session.study_category 
                + " " + str(jido_session.study_level))}

        response = requests.get(
            jido_session.database_url + "/data", params=card)
        data = response.json()

        # If it does exist, pull data from database.
        if data is not None:
            print("Data found in the database. Loading...")
            jido_card.expr_reading_furigana = data["reading_furigana"]
            jido_card.status_furigana = ("success", "")
            jido_card.pitch_accent_type = str(data["pitch_type"])
            jido_card.pitch_accent = data["pitch_svg"]
            jido_card.status_pitch_accent = ("success", "")
            jido_card.sentence_japanese = data["sentence_jp"]
            jido_card.sentence_english = data["sentence_en"]
            jido_card.status_sentence = ("success", "")
            jido_card.audio = "[sound:" + data["audio_expr"] + "]"
            jido_session.media_files.append(
                "./output/audio/" + data["audio_expr"])
            jido_card.status_audio_expr = ("success", "")
            jido_card.audio_sentence = "[sound:" + data["audio_sentence"] + "]"
            jido_card.status_audio_sentence = ("success", "")
            jido_session.media_files.append(
                "./output/audio/" + data["audio_sentence"])
            fetched_from_database = True
            print("Successfully loaded data from the database.")

            return (jido_card, "fetched from database")
    except requests.exceptions.ConnectionError:
        print("Database offline. Querying...")
    except Exception as e:
        print(f"Database error: {e}.")
        print("Data not found in the database, querying...")

    # If data not loaded from database, enter the pipeline.
    if not fetched_from_database:
        # Retrieve pitch accent data.
        fetch_pitch_accent(jido_session, jido_card)

    return (jido_card, "not fetched from database")


def generate_card(jido_session, jido_card):
    # Fetch furigana data.
    fetch_furigana_data(jido_session, jido_card)

    # Retrieve sentence data.
    fetch_sentences(jido_session, jido_card)

    # Retrieve audio data.
    fetch_audio(jido_session, jido_card)

    # Add card to database.
    if (
            jido_card.status_jisho[0] == "success"
            and jido_card.status_sentence[0] == "success"
            and jido_card.status_audio_expr[0] == "success"
            and jido_card.status_audio_sentence[0] == "success"):

        try:
            card = {
                "user_input": jido_card.user_input,
                "expr": jido_card.expr,
                "reading": jido_card.expr_reading,
                "reading_furigana": jido_card.expr_reading_furigana,
                "pitch_type": int(jido_card.pitch_accent_type),
                "pitch_svg": jido_card.pitch_accent,
                "audio_expr": jido_card.audio[7:-1],
                "meaning": jido_card.expr_meaning,
                "notes": jido_card.notes,
                "sentence_jp": jido_card.sentence_japanese,
                "sentence_en": jido_card.sentence_english,
                "audio_sentence": jido_card.audio_sentence[7:-1],
                "user_level": (
                    jido_session.study_category + " "
                    + jido_session.study_level)
            }

            response = requests.post(
                jido_session.database_url + "/data", json=card)

            # if response.status_code == 200:
            #     print("Card successfully added to database.")
            # elif response.status_code == 422:
            #     print("Database validation error. Card not uploaded.")
            # else:
            #     print(
            #         f"Database error {response.status_code}. "
            #         "Card not uploaded.")
        except requests.exceptions.ConnectionError:
            pass
            # print("Database offline. Card not uploaded.")
        except Exception as e:
            pass
            # print(f"Database error. Card not uploaded. {e}.")
            
    
    # Create note.
    create_note(jido_session, jido_card)

    # Add card to cards log.
    jido_session.cards_log.append(jido_card)


def main():
    deck_name = ""
    output_name = ""
    valid_output_name = False
    valid_study_level = False

    while deck_name == "":
        deck_name = input("Enter your deck name: ")

    while not valid_output_name:
        output_name = input("Enter your output name (excluding .apkg): ")
        output_name = output_name.lower().strip(" .").replace(" ", "-")
        output_name = "".join(c for c in output_name if c not in '<>:"/\\|?*')

        if len(output_name) > 0:
            valid_output_name = True
    
    while not valid_study_level:
        study_category = input(
            "For sentence generation purposes, please enter your study system "
            "(JLPT, Genki, Quartet): ")
        if study_category.lower() not in ["jlpt", "genki", "quartet"]:
            continue

        if study_category.lower() == "jlpt":
            study_category = "JLPT"
            study_level = input(
                "Please enter your level (N5, N4, N3, N2, N1): ")
            if study_level.lower() not in ["n5", "n4", "n3", "n2", "n1"]:
                continue
            else:
                study_level = study_level.upper()
                valid_study_level = True
        elif study_category.lower() == "genki":
            study_category = "Genki"
            study_level = input(
                "Please enter your chapter (1-23): ")
            try:
                study_level_int = int(study_level)
            except ValueError:
                continue

            if study_level_int < 1 or study_level_int > 23:
                continue
            else:
                valid_study_level = True
        elif study_category.lower() == "quartet":
            study_category = "Genki"
            study_level = input(
                "Please enter your chapter (1-12): ")
            try:
                study_level_int = int(study_level)
            except ValueError:
                continue

            if study_level_int < 1 or study_level_int > 12:
                continue
            else:
                valid_study_level = True
    
    jido_session = JidoSession(deck_name, study_category, study_level)
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
            print("Exiting...")
            jido_session.executor.shutdown(wait=True)
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