import datetime
from pathlib import Path

import genanki

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