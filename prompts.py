
RECEIPT_ANALYSIS_PROMPT = """
Analyze the receipt image and extract its information.

Return valid JSON only. Do not include markdown
code fences or explanations.

Use this exact structure:

{
  "merchant": "Merchant name or Unknown",
  "date": "Date or Unknown",
  "currency": "INR",
  "items": [
    {
      "name": "Item name",
      "quantity": 1,
      "unit_price": 0.00,
      "line_total": 0.00
    }
  ],
  "receipt_total": 0.00
}

Rules:
- Include every readable item.
- Use numeric values for readable quantities and prices.
- Use null for missing or unreadable values.
- Do not guess prices or quantities.
- Preserve the values shown on the receipt.
- Unit price means price for one unit.
- Line total means total price for that item.
- Do not confuse subtotal with receipt total.
- Return valid JSON only.
"""


def get_receipt_chat_prompt(receipt_context, conversation):
    return f"""
You are a helpful receipt and expense assistant.

Answer the user's questions using the receipt information below.
Be clear and beginner-friendly.
Do not invent prices, items, or details that are not present.
If the information is missing, say that it is not available.

RECEIPT INFORMATION:
{receipt_context}

CONVERSATION:
{conversation}

Answer the user's latest question.
"""
