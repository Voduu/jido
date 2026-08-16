CREATE TABLE expressions (
    "expr_id" INTEGER UNIQUE NOT NULL,
    "user_input" TEXT NOT NULL,
    "expr" TEXT NOT NULL,
    "reading" TEXT NOT NULL,
    "reading_furigana" TEXT NOT NULL,
    "pitch_type" INTEGER NOT NULL,
    "pitch_svg" TEXT NOT NULL,
    "pitch_manual" BOOLEAN DEFAULT 0,
    "audio_expr" TEXT NOT NULL,
    UNIQUE(user_input, reading),
    PRIMARY KEY("expr_id")
);

CREATE TABLE meanings (
    "meaning_id" INTEGER UNIQUE NOT NULL,
    "expr_id" INTEGER NOT NULL,
    "meaning" TEXT NOT NULL,
    "notes" TEXT,
    UNIQUE(expr_id, meaning),
    PRIMARY KEY("meaning_id"),
    FOREIGN KEY("expr_id") REFERENCES "expressions"("expr_id") ON DELETE CASCADE
);

CREATE TABLE sentences (
    "sentence_id" INTEGER UNIQUE NOT NULL,
    "meaning_id" INTEGER NOT NULL,
    "user_level" TEXT NOT NULL,
    "sentence_jp" TEXT NOT NULL,
    "sentence_en" TEXT NOT NULL,
    "audio_sentence" TEXT NOT NULL,
    "created_date" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(meaning_id, user_level),
    PRIMARY KEY("sentence_id"),
    FOREIGN KEY("meaning_id") REFERENCES "meanings"("meaning_id") ON DELETE CASCADE
);