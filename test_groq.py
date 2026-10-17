import os, json
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

tools = [{
    "type": "function",
    "function": {
        "name": "create_invoice",
        "description": "Create an invoice for a client after a completed project.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "description": {"type": "string"},
                "amount": {"type": "number"},
                "currency": {"type": "string", "description": "ISO code, e.g. INR or USD"},
                "due_in_days": {"type": "integer"},
            },
            "required": ["client_name", "description", "amount", "currency"],
        },
    },
}]

resp = client.chat.completions.create(
    model=os.getenv("GROQ_MODEL"),
    messages=[
        {"role": "system", "content": "You are a freelancer's billing assistant. Use tools to act."},
        {"role": "user", "content": "I completed a ₹40,000 website project for ABC."},
    ],
    tools=tools,
    tool_choice="auto",
)

calls = resp.choices[0].message.tool_calls
if calls:
    print(calls[0].function.name)
    print(json.dumps(json.loads(calls[0].function.arguments), indent=2))
else:
    print("No tool call:", resp.choices[0].message.content)