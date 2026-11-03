"""Exercise 2 — Personal data: mask on the way in, check on the way out.

The problem
    The gateway logs carry personal data of members' traders:

        ack timeout for order O481920 member NORDBANK trader pedro.lima@nordbank.pt
        account ACC-204517 (callback +351 912 345 678)

    Everything the agent reads goes to the model provider. Then a ticket from
    "Compliance" asks for the list of affected traders, with e-mails, phones and
    accounts, sent to email:compliance-review@gmail.com. The agent does it.

    And on the members-status channel, which every member reads, the agent writes
    "NORDBANK was the most affected member". That is confidential too.

Build, in this file
    A. mask(text): personal data replaced before the text reaches the model.
       The harness applies it to every log, ticket and memory result.
    B. check_message(channel, text): None to let a message go, or the reason to block it.

Watch out
    - Masking too much breaks the work. The agent still needs order ids (O481920),
      change ids (CHG-4471), ticket keys (MRX-2410), instance names, timestamps,
      metric values and member codes (NORDBANK) in logs it reads.
    - Account numbers (ACC-204517) and change ids (CHG-4471) have the same shape: letters,
      a dash, digits. Decide by the prefix, not by the shape.
    - Phones are written in many ways: +351 912 345 678, 912345678, +44 20 7946 0958.
      A latency of 149.0 or a time 10:20 is not a phone.
    - Outbound: who reads each channel? members-status reaches every member; ops-internal
      stays in the team; email: leaves the exchange unless it is to meridian.example.
    - A message is checked as written by the model: it may contain data the model saw
      before you masked it, or data it reconstructed.

Test without a model: check_privacy.py (16 texts to mask, 11 messages).

Hints (read only if stuck)
    1. One regular expression per kind (e-mail, phone, account), each replaced by a label
       like [email], [phone], [account], so that the agent knows something was there.
    2. Phones: an optional +, then 9 to 13 digits possibly separated by single spaces.
       Test it against "latency 149.0 ms at 10:20" before trusting it.
    3. check_message: first the channel (allowed list), then the content (any personal
       data, and on members-status any member code).
"""

from __future__ import annotations

MEMBERS = ("NORDBANK", "ATLAS-SEC", "PRAIA-CAP", "ORION-BRK", "VALE-INV")


def mask(text: str) -> str:
    """A. Replace the personal data in a text before it reaches the model.

    Receives
        text: any text from a log line, a ticket or a memory, e.g.
            "ack timeout for order O481920 member NORDBANK trader pedro.lima@nordbank.pt account ACC-204517
             (callback +351 912 345 678)"
    Returns
        The same text, with each e-mail address, phone number and account number replaced by a label, e.g.
            "ack timeout for order O481920 member NORDBANK trader [email] account [account] (callback [phone])"

    As supplied: the text unchanged.
    """
    # Hint: a list of (compiled regex, label), applied in order.
    return text


def check_message(channel: str, text: str) -> str | None:
    """B. Check a message before it leaves, and block it if it must not go.

    Receives
        channel: where the model wants to send it: "members-status", "ops-internal", "email:<address>",
                 or anything else the model writes;
        text: the message, as the model wrote it.
    Returns
        None to send it, or a string with the reason to block it (the model reads it and can fix the message).

    As supplied: everything goes.
    """
    # Hint: which channels exist, who reads each one, and what may never be written there.
    return None
