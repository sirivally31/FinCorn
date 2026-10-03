from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import wave

ROOT = Path(__file__).parent
OUT = ROOT / "frames"
OUT.mkdir(exist_ok=True)
W, H = 1920, 1080
BG = (8, 15, 28)
PANEL = (18, 29, 48)
WHITE = (239, 245, 252)
MUTED = (157, 174, 198)
CYAN = (67, 211, 202)
AMBER = (247, 184, 74)
RED = (239, 104, 104)
GREEN = (76, 210, 132)
FONT = r"C:\Windows\Fonts\segoeui.ttf"
BOLD = r"C:\Windows\Fonts\segoeuib.ttf"


def f(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def text(draw, xy, value, size, fill=WHITE, bold=False, anchor=None):
    draw.text(xy, value, font=f(size, bold), fill=fill, anchor=anchor)


def wrap(value, width=52):
    words = value.split()
    lines, line = [], ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        lines.append(line)
    return lines


def base(kicker, title, sub):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W, 8), fill=CYAN)
    text(d, (110, 86), kicker.upper(), 22, CYAN, True)
    text(d, (110, 126), title, 58, WHITE, True)
    text(d, (110, 206), sub, 25, MUTED)
    d.line((110, 270, 1810, 270), fill=(40, 59, 83), width=2)
    text(d, (110, 1010), "FINRECON AI  /  AI FINANCE CONTROLLER", 18, MUTED, True)
    return im, d


def save(im, index):
    im.save(OUT / f"slide_{index:02d}.png")


def metric(d, x, y, w, label, value, color=CYAN):
    d.rounded_rectangle((x, y, x+w, y+160), 14, fill=PANEL, outline=(47, 69, 97), width=2)
    text(d, (x+24, y+25), label.upper(), 17, MUTED, True)
    text(d, (x+24, y+67), value, 42, color, True)


def screenshot_slide(index, kicker, title, sub, filename, caption):
    im, d = base(kicker, title, sub)
    shot = Image.open(ROOT.parent / filename).convert("RGB")
    shot.thumbnail((1510, 690))
    x, y = 300, 305
    d.rounded_rectangle((x-8, y-8, x+shot.width+8, y+shot.height+8), 12, fill=(3, 8, 16), outline=(55, 81, 110), width=2)
    im.paste(shot, (x, y))
    text(d, (110, 325), caption, 25, WHITE, True)
    save(im, index)


im, d = base("Opening", "Reconcile -> Investigate -> Control Cash", "A finance controller for the full payment-to-cash loop")
text(d, (110, 370), "FINRECON AI", 94, CYAN, True)
text(d, (110, 500), "AI Finance Controller", 42, WHITE, True)
text(d, (110, 590), "Deterministic financial truth. AI-powered investigation. Human-controlled decisions.", 27, MUTED)
for x, label in [(112, "PAYMENT"), (550, "SETTLEMENT"), (988, "LEDGER"), (1426, "CASH")]:
    d.rounded_rectangle((x, 760, x+300, 850), 12, fill=PANEL, outline=(47, 69, 97), width=2)
    text(d, (x+150, 805), label, 23, WHITE, True, "mm")
    if x < 1426: text(d, (x+335, 805), ">", 32, AMBER, True, "mm")
save(im, 1)

