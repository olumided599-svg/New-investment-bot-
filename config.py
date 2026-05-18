import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv("8705960443:AAHxFw3NKtyKzr_gNcc6hMO54zhrvE_9yd0")
if not BOT_TOKEN:
    raise ValueError("⚠️ TELEGRAM_BOT_TOKEN is missing from environment variables!")

# Admin Configuration - CHANGE THIS TO YOUR TELEGRAM USER ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "8180581077"))  # Replace with your actual Telegram ID

# Bank Details (Opay)
BANK_NAME = os.getenv("BANK_NAME", "Opay")
ACCOUNT_NAME = os.getenv("ACCOUNT_NAME", "Omotayo Anike Olumide")
ACCOUNT_NUMBER = os.getenv("ACCOUNT_NUMBER", "8037840735")

# Investment Plans (Amount in Naira, Daily Profit %, Duration Days)
INVESTMENT_PLANS = {
    "starter": {"name": "Starter", "amount": 3000, "daily_profit": 25, "duration": 60},
    "silver": {"name": "Silver", "amount": 5000, "daily_profit": 25, "duration": 60},
    "gold": {"name": "Gold", "amount": 10000, "daily_profit": 25, "duration": 60},
    "premium": {"name": "Premium", "amount": 20000, "daily_profit": 25, "duration": 60},
    "diamond": {"name": "Diamond", "amount": 25000, "daily_profit": 25, "duration": 60},
    "elite": {"name": "Elite", "amount": 40000, "daily_profit": 25, "duration": 60},
    "vip": {"name": "VIP", "amount": 50000, "daily_profit": 25, "duration": 60},
}

# Referral Commission (18%)
REFERRAL_COMMISSION = 0.18

# Welcome Bonus on Registration
WELCOME_BONUS = 500

# Minimum Withdrawal Amount
MIN_WITHDRAWAL = 500

# Database Path (Railway volume or default)
DATABASE_PATH = os.getenv("DATABASE_PATH", "/data/nexavault.db" if os.getenv("RAILWAY_VOLUME_MOUNT_PATH") else "nexavault.db")
