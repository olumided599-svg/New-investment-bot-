import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import sys

# Configure logging for Railway
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

import config
from database import (
    create_user, get_user, update_balance, create_deposit, create_withdrawal,
    create_investment, get_active_investments, get_pending_deposits,
    get_pending_withdrawals, approve_deposit, reject_deposit,
    approve_withdrawal, reject_withdrawal, get_all_users, process_daily_profits
)

# Conversation states
DEPOSIT_AMOUNT, WITHDRAW_AMOUNT, WITHDRAW_BANK, WITHDRAW_ACCOUNT, WITHDRAW_NAME, ADMIN_NOTE = range(6)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    referred_by = None
    if context.args and context.args[0].startswith('ref_'):
        try:
            referred_by = int(context.args[0].split('_')[1])
        except (IndexError, ValueError):
            pass
    
    create_user(user.id, user.username, user.first_name, referred_by)
    
    keyboard = [
        [InlineKeyboardButton("💰 My Wallet", callback_data="wallet")],
        [InlineKeyboardButton("📈 Invest Now", callback_data="invest")],
        [InlineKeyboardButton("💳 Deposit", callback_data="deposit")],
        [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
        [InlineKeyboardButton("👥 Referrals", callback_data="referrals")],
        [InlineKeyboardButton("📊 My Investments", callback_data="my_investments")],
        [InlineKeyboardButton("🎧 Support", callback_data="support")],
    ]
    
    if user.id == config.ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔧 Admin Panel", callback_data="admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        f"🎉 *Welcome to NexaVault, {user.first_name}!* 🎉\n\n"
        f"💵 *Welcome Bonus:* ₦{config.WELCOME_BONUS:,} credited to your wallet!\n\n"
        "🚀 *Start earning up to 25% daily profit!*\n\n"
        "✨ *Why Choose NexaVault?*\n"
        "• ✅ Secure & Trusted Platform\n"
        "• ⚡ Fast Withdrawals (0-24hrs)\n"
        "• 💰 Daily Profit Payments\n"
        "• 👥 18% Referral Commission\n"
        "• 🎧 24/7 Customer Support\n\n"
        "👇 *Choose an option below to get started:*"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button clicks"""
    query = update.callback_query
    await query.answer()
    
    user = get_user(query.from_user.id)
    
    if query.data == "back":
        await start(update, context)
        return
    
    if query.data == "wallet":
        investments = get_active_investments(query.from_user.id)
        total_invested = sum(inv["amount"] for inv in investments)
        total_profit = sum(inv["total_profit"] for inv in investments)
        
        text = (
            f"💰 *Your Wallet*\n\n"
            f"👤 *User ID:* `{query.from_user.id}`\n"
            f"💵 *Available Balance:* ₦{user['balance']:,.2f}\n"
            f"📊 *Total Invested:* ₦{total_invested:,.2f}\n"
            f"📈 *Total Profit Earned:* ₦{total_profit:,.2f}\n\n"
            f"💡 *Minimum Withdrawal:* ₦{config.MIN_WITHDRAWAL:,}"
        )
        
        keyboard = [
            [InlineKeyboardButton("💳 Deposit", callback_data="deposit")],
            [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")],
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data == "invest":
        keyboard = []
        for plan_key, plan in config.INVESTMENT_PLANS.items():
            profit = plan["amount"] * (plan["daily_profit"] / 100)
            keyboard.append([
                InlineKeyboardButton(
                    f"{plan['name']} - ₦{plan['amount']:,} (Earn ₦{profit:,.0f}/day)",
                    callback_data=f"invest_{plan_key}"
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back")])
        
        text = (
            "📈 *Investment Plans*\n\n"
            "Choose your investment plan:\n"
            "⚡ All plans run for 60 days\n"
            "💰 25% daily profit\n"
            "🔄 Profits paid daily to your wallet\n\n"
            "*Select a plan:*"
        )
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith("invest_"):
        plan_key = query.data.split("_")[1]
        plan = config.INVESTMENT_PLANS[plan_key]
        
        if user["balance"] < plan["amount"]:
            await query.edit_message_text(
                f"❌ *Insufficient Balance!*\n\n"
                f"Required: ₦{plan['amount']:,}\n"
                f"Your Balance: ₦{user['balance']:,.2f}\n\n"
                "Please deposit to continue.",
                parse_mode='Markdown'
            )
            return
        
        create_investment(query.from_user.id, plan_key, plan["amount"])
        
        await query.edit_message_text(
            f"✅ *Investment Successful!*\n\n"
            f"📦 Plan: *{plan['name']}*\n"
            f"💰 Amount: ₦{plan['amount']:,}\n"
            f"📈 Daily Profit: ₦{plan['amount'] * (plan['daily_profit']/100):,.0f}\n"
            f"⏳ Duration: {plan['duration']} days\n\n"
            f"Your investment is now active! Profits will be credited daily.",
            parse_mode='Markdown'
        )
    
    elif query.data == "deposit":
        text = (
            "💳 *Make a Deposit*\n\n"
            "📝 *Instructions:*\n"
            "1. Transfer to the account below\n"
            "2. Click 'I Have Paid' button\n"
            "3. Enter the amount you sent\n\n"
            f"🏦 *Bank:* {config.BANK_NAME}\n"
            f"👤 *Account Name:* {config.ACCOUNT_NAME}\n"
            f"🔢 *Account Number:* `{config.ACCOUNT_NUMBER}`\n\n"
            "⚠️ *Note:* Deposits are approved manually within 24 hours."
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ I Have Paid", callback_data="deposit_paid")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")],
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data == "deposit_paid":
        context.user_data['deposit_step'] = 'amount'
        await query.edit_message_text(
            "💵 *Enter Deposit Amount*\n\n"
            "Please enter the amount you transferred (in Naira):\n\n"
            "Example: `5000`\n\n"
            "Type /cancel to cancel",
            parse_mode='Markdown'
        )
        return DEPOSIT_AMOUNT
    
    elif query.data == "withdraw":
        if user["balance"] < config.MIN_WITHDRAWAL:
            await query.edit_message_text(
                f"❌ *Insufficient Balance!*\n\n"
                f"Minimum withdrawal: ₦{config.MIN_WITHDRAWAL:,}\n"
                f"Your balance: ₦{user['balance']:,.2f}",
                parse_mode='Markdown'
            )
            return
        
        text = (
            "💸 *Request Withdrawal*\n\n"
            f"💰 Available Balance: ₦{user['balance']:,.2f}\n"
            f"📊 Minimum: ₦{config.MIN_WITHDRAWAL:,}\n\n"
            "Click below to start withdrawal process:"
        )
        
        keyboard = [
            [InlineKeyboardButton("💸 Withdraw Now", callback_data="withdraw_start")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")],
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data == "withdraw_start":
        context.user_data['withdraw_step'] = 'amount'
        await query.edit_message_text(
            "💵 *Enter Withdrawal Amount*\n\n"
            f"Available: ₦{user['balance']:,.2f}\n"
            f"Minimum: ₦{config.MIN_WITHDRAWAL:,}\n\n"
            "Enter amount:",
            parse_mode='Markdown'
        )
        return WITHDRAW_AMOUNT
    
    elif query.data == "referrals":
        conn = __import__('database').get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as count, COALESCE(SUM(commission_earned), 0) as total
            FROM referrals WHERE referrer_id = ?
        ''', (query.from_user.id,))
        stats = cursor.fetchone()
        conn.close()
        
        ref_link = f"https://t.me/NexaVaultBot?start=ref_{query.from_user.id}"
        
        text = (
            "👥 *Referral Program*\n\n"
            f"🔗 *Your Referral Link:*\n`{ref_link}`\n\n"
            f"👤 Total Referrals: {stats['count']}\n"
            f"💰 Total Commission Earned: ₦{stats['total']:,.2f}\n"
            f"💵 Commission Rate: {int(config.REFERRAL_COMMISSION * 100)}%\n\n"
            "💡 *How it works:*\n"
            "• Share your link with friends\n"
            "• They sign up and invest\n"
            "• You earn 18% of their daily profits!\n"
            "• Commission paid automatically every day",
            parse_mode='Markdown'
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data == "my_investments":
        investments = get_active_investments(query.from_user.id)
        
        if not investments:
            text = "📊 *No Active Investments*\n\nYou haven't invested yet. Start earning today!"
        else:
            text = "📊 *Your Active Investments*\n\n"
            for inv in investments:
                days_left = (datetime.fromisoformat(inv["end_date"].replace('Z', '+00:00')) - datetime.now()).days
                text += (
                    f"📦 *{config.INVESTMENT_PLANS[inv['plan_name']]['name']} Plan*\n"
                    f"💰 Amount: ₦{inv['amount']:,.2f}\n"
                    f"📈 Daily Profit: ₦{inv['daily_profit']:,.2f}\n"
                    f"💵 Total Profit: ₦{inv['total_profit']:,.2f}\n"
                    f"⏳ Days Remaining: {days_left}\n\n"
                )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data == "support":
        text = (
            "🎧 *Customer Support*\n\n"
            "We're here to help 24/7!\n\n"
            "📧 Email: support@nexavault.com\n"
            "💬 Telegram: @NexaVaultSupport\n"
            "🌐 Website: www.nexavault.com\n\n"
            "⚡ Average response time: < 5 minutes"
        )
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data == "admin":
        if query.from_user.id != config.ADMIN_ID:
            await query.edit_message_text("🔒 Access Denied!")
            return
        
        pending_deposits = get_pending_deposits()
        pending_withdrawals = get_pending_withdrawals()
        all_users = get_all_users()
        
        text = (
            "🔧 *Admin Panel*\n\n"
            f"👥 Total Users: {len(all_users)}\n"
            f"⏳ Pending Deposits: {len(pending_deposits)}\n"
            f"💸 Pending Withdrawals: {len(pending_withdrawals)}\n\n"
            "*Select an option:*"
        )
        
        keyboard = [
            [InlineKeyboardButton(f"⏳ Deposits ({len(pending_deposits)})", callback_data="admin_deposits")],
            [InlineKeyboardButton(f"💸 Withdrawals ({len(pending_withdrawals)})", callback_data="admin_withdrawals")],
            [InlineKeyboardButton("👥 All Users", callback_data="admin_users")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("🔙 Back", callback_data="back")],
        ]
        
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data == "admin_deposits":
        deposits = get_pending_deposits()
        
        if not deposits:
            await query.edit_message_text("✅ No pending deposits!")
            return
        
        text = "⏳ *Pending Deposits*\n\n"
        keyboard = []
        
        for dep in deposits:
            text += f"📝 ID: {dep['id']} | User: {dep['first_name']} | ₦{dep['amount']:,.2f}\n"
            keyboard.append([
                InlineKeyboardButton(f"✅ #{dep['id']} - ₦{dep['amount']:,.0f}", callback_data=f"admin_dep_approve_{dep['id']}"),
                InlineKeyboardButton(f"❌ #{dep['id']}", callback_data=f"admin_dep_reject_{dep['id']}"),
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith("admin_dep_approve_"):
        dep_id = int(query.data.split("_")[-1])
        approve_deposit(dep_id)
        await query.edit_message_text(f"✅ Deposit #{dep_id} approved!")
    
    elif query.data.startswith("admin_dep_reject_"):
        dep_id = int(query.data.split("_")[-1])
        context.user_data['admin_action'] = f"reject_deposit_{dep_id}"
        await query.edit_message_text("Enter rejection reason:")
        return ADMIN_NOTE
    
    elif query.data == "admin_withdrawals":
        withdrawals = get_pending_withdrawals()
        
        if not withdrawals:
            await query.edit_message_text("✅ No pending withdrawals!")
            return
        
        text = "💸 *Pending Withdrawals*\n\n"
        keyboard = []
        
        for wd in withdrawals:
            text += (
                f"📝 ID: {wd['id']} | User: {wd['first_name']}\n"
                f"💰 Amount: {wd['amount']:,.2f}\n"
                f"🏦 {wd['bank_name']} | {wd['account_number']}\n"
                f"👤 {wd['account_name']}\n\n"
            )
            keyboard.append([
                InlineKeyboardButton(f"✅ #{wd['id']}", callback_data=f"admin_wd_approve_{wd['id']}"),
                InlineKeyboardButton(f"❌ #{wd['id']}", callback_data=f"admin_wd_reject_{wd['id']}"),
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    
    elif query.data.startswith("admin_wd_approve_"):
        wd_id = int(query.data.split("_")[-1])
        approve_withdrawal(wd_id)
        await query.edit_message_text(f"✅ Withdrawal #{wd_id} approved!")
    
    elif query.data.startswith("admin_wd_reject_"):
        wd_id = int(query.data.split("_")[-1])
        context.user_data['admin_action'] = f"reject_withdrawal_{wd_id}"
        await query.edit_message_text("Enter rejection reason:")
        return ADMIN_NOTE
    
    elif query.data == "admin_users":
        users = get_all_users()
        text = f"👥 *Total Users: {len(users)}*\n\n"
        
        for u in users[:20]:
            text += f"👤 {u['first_name']} (@{u['username'] or 'N/A'}) | ₦{u['balance']:,.2f}\n"
        
        if len(users) > 20:
            text += f"\n... and {len(users) - 20} more"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# Deposit handler
async def deposit_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        if amount < 1000:
            await update.message.reply_text("❌ Minimum deposit is ₦1,000. Please enter a valid amount:")
            return DEPOSIT_AMOUNT
        
        create_deposit(update.effective_user.id, amount)
        
        await context.bot.send_message(
            config.ADMIN_ID,
            f"🔔 *New Deposit Request*\n\n"
            f"👤 User: {update.effective_user.first_name} (@{update.effective_user.username})\n"
            f"💰 Amount: ₦{amount:,.2f}\n"
            f"ID: {update.effective_user.id}",
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(
            "✅ *Deposit Request Submitted!*\n\n"
            f"Amount: ₦{amount:,.2f}\n"
            "⏳ Your deposit will be reviewed and approved within 24 hours.\n\n"
            "You'll be notified once approved.",
            parse_mode='Markdown'
        )
        
        return ConversationHandler.END
    
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a number:")
        return DEPOSIT_AMOUNT

# Withdrawal handlers
async def withdraw_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
        user = get_user(update.effective_user.id)
        
        if amount < config.MIN_WITHDRAWAL:
            await update.message.reply_text(f"❌ Minimum withdrawal is ₦{config.MIN_WITHDRAWAL:,}:")
            return WITHDRAW_AMOUNT
        
        if amount > user["balance"]:
            await update.message.reply_text(f"❌ Insufficient balance! Your balance: ₦{user['balance']:,.2f}")
            return WITHDRAW_AMOUNT
        
        context.user_data['withdraw_amount'] = amount
        await update.message.reply_text("🏦 Enter your bank name (e.g., Opay, GTBank, Zenith):")
        return WITHDRAW_BANK
    
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a number:")
        return WITHDRAW_AMOUNT

async def withdraw_bank_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['withdraw_bank'] = update.message.text
    await update.message.reply_text("🔢 Enter your account number:")
    return WITHDRAW_ACCOUNT

async def withdraw_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['withdraw_account'] = update.message.text
    await update.message.reply_text("👤 Enter your account name:")
    return WITHDRAW_NAME

async def withdraw_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    account_name = update.message.text
    amount = context.user_data['withdraw_amount']
    bank = context.user_data['withdraw_bank']
    account = context.user_data['withdraw_account']
    
    create_withdrawal(update.effective_user.id, amount, bank, account, account_name)
    
    await context.bot.send_message(
        config.ADMIN_ID,
        f"🔔 *New Withdrawal Request*\n\n"
        f"👤 User: {update.effective_user.first_name}\n"
        f"💰 Amount: ₦{amount:,.2f}\n"
        f"🏦 Bank: {bank}\n"
        f"🔢 Account: {account}\n"
        f"👤 Name: {account_name}",
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(
        "✅ *Withdrawal Request Submitted!*\n\n"
        f"Amount: ₦{amount:,.2f}\n"
        f"Bank: {bank}\n"
        f"Account: {account}\n\n"
        "⏳ Processing time: 0-24 hours",
        parse_mode='Markdown'
    )
    
    return ConversationHandler.END

# Admin note handler
async def admin_note_handler(update: Update, context: ContextTypes.DEFAULT
