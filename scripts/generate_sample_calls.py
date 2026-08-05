"""
Generate 5-6 synthetic sales calls covering the scenarios in the design doc
(Section 14), using edge-tts for genuinely distinct male/female voices so
Deepgram's diarization has real acoustic separation to work with — gTTS was
tried first and confirmed (via a live Deepgram round-trip) to produce voices
too similar for diarization to distinguish; see backend/app/services/
transcription.py docstring for that finding.

Each call is mapped 1:1 to one of the 6 seeded advisors (see scripts/
seed_db.py) so Phase 5's dashboards get real variety across teams without
extra fixture work. A manifest.json is written alongside the audio so
scripts/process_all_samples.py doesn't need to duplicate this mapping.

Run from fitnova/backend/: python ../scripts/generate_sample_calls.py
"""
import asyncio
import io
import json
import sys
from pathlib import Path

import edge_tts
from pydub import AudioSegment

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

OUT_DIR = BACKEND_DIR / "sample_calls"
TURN_GAP_MS = 450

# Advisor UUIDs from scripts/seed_db.py — kept in sync manually since this
# script has no DB dependency (it only needs to run once, offline).
ADVISOR_IDS = {
    "Priya Sharma": "c0000000-0000-0000-0000-000000000001",
    "Rahul Mehta": "c0000000-0000-0000-0000-000000000002",
    "Ananya Reddy": "c0000000-0000-0000-0000-000000000003",
    "Vikram Patel": "c0000000-0000-0000-0000-000000000004",
    "Sneha Gupta": "c0000000-0000-0000-0000-000000000005",
    "Arjun Nair": "c0000000-0000-0000-0000-000000000006",
}

VOICE_F_EN = "en-IN-NeerjaNeural"
VOICE_M_EN = "en-IN-PrabhatNeural"
VOICE_F_HI = "hi-IN-SwaraNeural"
VOICE_M_HI = "hi-IN-MadhurNeural"

