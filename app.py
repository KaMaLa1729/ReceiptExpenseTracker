
import streamlit as st
import json
from google import genai
from PIL import Image
from pathlib import Path
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import re

# ==================================================
# EMAIL VALIDATION
# ==================================================
def is_valid_email(email):
    pattern = r"^[\w\.-]+@[\w\.-]+\.[A-Za-z]{2,}$"
    return bool(re.match(pattern, email.strip()))

# ==================================================
# RECEIPT DATA VALIDATION
# ==================================================

def validate_receipt(receipt):
    errors = []

    if not isinstance(receipt, dict):
        return ["Receipt data is not in the expected format."]

    # Check merchant
    if not str(receipt.get("merchant", "")).strip():
        errors.append("Merchant name is missing.")

    # Check receipt date
    if not str(receipt.get("date", "")).strip():
        errors.append("Receipt date is missing.")

    # Check items
    items = receipt.get("items")

    if not isinstance(items, list) or not items:
        errors.append("No receipt items were found.")
    else:
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                errors.append(f"Item {index} has invalid data.")
                continue

            if not str(item.get("name", "")).strip():
                errors.append(f"Item {index} is missing a name.")

            try:
                quantity = float(item.get("quantity"))
                if quantity <= 0:
                    errors.append(f"Item {index} has an invalid quantity.")
            except (TypeError, ValueError):
                errors.append(f"Item {index} has an invalid quantity.")

            try:
                line_total = float(item.get("line_total"))
                if line_total < 0:
                    errors.append(f"Item {index} has an invalid amount.")
            except (TypeError, ValueError):
                errors.append(f"Item {index} has an invalid amount.")

    # Check receipt total
    try:
        total = float(receipt.get("receipt_total"))
        if total < 0:
            errors.append("Receipt total cannot be negative.")
    except (TypeError, ValueError):
        errors.append("Receipt total is missing or invalid.")

    return errors
# ==================================================
# 1. PAGE CONFIGURATION
# ==================================================

st.set_page_config(
    page_title="Receipt & Expense Tracker",
    page_icon="🧾",
    layout="centered"
)


# Gmail configuration
GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"] 



# ==================================================
# EMAIL SENDING FUNCTION
# ==================================================

def send_email(to_address, subject, body):
    message = MIMEText(body)
    message["Subject"] = subject
    message["From"] = GMAIL_ADDRESS
    message["To"] = to_address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.send_message(message) 


# ==================================================
# 2. CONNECT TO GEMINI
# ==================================================

api_key = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=api_key)

# ==================================================
# 3. EXPENSE HISTORY STORAGE
# ==================================================

EXPENSES_FILE = Path(__file__).parent / "expenses.json"


