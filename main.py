from jisho_api.word import Word

expr = ""
expr_meaning = ""
expr_reading = ""

user_input = ""

while user_input != "exit":
    user_input = input("Enter a word: ")

    if user_input == "exit":
        break
    
    # Retrieve data from Jisho API.
    data = Word.request(user_input).data
    print(data)

    if len(data) == 0:
        print(f"No match found for {user_input}.")
        continue
    
    # Search for at least a single matching slug.
    match_found = False
    slug_count = 0
    readings = []
    for i in range(len(data)):
        parsed_slug = "".join(c for c in data[i].slug if c not in "-0123456789")

        # Keep track of the number of matches and skip mismatches.
        if parsed_slug == user_input:
            slug_count += 1
            match_found = True
        else: continue

        # Handle any number of readings.
        # NOTE: Will have to later come back and handle kana-only words, 
        # where the word=None as it has no kanji.
        slug_readings = []
        for j in range(len(data[i].japanese)):
            if data[i].japanese[j].word == user_input:
                slug_readings.append(data[i].japanese[j].reading)
        readings.append("\uff0f".join(slug_readings))

    # Exit if no matches found.
    if match_found == False:
        print(f"No match found for {user_input}.")
        continue

    # If there are multiple readings, prompt the user to choose one.
    selected_slug = 0
    if slug_count > 1:
        for i in range(slug_count):
            print(f"{i + 1}. {user_input}\uff08{readings[i]}\uff09")
        
        user_selection = 0
        while user_selection not in range(1, slug_count + 1):
            user_selection = input(f"Muliple readings were found for {user_input}. Please choose the correct reading: ")
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
            print(f"{i + 1}. {"; ".join(data[selected_slug].senses[i].english_definitions)}")
        
        user_selection = 0
        while user_selection not in range(1, senses_count + 1):
            user_selection = input(f"Multiple senses were found for {user_input}. Please choose the correct sense: ")
            try:
                user_selection = int(user_selection)
            except ValueError:
                continue
        
        selected_sense = user_selection - 1

    # Finally, apply the slug, sense, and reading.
    # NOTE: Probably need to handle this during the previous checks instead of waiting until the end.
    expr = data[selected_slug].slug
    expr_meaning = "; ".join(data[selected_slug].senses[selected_sense].english_definitions)
    expr_reading = readings[selected_slug]

    print(f"Expression: {expr}")
    print(f"Reading: {expr_reading}")
    print(f"Meaning: {expr_meaning}")