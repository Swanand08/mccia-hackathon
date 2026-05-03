"""
Feature 7 — Morning Digest Script
Standalone script to generate a daily inventory summary using Claude AI and send it via email.
"""
import os
import pandas as pd
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

# Import system modules
from config import TODAY, CREDIT_LIMIT, get_current_outstanding
from unit_normalizer import normalize_units
from bom_forecaster import run_forecast
from stockout_alerter import run_stockout_alerts
from procurement_engine import run_procurement_engine
from substitution_engine import run_substitution_engine
from data_utils import load_normalized_csv

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def send_email(subject, body):
    """Sends the digest via email using SMTP config from .env."""
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    recipient = os.getenv("DIGEST_RECIPIENT")
    
    if not all([smtp_server, smtp_port, smtp_user, smtp_pass, recipient]):
        print("  WARNING: SMTP configuration incomplete in .env. Skipping email.")
        return False
    
    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = recipient
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        print(f"  Email digest sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"  ERROR: Failed to send email: {e}")
        return False

def generate_digest():
    print(f"Generating Daily Digest for {TODAY.strftime('%Y-%m-%d')}...")
    
    # 1. Load Data with Normalization
    if not os.path.exists(DATA_DIR):
        print(f"  ERROR: Data directory {DATA_DIR} not found.")
        return

    try:
        mat_master = load_normalized_csv(os.path.join(DATA_DIR, "material_master.csv"), "material_master.csv")
        sup_master = load_normalized_csv(os.path.join(DATA_DIR, "supplier_master.csv"), "supplier_master.csv")
        prod_orders = load_normalized_csv(os.path.join(DATA_DIR, "production_orders.csv"), "production_orders.csv")
        seasonal = load_normalized_csv(os.path.join(DATA_DIR, "seasonal_index.csv"), "seasonal_index.csv")
        
        # 2. Run Pipeline
        forecast, explosion, upcoming = run_forecast(DATA_DIR, prod_orders=prod_orders, material_master=mat_master, seasonal_index=seasonal)
        alerts_df = run_stockout_alerts(forecast, mat_master, sup_master)
        proc_df = run_procurement_engine(forecast, mat_master, sup_master, DATA_DIR)
        subs_df = run_substitution_engine(forecast, mat_master, sup_master)
        
        current_out = get_current_outstanding(DATA_DIR)
        
        # 3. Prepare Context for Claude
        critical = alerts_df[alerts_df["alert_level"].str.contains("CRITICAL", na=False)]
        approved = proc_df[proc_df["status"].isin(["APPROVED", "PARTIAL"])]
        total_spend = approved["order_cost_inr"].sum()
        
        context = f"""
        Inventory Status as of {TODAY.strftime('%d %B %Y')}:
        - Critical Stockouts: {len(critical)} items
        - Approved Orders Today: {len(approved)} items
        - Total Spend Recommended: Rs.{total_spend:,.0f}
        - Current Credit Used: Rs.{current_out:,.0f} / Rs.{CREDIT_LIMIT:,}
        - Top Substitution: {subs_df.iloc[0]['action'] if not subs_df.empty else 'None'}
        """
        
        # 4. Ask Claude
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("  ERROR: GEMINI_API_KEY not found in .env")
            return
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = f"Write a 5-bullet plain-English WhatsApp-style morning summary for a business owner based on this data:\\n{context}"
        
        msg = model.generate_content(prompt)
        digest = msg.text
        
        # 5. Output
        print("\\n" + "="*50)
        print("PACKRIGHT MORNING DIGEST")
        print("="*50)
        print(digest)
        print("="*50)
        
        # 6. Email (Optional)
        send_email(f"PackRight Inventory Digest — {TODAY.strftime('%d %b %Y')}", digest)
        
    except Exception as e:
        print(f"  ERROR generating digest: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    generate_digest()
