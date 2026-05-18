import os
import logging
import asyncio
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in Environment Variables!")

PLANS = {
    "starter": {"name": "Starter", "amt": 3000},
    "silver": {"name": "Silver", "amt": 5000},
    "gold": {"name": "Gold", "amt": 10000},
    "premium": {"name": "Premium", "amt": 20000},
    "diamond": {"name": "Diamond", "amt": 25000},
    "elite": {"name": "Elite", "amt": 40000},
    "vip": {"name": "VIP", "amt": 50000}
}

# --- DATABASE SETUP (SQLite) ---
import sqlite3
def get_db():
    conn = sqlite3.connect("nexavault.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    c = get_db().cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 500, username TEXT);
        CREATE TABLE IF NOT EXISTS deposits(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INT, amount REAL, status TEXT DEFAULT 'pending');
        CREATE TABLE IF NOT EXISTS withdrawals(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INT, amount REAL, bank TEXT, acc TEXT, status TEXT DEFAULT 'pending');
    """)
    get_db().commit(); get_db().close()

init_db()

# --- BOT HANDLERS ---
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    c = get_db().cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id, username, balance) VALUES(?,?,500)", (u.id, u.username))
    get_db().commit(); get_db().close()
    
    kb = [[InlineKeyboardButton("💰 Wallet", callback_data="wallet")],
          [InlineKeyboardButton("📈 Invest", callback_data="invest")],
          [InlineKeyboardButton("💳 Deposit", callback_data="deposit")],
          [InlineKeyboardButton("💸 Withdraw", callback_data="withdraw")]]
    await update.message.reply_text(f"👋 Welcome {u.first_name}! ₦500 bonus credited.", reply_markup=InlineKeyboardMarkup(kb))

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    
    c = get_db().cursor()
    c.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    bal = c.fetchone()["balance"]
    get_db().close()

    if q.data == "wallet":
        await q.edit_message_text(f"💰 *Balance*\n₦{bal:,.2f}", parse_mode='Markdown')
    elif q.data == "invest":
        kb = [[InlineKeyboardButton(f"{p['name']} ₦{p['amt']:,}", callback_data=f"i_{k}")] for k,p in PLANS.items()]
        await q.edit_message_text("📈 Choose Plan (25% daily profit):", reply_markup=InlineKeyboardMarkup(kb))
    elif q.data.startswith("i_"):
        plan = PLANS[q.data.split("_")[1]]
        if bal >= plan["amt"]:
            c = get_db().cursor()
            c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (plan["amt"], uid))
            get_db().commit(); get_db().close()
            await q.edit_message_text(f"✅ Invested {plan['amt']:,} in {plan['name']}!\nDaily Profit: ₦{plan['amt']*0.25:,.2f}")
        else:
            await q.edit_message_text(f"❌ Insufficient balance. Need ₦{plan['amt']:,}. You have ₦{bal:,.2f}")
    elif q.data == "deposit":
        await q.edit_message_text("💳 *Deposit Instructions*\n\nBank: Opay\nName: Omotayo Anike Olumide\nAccount: `8037840735`\n\nAfter sending, type: `/confirm_deposit 5000`", parse_mode='Markdown')
    elif q.data == "withdraw":
        if bal < 500: await q.edit_message_text(" Minimum withdrawal is ₦500")
        else: await q.edit_message_text("💸 To withdraw, type: `/withdraw_request 1000 Opay 8037840735`")

async def confirm_dep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(ctx.args[0])
        uid = update.effective_user.id
        c = get_db().cursor()
        c.execute("INSERT INTO deposits(user_id, amount) VALUES(?,?)", (uid, amt))
        get_db().commit(); get_db().close()
        await update.message.reply_text(f"✅ Deposit ₦{amt:,.2f} submitted. Admin will approve.")
    except: await update.message.reply_text("❌ Usage: /confirm_deposit 5000")

async def approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != 0: return # Change 0 to your Admin ID
    try:
        did = int(ctx.args[0])
        c = get_db().cursor()
        c.execute("SELECT user_id, amount FROM deposits WHERE id=?", (did,))
        dep = c.fetchone()
        if dep:
            c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (dep["amount"], dep["user_id"]))
            c.execute("UPDATE deposits SET status='approved' WHERE id=?", (did,))
            get_db().commit(); get_db().close()
            await update.message.reply_text(f"✅ Deposit #{did} approved.")
    except: await update.message.reply_text("❌ /approve <deposit_id>")

# --- RENDER WEB SERVER (Keeps it alive) ---
async def web_server():
    web_app = web.Application()
    # This route tells Render the app is healthy
    web_app.router.add_get('/', lambda request: web.Response(text="NexaVault Bot is Running ✅"))
    
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"🌐 Web server running on port {PORT}")
    
    # Keep server alive forever
    while True:
        await asyncio.sleep(3600)

# --- MAIN EXECUTION ---
async def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("confirm_deposit", confirm_dep))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CallbackQueryHandler(buttons))
    
    print(" Bot starting...")
    
    # Run Bot and Web Server together
    await asyncio.gather(
        application.run_polling(drop_pending_updates=True),
        web_server()
    )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
