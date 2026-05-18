import sqlite3
from datetime import datetime, timedelta
from config import DATABASE_PATH, INVESTMENT_PLANS, REFERRAL_COMMISSION

def get_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            balance REAL DEFAULT 0,
            referred_by INTEGER,
            referral_code TEXT UNIQUE,
            is_suspended INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Deposits table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            status TEXT DEFAULT 'pending',
            proof TEXT,
            admin_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Withdrawals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            bank_name TEXT,
            account_number TEXT,
            account_name TEXT,
            status TEXT DEFAULT 'pending',
            admin_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Investments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS investments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_name TEXT,
            amount REAL,
            daily_profit REAL,
            total_profit REAL DEFAULT 0,
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            last_profit_date TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Referrals table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER UNIQUE,
            commission_earned REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES users(user_id),
            FOREIGN KEY (referred_id) REFERENCES users(user_id)
        )
    ''')
    
    # Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def create_user(user_id, username, first_name, referred_by=None):
    """Create or get user with welcome bonus"""
    conn = get_connection()
    cursor = conn.cursor()
    
    import secrets
    referral_code = f"NV{user_id}{secrets.token_hex(4)}"
    
    cursor.execute('''
        INSERT OR IGNORE INTO users (user_id, username, first_name, referral_code, referred_by, balance)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, referral_code, referred_by, 500))
    
    if referred_by:
        cursor.execute('''
            INSERT OR IGNORE INTO referrals (referrer_id, referred_id)
            VALUES (?, ?)
        ''', (referred_by, user_id))
    
    conn.commit()
    conn.close()

def get_user(user_id):
    """Get user by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_balance(user_id, amount, description=""):
    """Update user balance"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    
    if description:
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'credit' if amount > 0 else 'debit', abs(amount), description))
    
    conn.commit()
    conn.close()

def create_deposit(user_id, amount, proof=None):
    """Create deposit request"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO deposits (user_id, amount, proof)
        VALUES (?, ?, ?)
    ''', (user_id, amount, proof))
    deposit_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return deposit_id

def create_withdrawal(user_id, amount, bank_name, account_number, account_name):
    """Create withdrawal request"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO withdrawals (user_id, amount, bank_name, account_number, account_name)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, amount, bank_name, account_number, account_name))
    withdrawal_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return withdrawal_id

def create_investment(user_id, plan_name, amount):
    """Create investment and deduct balance"""
    plan = INVESTMENT_PLANS[plan_name]
    daily_profit = amount * (plan["daily_profit"] / 100)
    start_date = datetime.now()
    end_date = start_date + timedelta(days=plan["duration"])
    
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO investments (user_id, plan_name, amount, daily_profit, start_date, end_date, last_profit_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, plan_name, amount, daily_profit, start_date, end_date, start_date))
    
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

def get_active_investments(user_id):
    """Get user's active investments"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM investments 
        WHERE user_id = ? AND is_active = 1 AND end_date > datetime('now')
    ''', (user_id,))
    investments = cursor.fetchall()
    conn.close()
    return investments

def process_daily_profits():
    """Process daily profits for all active investments"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM investments 
        WHERE is_active = 1 AND end_date > datetime('now') AND date(last_profit_date) < date('now')
    ''')
    
    investments = cursor.fetchall()
    processed = 0
    
    for inv in investments:
        user_id = inv["user_id"]
        daily_profit = inv["daily_profit"]
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (daily_profit, user_id))
        
        cursor.execute('''
            UPDATE investments SET total_profit = total_profit + ?, last_profit_date = datetime('now')
            WHERE id = ?
        ''', (daily_profit, inv["id"]))
        
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (user_id, 'credit', daily_profit, f'Daily profit from {inv["plan_name"]} plan'))
        
        # Add referral commission
        cursor.execute('SELECT referred_by FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if user and user["referred_by"]:
            referrer_id = user["referred_by"]
            commission = daily_profit * REFERRAL_COMMISSION
            
            cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (commission, referrer_id))
            cursor.execute('''
                UPDATE referrals SET commission_earned = commission_earned + ?
                WHERE referrer_id = ? AND referred_id = ?
            ''', (commission, referrer_id, user_id))
            cursor.execute('''
                INSERT INTO transactions (user_id, type, amount, description)
                VALUES (?, ?, ?, ?)
            ''', (referrer_id, 'credit', commission, f'Referral commission from user {user_id}'))
        
        processed += 1
    
    conn.commit()
    conn.close()
    return processed

def get_pending_deposits():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*, u.username, u.first_name 
        FROM deposits d JOIN users u ON d.user_id = u.user_id 
        WHERE d.status = 'pending'
    ''')
    deposits = cursor.fetchall()
    conn.close()
    return deposits

def get_pending_withdrawals():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT w.*, u.username, u.first_name, u.balance 
        FROM withdrawals w JOIN users u ON w.user_id = u.user_id 
        WHERE w.status = 'pending'
    ''')
    withdrawals = cursor.fetchall()
    conn.close()
    return withdrawals

def approve_deposit(deposit_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM deposits WHERE id = ?', (deposit_id,))
    deposit = cursor.fetchone()
    
    if deposit:
        cursor.execute('''
            UPDATE deposits SET status = 'approved', approved_at = datetime('now') WHERE id = ?
        ''', (deposit_id,))
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (deposit["amount"], deposit["user_id"]))
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (deposit["user_id"], 'credit', deposit["amount"], 'Deposit approved'))
    
    conn.commit()
    conn.close()

def reject_deposit(deposit_id, admin_note):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE deposits SET status = 'rejected', admin_note = ? WHERE id = ?
    ''', (admin_note, deposit_id))
    conn.commit()
    conn.close()

def approve_withdrawal(withdrawal_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT w.*, u.balance FROM withdrawals w JOIN users u ON w.user_id = u.user_id WHERE w.id = ?', (withdrawal_id,))
    withdrawal = cursor.fetchone()
    
    if withdrawal and withdrawal["amount"] <= withdrawal["balance"]:
        cursor.execute('''
            UPDATE withdrawals SET status = 'approved', approved_at = datetime('now') WHERE id = ?
        ''', (withdrawal_id,))
        
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (withdrawal["amount"], withdrawal["user_id"]))
        cursor.execute('''
            INSERT INTO transactions (user_id, type, amount, description)
            VALUES (?, ?, ?, ?)
        ''', (withdrawal["user_id"], 'debit', withdrawal["amount"], 'Withdrawal approved'))
    
    conn.commit()
    conn.close()

def reject_withdrawal(withdrawal_id, admin_note):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE withdrawals SET status = 'rejected', admin_note = ? WHERE id = ?
    ''', (admin_note, withdrawal_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

# Initialize database on import
init_database()
