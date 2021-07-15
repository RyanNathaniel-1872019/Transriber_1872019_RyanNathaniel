import PySimpleGUI as sg

import io
import os

from pydub import AudioSegment
from google.cloud import speech_v1p1beta1 as speech
from google.cloud.speech_v1p1beta1 import types
from google.cloud import storage
import wave
import codecs
import winsound
import subprocess

#menu bar
menu_def = [['File', ['Open Text File', 'Open Sound File', 'Exit']],      
            ['About', ['About']],      
            ['Help', ['Help']]]


#whole design
sg.theme('darkamber')
layout = [      
    [sg.Text("Choose a file : "), sg.Input(sg.user_settings_get_entry('-filename-', '')), sg.FileBrowse(file_types=(("Video Files", "*.mp4"),))],
    [sg.Text("Language      : "), sg.Combo(values = ['English', 'Indonesia', 'Chinese'], default_value='English')],
    [sg.Text("Speaker-D     : "), sg.Checkbox('Enable', default=False)],
    [sg.Text("Save as       : "), sg.Input(sg.user_settings_get_entry('-filename-', ''), enable_events=True), sg.FileSaveAs(initial_folder='/tmp')],
    [sg.Button('Ok'), sg.Button('Exit')],
    [sg.Menu(menu_def)]
]

window = sg.Window('Transcriber', layout)

while True:
    event, values = window.read()
    if event == 'Ok':
        if(values[0] == '' or values[3] == ''):
            sg.popup("Please fill all the fields", title="Error")
        else:
            #Converting Video -> Audio
            video_input = str(values[0])[2:]
            audio_output = values[3]
            command = 'ffmpeg -i ' + video_input + ' -ab 160k -ar 8000 -vn ' + audio_output + '.wav'
            subprocess.call(command, shell=True)

            #variable
            audio_filename = os.path.basename(audio_output + '.wav')
            audio_filepath = os.path.dirname(audio_output) + '/'
            text_output = os.path.dirname(audio_output) + '/'
            bucketname = 'getaudiofiles'

            #changing stereo to mono
            def stereoToMono(audio):
                sound = AudioSegment.from_wav(audio)
                sound = sound.set_channels(1)
                sound.export(audio, format="wav")

            #frame rate
            def frChannel(audio):
                with wave.open(audio, "rb") as wave_file:
                    frame_rate = wave_file.getframerate()
                    channels = wave_file.getnchannels()
                    return frame_rate,channels

            #upload file GCS
            def uploadGCS(bucket, source_audio, destination_audio):
                storage_client = storage.Client()
                bucket = storage_client.get_bucket(bucket)
                blob = bucket.blob(destination_audio)

                blob.upload_from_filename(source_audio)

            #delete file GCS
            def deleteGCS(bucket, blob_name):
                storage_client = storage.Client()
                bucket = storage_client.get_bucket(bucket)
                blob = bucket.blob(blob_name)

                blob.delete()

            # transcribe
            def transcribe(audio, lang, diar):
                audio_file = audio_filepath + audio_filename
                
                frame_rate, channels = frChannel(audio_file)
                
                if(channels > 1):
                    stereoToMono(audio_file)
                
                bucket = bucketname
                source_audio = audio_filepath + audio_filename
                destination_audio = audio_filename
                
                uploadGCS(bucket, source_audio, destination_audio)
                
                gcs_uri = 'gs://' + bucketname + '/' + audio_filename
                transcript = ''
                
                client = speech.SpeechClient()
                audio = types.RecognitionAudio(uri=gcs_uri)

                config = types.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=frame_rate,
                    language_code=lang,
                    enable_speaker_diarization=diar,
                    diarization_speaker_count=2
                )

                # Detects speech in the audio file
                operation = client.long_running_recognize(request={"config": config, "audio": audio})
                response = operation.result(timeout=10000)

                if(diar == True):
                    result = response.results[-1]
                    words_info = result.alternatives[0].words
                    
                    speaker_label=1
                    speaker_word=""

                    for word_info in words_info:
                        if word_info.speaker_tag==speaker_label:
                            speaker_word=speaker_word+" "+word_info.word
                        else:
                            transcript += "speaker {}: {}".format(speaker_label,speaker_word) + '\n'
                            speaker_label=word_info.speaker_tag
                            speaker_word=""+word_info.word
                
                    transcript += "speaker {}: {}".format(speaker_label,speaker_word)
                
                else:
                    for result in response.results:
                        transcript += result.alternatives[0].transcript
                
                deleteGCS(bucket, destination_audio)
                return transcript
                
            #write the transcript
            def write_transcripts(transcript_filename,transcript):
                with codecs.open(text_output + transcript_filename,"w+", encoding='utf-8') as f:
                    f.write(transcript)
                    f.close()

            if __name__ == "__main__":
                if(str(values[1]) == "English"):
                    lang = 'en-US'
                if(str(values[1]) == "Indonesia"):
                    lang = 'id-ID'
                if(str(values[1]) == "Chinese"):
                    lang = 'zh'
                if(str(values[2]) == "True"):
                    diar = True
                if(str(values[2]) == "False"):
                    diar = False
                for audio_file_name in os.listdir(audio_filepath):
                    if(audio_file_name == audio_filename):
                        transcript = transcribe(audio_file_name, lang, diar)
                        transcript_filename = audio_file_name.split('.')[0] + '.txt'
                        write_transcripts(transcript_filename,transcript)

    elif event == 'Open Text File':
        filename = sg.popup_get_file('file to open', no_window=True, file_types = (('Text Files', '*txt'),))
        if(filename == ""):
            sg.popup("No transcription")
        else:
            text = ""
            with open(filename, encoding='utf8') as f:
                for line in f:
                    text += line
            sg.popup_scrolled(text, title="Transcript")

    elif event == 'Open Sound File':
        sound = sg.popup_get_file('file to open', no_window=True, file_types = (('Sound Files', '*wav'),))
        if(sound == ""):
            sg.popup("No sound")
        else:
            sg.popup(winsound.PlaySound(sound, winsound.SND_ASYNC), title="Sound")
            if(sg.POPUP_BUTTONS_OK or sg.POPUP_BUTTONS_CANCELLED):
                winsound.PlaySound(None, winsound.SND_PURGE)
    
    elif event == 'About':
        sg.popup("Transcriber is an application to extract texts from videos" +
        "\nAuthor : Ryan Nathaniel - 1872019", title="About")
    
    elif event == 'Help':
        sg.popup("HELP " +
        "To use transcriber, you need to :" + 
        "\n1. Select the video file" +
        "\n2. Choose the languange" +
        "\n3. Enable or disable the speaker diarization feature" +
        "\n4. Choose the location to save your output" +
        "\n5. Start transcribe by clicking the OK button" +
        "\nThank you", title="Help")

    elif event == sg.WIN_CLOSED or event == 'Exit':
        break

window.close()
