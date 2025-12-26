import sqlite3
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

# ================= CONFIG =================
BOT_TOKEN = "import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(osgetenv("ADMIN_ID"))
MIN_WITHDRAW = 500
REFERRAL_BONUS = 500

# ================= DATABASE =================
db = sqlite3.connect("bot.db", check_same_thread=False)
cur = db.cursor()

cur.execute(""" CREATE TABLE IF NOT EXISTS users (
user_id INTEGER PRIMARY KEY,
balance INTEGER DEFAULT 0,
wallet TEXT,
ref_by INTEGER
) """)

cur.execute(""" CREATE TABLE IF NOT EXISTS tasks (
task_id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT,
rule TEXT,
link TEXT,
reward INTEGER
) """)

cur.execute(""" CREATE TABLE IF NOT EXISTS completed_tasks (
user_id INTEGER,
task_id INTEGER,
UNIQUE(user_id, task_id)
) """)

cur.execute(""" CREATE TABLE IF NOT EXISTS withdraws (
user_id INTEGER,
amount INTEGER,
status TEXT
) """)

cur.execute(""" CREATE TABLE IF NOT EXISTS proofs (
user_id INTEGER,
task_id INTEGER,
status TEXT
) """)

db.commit()

# ================= DATA =================
USER_STATE = {}  # uid: state
USER_TEMP = {}   # For storing task id when sending proof
USER_DATA = {}   # For admin temporary task info
MENU_BTNS = [
    "📊 Dashboard","🎯 Tasks","💰 Withdraw",
    "🏦 Set Wallet","🎁 Bonus","👥 Referrals","ℹ Help","🛠 Admin Panel"
]

# ================= HELPERS =================
def is_admin(uid):
    return uid == ADMIN_ID

def add_user(uid, ref=None):
    cur.execute("INSERT OR IGNORE INTO users (user_id, ref_by) VALUES (?,?)", (uid, ref))
    db.commit()

def get_balance(uid):
    cur.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else 0

def add_balance(uid, amt):
    cur.execute("""
    INSERT INTO users (user_id, balance) VALUES (?,?)
    ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?
    """, (uid, amt, amt))
    db.commit()

def set_wallet(uid, wallet):
    if not wallet.lower().startswith("opay"):
        return False
    cur.execute("UPDATE users SET wallet=? WHERE user_id=?", (wallet, uid))
    db.commit()
    return True

def get_wallet(uid):
    cur.execute("SELECT wallet FROM users WHERE user_id=?", (uid,))
    row = cur.fetchone()
    return row[0] if row else None

def add_task(title, rule, reward, link):
    cur.execute("INSERT INTO tasks (title, rule, reward, link) VALUES (?,?,?,?)", (title, rule, reward, link))
    db.commit()

def remove_task(task_id):
    cur.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
    cur.execute("DELETE FROM proofs WHERE task_id=?", (task_id,))
    cur.execute("DELETE FROM completed_tasks WHERE task_id=?", (task_id,))
    db.commit()

def get_tasks():
    cur.execute("SELECT * FROM tasks")
    return cur.fetchall()

def complete_task(uid, tid, reward):
    cur.execute("SELECT 1 FROM completed_tasks WHERE user_id=? AND task_id=?", (uid, tid))
    if cur.fetchone():
        return False
    add_balance(uid, reward)
    cur.execute("INSERT INTO completed_tasks (user_id, task_id) VALUES (?,?)", (uid, tid))
    db.commit()
    return True

def add_withdraw(uid, amt):
    cur.execute("SELECT 1 FROM withdraws WHERE user_id=? AND status='pending'", (uid,))
    if cur.fetchone():
        return False
    cur.execute("INSERT INTO withdraws (user_id, amount, status) VALUES (?,?,?)", (uid, amt, "pending"))
    db.commit()
    return True

def get_pending_withdraws():
    cur.execute("SELECT user_id, amount FROM withdraws WHERE status='pending'")
    return cur.fetchall()

def get_total_users():
    cur.execute("SELECT COUNT(*) FROM users")
    return cur.fetchone()[0]

