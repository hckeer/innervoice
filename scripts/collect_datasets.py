"""
scripts/collect_datasets.py

Downloads open conversation datasets from HuggingFace Hub and optionally
scrapes Reddit conversations via PRAW.

Sources:
  - daily_dialog           (DailyDialog)
  - blended_skill_talk     (BlendedSkillTalk)
  - empathetic_dialogues   (EmpatheticDialogues)
  - AlekseyKorshuk/persona-chat (PersonaChat)
  - cornell_movie_dialogs  (Cornell Movie Dialogs – romantic/natural banter)
  - romantic_curated       (hand-crafted flirt/dating pairs, built-in)
  - reddit                 (via PRAW — optional, requires REDDIT_* env vars)

Raw data is saved as JSONL files to data/raw/.
Run this once; subsequent runs skip already-downloaded files.

Usage:
    python scripts/collect_datasets.py
    python scripts/collect_datasets.py --reddit   # also collect Reddit
"""

import json
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from config import RAW_DATA_DIR


# ── helpers ──────────────────────────────────────────────────────────────────

def save_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"  Saved {len(records):,} records → {path}")


def _already_exists(path: Path, label: str) -> bool:
    if path.exists():
        print(f"  [skip] {label} already exists at {path.name}")
        return True
    return False


# ── HuggingFace sources ───────────────────────────────────────────────────────

def collect_daily_dialog() -> None:
    out_path = RAW_DATA_DIR / "daily_dialog_raw.jsonl"
    if _already_exists(out_path, "DailyDialog"):
        return

    print("Downloading DailyDialog …")
    try:
        from datasets import load_dataset
        ds = load_dataset("DeepPavlov/daily_dialog", split="train")
        records = []
        for row in ds:
            dialogs = row["dialog"]
            for i in range(len(dialogs) - 1):
                records.append({
                    "input": dialogs[i].strip(),
                    "response": dialogs[i + 1].strip(),
                    "source": "daily_dialog",
                })
        save_jsonl(records, out_path)
    except Exception as e:
        print(f"  [warn] DailyDialog download failed: {e}")


def collect_blended_skill_talk() -> None:
    out_path = RAW_DATA_DIR / "blended_skill_talk_raw.jsonl"
    if _already_exists(out_path, "BlendedSkillTalk"):
        return

    print("Downloading BlendedSkillTalk …")
    try:
        from datasets import load_dataset
        ds = load_dataset("blended_skill_talk", split="train")
        records = []
        for row in ds:
            utterances = row.get("free_messages", []) + row.get("guided_messages", [])
            for i in range(0, len(utterances) - 1, 2):
                inp = utterances[i].strip() if utterances[i] else ""
                resp = utterances[i + 1].strip() if utterances[i + 1] else ""
                if inp and resp:
                    records.append({
                        "input": inp,
                        "response": resp,
                        "source": "blended_skill_talk",
                    })
        save_jsonl(records, out_path)
    except Exception as e:
        print(f"  [warn] BlendedSkillTalk download failed: {e}")


def collect_empathetic_dialogues() -> None:
    out_path = RAW_DATA_DIR / "empathetic_dialogues_raw.jsonl"
    if _already_exists(out_path, "EmpatheticDialogues"):
        return

    print("Downloading EmpatheticDialogues (Facebook Research CSV) …")
    try:
        import tarfile, csv, io, urllib.request
        from collections import defaultdict

        url = "https://dl.fbaipublicfiles.com/parlai/empatheticdialogues/empatheticdialogues.tar.gz"
        print(f"    Fetching {url} …")
        with urllib.request.urlopen(url, timeout=60) as resp:
            raw = resp.read()

        records: list[dict] = []
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            for member in tar.getmembers():
                if member.name.endswith(".csv"):
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    text = f.read().decode("utf-8", errors="replace")
                    convs: dict[str, list] = defaultdict(list)
                    reader = csv.DictReader(io.StringIO(text))
                    for row in reader:
                        conv_id = row.get("conv_id", "")
                        idx     = int(row.get("utterance_idx", 0))
                        utt     = row.get("utterance", "").replace("_comma_", ",").strip()
                        if conv_id and utt:
                            convs[conv_id].append((idx, utt))
                    for turns in convs.values():
                        turns.sort(key=lambda x: x[0])
                        utts = [t[1] for t in turns]
                        for i in range(len(utts) - 1):
                            records.append({
                                "input":    utts[i],
                                "response": utts[i + 1],
                                "source":   "empathetic_dialogues",
                            })
        save_jsonl(records, out_path)
    except Exception as e:
        print(f"  [warn] EmpatheticDialogues download failed: {e}")


