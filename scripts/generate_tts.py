#!/usr/bin/env python3
"""
CrossAIHub — optional cloud TTS.
Reads a narration script (plain text) and writes narration.mp3 using OpenAI TTS.
Only runs when the workflow is dispatched with generate_tts=true.

Usage: python3 generate_tts.py <script.txt> <out.mp3>
Env:   OPENAI_API_KEY  (from GitHub secret)
       OPENAI_TTS_MODEL (default: gpt-4o-mini-tts)
       OPENAI_TTS_VOICE (default: alloy)
"""
import os
import sys

def main():
    if len(sys.argv) != 3:
        sys.exit("usage: generate_tts.py <script.txt> <out.mp3>")
    script_path, out_path = sys.argv[1], sys.argv[2]
    if not os.path.isfile(script_path):
        sys.exit(f"narration script not found: {script_path}")

    with open(script_path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    if not text:
        sys.exit("narration script is empty.")

    model = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    voice = os.environ.get("OPENAI_TTS_VOICE", "alloy")

    from openai import OpenAI
    client = OpenAI()  # reads OPENAI_API_KEY from env

    # Streaming write to file (keeps memory low on the runner).
    with client.audio.speech.with_streaming_response.create(
        model=model, voice=voice, input=text, response_format="mp3",
    ) as resp:
        resp.stream_to_file(out_path)

    print(f"TTS written: {out_path} ({os.path.getsize(out_path)} bytes)")

if __name__ == "__main__":
    main()
