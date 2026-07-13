import json
import re

def fetch_sentences(jido_session, jido_card):
    for i in range(2):
        content_message = (
            f"Expression: {jido_card.user_input}; Meaning: "
            f"{jido_card.expr_meaning}; Pitch Formatting Number: "
            f"{jido_card.pitch_accent_type}")
        message = jido_session.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            system=[
                {
                    "type": "text",
                    "text": jido_session.client_system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": content_message
                }
            ]
        )

        try:
            clean_message_content = re.sub(
                "(```json|```|)", "", message.content[0].text).strip()
            sentence_data = json.loads(clean_message_content)

            jido_card.sentence_japanese = sentence_data["japanese"]
            jido_card.sentence_english = sentence_data["english"]

            # Clean Japanese sentence for Azure TTS.
            jido_card.sentence_japanese_clean = re.sub(
                r"<.*?>", "", sentence_data["japanese"])
            
            # Check for color formatting.
            if ("<span" in jido_card.sentence_japanese
                    and "<span" in jido_card.sentence_english):
                jido_card.status_sentence = ("success", "")
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
                    jido_card.status_sentence = ("failed", "formatting")
                    jido_session.cards_partial_failure.append(jido_card)
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
                jido_card.status_sentence = ("failed", "failed to generate")
                jido_session.cards_partial_failure.append(jido_card)