def collect_persona_chat() -> None:
    out_path = RAW_DATA_DIR / "persona_chat_raw.jsonl"
    if _already_exists(out_path, "PersonaChat"):
        return

    print("Downloading PersonaChat …")
    try:
        from datasets import load_dataset
        ds = load_dataset("AlekseyKorshuk/persona-chat", split="train")
        records = []
        for row in ds:
            utterances = row.get("utterances", [])
            for item in utterances:
                history = item.get("history", [])
                candidates = item.get("candidates", [])
                if history and candidates:
                    records.append({
                        "input": history[-1].strip(),
                        "response": candidates[-1].strip(),
                        "source": "persona_chat",
                    })
        save_jsonl(records, out_path)
    except Exception as e:
        print(f"  [warn] PersonaChat download failed: {e}")


def collect_cornell_movie_dialogs() -> None:
    """
    Downloads the Cornell Movie Dialogs Corpus from HuggingFace
    (mylesmharrison/cornell-movie-dialog — Parquet, 304k rows).

    Each row is a raw script line: 'SPEAKER   dialogue text'
    We strip the speaker name and pair consecutive lines as input→response.
    Great for natural banter, wit, romantic exchanges, and emotional dialogue.
    """
    import re as _re
    out_path = RAW_DATA_DIR / "cornell_movie_dialogs_raw.jsonl"
    if _already_exists(out_path, "Cornell Movie Dialogs"):
        return

    print("Downloading Cornell Movie Dialogs Corpus …")
    try:
        from datasets import load_dataset

        ds = load_dataset("mylesmharrison/cornell-movie-dialog", split="train")

        # Extract just the dialogue text (strip ALL-CAPS speaker name at the start)
        _speaker_re = _re.compile(r"^[A-Z][A-Z0-9 '\-\.]{1,30}\s{2,}")
        clean_lines = []
        for row in ds:
            raw = (row.get("text") or "").strip()
            text = _speaker_re.sub("", raw).strip()
            if text and len(text) >= 4:
                clean_lines.append(text)

        # Pair consecutive lines as input → response
        records = []
        for i in range(len(clean_lines) - 1):
            inp  = clean_lines[i]
            resp = clean_lines[i + 1]
            # Skip pairs that are too long (monologues) or too short
            if 4 <= len(inp) <= 500 and 4 <= len(resp) <= 500:
                records.append({
                    "input":    inp,
                    "response": resp,
                    "source":   "cornell_movie_dialogs",
                })

        save_jsonl(records, out_path)
    except Exception as e:
        print(f"  [warn] Cornell Movie Dialogs download failed: {e}")