def main_menu(uid):
    btns = [
        ["📊 Dashboard", "🎯 Tasks"],
        ["💰 Withdraw", "🏦 Set Wallet"],
        ["🎁 Bonus","👥 Referrals"],
        ["ℹ Help"]
    ]
    if is_admin(uid):
        btns.append(["🛠 Admin Panel"])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

# ================= APPROVE / REJECT HELPERS =================
def approve_proof(uid, task_id):
    cur.execute("SELECT reward FROM tasks WHERE task_id=?", (task_id,))
    reward = cur.fetchone()[0]
    complete_task(uid, task_id, reward)
    cur.execute("DELETE FROM proofs WHERE user_id=? AND task_id=?", (uid, task_id))
    db.commit()

def reject_proof(uid, task_id):
    cur.execute("DELETE FROM proofs WHERE user_id=? AND task_id=?", (uid, task_id))
    db.commit()

def approve_withdraw(uid):
    cur.execute("SELECT amount FROM withdraws WHERE user_id=? AND status='pending'", (uid,))
    amt = cur.fetchone()
    if not amt:
        return
    amt = amt[0]
    cur.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amt, uid))
    cur.execute("UPDATE withdraws SET status='approved' WHERE user_id=?", (uid,))
    db.commit()

def reject_withdraw(uid):
    cur.execute("UPDATE withdraws SET status='rejected' WHERE user_id=?", (uid,))
    db.commit()

# ================= HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    args = context.args
    ref = None
    if args:    
        try:    
            r = int(args[0])    
            if r != uid:    
                ref = r    
        except:    
            pass    
    cur.execute("SELECT 1 FROM users WHERE user_id=?", (uid,))    
    is_new_user = cur.fetchone() is None    
    add_user(uid, ref if is_new_user else None)    
    if is_new_user and ref:    
        add_balance(ref, REFERRAL_BONUS)    
        await context.bot.send_message(ref, f"🎉 You earned {REFERRAL_BONUS} coins! Your friend {update.effective_user.first_name} joined.")
    welcome_text = f"""
🌟✨🚀 WELCOME TO TASK EARN BOT 🚀✨🌟

Hello, {update.effective_user.first_name} 👋

⚡ Pro Tip: Use your referral link to earn bonus coins faster!

📱 Contact Admin: WhatsApp
Message lukuman Umar on WhatsApp. https://wa.me/2349036466194

🌈 Let the rewards begin! 🎁🎉
"""
    kb = ReplyKeyboardMarkup([
        ["📋 Copy Referral Link"],
        ["📊 Dashboard", "🎯 Tasks"],
        ["💰 Withdraw", "🏦 Set Wallet"],
        ["🎁 Bonus", "👥 Referrals"],
        ["ℹ Help"]
    ], resize_keyboard=True)
    await update.message.reply_text(welcome_text, reply_markup=kb, parse_mode="Markdown", disable_web_page_preview=True)

