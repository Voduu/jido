import sqlite3

from fastapi import Depends, FastAPI
from pydantic import BaseModel


app = FastAPI()

class CardModel(BaseModel):
    user_input: str
    expr: str
    reading: str
    reading_furigana: str
    pitch_type: int
    pitch_svg: str
    pitch_manual: bool
    audio_expr: str
    meaning: str
    notes: str | None
    sentence_jp: str
    sentence_en: str
    audio_sentence: str
    user_level: str

def get_db():
    connection = sqlite3.connect("./jido.db")
    try:
        yield connection
    finally:
        connection.close()

@app.get("/data")
def get_data(
        user_input: str, reading: str, meaning: str, user_level: str,
        db = Depends(get_db)):
    cursor = None
    try:
        db.row_factory = sqlite3.Row
        cursor = db.cursor()

        cursor.execute("""
            SELECT expressions.expr_id, user_input, expr, reading, reading_furigana,
                pitch_type, pitch_svg, pitch_manual, audio_expr,
                meanings.meaning_id, meaning, notes,
                sentence_id, user_level, sentence_jp, sentence_en,
                audio_sentence, created_date
            FROM expressions
            JOIN meanings ON meanings.expr_id = expressions.expr_id
            JOIN sentences ON sentences.meaning_id = meanings.meaning_id
            WHERE expressions.user_input = ?
                AND expressions.reading = ?
                AND meanings.meaning = ?
                AND sentences.user_level = ?""",
            (user_input, reading, meaning, user_level))

        data = cursor.fetchone()

        if data is None:
            print("Jido database not found.")
            return None

        return(dict(data))
    except sqlite3.Error as error:
        print("Jido database error: ", error)
        return None
    except TypeError as error:
        print("Jido database not found.")
        return None
    finally:
        if cursor:
            cursor.close()

@app.post("/data")
def add_data(card: CardModel, db = Depends(get_db)):
    cursor = None
    try:
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO expressions
                (user_input, expr, reading, reading_furigana, pitch_type,
                 pitch_svg, audio_expr)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (card.user_input, card.expr, card.reading, card.reading_furigana,
             card.pitch_type, card.pitch_svg, card.audio_expr))
        db.commit()

        expr_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO meanings (expr_id, meaning, notes)
            VALUES (?, ?, ?)""",
            (expr_id, card.meaning, card.notes))
        db.commit()

        meaning_id = cursor.lastrowid
        cursor.execute("""
            INSERT INTO sentences
                (meaning_id, user_level, sentence_jp, sentence_en,
                 audio_sentence)
            VALUES (?, ?, ?, ?, ?)""",
            (meaning_id, card.user_level, card.sentence_jp, card.sentence_en,
             card.audio_sentence))
        db.commit()
    except sqlite3.Error as error:
        print("Jido database error: ", error)
    except TypeError as error:
        print("Jido database not found.")
    finally:
        if cursor:
            cursor.close()

@app.patch("/data")
def update_data(card: CardModel, db = Depends(get_db)):
    cursor = None

    try:
        cursor = db.cursor()

        cursor.execute("""
            UPDATE expressions SET
                pitch_type = ?,
                pitch_svg = ?,
                pitch_manual = ?
            WHERE user_input = ?
                AND reading = ?""",
            (card.pitch_type, card.pitch_svg,
             int(card.pitch_manual), card.user_input, card.reading))

        cursor.execute("""
            UPDATE sentences SET
                sentence_jp = ?,
                sentence_en = ?
            WHERE user_level = ?
                AND meaning_id = (
                    SELECT meaning_id FROM meanings
                    WHERE meaning = ?
                        AND expr_id = (
                            SELECT expr_id FROM expressions
                            WHERE user_input = ?
                                AND reading = ?))""",
            (card.sentence_jp, card.sentence_en, card.user_level,
            card.meaning, card.user_input, card.reading))

        db.commit()
    except sqlite3.Error as error:
        print("Jido database error: ", error)
    except TypeError as error:
        print("Jido database not found.")
    finally:
        if cursor:
            cursor.close()