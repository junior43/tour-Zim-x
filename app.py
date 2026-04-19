
import os
from datetime import datetime

import requests
from flask import Flask, request, Response
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
ZAPIER_WEBHOOK_URL = os.environ.get("ZAPIER_WEBHOOK_URL")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """
You are Tour_Zim_X WhatsApp assistant for Zimbabwe tourism.

You do two things:
1) Answer questions about any Zimbabwe tourism attraction (overview, highlights, best time to visit, how to get there, safety, what to pack, photo spots).
2) Sell Tour_Zim_X tour packages and collect leads.

Tour_Zim_X base city: Bulawayo.

Packages (offer when relevant):
- Matobo Hills Day Trip (half-day/full-day from Bulawayo)
- Hwange 2-Day Safari (from Bulawayo or Victoria Falls; upgrades available)
- Great Zimbabwe 2–3 Day Heritage Trip (Masvingo)

Lead capture:
If user asks to book, price, quote, availability, or says they want a tour, ask them to reply with all details in one message using:
1) name
2) travel dates (or month)
3) group size
4) budget (USD)
5) pickup city (default Bulawayo)
6) attraction/package

Rules:
- If uncertain about fees/opening hours/current rules, say so and suggest verifying via official sources.
- Keep replies concise for WhatsApp.
"""

def twiml(message: str) -> Response:
    xml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{message}</Message></Response>'
    return Response(xml, mimetype="text/xml")

def is_lead_intent(text: str) -> bool:
    t = text.lower()
    keywords = [
        "book", "booking", "price", "prices", "cost", "quote", "rates",
        "available", "availability", "package", "tour", "guide", "transport"
    ]
    return any(k in t for k in keywords)

@app.get("/")
def home():
    return "OK"

@app.post("/whatsapp")
def whatsapp():
    from_number = request.form.get("From", "")
    body = (request.form.get("Body") or "").strip()

    # Start lead capture
    if is_lead_intent(body) and not (body.startswith("1)") or body.startswith("1.")):
        msg = (
            "Great — I can help you with that. Please reply with:\n"
            "1) Your name\n"
            "2) Travel dates (or month)\n"
            "3) Group size\n"
            "4) Budget (USD)\n"
            "5) Pickup city (default Bulawayo)\n"
            "6) Which attraction/package (e.g., Gonarezhou, Hwange 2-day, Matobo day trip)"
        )
        return twiml(msg)

    # Save lead if user replies with the numbered template
    if body.startswith("1)") or body.startswith("1."):
        lines = body.splitlines()
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "name": "",
            "phone": from_number,
            "trip_dates": "",
            "group_size": "",
            "budget": "",
            "interest": "",
            "pickup_city": "Bulawayo",
            "notes": body
        }

        for line in lines:
            l = line.strip()
            low = l.lower()
            if low.startswith(("1)", "1.")):
                payload["name"] = l[2:].strip()
            elif low.startswith(("2)", "2.")):
                payload["trip_dates"] = l[2:].strip()
            elif low.startswith(("3)", "3.")):
                payload["group_size"] = l[2:].strip()
            elif low.startswith(("4)", "4.")):
                payload["budget"] = l[2:].strip()
            elif low.startswith(("5)", "5.")):
                city = l[2:].strip()
                if city:
                    payload["pickup_city"] = city
            elif low.startswith(("6)", "6.")):
                payload["interest"] = l[2:].strip()

        # Post lead to Zapier webhook
        if ZAPIER_WEBHOOK_URL:
            try:
                requests.post(ZAPIER_WEBHOOK_URL, json={"lead": payload}, timeout=20)
            except Exception:
                pass

        return twiml("Thank you! ✅ Tour_Zim_X received your details and will reply with options and pricing shortly.")

    # Normal Q&A
    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": body}
        ],
        temperature=0.7
    )
    answer = completion.choices[0].message.content.strip()
    answer += "\n\nTo get a quote/package, reply: BOOK"

    return twiml(answer)
