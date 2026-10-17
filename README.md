# AI Freelancer Payment Agent

An AI agent that handles the money side of freelancing. Describe finished work in plain language, approve the generated invoice, and the agent sends it through PayPal, tracks whether it is paid, writes reminders when it is overdue, and summarizes your monthly earnings.

Built for the **Build What's Next with PayPal and AI** hackathon.

**Demo video:** [YouTube link]
**Live demo:** [https://freelancer-payment-agent.onrender.com/]
“Hosted on a free tier: the first load can take about a minute, and demo data resets when the server restarts.”

## The problem

Freelancers lose hours creating invoices, chasing late payments, and tracking what they are owed. This agent automates that loop while keeping the freelancer in control of anything that reaches a client.

## How it works

1. **Chat:** "I completed a ₹40,000 website project for ABC."
2. **AI extracts** the client, line item, amount, currency, and payment terms. If something is missing, it asks a follow-up question instead of guessing.
3. **Preview and approve:** the freelancer reviews the invoice. Nothing is sent without clicking **Approve**.
4. **PayPal invoice** is created and sent to the client.
5. **Payment tracking:** the dashboard checks PayPal every 20 seconds. When the client pays, the status updates and the AI writes a confirmation.
6. **Overdue reminders:** the AI drafts a reminder whose tone depends on how late the invoice is (friendly, firm, then formal final notice). The freelancer approves it before it is sent through PayPal.
7. **Monthly summary:** the AI narrates earnings, outstanding amounts, and which client to follow up with first.

## How PayPal is used

PayPal is central to the project. It uses the **PayPal Invoicing API v2** in the sandbox:

- OAuth 2.0 client credentials for authentication
- Generate invoice number and create a draft invoice
- Send the invoice to the client
- Get invoice status and the client's payment link
- Send payment reminders

## How AI is used

The AI model is **Groq** (`llama-3.3-70b-versatile`, configurable in `.env`):

- **Tool calling** turns free-form messages into structured invoice data.
- **Reminder writing** adapts tone to days overdue and reminders already sent.
- **Payment confirmations** and **monthly summaries** in natural language.

**Design choice:** the AI never does arithmetic or decides business rules. Python computes totals, overdue status, and statistics, and the AI only writes the words. The AI also cannot send anything: invoices and reminders are stored on the server as proposals, and only an explicit approval from the freelancer triggers PayPal.

## Tech stack

Python, FastAPI, SQLite, vanilla HTML/JS dashboard, PayPal Invoicing API, Groq API.

## Setup

Requirements: Python 3.10 or newer.

```bash
git clone [your-repo-url]
cd freelancer-payment-agent
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # Windows: copy .env.example .env
```

Fill in `.env`:

| Variable | Description |
|---|---|
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | From a PayPal **Sandbox** app with **Invoicing** enabled |
| `PAYPAL_BASE_URL` | `https://api-m.sandbox.paypal.com` |
| `GROQ_API_KEY` | From console.groq.com |
| `GROQ_MODEL` | e.g. `llama-3.3-70b-versatile` |
| `DEMO_CLIENT_EMAIL` | Email of a sandbox **Personal** (client) account |
| `INR_PER_USD` | Conversion rate used for INR amounts (default 88) |

Run:

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## PayPal sandbox notes

- Create a sandbox **Business** account (the freelancer) and a **Personal** account (the client), both with country **United States**. PayPal blocks sending invoices to customers within India, so India-based sandbox accounts fail.
- In your sandbox app's features, enable **Invoicing**.
- INR amounts are converted to USD for the PayPal invoice, and the original INR amount is included in the invoice note.
- To pay an invoice, open its **Pay link** in a private window and log in with the sandbox Personal account.

## Try it (demo path)

1. Type `I finished some work for Sam.`: the AI asks for the missing details.
2. Reply `$300 for logo design` and approve the preview.
3. Click **Demo: make overdue** on the invoice, then **AI reminder**, review the draft, and send.
4. Pay the invoice with the Pay link as the sandbox client.
5. Watch the status change to Paid and the AI confirmation appear.
6. Click **Generate AI monthly summary**.

## Limitations and future work

- Payment tracking uses polling, and a PayPal webhook would make it instant.
- Every invoice goes to the demo client email, and a client address book is a next step.
- The overdue demo button changes the local due date only, not PayPal's.
- Pending previews are kept in memory and are cleared when the server restarts.
- Production use would need real INR support, authentication, and PayPal live credentials.

## License

MIT, see [LICENSE](LICENSE).