# ReceiptExpenseTracker

ReceiptExpenseTracker is a Streamlit-based expense tracking application that uses AI to extract information from receipt images, organize expenses, split bills, and generate expense summaries.

## Features

* Upload receipt images for AI-powered data extraction.
* Extract merchant, date, items, quantities, prices, and total amount.
* Track and review saved expenses.
* Split bills equally or by individual items.
* View expense summaries and charts.
* Ask questions about receipts using AI.
* Email receipt summaries using Gmail.

## Technologies Used

* Python
* Streamlit
* Google Gemini API
* Pillow
* Gmail SMTP

## Requirements

* Python 3.10 or later
* A Google Gemini API key
* Gmail account with an App Password for email features

## Run Locally

1. Clone the repository:

   ```bash
   git clone https://github.com/KaMaLa1729/ReceiptExpenseTracker.git
   ```

2. Open the project folder:

   ```bash
   cd ReceiptExpenseTracker
   ```

3. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   On Windows:

   ```powershell
   .venv\Scripts\activate
   ```

4. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Create a `.streamlit/secrets.toml` file and add your own credentials:

   ```toml
   GMAIL_ADDRESS = "your-email@gmail.com"
   GMAIL_APP_PASSWORD = "your-gmail-app-password"
   GEMINI_API_KEY = "your-gemini-api-key"
   ```

   Replace the placeholders with your actual credentials. Keep this file private and do not commit it to GitHub.

6. Start the application:

   ```bash
   streamlit run app.py
   ```

## Deployment

The application can be deployed using Streamlit Community Cloud. Add the required secrets in the app's Streamlit Cloud settings before running it.

## Security

Never publish real API keys, Gmail App Passwords, or other credentials. The `.gitignore` file excludes local secrets and environment files.