# ================= TEXT HANDLER =================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    state = USER_STATE.get(uid)
    if text in MENU_BTNS:
        USER_STATE[uid] = None
        state = None
    # ===== ADMIN ADD TASK FLOW =====
    if uid == ADMIN_ID:
        state = USER_STATE.get(ADMIN_ID)
        if state in ["task_title","task_rule","task_link","task_reward"]:
            if state == "task_title":
                USER_DATA[ADMIN_ID] = {}
                USER_DATA[ADMIN_ID]['title'] = text
                USER_STATE[ADMIN_ID] = "task_rule"
                await update.message.reply_text("✏️ Send TASK RULE")
                return
            elif state == "task_rule":
                USER_DATA[ADMIN_ID]['rule'] = text
                USER_STATE[ADMIN_ID] = "task_link"
                await update.message.reply_text("✏️ Send TASK LINK (URL)")
                return
            elif state == "task_link":
                USER_DATA[ADMIN_ID]['link'] = text
                USER_STATE[ADMIN_ID] = "task_reward"
                await update.message.reply_text("✏️ Send TASK REWARD (number)")
                return
            elif state == "task_reward":
                if not text.isdigit():
                    await update.message.reply_text("❌ Reward must be a number. Send again.")
                    return
                USER_DATA[ADMIN_ID]['reward'] = int(text)
                data_task = USER_DATA.pop(ADMIN_ID)
                add_task(data_task['title'], data_task['rule'], data_task['reward'], data_task['link'])
                USER_STATE[ADMIN_ID] = None
                await update.message.reply_text(f"✅ Task '{data_task['title']}' added successfully!", reply_markup=main_menu(ADMIN_ID))
                return
    # ===== COPY REFERRAL LINK =====
    if text == "📋 Copy Referral Link":
        referral_link = f"http://t.me/Mojezuwabot?start={uid}"
        await update.message.reply_text(f"📎 Here’s your referral link:\n{referral_link}", reply_markup=main_menu(uid))
        return
    # ===== DASHBOARD =====
    if text == "📊 Dashboard":
        await update.message.reply_text(f"💰 Balance: {get_balance(uid)}")
        return
    # ===== TASKS =====
    elif text == "🎯 Tasks":
        tasks = get_tasks()
        if not tasks:
            await update.message.reply_text("No tasks available")
            return
        for tid, title, rule, link, reward in tasks:
            cur.execute("SELECT status FROM proofs WHERE user_id=? AND task_id=?", (uid, tid))
            proof = cur.fetchone()
            completed = proof and proof[0] != "rejected"
            kb_buttons = [[InlineKeyboardButton("🔗 Visit Task", url=link)]]
            if completed:
                kb_buttons.append([InlineKeyboardButton("📸 Submit Proof", callback_data="done_already")])
            else:
                kb_buttons.append([InlineKeyboardButton("📸 Submit Proof", callback_data=f"proof_{tid}")])
            kb = InlineKeyboardMarkup(kb_buttons)
            await update.message.reply_text(f"📌 {title}\n📜 {rule}\n💰 {reward}\n{'✅ Already completed' if completed else ''}", reply_markup=kb)
        return
    # ===== WITHDRAW =====
    elif text == "💰 Withdraw":
        wallet = get_wallet(uid)
        balance = get_balance(uid)
        if not wallet:
            USER_STATE[uid] = "wallet"
            await update.message.reply_text("⚠ Your wallet is not set. Please send your OPAY wallet details first.")
            return
        USER_STATE[uid] = "withdraw"
        await update.message.reply_text(f"💳 Enter the amount to withdraw (minimum {MIN_WITHDRAW}, your balance: {balance}):")
        return
    # ===== SET WALLET =====
    elif text == "🏦 Set Wallet":
        USER_STATE[uid] = "wallet"
        await update.message.reply_text("Send wallet details (OPAY only)")
        return
    # ===== REFERRALS =====
    elif text == "👥 Referrals":
        referral_link = f"http://t.me/Mojezuwabot?start={uid}"
        referral_text = f"""
🔥✨ INVITE FRIENDS & EARN COINS ✨🔥
📎 {referral_link}
"""
        await update.message.reply_text(referral_text, parse_mode="Markdown", disable_web_page_preview=True)
        return
    # ===== ADMIN PANEL =====
    elif text == "🛠 Admin Panel" and is_admin(uid):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Task", callback_data="add_task")],
            [InlineKeyboardButton("🗑 Remove Task", callback_data="remove_task")],
            [InlineKeyboardButton("👥 Total Users", callback_data="users")],
            [InlineKeyboardButton("💰 Pending Withdrawals", callback_data="withdraws")]
        ])
        await update.message.reply_text("Admin Panel", reply_markup=kb)
        return
    # ===== HANDLE WALLET INPUT =====
    elif state == "wallet":
        if set_wallet(uid, text):
            await update.message.reply_text("✅ Wallet saved successfully.", reply_markup=main_menu(uid))
            USER_STATE[uid] = None
        else:
            await update.message.reply_text("❌ Only OPAY wallet allowed. Send again.", reply_markup=main_menu(uid))
        return
    # ===== HANDLE WITHDRAW INPUT =====
    elif state == "withdraw":
        if not text.isdigit():
            await update.message.reply_text("❌ Enter numbers only")
            return
        amt = int(text)
        balance = get_balance(uid)
        wallet = get_wallet(uid)
        if amt < MIN_WITHDRAW:
            await update.message.reply_text(f"❌ Minimum withdraw amount is {MIN_WITHDRAW}")
            return
        if amt > balance:
            await update.message.reply_text(f"❌ insufficient balance ({balance})")
            return
        if not add_withdraw(uid, amt):
            await update.message.reply_text("⚠ You already have a pending withdraw request.")
            return
        USER_STATE[uid] = None
        kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")
            ]
        ])
        await context.bot.send_message(ADMIN_ID, f"💰 Withdraw Request\nUser: {uid}\nAmount: {amt}\nWallet: {wallet}", reply_markup=kb)
        await update.message.reply_text(f"⏳ Withdraw request of {amt} coins submitted.\n✅ Waiting for admin approval.", reply_markup=main_menu(uid))
        return

