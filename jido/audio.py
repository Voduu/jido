import azure.cognitiveservices.speech as speechsdk


def fetch_audio(jido_session, jido_card):
    for i in range(2):
        try:
            synthesizer = jido_session.speech_synthesizer
            audio_result = synthesizer.speak_text_async(jido_card.expr)

            expression_audio = audio_result.get()
            expression_stream = speechsdk.AudioDataStream(expression_audio)
            expression_audio_path = (
                "./output/audio/" + jido_card.expr + "_expr.mp3")
            expression_stream.save_to_wav_file(expression_audio_path)
            jido_card.audio = "[sound:" + jido_card.expr + "_expr.mp3]"
            jido_session.media_files.append(
                "./output/audio/" + jido_card.expr + "_expr.mp3")
            
            jido_card.status_audio_expr = ("success", "")
            break
        except Exception:
            if i == 0:
                print(
                    f"Error obtaining expression audio for {jido_card.expr}. "
                    "Retrying once...")
            else:
                print(
                    f"Failed to obtain expression audio for {jido_card.expr}. "
                    "Continuing without audio.")
                jido_card.audio = ""
                jido_card.status_audio_expr = ("failed", "failed to generate")
                jido_session.cards_partial_failure.append(jido_card)

    for i in range(2):
        try:
            synthesizer = jido_session.speech_synthesizer
            audio_result = synthesizer.speak_text_async(
                jido_card.sentence_japanese_clean)

            sentence_audio = audio_result.get()
            sentence_stream = speechsdk.AudioDataStream(sentence_audio)
            sentence_audio_path = (
                "./output/audio/" + jido_card.expr + "_sentence.mp3")
            sentence_stream.save_to_wav_file(sentence_audio_path)
            jido_card.audio_sentence = (
                "[sound:" + jido_card.expr + "_sentence.mp3]")
            jido_session.media_files.append(
                "./output/audio/" + jido_card.expr + "_sentence.mp3")
            
            jido_card.status_audio_sentence = ("success", "")
            break
        except Exception:
            if i == 0:
                print(
                    f"Error obtaining sentence audio for {jido_card.expr}. "
                    "Retrying once...")
            else:
                print(
                    f"Failed to obtain sentence audio for {jido_card.expr}. "
                    "Continuing without audio.")
                jido_card.audio_sentence = ""
                jido_card.status_audio_sentence = (
                    "failed", "failed to generate")
                jido_session.cards_partial_failure.append(jido_card)