
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('admin','member','client')), display_name TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS members (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
 name TEXT NOT NULL, phone TEXT, joined_at TEXT, status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS member_shares (
 id INTEGER PRIMARY KEY AUTOINCREMENT, member_id INTEGER NOT NULL REFERENCES members(id),
 quantity INTEGER NOT NULL CHECK(quantity>0), entry_price REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1, created_at TEXT
);
CREATE TABLE IF NOT EXISTS contributions (
 id INTEGER PRIMARY KEY AUTOINCREMENT, member_id INTEGER NOT NULL REFERENCES members(id),
 type TEXT NOT NULL CHECK(type IN ('initial','monthly','increment','entry')),
 amount REAL NOT NULL CHECK(amount>=0), due_date TEXT, paid_date TEXT, status TEXT NOT NULL DEFAULT 'paid', note TEXT
);
CREATE TABLE IF NOT EXISTS clients (
 id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
 name TEXT NOT NULL, phone TEXT, address TEXT, status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS client_contracts (
 id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL REFERENCES clients(id),
 product_name TEXT NOT NULL, product_cost REAL NOT NULL, profit_rate REAL NOT NULL,
 total_profit REAL NOT NULL, total_sale_price REAL NOT NULL, months INTEGER NOT NULL,
 start_date TEXT, status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS installments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL REFERENCES client_contracts(id) ON DELETE CASCADE,
 installment_no INTEGER NOT NULL, due_date TEXT, amount REAL NOT NULL, principal_due REAL NOT NULL,
 profit_due REAL NOT NULL, status TEXT NOT NULL DEFAULT 'due'
);
CREATE TABLE IF NOT EXISTS installment_payments (
 id INTEGER PRIMARY KEY AUTOINCREMENT, installment_id INTEGER NOT NULL REFERENCES installments(id) ON DELETE CASCADE,
 amount REAL NOT NULL, principal_component REAL NOT NULL, profit_component REAL NOT NULL,
 paid_date TEXT, note TEXT
);
CREATE TABLE IF NOT EXISTS expenses (
 id INTEGER PRIMARY KEY AUTOINCREMENT, expense_type TEXT NOT NULL CHECK(expense_type IN ('product','necessary')),
 title TEXT NOT NULL, amount REAL NOT NULL, expense_date TEXT NOT NULL, description TEXT, recipient TEXT,
 created_by INTEGER REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