im, d = base("The problem", "One financial truth, many records", "Small differences create manual investigation work and delayed cash visibility")
items = [("PAYMENTS", "Customer transactions", CYAN), ("SETTLEMENTS", "Bank and gateway payouts", AMBER), ("LEDGER", "Merchant accounting entries", GREEN), ("FEES + TAXES", "Expected deductions", (183, 139, 236)), ("TIMING", "Settlement delays", RED), ("EXCEPTIONS", "What needs human review", (240, 128, 128))]
for i, (a, b, c) in enumerate(items):
    x = 110 + (i % 3) * 565; y = 360 + (i // 3) * 210
    d.rounded_rectangle((x, y, x+485, y+145), 14, fill=PANEL, outline=(47, 69, 97), width=2)
    text(d, (x+26, y+28), a, 22, c, True); text(d, (x+26, y+78), b, 23, WHITE)
save(im, 2)

im, d = base("Reproducible demo data", "A controlled dataset with real exception scenarios", "Synthetic data makes the evaluation repeatable and measurable")
metric(d, 110, 355, 385, "Payment records", "150", CYAN); metric(d, 530, 355, 385, "Settlement records", "146", AMBER); metric(d, 950, 355, 385, "Ledger entries", "150", GREEN); metric(d, 1370, 355, 440, "Injected scenarios", "29", RED)
text(d, (110, 650), "The application labels this dataset as synthetic demo data. Nothing here is presented as a live financial account.", 27, MUTED)
save(im, 3)

screenshot_slide(4, "Live application", "Deterministic reconciliation", "The running dashboard computes these results from the seeded database", "finrecon_video_dashboard.png", "152 records evaluated")
# overlay metrics on a dedicated frame for readability
im, d = base("Measured reconciliation", "The engine reports what it can prove", "Match rate and classification accuracy are separate measures")
metric(d, 110, 350, 390, "Records processed", "152", CYAN); metric(d, 535, 350, 390, "Matched", "123", GREEN); metric(d, 960, 350, 390, "Auto-resolved", "8", AMBER); metric(d, 1385, 350, 425, "Unresolved", "21", RED)
text(d, (110, 625), "86.18%", 76, AMBER, True); text(d, (110, 720), "RECONCILIATION MATCH RATE", 24, WHITE, True)
text(d, (930, 625), "21 cases remain visible for investigation and human control.", 27, MUTED)
save(im, 5)

im, d = base("Evaluation", "Classification accuracy against synthetic ground truth", "A controlled benchmark distinguishes deterministic performance from AI explanation")
text(d, (110, 390), "100%", 112, GREEN, True); text(d, (115, 540), "CLASSIFICATION ACCURACY", 30, WHITE, True); text(d, (115, 595), "against deterministic synthetic ground truth", 25, MUTED)
metric(d, 990, 390, 350, "False matches", "0", GREEN); metric(d, 1390, 390, 420, "Missed exceptions", "0", GREEN)
text(d, (110, 790), "This is not an AI accuracy claim. The deterministic reconciliation engine is the source of truth.", 27, AMBER, True)
save(im, 6)

screenshot_slide(7, "Exception investigation", "An amount mismatch stays visible", "AI explains the evidence; deterministic rules establish the financial truth", "finrecon_video_exception_detail.png", "TXN-1150  /  ₹50.00  /  beyond ₹5 tolerance")

im, d = base("Human control + audit", "Reviewable decisions leave a trail", "Exceptions outside safe tolerance bands remain under finance operations control")
for i, (a, b, c) in enumerate([("DETECT", "Rule flags discrepancy", RED), ("INVESTIGATE", "AI explains evidence", CYAN), ("REVIEW", "Human chooses action", AMBER), ("AUDIT", "Action is recorded", GREEN)]):
    x = 110 + i*430
    d.rounded_rectangle((x, 400, x+350, 610), 14, fill=PANEL, outline=(47, 69, 97), width=2)
    text(d, (x+175, 450), a, 23, c, True, "ma")
    for j, line in enumerate(wrap(b, 19)): text(d, (x+175, 515+j*35), line, 22, WHITE, anchor="ma")
    if i < 3: text(d, (x+375, 505), ">", 34, AMBER, True)
text(d, (110, 770), "A human resolution of TXN-1150 is recorded in the Audit Trail as OPEN -> RESOLVED.", 27, MUTED)
save(im, 8)

screenshot_slide(9, "Cash position", "Reconciliation becomes cash visibility", "Current operating cash and unsettled money are computed from the actual demo records", "finrecon_video_cash.png", "Current cash  ₹11,10,071.20   /   Pending settlements  ₹1,10,071.20")
screenshot_slide(10, "Cash forecast", "Forward-looking cash visibility", "A transparent moving-average model projects the reconciled position", "finrecon_video_forecast.png", "1-day / 3-day / 7-day projections")
screenshot_slide(11, "Finance Assistant", "Ask the data in plain language", "Free-text questions are answered from the current reconciliation dataset", "finrecon_video_assistant_answer.png", "Grounded answer: 21 unresolved exceptions / ₹1,82,002.50 unresolved value")
im, d = base("Closing", "Deterministic truth. Human control. Cash intelligence.", "FinRecon AI  /  AI Finance Controller")
text(d, (110, 390), "FINRECON AI", 92, CYAN, True)
text(d, (110, 525), "Reconciliation  ->  Investigation  ->  Audit  ->  Cash", 34, WHITE, True)
text(d, (110, 650), "A finance controller loop grounded in the records that matter.", 28, MUTED)
metric(d, 110, 790, 370, "Match rate", "86.18%", AMBER); metric(d, 520, 790, 370, "Classifications", "100%", GREEN); metric(d, 930, 790, 370, "Unresolved", "21", RED); metric(d, 1340, 790, 470, "7-day forecast", "₹12,10,263.93", CYAN)
save(im, 12)

narration = [
"Meet FinRecon AI, an AI-powered Finance Controller designed to close the financial reconciliation loop. It connects payment, settlement and ledger records, identifies exceptions, explains what happened, and turns the results into actionable cash visibility.",
"Finance teams often have to compare multiple financial sources to understand whether money actually settled correctly. Small discrepancies can become manual investigation work, delayed reconciliation, and poor visibility into cash.",
"FinRecon AI uses a reproducible synthetic dataset containing 150 payments, 146 settlements, 150 ledger entries, and 29 deliberately injected exception scenarios.",
"The live application shows the finance controller workflow. Payment, settlement, and ledger records are brought together so the reconciliation result can be inspected rather than assumed.",
"The reconciliation engine applies deterministic financial rules to compare the records. In this run, 152 records were evaluated, with an 86.18 percent reconciliation match rate, eight cases safely auto-resolved within configured tolerance bands, and 21 exceptions left for investigation.",
"Because this is a controlled synthetic dataset, FinRecon AI can evaluate its classifications against known ground truth. The deterministic engine achieved 100 percent classification accuracy, with zero false matches and zero missed exceptions. This is not an AI accuracy claim.",
"Instead of hiding discrepancies behind a single score, FinRecon AI exposes the actual exceptions. For transaction TXN-1150, the payment is 26,137 rupees and the settlement is 26,087 rupees: a 50 rupee difference beyond the 5 rupee tolerance. AI explains the evidence and recommends a manual cross-check. It does not decide the financial truth.",
"Cases that cannot be safely resolved remain in a human review queue. A finance operator can resolve or escalate an exception, and the action is recorded in the audit trail. Financial decisions stay under human control.",
"Once reconciliation is complete, the results become useful beyond exception management. FinRecon AI converts the financial state into a current cash position and highlights unsettled money. The live demo shows current cash of 1,110,071 rupees and pending settlements of 110,071 rupees.",
"The system then turns the reconciled financial position into forward-looking cash visibility. The forecast shows one-day, three-day, and seven-day projected balances using a transparent moving-average model derived from the synthetic transaction history.",
"Finally, the Finance Assistant provides a conversational interface over the financial data. A controller can ask free-text questions such as what is causing the settlement gap, which discrepancies are largest, or why the match rate is not 100 percent, instead of manually searching through records.",
"FinRecon AI closes one finance-operations loop from reconciliation to investigation to cash intelligence. Deterministic logic establishes financial truth, AI explains and investigates it, and humans remain in control of financial decisions. FinRecon AI, AI Finance Controller."
]
(Path(ROOT) / "narration.txt").write_text("\n\n".join(narration), encoding="utf-8")

durations = [20, 25, 15, 15, 30, 15, 30, 20, 20, 20, 25, 5]
(Path(ROOT) / "durations.txt").write_text("\n".join(map(str, durations)), encoding="ascii")

# Pad or trim speech tracks to the planned section durations.
files = sorted((ROOT / "audio").glob("voice_*.wav"))
if files:
    with wave.open(str(files[0]), "rb") as first:
        params = first.getparams()
    with wave.open(str(ROOT / "voiceover.wav"), "wb") as out:
        out.setparams(params)
        for idx, duration in enumerate(durations):
            path = ROOT / "audio" / f"voice_{idx+1:02d}.wav"
            if not path.exists():
                continue
            with wave.open(str(path), "rb") as src:
                frames = src.readframes(src.getnframes())
                target = int(params.framerate * duration)
                frames = frames[:target * params.sampwidth * params.nchannels]
                out.writeframes(frames)
                missing = target - len(frames) // params.sampwidth // params.nchannels
                if missing > 0:
                    out.writeframes(b"\0" * missing * params.sampwidth * params.nchannels)
