from jisho_api.word import Word
import random
import genanki


class JidoSession:
    def __init__(self, deck_name):
        self.accents_by_expression = {}
        self.accents_by_reading = {}
        model_id = random.randrange(1 << 30, 1 << 31)
        deck_id = random.randrange(1 << 30, 1 << 31)

        self.anki_model = genanki.Model(
            model_id,
            "Jido Model",
            fields=[
                {"name": "Expression"},
                {"name": "Meaning"},
                {"name": "Reading"},
            ],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": "{{Expression}}",
                    "afmt": "{{Expression}}<hr>{{Reading}}<hr>{{Meaning}}"
                }
            ]
        )

        self.anki_deck = genanki.Deck(
            deck_id,
            deck_name
        )

    def add_note(self, anki_note):
        self.anki_deck.add_note(anki_note)
    

class Card:
    def __init__(self, expr, expr_meaning, expr_reading):
        self.expr = expr
        self.expr_meaning = expr_meaning
        self.expr_reading = expr_reading
        self.pitch_accent = ""
        self.pitch_accent_type = 0
        self.sentence_japanese = ""
        self.sentence_english = ""


def fetch_word(user_input):
    # Retrieve data from Jisho API.
    try:
        data = Word.request(user_input).data
    except AttributeError:
        return None
    # print(data)

    if len(data) == 0:
        print(f"No match found for {user_input}.")
        return None
    
    # Search for at least one single matching slug.
    match_found = False
    slug_count = 0
    readings = []
    for i in range(len(data)):
        parsed_slug = "".join(
            c for c in data[i].slug if c not in "-0123456789")

        # Keep track of the number of matches and skip mismatches.
        if parsed_slug == user_input:
            slug_count += 1
            match_found = True
        else:
            continue
        
        # Handle any number of readings.
        # NOTE: Will have to later come back and handle kana-only words,
        # where the word=None as it has no kanji.
        slug_readings = []
        for j in range(len(data[i].japanese)):
            if data[i].japanese[j].word == user_input:
                slug_readings.append(data[i].japanese[j].reading)
        readings.append("\uff0f".join(slug_readings))

    # Exit if no matches found.
    if not match_found:
        print(f"No match found for {user_input}.")
        return None
    
    # If there are multiple readings, prompt the user to choose one.
    selected_slug = 0
    if slug_count > 1:
        for i in range(slug_count):
            print(f"{i + 1}. {user_input}\uff08{readings[i]}\uff09")
        
        user_selection = 0
        while user_selection not in range(1, slug_count + 1):
            user_selection = input(
                f"Multiple readings were found for {user_input}. Please " \
                 "choose the number of the correct reading (i.e., 1): ")
            try:
                user_selection = int(user_selection)
            except ValueError:
                continue
        
        selected_slug = user_selection - 1
    
    # If there are multiple senses, prompt the user to choose one.
    senses_count = len(data[selected_slug].senses)
    selected_sense = 0
    if senses_count > 1:
        for i in range(senses_count):
            print(f"{i + 1}. {"; ".join(
                data[selected_slug].senses[i].english_definitions)}")
        
        user_selection = 0
        while user_selection not in range(1, senses_count + 1):
            user_selection = input(
                f"Multiple senses were found for {user_input}. Please " \
                 "choose the number of the correct sense (i.e., 1): ")
            try:
                user_selection = int(user_selection)
            except ValueError:
                continue
        
        selected_sense = user_selection - 1

    # Finally, create the card.
    jido_card = Card(
        "".join(c for c in data[selected_slug].slug if c not in "-0123456789"),
        "; ".join(
            data[selected_slug].senses[selected_sense].english_definitions),
        readings[selected_slug].split("\uff0f")[0]
    )

    return jido_card


def fetch_pitch_accent(jido_session, jido_card):
    expr = jido_card.expr
    reading = jido_card.expr_reading
    reading_found = False
    pitch_data = 0


    # Find the expression in one of the dictionaries.
    if expr in jido_session.accents_by_expression:
        accent_data = jido_session.accents_by_expression[expr]
        print(accent_data)
        for i in range(len(accent_data)):
            if accent_data[i][0] == reading:
                pitch_data = int(accent_data[i][1].split(",")[0])
                reading_found = True
                print(f"Reading found for {expr}: {accent_data[i][0]}.")
                print(f"Pitch accent for {expr}: {pitch_data}.")
    # NOTE: add handling for kana-only edge cases
    # elif reading in jido_session.accents_by_reading:

    if not reading_found:
        pass            


def create_note(jido_session, jido_card):
    anki_note = genanki.Note(
        model=jido_session.anki_model,
        fields=[
            jido_card.expr,
            jido_card.expr_meaning,
            jido_card.expr_reading
        ]
    )

    jido_session.add_note(anki_note)


def export_deck(output_name, jido_session):
    genanki.Package(jido_session.anki_deck).write_to_file("./output/" + output_name + ".apkg")


def main():
    deck_name = ""
    output_name = ""
    valid_output_name = False
    jido_session = JidoSession(deck_name)

    # Create accent data dictionary
    try:
        with open("./data/accents.txt") as accents_file:
            for line in accents_file:
                expression, reading, pitch_number = line.split("\t")
                
                if expression in jido_session.accents_by_expression:
                    jido_session.accents_by_expression[expression].append([reading, pitch_number.rstrip()])
                else:
                    jido_session.accents_by_expression[expression] = [[reading, pitch_number.rstrip()]]
                
                if reading in jido_session.accents_by_reading:
                    jido_session.accents_by_reading[reading].append([expression, pitch_number.rstrip()])
                else:
                    jido_session.accents_by_reading[reading] = [[expression, pitch_number.rstrip()]]
    except FileNotFoundError:
        print("accents.txt not found.")
        return

    while deck_name == "":
        deck_name = input("Enter your deck name: ")

    while not valid_output_name:
        output_name = input("Enter your output name (excluding .apkg): ")
        output_name = output_name.lower().strip(" .").replace(" ", "-")
        output_name = "".join(c for c in output_name if c not in '<>:"/\\|?*')

        if len(output_name) > 0:
            valid_output_name = True

    while True:
        user_input = input(
            "Enter a word ('exit' to exit, 'export' to create .apkg " \
            "package): ")

        if user_input == "exit":
            break

        if user_input == "export":
            export_deck(output_name, jido_session)
            break
        
        # Retrieve Jisho data.
        jido_card = fetch_word(user_input)
        if jido_card is None:
            continue

        # Retrieve pitch accent data.
        fetch_pitch_accent(jido_session, jido_card)

        # Create note.
        create_note(jido_session, jido_card)


if __name__ == "__main__":
    main()