CALLS = [
    {
        "file": "call_01_good.wav",
        "advisor_name": "Priya Sharma",
        "scenario": "Good call — full discovery, proper booking, compliant",
        "expected_tags": [],
        "expected_score_range": [80, 95],
        "advisor_voice": VOICE_F_EN,
        "customer_voice": VOICE_M_EN,
        "turns": [
            ("advisor", "Hi, good afternoon! This is Priya calling from FitNova. Am I speaking with Rohan?"),
            ("customer", "Yes, this is Rohan speaking."),
            ("advisor", "Great to connect with you, Rohan! I saw you filled out our interest form online. Do you have a few minutes to chat about your fitness goals?"),
            ("customer", "Sure, I have about ten minutes."),
            ("advisor", "Perfect. So tell me, what are you currently looking to achieve? Weight loss, strength training, or general fitness?"),
            ("customer", "Mainly weight loss. I've put on some weight over the last year and want to get back in shape."),
            ("advisor", "Got it. And how would you describe your current fitness level? Are you currently doing any exercise?"),
            ("customer", "Not really, I used to go to the gym a couple of years ago but I've been pretty inactive since then."),
            ("advisor", "Understood, that's really common, don't worry. Have you had any past injuries or health conditions I should know about?"),
            ("customer", "I had a minor knee issue a couple of years back, nothing serious now though."),
            ("advisor", "Thanks for sharing that, we'll make sure your trainer keeps that in mind. What does your weekly schedule look like? Mornings, evenings, weekends?"),
            ("customer", "I'm free most evenings after 7 and on weekends."),
            ("advisor", "That works well with our evening batches. And just so I can recommend the right plan, what budget range were you thinking for a monthly program?"),
            ("customer", "Somewhere around three to five thousand rupees a month, I think."),
            ("advisor", "That fits nicely into our Standard Coaching plan, which is four thousand five hundred rupees a month. It includes three personal training sessions a week, a customized diet plan, and weekly check-ins with your coach."),
            ("customer", "That sounds reasonable. Is there anything else I would need to pay for separately?"),
            ("advisor", "Good question. The plan covers all training and coaching. The only additional cost would be gym equipment if you choose in-person sessions at a partner gym, which is optional since we also offer fully online coaching."),
            ("customer", "I think I'd prefer online sessions since my schedule is unpredictable."),
            ("advisor", "That works perfectly. Now, given your knee history, I'd also recommend a free trial session first so your coach can assess your mobility before building your plan."),
            ("customer", "Yeah, that sounds like a good idea. I am a little worried this might be too intense for me though."),
            ("advisor", "That's a completely fair concern. Our coaches start every new member with a low-impact assessment, and we adjust intensity gradually based on how your body responds, especially with your knee history. Nothing is forced."),
            ("customer", "Okay, that's reassuring."),
            ("advisor", "Great! Let's get your free trial booked. I have an online slot this Saturday at 6 PM, or Sunday at 9 AM. Which works better for you?"),
            ("customer", "Saturday at 6 works for me."),
            ("advisor", "Perfect, I've booked your online trial session for Saturday at 6 PM. You'll get a confirmation email with the video call link and a short form about your knee history for the coach to review beforehand. I'll also call you Friday evening just to confirm you're all set."),
            ("customer", "Sounds great, thank you Priya."),
            ("advisor", "My pleasure, Rohan. Looking forward to Saturday. Have a great day!"),
        ],
    },
    {
        "file": "call_02_pressure.wav",
        "advisor_name": "Rahul Mehta",
        "scenario": "Pressure selling — artificial urgency to force a decision",
        "expected_tags": ["PRESSURE_SELLING"],
        "expected_score_range": [50, 65],
        "advisor_voice": VOICE_M_EN,
        "customer_voice": VOICE_F_EN,
        "turns": [
            ("advisor", "Hello, this is Rahul from FitNova, calling about the fitness inquiry you submitted."),
            ("customer", "Oh yes, hi."),
            ("advisor", "Great! So Anjali, are you looking for weight loss or muscle building?"),
            ("customer", "Weight loss mainly."),
            ("advisor", "Okay perfect. Look, I'll be honest with you, we're running a special offer that ends today at midnight, so I want to make sure you don't miss out."),
            ("customer", "Oh, what kind of offer?"),
            ("advisor", "We normally charge six thousand rupees a month, but if you lock in your free trial right now, in the next few minutes, I can get you our premium plan for just three thousand five hundred. This price disappears the second I hang up this call."),
            ("customer", "That's a big discount, but I was hoping to think about it for a day or two."),
            ("advisor", "I completely understand, but honestly this slot is one of only two left for this month's batch, and once they're gone you'll be on the waitlist for at least six weeks. I'd hate for you to lose this over a day of thinking."),
            ("customer", "I mean, I do want to lose weight, but I'm not sure about committing right this second."),
            ("advisor", "Anjali, thousands of people put off their fitness journey by thinking about it and regret it later. This offer really won't be here tomorrow. Should I just lock in your slot right now before it's gone?"),
            ("customer", "Um, okay, I guess if it's really ending today."),
            ("advisor", "Great decision! I've booked you in. You'll get a message with the details soon."),
        ],
    },
    {
        "file": "call_03_no_discovery.wav",
        "advisor_name": "Ananya Reddy",
        "scenario": "No discovery — jumps straight to pricing",
        "expected_tags": ["NO_NEEDS_DISCOVERY", "PRICE_BEFORE_VALUE"],
        "expected_score_range": [40, 60],
        "advisor_voice": VOICE_F_EN,
        "customer_voice": VOICE_M_EN,
        "turns": [
            ("advisor", "Hi, this is Ananya from FitNova, calling regarding your fitness enquiry."),
            ("customer", "Hi."),
            ("advisor", "So, we have some great plans running currently. Our most popular is the Premium Transformation Package at twelve thousand rupees for three months."),
            ("customer", "Oh okay, what does that include exactly?"),
            ("advisor", "It includes personal training sessions and diet guidance. We also have a Basic plan at seven thousand for three months if that suits your budget better."),
            ("customer", "I see. I haven't really thought about what kind of program I need yet, to be honest."),
            ("advisor", "No worries, most people just start with the Basic plan and upgrade later if needed. Should I go ahead and send you the payment link for the Basic plan?"),
            ("customer", "Wait, I don't even know what my fitness goals should be mapped to. Can you help me understand which one suits someone like me?"),
            ("advisor", "Sure, honestly both plans work for most people. The Premium one just has more sessions per week. Would you like me to send the payment link for either one?"),
            ("customer", "I guess... send me the Basic one I suppose."),
            ("advisor", "Great, sending that over now. Thanks for choosing FitNova!"),
        ],
    },
    {
        "file": "call_04_overpromise.wav",
        "advisor_name": "Vikram Patel",
        "scenario": "Over-promising + compliance violation (medical claims)",
        "expected_tags": ["OVER_PROMISING", "COMPLIANCE_VIOLATION"],
        "expected_score_range": [30, 50],
        "advisor_voice": VOICE_M_EN,
        "customer_voice": VOICE_F_EN,
        "turns": [
            ("advisor", "Hi, this is Vikram from FitNova. Am I speaking with Meera?"),
            ("customer", "Yes, hi."),
            ("advisor", "Great! So tell me a little bit, what brings you to look into a fitness program?"),
            ("customer", "I've been struggling with my weight for a while and also have some lower back pain that's been bothering me."),
            ("advisor", "Oh don't worry at all, our program is exactly what you need. I can guarantee you'll lose ten kilos within the first month alone."),
            ("customer", "Really? That seems like a lot."),
            ("advisor", "Absolutely, we've seen it happen with hundreds of our clients, guaranteed results every time. And honestly, our program will completely cure that back pain of yours too, it's designed specifically to fix issues like that."),
            ("customer", "That's amazing to hear, I've tried a lot of things for the back pain without much luck."),
            ("advisor", "Yes, our trainers are basically like physiotherapists, they'll diagnose exactly what's wrong with your spine and fix it through our exercises. You won't need to see a doctor after this."),
            ("customer", "Wow, okay. What does the program cost?"),
            ("advisor", "It's eight thousand rupees a month, and honestly, given a guaranteed ten kilo loss and a permanent fix for your back, that's basically nothing."),
            ("customer", "Okay, I'm interested, what's the next step?"),
            ("advisor", "I'll get you signed up right away. You'll lose the weight and fix your back within weeks, trust me."),
        ],
    },
    {
        "file": "call_05_codeswitching.wav",
        "advisor_name": "Sneha Gupta",
        "scenario": "Hindi-English code-switching — good call in mixed language",
        "expected_tags": [],
        "expected_score_range": [75, 90],
        "advisor_voice": VOICE_F_HI,
        "customer_voice": VOICE_M_HI,
        "language": "hi",
        "turns": [
            ("advisor", "नमस्ते, मैं Sneha बोल रही हूँ FitNova से। क्या मेरी बात Amit जी से हो रही है?"),
            ("customer", "जी हाँ, मैं Amit बोल रहा हूँ।"),
            ("advisor", "बहुत बढ़िया Amit जी! आपने हमारी website पर fitness inquiry डाली थी, इसलिए मैं call कर रही हूँ। आपका मुख्य goal क्या है, weight loss या muscle building?"),
            ("customer", "मुझे actually थोड़ा weight loss करना है, और strength भी बढ़ानी है।"),
            ("advisor", "समझ गयी। अभी आप कोई exercise या workout कर रहे हैं क्या?"),
            ("customer", "नहीं, अभी बिल्कुल भी नहीं कर रहा, but पहले कभी-कभी gym जाता था।"),
            ("advisor", "ठीक है, कोई बात नहीं। क्या आपको पहले कोई injury या health issue रहा है जो हमें पता होना चाहिए?"),
            ("customer", "नहीं, ऐसा कुछ नहीं है, मैं पूरी तरह fit हूँ बस थोड़ा out of shape हूँ।"),
            ("advisor", "बढ़िया। आपका weekly schedule कैसा रहता है, evenings free रहती हैं क्या?"),
            ("customer", "हाँ, evenings मेरे पास free रहती हैं, ज़्यादातर 7 बजे के बाद।"),
            ("advisor", "Perfect, हमारे evening batches उसी समय होते हैं। और budget के हिसाब से, आप monthly कितना खर्च करने को तैयार हैं?"),
            ("customer", "कुछ चार से पाँच हज़ार के बीच सोच रहा था।"),
            ("advisor", "ये हमारे Standard plan में fit हो जाता है, जो साढ़े चार हज़ार रुपये महीना है, इसमें personal training और diet plan दोनों शामिल हैं।"),
            ("customer", "ठीक लगता है, but क्या इसमें कोई hidden cost तो नहीं है?"),
            ("advisor", "बिल्कुल नहीं, ये पूरी तरह transparent है, सिर्फ यही plan cost है, कोई extra charge नहीं। अगर आप चाहें तो पहले एक free trial session ले सकते हैं।"),
            ("customer", "हाँ, वो अच्छा रहेगा, पहले try करना चाहूँगा।"),
            ("advisor", "बिल्कुल! मेरे पास शनिवार शाम 6 बजे का online slot है, वो ठीक रहेगा?"),
            ("customer", "हाँ, वो perfect रहेगा।"),
            ("advisor", "बढ़िया Amit जी, मैंने आपका trial book कर दिया है शनिवार शाम 6 बजे के लिए, online mode में। मैं शुक्रवार को एक बार confirm करने के लिए call करूँगी।"),
            ("customer", "बहुत बढ़िया, धन्यवाद Sneha जी।"),
            ("advisor", "आपका स्वागत है, मिलते हैं शनिवार को!"),
        ],
    },
    {
        "file": "call_06_nonsales.wav",
        "advisor_name": "Arjun Nair",
        "scenario": "Non-sales call — wrong number",
        "expected_tags": [],
        "expected_score_range": None,
        "advisor_voice": VOICE_M_EN,
        "customer_voice": VOICE_F_EN,
        "turns": [
            ("advisor", "Hi, good afternoon, this is Arjun calling from FitNova regarding a fitness program inquiry."),
            ("customer", "I'm sorry, I think you have the wrong number. I didn't submit any inquiry."),
            ("advisor", "Oh, I apologize. Is this not the number ending in... let me just check... 4521?"),
            ("customer", "No, this isn't that number. You've got the wrong person."),
            ("advisor", "My apologies for the confusion, have a good day."),
            ("customer", "No problem, bye."),
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
    manifest = []

    for call in CALLS:
        print(f"Generating {call['file']} ({call['scenario']})...")
        audio, duration = await build_call(call)
        out_path = OUT_DIR / call["file"]
        audio.export(out_path, format="wav")
        print(f"  wrote {out_path.name}: {duration:.1f}s, {len(call['turns'])} turns")

        manifest.append(
            {
                "file": call["file"],
                "advisor_name": call["advisor_name"],
                "advisor_id": ADVISOR_IDS[call["advisor_name"]],
                "scenario": call["scenario"],
                "expected_tags": call["expected_tags"],
                "expected_score_range": call["expected_score_range"],
                "duration_secs": round(duration, 1),
            }
        )

    manifest_path = OUT_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote manifest: {manifest_path}")
    print(f"Generated {len(CALLS)} sample calls in {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
