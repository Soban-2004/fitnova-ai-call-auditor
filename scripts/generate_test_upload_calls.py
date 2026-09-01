"""
Generates 2 short, throwaway audio files for manually testing the deployed
Upload page (upload -> B2 backup -> live progress -> playback after restart)
— separate from backend/sample_calls/ (the committed demo dataset), so this
never touches or risks that. Output goes to backend/test_uploads/, which is
gitignored — not meant to be committed, just picked in a browser file dialog.

Run from fitnova/backend/: python ../scripts/generate_test_upload_calls.py
"""
import asyncio
import io
import sys
from pathlib import Path

import edge_tts
from pydub import AudioSegment

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

OUT_DIR = BACKEND_DIR / "test_uploads"
TURN_GAP_MS = 450

VOICE_F_EN = "en-IN-NeerjaNeural"
VOICE_M_EN = "en-IN-PrabhatNeural"

# advisor_id values are the real seeded advisors (scripts/seed_db.py) — pick
# whichever name you want in the Upload page's advisor dropdown.
CALLS = [
    {
        "file": "test_upload_01_good.wav",
        "advisor_name": "Priya Sharma",
        "advisor_id": "c0000000-0000-0000-0000-000000000001",
        "advisor_voice": VOICE_F_EN,
        "customer_voice": VOICE_M_EN,
        "turns": [
            ("advisor", "Hi, this is Priya from FitNova. Am I speaking with Karan?"),
            ("customer", "Yes, speaking."),
            ("advisor", "Great! What are you currently looking to work on — weight loss, strength, or general fitness?"),
            ("customer", "Mostly general fitness, I sit at a desk all day and want to get more active."),
            ("advisor", "Makes sense. Any injuries or health conditions I should know about before we go further?"),
            ("customer", "No, nothing like that, I'm generally healthy."),
            ("advisor", "Good to know. Our Standard plan is four thousand five hundred a month, three sessions a week plus a diet plan. Want me to book a free trial first so your coach can assess you?"),
            ("customer", "Yes, that sounds good."),
            ("advisor", "I have a slot Saturday at 5 PM online — does that work?"),
            ("customer", "Saturday works for me, thank you."),
            ("advisor", "Perfect, you're all booked. Have a great day!"),
        ],
    },
    {
        "file": "test_upload_02_pressure.wav",
        "advisor_name": "Rahul Mehta",
        "advisor_id": "c0000000-0000-0000-0000-000000000002",
        "advisor_voice": VOICE_M_EN,
        "customer_voice": VOICE_F_EN,
        "turns": [
            ("advisor", "Hi, this is Rahul from FitNova calling about your fitness enquiry."),
            ("customer", "Oh, hi."),
            ("advisor", "Look, I'll be direct — we have an offer that expires tonight at midnight, so I don't want you to miss it."),
            ("customer", "What's the offer?"),
            ("advisor", "Normally six thousand a month, but if you lock in right now I can get you three thousand five hundred. This price is gone the moment I hang up."),
            ("customer", "I was hoping to think it over for a day."),
            ("advisor", "Honestly there's only one slot left this month, and thinking about it means losing it. Should I just book you in right now?"),
            ("customer", "Okay, I guess, if it's really ending today."),
            ("advisor", "Great, you're locked in. I'll send the details shortly."),
        ],
    },
]


async def synth_turn(text: str, voice: str) -> AudioSegment:
    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return AudioSegment.from_file(buf, format="mp3")


async def build_call(call: dict) -> tuple[AudioSegment, float]:
    silence = AudioSegment.silent(duration=TURN_GAP_MS)
    combined = AudioSegment.silent(duration=0)
    for speaker, text in call["turns"]:
        voice = call["advisor_voice"] if speaker == "advisor" else call["customer_voice"]
        seg = await synth_turn(text, voice)
        combined += seg + silence
    return combined, len(combined) / 1000.0


async def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Writing to {OUT_DIR}\n")
    for call in CALLS:
        print(f"Generating {call['file']} (advisor: {call['advisor_name']})...")
        audio, duration = await build_call(call)
        out_path = OUT_DIR / call["file"]
        audio.export(out_path, format="wav")
        print(f"  wrote {out_path}: {duration:.1f}s\n")
    print("Done. Pick any of these in the deployed Upload page's file dialog —")
    print(f"they're at: {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