# ================= PHOTO HANDLER =================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if USER_STATE.get(uid) != "send_proof":
        return
    task_id = USER_TEMP[uid]
    photo = update.message.photo[-1].file_id
    cur.execute("INSERT INTO proofs VALUES (?,?,?)", (uid, task_id, "pending"))
    db.commit()
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_{uid}_{task_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}_{task_id}")
        ]
    ])
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=photo, caption=f"📸 Proof Submitted\nUser: {uid}\nTask ID: {task_id}", reply_markup=kb)
    USER_STATE.pop(uid)
    USER_TEMP.pop(uid)
    await update.message.reply_text("✅ Proof sent for review", reply_markup=main_menu(uid))

# ================= CALLBACK HANDLER =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid = q.from_user.id

    if data == "done_already":
        await q.message.reply_text("⚠ You have already completed this task or submitted proof!")
        return

    if data.startswith("proof_"):
        tid = int(data.split("_")[1])
        USER_STATE[uid] = "send_proof"
        USER_TEMP[uid] = tid
        await q.message.reply_text("📸 Please send your screenshot proof")
        return

    if not is_admin(uid):
        return

    # ===== APPROVE / REJECT TASK PROOF =====
    if data.startswith("approve_") and data.count("_") == 2:
        _, user_id, task_id = data.split("_")
        approve_proof(int(user_id), int(task_id))
        await context.bot.send_message(int(user_id), "✅ Your task proof has been approved!")
        await q.edit_message_caption("✅ Proof approved")
        return

    if data.startswith("reject_") and data.count("_") == 2:
        _, user_id, task_id = data.split("_")
        reject_proof(int(user_id), int(task_id))
        await context.bot.send_message(int(user_id), "❌ Your task proof was rejected.")
        await q.edit_message_caption("❌ Proof rejected")
        return

    # ===== APPROVE / REJECT WITHDRAW =====
    if data.startswith("approve_") and data.count("_") == 1:
        user_id = int(data.split("_")[1])
        approve_withdraw(user_id)
        await context.bot.send_message(user_id, "✅ Your withdrawal has been approved!")
        await q.edit_message_text("✅ Withdrawal approved")
        return

    if data.startswith("reject_") and data.count("_") == 1:
        user_id = int(data.split("_")[1])
        reject_withdraw(user_id)
        await context.bot.send_message(user_id, "❌ Your withdrawal was rejected!")
        await q.edit_message_text("❌ Withdrawal rejected")
        return

    # ===== ADMIN PANEL LOGIC =====
    if data == "add_task":
        USER_STATE[ADMIN_ID] = "task_title"
        USER_DATA[ADMIN_ID] = {}
        await q.edit_message_text("✏️ Send TASK TITLE")
        return
    elif data == "users":
        await q.edit_message_text(f"👥 Total users: {get_total_users()}")
        return
    elif data == "withdraws":
        pendings = get_pending_withdraws()
        msg = "Pending Withdrawals:\n"
        for u,a in pendings:
            wallet = get_wallet(u)
            msg += f"User:{u}, Amount:{a}, Wallet:{wallet}\n"
        await q.edit_message_text(msg or "No pending withdraws")
        return
    elif data == "remove_task":
        tasks = get_tasks()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"{tid} - {title}", callback_data=f"del_{tid}")] for tid, title, _, _, _ in tasks])
        await q.edit_message_text("Select a task to remove:", reply_markup=kb)
        return
    elif data.startswith("del_"):
        tid = int(data.split("_")[1])
        remove_task(tid)
        await q.edit_message_text(f"✅ Task {tid} removed successfully")
        return

# ================= MAIN =================
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(CallbackQueryHandler(callback_handler))

    print("🤖 Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()