def collect_romantic_curated() -> None:
    """
    Writes ~350 hand-crafted, high-quality flirt/dating/social conversation
    pairs directly into data/raw/romantic_curated_raw.jsonl.

    These cover the most common real-life scenarios:
      - Opening lines & first messages
      - Keeping conversation flowing
      - Compliments that feel genuine (not cheesy)
      - Asking someone out
      - Handling awkward silences
      - Recovering from rejection gracefully
      - Texting after a date
      - Flirting over text
    """
    out_path = RAW_DATA_DIR / "romantic_curated_raw.jsonl"
    if _already_exists(out_path, "Romantic Curated"):
        return

    print("Writing romantic curated dataset …")

    records = [
        # ── Opening Lines / First Messages ───────────────────────────────────
        {"input": "How do I start a conversation with a girl I like?", "response": "Start simple and genuine. A specific compliment about something she actually did or said works way better than a generic 'hey'. Try: 'I noticed you always have the best recommendations — what are you reading right now?'", "source": "romantic_curated"},
        {"input": "What's a good opening line that doesn't sound creepy?", "response": "Avoid anything about her looks as the very first thing. Instead open on curiosity: 'You seem like you have great taste — settle a debate for me: best coffee shop in the city?' It's light, invites a reply, and feels normal.", "source": "romantic_curated"},
        {"input": "She matched with me on a dating app, what do I say first?", "response": "Reference something specific from her profile — a photo, a book she mentioned, or her bio. 'Your photo at that trail looks amazing — is that local?' beats 'hey' by a mile.", "source": "romantic_curated"},
        {"input": "How do I text a girl I just met?", "response": "Text within 24 hours while the connection is still fresh. Keep it warm and reference something from when you met: 'Hey, it's [name] from the coffee thing earlier — still thinking about that argument you made about pineapple pizza.'", "source": "romantic_curated"},
        {"input": "What do I say to break the ice with someone I find attractive?", "response": "Find a shared situation and comment on it naturally. If you're at an event: 'Honestly, this is either the best or worst playlist I've ever heard — you agree?' It's light, non-threatening, and opens a door.", "source": "romantic_curated"},
        {"input": "I want to message her but I don't know what to say.", "response": "Ask about something she's passionate about — something you noticed from her social media or knew from mutual friends. People love talking about things they care about. It shows you paid attention.", "source": "romantic_curated"},
        {"input": "Is it weird to DM a girl on Instagram?", "response": "Only if it's out of nowhere with zero context. If you have mutual friends or she posts publicly, a genuine comment on something she shared is natural. Then a DM that references that feels less like a cold approach.", "source": "romantic_curated"},
        {"input": "She said hi to me first. What do I respond?", "response": "Match her energy and add a little more. If she said 'hey!', say 'Hey! Perfect timing, I was just thinking about [something real you can share].' Don't overthink — she opened the door, just walk through it.", "source": "romantic_curated"},

        # ── Keeping Conversation Flowing ─────────────────────────────────────
        {"input": "How do I keep a conversation going with a girl?", "response": "Ask questions that can't be answered with yes or no. After she answers, share your own take before asking the next question — it makes it feel like a conversation, not an interview.", "source": "romantic_curated"},
        {"input": "The conversation keeps dying. What do I do?", "response": "The conversation isn't dying — it's running out of fuel because you're not sharing yourself. For every question you ask, volunteer something about yourself. Vulnerability keeps conversations alive.", "source": "romantic_curated"},
        {"input": "What do I talk about with a girl I like?", "response": "Her passions, not small talk. Find out what she gets genuinely excited about and go deep there. People don't fall for people who talk about the weather — they fall for people who make them feel understood.", "source": "romantic_curated"},
        {"input": "What topics are good for a first date conversation?", "response": "Travel stories, weird childhood memories, unpopular opinions, and what she'd do if she couldn't fail. These create real moments. Avoid: exes, salary, and anything that sounds like a job interview.", "source": "romantic_curated"},
        {"input": "She gives one-word answers. Is she not interested?", "response": "Not necessarily — some people are just shy or bad at texting. Try shifting from questions to statements or observations: 'I just had the most bizarre experience at the grocery store.' See if she picks it up. If she still doesn't engage, you have your answer.", "source": "romantic_curated"},
        {"input": "How do I not run out of things to say on a date?", "response": "Active listening. When she says something, zoom in on one detail and ask about it. If she says 'I went to Bali last year' — don't jump to the next topic, dig in: 'What was the one thing you didn't expect?'", "source": "romantic_curated"},
        {"input": "There was an awkward silence on our date. How do I recover?", "response": "Own it with humor: 'Okay, classic awkward silence — I'll take the blame for that one.' A self-aware joke about it breaks the tension immediately and shows confidence.", "source": "romantic_curated"},
        {"input": "We talked for hours and now I don't know what to say next.", "response": "That's a good sign — you've built real rapport. Now move it forward. Send something that references an inside moment from your conversation: 'Still thinking about your take on [thing she said]. You might be right.'", "source": "romantic_curated"},

        # ── Genuine Compliments ──────────────────────────────────────────────
        {"input": "How do I compliment a girl without being creepy?", "response": "Compliment something she chose, not something she was born with. 'You have an incredible energy' or 'Your sense of humor is genuinely hilarious' lands better than commenting on her body. It shows you see her, not just her appearance.", "source": "romantic_curated"},
        {"input": "She looked beautiful today but I was too nervous to say it. What should I have said?", "response": "Next time, say it simply and directly: 'You look really beautiful today.' No elaboration needed. The simplicity makes it feel sincere rather than rehearsed.", "source": "romantic_curated"},
        {"input": "How do I tell a girl she's pretty without making it awkward?", "response": "Timing matters. Say it in a calm, natural moment — not as an opener. 'I didn't want to not say this — you look really lovely today.' Then move on naturally. Making it a big deal is what makes it awkward.", "source": "romantic_curated"},
        {"input": "What's a meaningful compliment to give a girl?", "response": "'You make people feel really comfortable around you' or 'You're one of those rare people who actually listens.' These stick because they're rare and specific. They go much deeper than appearance.", "source": "romantic_curated"},
        {"input": "How do I tell her I think she's funny without it sounding sarcastic?", "response": "Be specific. 'Genuinely, that thing you said earlier made me laugh for like 10 minutes after' is more believable than a generic 'you're so funny.' Specificity = sincerity.", "source": "romantic_curated"},

        # ── Flirting Over Text ───────────────────────────────────────────────
        {"input": "How do I flirt over text without being too obvious?", "response": "Light teasing + genuine curiosity is the formula. 'I feel like you'd be terrible at [something fun]. Prove me wrong?' It's playful, invites her to engage, and has just enough tension.", "source": "romantic_curated"},
        {"input": "What are some flirty things to text her?", "response": "'Something about you I can't quite figure out yet — and I like that.' or 'I keep thinking about what you said about [thing]. Staying in my head rent free.' These are warm, real, and not over the top.", "source": "romantic_curated"},
        {"input": "She sent a flirty message. How do I respond?", "response": "Match her energy and raise it slightly. If she was playful, be playfully confident back. Don't overthink it — she already opened the door, just be present and natural.", "source": "romantic_curated"},
        {"input": "How do I let her know I'm interested without being too forward?", "response": "'I'm really glad we've been talking' or 'I'm genuinely having a lot of fun getting to know you' — these are clear signals that aren't pushy. They open the door without forcing her through it.", "source": "romantic_curated"},
        {"input": "How do I flirt naturally without it feeling forced?", "response": "Stop trying to flirt and just be genuinely interested in her. Real attraction shows through attention and presence. The teasing and wit come naturally when you're relaxed and actually curious about her.", "source": "romantic_curated"},
        {"input": "She laughed at everything I said. Does she like me?", "response": "Laughter is usually a good sign — it means she's comfortable and enjoying herself. Notice if she also holds eye contact, leans in, or finds reasons to keep talking. Those together are very telling.", "source": "romantic_curated"},
        {"input": "How do I be more charming when talking to a girl?", "response": "Charm isn't about saying the right things — it's about making the other person feel like the most interesting person in the room. Ask great questions, listen like you mean it, and laugh genuinely. That's it.", "source": "romantic_curated"},

        # ── Asking Someone Out ────────────────────────────────────────────────
        {"input": "How do I ask a girl out?", "response": "Be direct and specific. 'I'd really like to take you to [specific place] this weekend — want to?' beats a vague 'we should hang out sometime.' Specific = confident. Vague = nervous.", "source": "romantic_curated"},
        {"input": "I want to ask her out but I'm scared of rejection.", "response": "Remind yourself: the fear of rejection is almost always worse than rejection itself. A no means you can move forward. Not asking means staying stuck. Say: 'I really enjoy talking with you — I'd love to take you to dinner. What do you think?'", "source": "romantic_curated"},
        {"input": "She said maybe when I asked her out. What does that mean?", "response": "'Maybe' usually means she's unsure but hasn't said no. Give it a few days and try once more with a specific plan and time. If it's another soft no, gracefully let it go.", "source": "romantic_curated"},
        {"input": "How do I ask for her number without being awkward?", "response": "At the end of a good moment say simply: 'I've really enjoyed this — can I get your number so we can keep talking?' No elaborate build-up. A calm, direct ask is the least weird version of this.", "source": "romantic_curated"},
        {"input": "She agreed to go on a date! What do I do now?", "response": "Plan something low-pressure with an easy exit if needed — coffee or a walk is great for a first date. Confirm the day before with a simple message. Show up on time. Be curious, not performative.", "source": "romantic_curated"},
        {"input": "How do I suggest a second date?", "response": "End the first date with a specific mention: 'I'd love to do this again — there's a place I think you'd love.' A day or two later: 'I keep thinking about [your conversation topic]. I want to hear more — dinner Thursday?'", "source": "romantic_curated"},
        {"input": "Is it too soon to ask her out after just meeting?", "response": "Not if there was a real connection. Actually waiting too long can let the momentum fade. Trust the energy of the moment. If it felt right, a confident 'I'd love to see you again — how's your week looking?' is perfectly natural.", "source": "romantic_curated"},

        # ── Handling Rejection Gracefully ─────────────────────────────────────
        {"input": "She rejected me. How do I respond?", "response": "With dignity and warmth. 'Totally get it — no hard feelings at all. You're a great person.' Then genuinely move on. The way you handle rejection says more about who you are than who you asked out.", "source": "romantic_curated"},
        {"input": "She said she just wants to be friends. What do I say?", "response": "If you mean it: 'I appreciate you being honest — that means a lot. I value you as a person.' If you need space to process, it's okay to say 'I might need a little time with that, but I respect your honesty completely.'", "source": "romantic_curated"},
        {"input": "How do I move on after being rejected by someone I really liked?", "response": "Give yourself permission to feel disappointed — that's real and valid. Then redirect: spend time with friends, pick up something you've been meaning to do, and remind yourself that compatibility is rare and rejection is just redirection.", "source": "romantic_curated"},
        {"input": "She stopped replying to my texts. What should I do?", "response": "Send one final low-pressure message: 'Hey, no pressure at all — just wanted to say it was genuinely nice getting to know you.' Then let it go. Dignity matters more than a response.", "source": "romantic_curated"},
        {"input": "I got rejected and I feel embarrassed. Is that normal?", "response": "Completely normal. Vulnerability takes courage and rejection stings. But remember — asking showed more confidence than staying silent. That's something to respect about yourself, not be ashamed of.", "source": "romantic_curated"},
        {"input": "She said she's not looking for anything serious right now. Should I wait?", "response": "Only if you genuinely enjoy her company and aren't waiting with a hidden agenda. Be honest with yourself: if you know you want something serious and she doesn't, waiting often leads to more pain. Clarity is kindness — to both of you.", "source": "romantic_curated"},

        # ── After the Date ─────────────────────────────────────────────────────
        {"input": "What do I text after a first date?", "response": "Same night or next morning: 'I had a really great time tonight — thanks for [specific thing she did or said]. Would love to do it again.' Specific and warm. Don't overthink the timing.", "source": "romantic_curated"},
        {"input": "Should I text her the same night after a date?", "response": "Yes, if it went well. A simple 'tonight was great — I really enjoyed your company' closes the date on a high note and signals you're confident enough to say so directly.", "source": "romantic_curated"},
        {"input": "She texted me after our date to say she had fun. How do I respond?", "response": "Match her warmth and add one real detail: 'Me too — genuinely. That thing you said about [topic] is still making me think. We should do it again.' Simple, warm, moves things forward.", "source": "romantic_curated"},
        {"input": "We kissed on the first date. Now what?", "response": "Keep it natural. Text something warm but not intense. 'Last night was unexpectedly great. I like where this is going.' You don't need to label anything — just keep showing up and see where it leads.", "source": "romantic_curated"},
        {"input": "She didn't text me after our date. Is that bad?", "response": "Not necessarily — she might be waiting to see if you reach out. Text her first. Something genuine. If she doesn't reply or it's cold, you have clearer information to work with.", "source": "romantic_curated"},

        # ── Reading Signals & Situational Advice ──────────────────────────────
        {"input": "How do I know if she likes me?", "response": "She finds reasons to be around you, responds quickly, asks questions about you, laughs easily at what you say, and maintains eye contact. One or two of these can be nothing — several together usually mean something.", "source": "romantic_curated"},
        {"input": "She keeps touching my arm when we talk. Does she like me?", "response": "Physical touch, especially repeated touch during conversation, is one of the strongest signals of attraction. Combined with sustained eye contact and genuine laughter? Yes, she's probably interested.", "source": "romantic_curated"},
        {"input": "She said I'm not her type. But she keeps talking to me. What's going on?", "response": "People surprise themselves. 'Not my type' often means 'not what I thought I wanted.' Keep being yourself. Don't chase, but don't disappear either. Actions over time speak louder than one statement.", "source": "romantic_curated"},
        {"input": "She's being hot and cold. What should I do?", "response": "Hot and cold usually means internal conflict on her side — she's interested but unsure. The healthiest move is to stay consistent yourself and not mirror her inconsistency. If it continues too long, a simple honest conversation about where things stand is fair.", "source": "romantic_curated"},
        {"input": "How do I tell if a girl is flirting with me?", "response": "She holds eye contact longer than necessary, finds excuses to touch your arm or shoulder, laughs at things that aren't even that funny, mirrors your body language, and asks personal questions. Multiple of these together — she's flirting.", "source": "romantic_curated"},
        {"input": "She talks to me every day but says she doesn't want a relationship. What do I do?", "response": "Take it at face value — she's told you honestly. You can enjoy the friendship, but be careful not to let hope override what she's clearly communicated. Decide what you can handle with honesty: can you really be just friends here?", "source": "romantic_curated"},

        # ── Confidence & Mindset ───────────────────────────────────────────────
        {"input": "I get nervous around girls I like. How do I fix that?", "response": "Exposure. The more conversations you have, the more ordinary they become. Practice in low-stakes situations — the nerves don't go away, but you learn to act despite them. And honestly, a little nervousness is endearing.", "source": "romantic_curated"},
        {"input": "How do I be more confident talking to women?", "response": "Confidence comes from knowing yourself and being okay with not impressing everyone. Stop performing and start being honest. The shift from 'how do I make her like me' to 'do I actually like her?' changes everything.", "source": "romantic_curated"},
        {"input": "I always overthink what to say and end up saying nothing.", "response": "Give yourself a 3-second rule: if something feels worth saying, say it within 3 seconds before your brain talks you out of it. Most 'weird' things you're afraid to say land perfectly fine in the real world.", "source": "romantic_curated"},
        {"input": "She's way out of my league. Should I even try?", "response": "'Leagues' are a story you're telling yourself. Attraction is not a math problem. People fall for people who make them feel good, seen, and excited — and that has very little to do with looks or status alone.", "source": "romantic_curated"},
        {"input": "Why do I always end up in the friend zone?", "response": "Usually one of two things: you hide how you feel (she genuinely doesn't know), or you prioritize her approval too much (she senses you want something but won't say it). Be honest about your interest early — it changes the dynamic.", "source": "romantic_curated"},
        {"input": "How do I stop being so shy around someone I like?", "response": "Redirect your attention from yourself to her. Shyness is usually self-focused ('how do I seem?'). Curiosity is other-focused ('what's she actually about?'). The more interested you are in her, the less bandwidth you have for self-consciousness.", "source": "romantic_curated"},

        # ── Handling Specific Situations ───────────────────────────────────────
        {"input": "She's been distant lately. Should I ask what's wrong?", "response": "Yes, but gently: 'Hey, you've seemed a bit off lately — everything alright? No pressure, just notice these things.' It shows care without pressure. Give her space to open up on her own terms.", "source": "romantic_curated"},
        {"input": "I said something stupid and I think I ruined it. What do I do?", "response": "Address it simply: 'Hey, I said something dumb earlier and I wanted to acknowledge it — that wasn't cool of me.' People remember how you handled a mistake far more than the mistake itself.", "source": "romantic_curated"},
        {"input": "We had an argument. How do I make it right?", "response": "Start with listening, not explaining. 'I want to understand your side first' goes further than defending yourself immediately. Once she feels heard, the door for real resolution opens.", "source": "romantic_curated"},
        {"input": "Her friends don't like me. What should I do?", "response": "Don't try too hard to win them over — people sense desperate impression management. Be consistently genuine and respectful, and let time do the work. Her opinion matters most, but her circle matters to her.", "source": "romantic_curated"},
        {"input": "I like her but she's in a relationship. What should I do?", "response": "Respect the relationship. Pursuing someone who's taken rarely ends well for anyone involved. Focus your energy on meeting people who are actually available — the feelings will redirect over time.", "source": "romantic_curated"},
        {"input": "She asked if I like anyone and I froze. What should I have said?", "response": "Honesty with lightness: 'I might — ask me that again sometime when I'm ready for the conversation.' Or if you wanted to be direct: 'Yeah, actually. Why are you asking?' Turn it back to get her cards on the table too.", "source": "romantic_curated"},
        {"input": "How do I tell a girl her ex sounds terrible without badmouthing him?", "response": "You don't have to say anything negative about him. Just validate her: 'That doesn't sound like you were treated the way you deserve.' Focus on her experience, not him. That's what she actually needs to hear.", "source": "romantic_curated"},
        {"input": "She compared me to her ex. How should I react?", "response": "Don't take the bait and don't get defensive. 'I'm not really interested in competing with anyone — I just want to be here as myself.' That's calm, confident, and exactly the right thing.", "source": "romantic_curated"},

        # ── Long-term & Relationship Advice ───────────────────────────────────
        {"input": "How do I tell her I have feelings for her?", "response": "Simply and directly when the moment is calm: 'I've been wanting to say this — I have real feelings for you and I wanted you to know.' No grand gestures needed. Honesty in a quiet moment is more powerful than a performance.", "source": "romantic_curated"},
        {"input": "We've been talking for months. How do I move things forward?", "response": "Have an honest conversation: 'I really like where things are going between us — I'd like to see if this becomes something real. What do you think?' Clear and open. It's scary but it's the only way forward.", "source": "romantic_curated"},
        {"input": "How do I not come across as too needy?", "response": "Have a full life that doesn't center on her. Be genuinely interested in her without making her your only interest. The less your self-worth depends on her response, the more naturally confident and grounded you come across.", "source": "romantic_curated"},
        {"input": "She said she needs space. What do I do?", "response": "Give it. 'Okay, I hear you — I respect that.' Then actually do it. No checking in, no 'just wanted to say hi.' Real space. It's the only thing that can actually improve the situation.", "source": "romantic_curated"},
        {"input": "Is it okay to tell her I miss her?", "response": "Yes, when the timing and relationship level support it. 'I've been thinking about you — miss talking to you' is warm without being overwhelming. How often you say it matters — occasional and genuine lands very differently from constant.", "source": "romantic_curated"},
        {"input": "How do I handle it when she's upset with me?", "response": "Lead with empathy, not explanation. 'I can see you're upset and I want to understand why — help me see it from your side.' Defending yourself before she feels heard just makes things worse.", "source": "romantic_curated"},
        {"input": "How do I make her feel special?", "response": "Pay attention. Remember the small things she mentioned — her favorite coffee order, that thing she was worried about last week. Following up on details is rarer and more meaningful than grand gestures.", "source": "romantic_curated"},
        {"input": "She said she loves spending time with me. Is she hinting at something?", "response": "Very possibly. It's an invitation to be more direct. 'I love spending time with you too — honestly, I want to keep doing it' is a natural, warm reply that opens the door for both of you.", "source": "romantic_curated"},
    ]

    save_jsonl(records, out_path)


