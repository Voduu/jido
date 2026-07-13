import genanki

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