def load_expenses():
    if not EXPENSES_FILE.exists():
        return []

    try:
        with open(EXPENSES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_expenses(expenses):
    with open(EXPENSES_FILE, "w", encoding="utf-8") as file:
        json.dump(
            expenses,
            file,
            indent=4,
            ensure_ascii=False
        )


# ==================================================
# 4. PAGE HEADING
# ==================================================

st.title("🧾 Receipt & Expense Tracker")

st.write(
    "Upload your receipt, extract expenses using AI, "
    "and split bills with friends."
)

# ==================================================
# 5. USER INFORMATION
# ==================================================

st.header("Your Details")

name = st.text_input(
    "Enter your name",
    key="user_name",
    placeholder="Your name"
)

email = st.text_input(
    "Enter your email address",
    key="user_email",
    placeholder="example@gmail.com"
)

if name.strip():
    st.write(f"Welcome, {name.strip()}!")

if email.strip():
    if is_valid_email(email):
        st.success("Valid email address.")
    else:
        st.warning("Please enter a valid email address.")

# ==================================================
# 6. RECEIPT UPLOAD
# ==================================================

st.divider()
st.header("Upload Your Receipt")

receipt = st.file_uploader(
    "Choose a receipt image",
    type=["jpg", "jpeg", "png"],
    key="receipt_uploader"
)

if receipt is not None:
    st.image(
        receipt,
        caption="Your Uploaded Receipt",
        use_container_width=True
    )

# ==================================================
# 7. GEMINI RECEIPT ANALYSIS
# ==================================================

if receipt is not None:
    if st.button("Analyze Receipt", type="primary"):

        try:
            image = Image.open(receipt).convert("RGB")

            prompt = """
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

            with st.spinner("Gemini is reading your receipt..."):
                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=[prompt, image]
                )

            response_text = (response.text or "").strip()

            # Remove optional markdown fences
            if response_text.startswith("```"):
                response_text = (
                    response_text
                    .replace("```json", "")
                    .replace("```", "")
                    .strip()
                )

            # Convert JSON into Python data
            receipt_data = json.loads(response_text)

            # Validate basic structure
            if not isinstance(receipt_data, dict):
                raise ValueError(
                    "Receipt response must be a JSON object."
                )

            receipt_items = receipt_data.get("items", [])

            if not isinstance(receipt_items, list):
                raise ValueError(
                    "Receipt items must be a list."
                )

            # Keep at most 50 items
            receipt_items = receipt_items[:50]
            receipt_data["items"] = receipt_items

            # Store extracted information
            st.session_state["receipt_data"] = receipt_data
            st.session_state["receipt_items"] = receipt_items
            

            # Automatically set item count
            st.session_state["item_split_count"] = max(
                1, len(receipt_items)
            )

            # Fill item splitter with extracted data
            for i, item in enumerate(receipt_items):
                if not isinstance(item, dict):
                    continue

                item_name = item.get("name") or ""
                quantity = item.get("quantity")
                unit_price = item.get("unit_price")
                line_total = item.get("line_total")

                if (
                    line_total is None
                    and quantity is not None
                    and unit_price is not None
                ):
                    line_total = (
                        float(quantity) * float(unit_price)
                    )

                st.session_state[
                    f"split_item_name_{i}"
                ] = item_name

                st.session_state[
                    f"split_item_price_{i}"
                ] = (
                    float(line_total)
                    if line_total is not None
                    else 0.0
                )

            # Clear old split result
            st.session_state.pop(
                "item_split_result", None
            )

            st.success("Receipt analyzed successfully!")

        except json.JSONDecodeError:
            st.error(
                "Gemini returned invalid JSON. "
                "Please try analyzing the receipt again."
            )

        except Exception as e:
            st.error(
                "Could not analyze the receipt. "
                "Check your connection and try again."
            )
            st.caption(str(e))

# ==================================================
# 8. DISPLAY EXTRACTED RECEIPT
# ==================================================

if "receipt_data" in st.session_state:
    receipt_data = st.session_state["receipt_data"]

    st.divider()
    st.header("Receipt Analysis")

    st.write(
        "**Merchant:**",
        receipt_data.get("merchant", "Unknown")
    )

    st.write(
        "**Date:**",
        receipt_data.get("date", "Unknown")
    )

    st.write(
        "**Currency:**",
        receipt_data.get("currency", "Unknown")
    )

    st.subheader("Extracted Items")

    receipt_items = receipt_data.get("items", [])

    if receipt_items:
        for item in receipt_items:
            if not isinstance(item, dict):
                continue

            item_name = item.get("name") or "Unknown item"
            quantity = item.get("quantity")
            unit_price = item.get("unit_price")
            line_total = item.get("line_total")

            st.write(f"**{item_name}**")
            st.write(f"Quantity: {quantity}")

            if unit_price is not None:
                st.write(
                    f"Unit price: {float(unit_price):.2f}"
                )

            if line_total is not None:
                st.write(
                    f"Line total: {float(line_total):.2f}"
                )

            st.divider()
    else:
        st.warning("No items were extracted.")

    # Calculate item subtotal
    items_total = 0.0
    has_missing_total = False

    for item in receipt_items:
        if not isinstance(item, dict):
            has_missing_total = True
            continue

        line_total = item.get("line_total")
        quantity = item.get("quantity")
        unit_price = item.get("unit_price")

        if (
            line_total is None
            and quantity is not None
            and unit_price is not None
        ):
            line_total = float(quantity) * float(unit_price)

        if line_total is not None:
            items_total += float(line_total)
        else:
            has_missing_total = True

    st.subheader("Expense Calculation")

    st.write(f"**Items subtotal: {items_total:.2f}**")

    if has_missing_total:
        st.warning(
            "Some item totals are missing. "
            "Verify the receipt before splitting."
        )

    receipt_total = receipt_data.get("receipt_total")

    if receipt_total is not None:
        receipt_total = float(receipt_total)

        st.write(f"**Receipt total: {receipt_total:.2f}**")

        if not has_missing_total:
            difference = receipt_total - items_total

            if abs(difference) >= 0.01:
                st.info(
                    f"The difference between the receipt "
                    f"total and item subtotal is "
                    f"{difference:.2f}. This may include "
                    f"tax, discounts or other charges."
                )

  
    # ==================================================
    # 8A. SAVE RECEIPT
    # ==================================================

    if st.button("💾 Save Receipt", key="save_receipt_button"):

        # Validate receipt data
        validation_errors = validate_receipt(
            st.session_state["receipt_data"]
        )

        if validation_errors:
            st.error("Please correct the receipt data before saving.")

            for error in validation_errors:
                st.write(f"- {error}")

        else:
            # Load existing saved expenses
            saved_expenses = load_expenses()

            # Create a new record
            new_record = {
                "user": st.session_state.get(
                    "user_name", "Unknown"
                ).strip() or "Unknown",

                "saved_at": datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),

                "receipt": st.session_state["receipt_data"]
            }

            # Add new record to expense history
            saved_expenses.append(new_record)

            # Save updated expense history
            save_expenses(saved_expenses)

            st.success("Receipt saved successfully!")

            st.rerun()

    # Use receipt total in equal splitter
    if receipt_total is not None:
        if st.button(
            "Use Receipt Total in Equal Splitter"
        ):
            st.session_state["equal_bill_total"] = (
                receipt_total
            )
            st.success(
                "Receipt total is ready for equal splitting."
            )

#
# ==================================================
# AI CHAT ABOUT RECEIPT
# ==================================================

st.header("💬 Ask About Your Receipt")

# Create chat history when the app first runs
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# Show chat only after a receipt has been analyzed
if st.session_state.get("receipt_data"):

    # Display previous messages
    for message in st.session_state["chat_history"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input box for a new question or command
    user_question = st.chat_input(
        "Ask about your receipt or request an email..."
    )

    if user_question:

        # Display the user's message
        with st.chat_message("user"):
            st.markdown(user_question)

        # Save user's message
        st.session_state["chat_history"].append({
            "role": "user",
            "content": user_question
        })

        # Get receipt information
        receipt = st.session_state["receipt_data"]

        # Check whether the user wants to send an email
        question_lower = user_question.lower()

        email_intent = (
            "email" in question_lower
            and any(word in question_lower for word in [
                "send", "share", "forward", "email"
            ])
        )

        # Prepare assistant response
        answer = ""

        with st.chat_message("assistant"):

            # ==========================================
            # EMAIL COMMAND
            # ==========================================

            if email_intent:

                with st.spinner("Preparing your receipt email..."):

                    # Check recipient email
                    if not (
                        email.strip()
                        and "@" in email
                        and "." in email.split("@")[-1]
                    ):
                        answer = (
                            "Please enter a valid recipient email "
                            "address before sending your receipt."
                        )

                    else:
                        # Validate receipt
                        validation_errors = validate_receipt(receipt)

                        if validation_errors:
                            answer = (
                                "I cannot send this receipt yet "
                                "because some receipt details need "
                                "to be corrected:\n\n"
                            )

                            for error in validation_errors:
                                answer += f"- {error}\n"

                        else:
                            # Prepare receipt details
                            merchant = receipt.get(
                                "merchant", "Unknown Merchant"
                            )
                            date = receipt.get(
                                "date", "Not available"
                            )
                            currency = receipt.get("currency", "")
                            total = receipt.get(
                                "receipt_total", "Not available"
                            )
                            items = receipt.get("items", [])

                            # Build email content
                            email_body = f"""
Hello {name.strip() or "there"},

Here is your receipt summary.

Merchant: {merchant}
Date: {date}
Total: {currency} {total}

Items:
"""

                            for item in items:
                                item_name = item.get(
                                    "name", "Unknown item"
                                )
                                quantity = item.get(
                                    "quantity", "N/A"
                                )
                                line_total = item.get(
                                    "line_total", "N/A"
                                )

                                email_body += (
                                    f"\n- {item_name} | "
                                    f"Quantity: {quantity} | "
                                    f"Amount: {currency} {line_total}"
                                )

                            email_body += """

Thank you for using Receipt & Expense Tracker.
"""

                            # Send email using existing function
                            try:
                                send_email(
                                    to_address=email.strip(),
                                    subject=(
                                        f"Your Receipt Summary - {merchant}"
                                    ),
                                    body=email_body
                                )

                                answer = (
                                    "Your receipt summary has been "
                                    "sent successfully to "
                                    f"{email.strip()}! "
                                )

                            except Exception:
                                answer = (
                                    "I couldn't send your email. "
                                    "Please check your Gmail "
                                    "configuration and try again."
                                )

                st.markdown(answer)

            # ==========================================
            # NORMAL GEMINI RECEIPT QUESTION
            # ==========================================

            else:

                # Prepare receipt information for Gemini
                receipt_context = json.dumps(
                    receipt,
                    ensure_ascii=False,
                    indent=2
                )

                # Prepare previous conversation
                conversation = "\n".join(
                    f'{message["role"]}: {message["content"]}'
                    for message in st.session_state["chat_history"]
                )

                # Create Gemini prompt
                chat_prompt = f"""
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

                # Generate Gemini's answer
                with st.spinner("Thinking..."):
                    try:
                        response = client.models.generate_content(
                            model="gemini-3.5-flash-lite",
                            contents=chat_prompt
                        )

                        answer = (
                            response.text.strip()
                            if response.text
                            else "I couldn't generate an answer. Please try again."
                        )

                    except Exception:
                        answer = (
                            "I couldn't get a response from Gemini. "
                            "Please check your connection and try again."
                        )

                st.markdown(answer)

        # Save assistant response in chat history
        st.session_state["chat_history"].append({
            "role": "assistant",
            "content": answer
        })

else:
    st.info("Upload and analyze a receipt to start chatting.")

# ==================================================
# SEND RECEIPT SUMMARY BY EMAIL
# ==================================================

st.header("📧 Email Your Receipt")

if st.session_state.get("receipt_data"):

    st.write("Receipt is ready to be emailed.")

    if not (email.strip() and "@" in email and "." in email.split("@")[-1]):
        st.warning("Please enter a valid recipient email address.")

    if st.button("📧 Send Receipt by Email", key="send_receipt_email"):

        if not (email.strip() and "@" in email and "." in email.split("@")[-1]):
            st.error("Enter a valid recipient email address first.")

        else:
            receipt = st.session_state["receipt_data"]

            validation_errors = validate_receipt(receipt)

            if validation_errors:
                st.error("Please correct the receipt data before emailing.")

                for error in validation_errors:
                    st.write(f"- {error}")

            else:
                merchant = receipt.get("merchant", "Unknown Merchant")
                date = receipt.get("date", "Not available")
                currency = receipt.get("currency", "")
                total = receipt.get("receipt_total", "Not available")
                items = receipt.get("items", [])

                email_body = f"""
Hello {name.strip() or "there"},

Here is your receipt summary.

Merchant: {merchant}
Date: {date}
Total: {currency} {total}

Items:
"""

                for item in items:
                    item_name = item.get("name", "Unknown item")
                    quantity = item.get("quantity", "N/A")
                    line_total = item.get("line_total", "N/A")

                    email_body += (
                        f"\n- {item_name} | "
                        f"Quantity: {quantity} | "
                        f"Amount: {currency} {line_total}"
                    )

                email_body += """

Thank you for using Receipt & Expense Tracker.
"""

                try:
                    with st.spinner("Sending email..."):
                        send_email(
                            to_address=email.strip(),
                            subject=f"Your Receipt Summary - {merchant}",
                            body=email_body
                        )

                    st.success("Receipt summary sent successfully!")

                except Exception:
                    st.error(
                        "Unable to send the email. "
                        "Check your Gmail configuration and try again."
                    )

else:
    st.info("Analyze a receipt before sending it by email.")
    
# ==================================================
# 9. EXPENSE HISTORY
# ==================================================

st.divider()
st.header("📚 Expense History")

saved_expenses = load_expenses()

if saved_expenses:
    st.write(
        f"Total saved receipts: {len(saved_expenses)}"
    )

    for index in reversed(range(len(saved_expenses))):
        record = saved_expenses[index]
        receipt_info = record.get("receipt", {})

        merchant = receipt_info.get("merchant", "Unknown")
        date = receipt_info.get("date", "Unknown")
        total = receipt_info.get("receipt_total")
        saved_at = record.get("saved_at", "Unknown")
        saved_by = record.get("user", "Unknown")

        with st.expander(f"{merchant} - {date}"):
            st.write(f"**Saved by:** {saved_by}")
            st.write(f"**Saved at:** {saved_at}")

            if total is not None:
                st.write(f"**Receipt total:** ₹{total}")
            else:
                st.write("**Receipt total:** Not available")

            st.write("**Items:**")

            for item in receipt_info.get("items", []):
                if isinstance(item, dict):
                    st.write(
                        f"- {item.get('name', 'Unknown item')}: "
                        f"{item.get('line_total', 'N/A')}"
                    )

            if st.button(
                "Delete This Receipt",
                key=f"delete_receipt_{index}",
                type="secondary"
            ):
                del saved_expenses[index]
                save_expenses(saved_expenses)
                st.rerun()
else:
    st.info(
        "No saved receipts yet. "
        "Analyze and save a receipt first."
    )

# ==================================================
# 10. EXPENSE SUMMARY
# ==================================================

st.divider()
st.header("📊 Expense Summary")

saved_expenses = load_expenses()
valid_totals = []

for record in saved_expenses:
    receipt_info = record.get("receipt", {})
    total = receipt_info.get("receipt_total")

    try:
        if total is not None:
            valid_totals.append(float(total))
    except (ValueError, TypeError):
        pass

total_spending = sum(valid_totals)

average_receipt = (
    total_spending / len(valid_totals)
    if valid_totals
    else 0
)

col1, col2, col3 = st.columns(3)

col1.metric(
    "Saved Receipts",
    len(saved_expenses)
)

col2.metric(
    "Total Spending",
    f"₹{total_spending:.2f}"
)

col3.metric(
    "Average Receipt",
    f"₹{average_receipt:.2f}"
)

# ==================================================
# 10A. SPENDING BY MERCHANT
# ==================================================

st.subheader("📈 Spending by Merchant")

merchant_totals = {}

for record in saved_expenses:
    receipt_info = record.get("receipt", {})

    merchant = receipt_info.get(
        "merchant", "Unknown"
    )

    total = receipt_info.get("receipt_total")

    try:
        if total is not None:
            merchant_totals[merchant] = (
                merchant_totals.get(merchant, 0)
                + float(total)
            )
    except (ValueError, TypeError):
        pass

if merchant_totals:
    chart_data = {
        "Merchant": list(merchant_totals.keys()),
        "Spending (₹)": list(merchant_totals.values())
    }

    st.bar_chart(
        chart_data,
        x="Merchant",
        y="Spending (₹)"
    )
else:
    st.info(
        "Save receipts to see your spending chart."
    )

# ==================================================
# 11. EQUAL BILL SPLITTER
# ==================================================

st.divider()
st.header("Equal Bill Splitter")

st.write(
    "Divide a verified receipt total equally "
    "among people."
)

bill_total = st.number_input(
    "Enter the verified bill total (₹)",
    min_value=0.0,
    value=st.session_state.get(
        "equal_bill_total", 0.0
    ),
    step=0.01,
    format="%.2f",
    key="equal_bill_total"
)

people = st.number_input(
    "Number of people",
    min_value=1,
    max_value=50,
    value=2,
    step=1,
    key="equal_people"
)

if st.button("Split Bill", key="equal_split_button"):
    total_cents = round(bill_total * 100)

    base_share, remainder = divmod(
        total_cents, int(people)
    )

    st.subheader("Equal Bill Breakdown")

    for person in range(1, int(people) + 1):
        share_cents = (
            base_share
            + (1 if person <= remainder else 0)
        )

        share = share_cents / 100

        st.write(
            f"**Person {person}:** ₹{share:.2f}"
        )

    st.success(
        f"Total bill: ₹{total_cents / 100:.2f}"
    )

# ==================================================
# 12. ITEM-BASED BILL SPLITTER
# ==================================================

st.divider()
st.header("Item-Based Bill Splitter")

st.write(
    "Assign each item to the person who ordered it."
)

# People
person_count = st.number_input(
    "Number of people",
    min_value=1,
    max_value=20,
    value=2,
    step=1,
    key="item_split_people"
)

people_names = []

for i in range(int(person_count)):
    person_name = st.text_input(
        f"Person {i + 1} name",
        value=f"Person {i + 1}",
        key=f"split_person_{i}"
    )

    people_names.append(
        person_name.strip() or f"Person {i + 1}"
    )

# Item count
if "item_split_count" not in st.session_state:
    st.session_state["item_split_count"] = 2

item_count = st.number_input(
    "Number of items",
    min_value=1,
    max_value=50,
    step=1,
    key="item_split_count"
)

# Enter items and assign people
items = []

for i in range(int(item_count)):
    st.subheader(f"Item {i + 1}")

    col1, col2 = st.columns(2)

    with col1:
        item_name = st.text_input(
            "Item name",
            key=f"split_item_name_{i}"
        )

    with col2:
        item_price = st.number_input(
            "Item line total (₹)",
            min_value=0.0,
            step=0.50,
            format="%.2f",
            key=f"split_item_price_{i}"
        )

    assigned_person = st.selectbox(
        "Who ordered this item?",
        people_names,
        key=f"split_item_person_{i}"
    )

    items.append({
        "name": item_name,
        "price": item_price,
        "person": assigned_person
    })

# Calculate item-based split
if st.button(
    "Calculate Item-Based Split",
    key="calculate_item_split"
):
    person_totals = {
        person: 0 for person in people_names
    }

    for item in items:
        price_cents = round(item["price"] * 100)

        person_totals[item["person"]] += price_cents

    st.session_state["item_split_result"] = {
        "totals": person_totals,
        "grand_total": sum(person_totals.values())
    }

# Display split result
if "item_split_result" in st.session_state:
    result = st.session_state["item_split_result"]

    st.subheader("Amount Each Person Owes")

    for person, total_cents in result["totals"].items():
        st.write(
            f"**{person}:** ₹{total_cents / 100:.2f}"
        )

    grand_total = result["grand_total"]

    st.divider()

    st.success(
        f"Total assigned items: ₹{grand_total / 100:.2f}"
    )

    st.caption(
        "This total includes the item line totals "
        "assigned above. Tax and other charges are "
        "not automatically allocated."
    )

# ==================================================
# 13. FOOTER
# ==================================================

st.divider()

st.caption(
    "Receipt & Expense Tracker | "
    "Built with Python, Streamlit and Gemini AI"
)

