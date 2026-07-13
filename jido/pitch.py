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