import hashlib
import os

import azure.cognitiveservices.speech as speechsdk


def hash_data(source):
    h = hashlib.sha1()
    h.update(source.encode())
    return h.hexdigest()

def fetch_audio(jido_session, jido_card):
    for i in range(2):
        try:
            synthesizer = jido_session.speech_synthesizer
            audio_result = synthesizer.speak_text_async(jido_card.expr)

            expression_audio = audio_result.get()
            if (
                    expression_audio.reason != 
                    speechsdk.ResultReason.SynthesizingAudioCompleted):
                raise Exception
            expression_stream = speechsdk.AudioDataStream(expression_audio)
            hash_result = hash_data(
                f"{jido_card.user_input}_{jido_card.expr_reading}")
            expression_audio_file_name = "jido-" + hash_result + ".mp3"
            expression_audio_path = (
                "./output/audio/" + expression_audio_file_name)
            expression_stream.save_to_wav_file(expression_audio_path)
            jido_card.audio = "[sound:" + expression_audio_file_name + "]"
            jido_session.media_files.append(expression_audio_path)

            if os.path.exists(expression_audio_path):
                jido_card.status_audio_expr = ("success", "")
            else:
                raise Exception
            break
        except Exception:
            if i == 0:
                pass
                # print(
                #     f"Error obtaining expression audio for {jido_card.expr}. "
                #     "Retrying once...")
            else:
                # print(
                #     f"Failed to obtain expression audio for {jido_card.expr}. "
                #     "Continuing without audio.")
                jido_card.audio = ""
                jido_card.status_audio_expr = ("failed", "failed to generate")

                if jido_card not in jido_session.cards_partial_failure:
                    jido_session.cards_partial_failure.append(jido_card)

    for i in range(2):
        try:
            synthesizer = jido_session.speech_synthesizer
            audio_result = synthesizer.speak_text_async(
                jido_card.sentence_japanese_clean)

            sentence_audio = audio_result.get()
            if (
                    sentence_audio.reason !=
                    speechsdk.ResultReason.SynthesizingAudioCompleted):
                raise Exception
            sentence_stream = speechsdk.AudioDataStream(sentence_audio)
            hash_result = hash_data(jido_card.sentence_japanese_clean)
            sentence_audio_file_name = "jido-" + hash_result + ".mp3"
            sentence_audio_path = (
                "./output/audio/" + sentence_audio_file_name)
            sentence_stream.save_to_wav_file(sentence_audio_path)
            jido_card.audio_sentence = (
                "[sound:" + sentence_audio_file_name + "]")
            jido_session.media_files.append(sentence_audio_path)

            if os.path.exists(sentence_audio_path):
                jido_card.status_audio_sentence = ("success", "")
            else:
                raise Exception
            break
        except Exception:
            if i == 0:
                pass
                # print(
                #     f"Error obtaining sentence audio for {jido_card.expr}. "
                #     "Retrying once...")
            else:
                # print(
                #     f"Failed to obtain sentence audio for {jido_card.expr}. "
                #     "Continuing without audio.")
                jido_card.audio_sentence = ""
                jido_card.status_audio_sentence = (
                    "failed", "failed to generate")

                if jido_card not in jido_session.cards_partial_failure:
                    jido_session.cards_partial_failure.append(jido_card)