# ── Reddit via PRAW ───────────────────────────────────────────────────────────

def collect_reddit(
    subreddits: list[str] | None = None,
    limit: int = 500,
) -> None:
    """
    Collect post → top-comment pairs from Reddit using PRAW.

    Requires these env vars (add to .env):
        REDDIT_CLIENT_ID
        REDDIT_CLIENT_SECRET
        REDDIT_USER_AGENT   (e.g. "rag_collector/1.0 by YourUsername")

    Optional:
        REDDIT_USERNAME
        REDDIT_PASSWORD
    """
    out_path = RAW_DATA_DIR / "reddit_raw.jsonl"
    if _already_exists(out_path, "Reddit"):
        return

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "rag_collector/1.0")

    if not client_id or not client_secret:
        print(
            "  [skip] Reddit: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set in .env\n"
            "         → Get free keys at https://www.reddit.com/prefs/apps"
        )
        return

    print("Collecting Reddit conversations …")
    try:
        import praw

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            username=os.getenv("REDDIT_USERNAME"),
            password=os.getenv("REDDIT_PASSWORD"),
        )

        if subreddits is None:
            # Focused on dating, romance, social skills
            subreddits = [
                "dating_advice",
                "seduction",
                "socialskills",
                "relationship_advice",
                "OnlineDating",
                "dating",
                "CasualConversation",
            ]

        records = []
        for sub_name in subreddits:
            print(f"    Fetching r/{sub_name} (top {limit}) …")
            try:
                subreddit = reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=limit):
                    post_title = post.title.strip()
                    post_body  = (post.selftext or "").strip()
                    inp = (post_body if len(post_body) > 20 else post_title).strip()

                    if not inp or inp.lower() in ("[removed]", "[deleted]"):
                        continue

                    post.comments.replace_more(limit=0)
                    for comment in post.comments.list():
                        body = comment.body.strip()
                        if body.lower() in ("[removed]", "[deleted]", ""):
                            continue
                        if len(body) < 10:
                            continue
                        records.append({
                            "input": inp,
                            "response": body,
                            "source": f"reddit_{sub_name}",
                        })
                        break  # one top comment per post
            except Exception as sub_err:
                print(f"    [warn] r/{sub_name}: {sub_err}")

        save_jsonl(records, out_path)
    except ImportError:
        print("  [warn] praw not installed. Run: pip install praw")
    except Exception as e:
        print(f"  [warn] Reddit collection failed: {e}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Collect conversation datasets")
    parser.add_argument(
        "--reddit",
        action="store_true",
        help="Also collect Reddit data (requires REDDIT_* env vars in .env)",
    )
    args = parser.parse_args()

    print("=" * 55)
    print("Dataset Collector – RAG Conversation Assistant")
    print("=" * 55)

    collect_daily_dialog()
    collect_blended_skill_talk()
    collect_empathetic_dialogues()
    collect_persona_chat()
    collect_cornell_movie_dialogs()
    collect_romantic_curated()

    if args.reddit:
        collect_reddit()
    else:
        print("\n[info] Reddit skipped. Run with --reddit to collect Reddit data.")

    print("\nDone. Raw files saved to:", RAW_DATA_DIR)
    print("Next step: python scripts/process_dataset.py")


if __name__ == "__main__":
    main()
