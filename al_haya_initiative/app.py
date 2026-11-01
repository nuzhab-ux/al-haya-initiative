
import os, sqlite3, secrets
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from flask import Flask, g, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["DATABASE"] = os.path.join(os.path.dirname(__file__), "al_haya.db")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_=None):
    x = g.pop("db", None)
    if x: x.close()

def q(sql, args=()):
    cur = db().execute(sql, args); db().commit(); return cur

def one(sql, args=()):
    return db().execute(sql, args).fetchone()

def all_(sql, args=()):
    return db().execute(sql, args).fetchall()

def money(v):
    return float(Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def init_db():
    schema = open(os.path.join(os.path.dirname(__file__), "schema.sql"), encoding="utf-8").read()
    db().executescript(schema); db().commit()

@app.cli.command("init-db")
def init_db_command():
    init_db()
    print("Database initialized.")

def current_user():
    uid = session.get("uid")
    return one("SELECT * FROM users WHERE id=?", (uid,)) if uid else None

@app.context_processor
def inject():
    return {"me": current_user(), "fmt": lambda x: f"৳{money(x):,.2f}"}

def login_required(*roles):
    def deco(fn):
        from functools import wraps
        @wraps(fn)
        def wrapped(*a, **kw):
            u = current_user()
            if not u: return redirect(url_for("login"))
            if roles and u["role"] not in roles: abort(403)
            return fn(*a, **kw)
        return wrapped
    return deco

def setting(key, default="0"):
    r = one("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default

def set_setting(key, value):
    q("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

def capital_summary():
    # Core rule: capital = member contributions + recognized profit - necessary expense.
    initial = one("SELECT COALESCE(SUM(amount),0) v FROM contributions WHERE type='initial' AND status='paid'")["v"]
    monthly = one("SELECT COALESCE(SUM(amount),0) v FROM contributions WHERE type='monthly' AND status='paid'")["v"]
    increment = one("SELECT COALESCE(SUM(amount),0) v FROM contributions WHERE type='increment' AND status='paid'")["v"]
    profit = one("SELECT COALESCE(SUM(profit_component),0) v FROM installment_payments")["v"]
    necessary = one("SELECT COALESCE(SUM(amount),0) v FROM expenses WHERE expense_type='necessary'")["v"]
    capital = initial + monthly + increment + profit - necessary
    shares = one("SELECT COALESCE(SUM(quantity),0) v FROM member_shares WHERE active=1")["v"]
    members = one("SELECT COUNT(*) v FROM members WHERE status='active'")["v"]
    return {
        "initial": money(initial), "monthly": money(monthly), "increment": money(increment),
        "profit": money(profit), "necessary_expense": money(necessary),
        "total_capital": money(capital), "total_shares": int(shares), "total_members": int(members),
        "share_value": money(capital / shares) if shares else 0
    }

def recovery_summary():
    product_cost = one("SELECT COALESCE(SUM(product_cost),0) v FROM client_contracts")["v"]
    principal = one("SELECT COALESCE(SUM(principal_component),0) v FROM installment_payments")["v"]
    total_sale = one("SELECT COALESCE(SUM(total_sale_price),0) v FROM client_contracts")["v"]
    paid = one("SELECT COALESCE(SUM(amount),0) v FROM installment_payments")["v"]
    expected_profit = one("SELECT COALESCE(SUM(total_profit),0) v FROM client_contracts")["v"]
    recognized_profit = one("SELECT COALESCE(SUM(profit_component),0) v FROM installment_payments")["v"]
    return {
        "total_product_cost": money(product_cost),
        "principal_recovered": money(principal),
        "principal_outstanding": money(product_cost-principal),
        "total_contract_value": money(total_sale),
        "total_client_paid": money(paid),
        "expected_profit": money(expected_profit),
        "recognized_profit": money(recognized_profit),
        "remaining_potential_profit": money(expected_profit-recognized_profit)
    }

@app.route("/")
def home():
    if not current_user():
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

@app.route("/setup", methods=["GET","POST"])
def setup():
    if one("SELECT id FROM users LIMIT 1"):
        return redirect(url_for("login"))
    if request.method == "POST":
        username=request.form["username"].strip()
        password=request.form["password"]
        if not username or len(password)<8:
            flash("Username দিন এবং অন্তত 8 অক্ষরের password দিন।","danger")
        else:
            q("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?, 'admin', ?)",
              (username, generate_password_hash(password), request.form.get("display_name") or "Administrator"))
            set_setting("monthly_per_share", request.form.get("monthly_per_share") or 500)
            set_setting("increment_per_share", request.form.get("increment_per_share") or 2000)
            set_setting("increment_interval_months", request.form.get("increment_interval_months") or 6)
            flash("Admin account তৈরি হয়েছে। এখন login করুন।","success")
            return redirect(url_for("login"))
    return render_template("setup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        u=one("SELECT * FROM users WHERE username=?", (request.form["username"].strip(),))
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear(); session["uid"]=u["id"]
            return redirect(url_for("dashboard"))
        flash("Login তথ্য সঠিক নয়।","danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

@app.route("/dashboard")
@login_required()
def dashboard():
    u=current_user()
    if u["role"]=="member":
        member=one("SELECT * FROM members WHERE user_id=?", (u["id"],))
        if not member: return render_template("member_dashboard.html", member=None, summary=capital_summary())
        mine=one("SELECT COALESCE(SUM(quantity),0) v FROM member_shares WHERE member_id=? AND active=1",(member["id"],))["v"]
        paid=one("SELECT COALESCE(SUM(amount),0) v FROM contributions WHERE member_id=? AND status='paid'",(member["id"],))["v"]
        return render_template("member_dashboard.html", member=member, my_shares=mine, my_paid=money(paid), summary=capital_summary())
    if u["role"]=="client":
        client=one("SELECT * FROM clients WHERE user_id=?", (u["id"],))
        contracts=all_("SELECT * FROM client_contracts WHERE client_id=? ORDER BY id DESC",(client["id"],)) if client else []
        return render_template("client_dashboard.html", client=client, contracts=contracts)
    return render_template("admin_dashboard.html", summary=capital_summary(), recovery=recovery_summary())

@app.route("/members")
@login_required("admin")
def members():
    return render_template("members.html", members=all_("SELECT m.*, COALESCE(SUM(CASE WHEN s.active=1 THEN s.quantity ELSE 0 END),0) shares FROM members m LEFT JOIN member_shares s ON s.member_id=m.id GROUP BY m.id ORDER BY m.id DESC"))

@app.route("/members/new", methods=["GET","POST"])
@login_required("admin")
def member_new():
    if request.method=="POST":
        name=request.form["name"].strip(); shares=int(request.form["shares"])
        username=request.form.get("username","").strip(); password=request.form.get("password","")
        user_id=None
        if username:
            if one("SELECT id FROM users WHERE username=?",(username,)): flash("Username ইতোমধ্যে আছে।","danger"); return redirect(request.url)
            user_id=q("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?, 'member',?)",(username,generate_password_hash(password or "ChangeMe123!"),name)).lastrowid
        mid=q("INSERT INTO members(user_id,name,phone,joined_at,status) VALUES(?,?,?,?, 'active')",(user_id,name,request.form.get("phone"),date.today().isoformat())).lastrowid
        current=capital_summary()
        entry_per_share=current["share_value"]
        # If no shares exist yet, admin may define initial amount through contribution; entry price is current share value.
        q("INSERT INTO member_shares(member_id,quantity,entry_price,active,created_at) VALUES(?,?,?,?,?)",(mid,shares,entry_per_share,1,date.today().isoformat()))
        entry_amount=money(entry_per_share*shares)
        if entry_amount>0:
            q("INSERT INTO contributions(member_id,type,amount,due_date,paid_date,status,note) VALUES(?,?,?,?,?,?,?)",(mid,"entry",entry_amount,date.today().isoformat(),date.today().isoformat(),"paid","New member share entry at current share value"))
        flash("Member ও shares যোগ হয়েছে।","success"); return redirect(url_for("members"))
    return render_template("member_new.html", summary=capital_summary())

@app.route("/contributions", methods=["GET","POST"])
@login_required("admin")
def contributions():
    if request.method=="POST":
        mid=int(request.form["member_id"]); typ=request.form["type"]; amount=money(request.form["amount"])
        q("INSERT INTO contributions(member_id,type,amount,due_date,paid_date,status,note) VALUES(?,?,?,?,?,?,?)",
          (mid,typ,amount,request.form.get("due_date") or date.today().isoformat(),request.form.get("paid_date") or date.today().isoformat(),"paid",request.form.get("note")))
        flash("Contribution record করা হয়েছে।","success"); return redirect(url_for("contributions"))
    return render_template("contributions.html", rows=all_("SELECT c.*,m.name FROM contributions c JOIN members m ON m.id=c.member_id ORDER BY c.id DESC LIMIT 200"), members=all_("SELECT id,name FROM members WHERE status='active' ORDER BY name"), monthly_per_share=setting("monthly_per_share"), increment_per_share=setting("increment_per_share"))

@app.route("/expenses", methods=["GET","POST"])
@login_required("admin")
def expenses():
    if request.method=="POST":
        typ=request.form["expense_type"]
        q("INSERT INTO expenses(expense_type,title,amount,expense_date,description,recipient,created_by) VALUES(?,?,?,?,?,?,?)",
          (typ,request.form["title"],money(request.form["amount"]),request.form.get("expense_date") or date.today().isoformat(),request.form.get("description"),request.form.get("recipient"),current_user()["id"]))
        flash("Expense record করা হয়েছে।","success"); return redirect(url_for("expenses"))
    return render_template("expenses.html", rows=all_("SELECT * FROM expenses ORDER BY id DESC LIMIT 200"))

@app.route("/clients")
@login_required("admin")
def clients():
    return render_template("clients.html", clients=all_("SELECT * FROM clients ORDER BY id DESC"))

@app.route("/clients/new", methods=["GET","POST"])
@login_required("admin")
def client_new():
    if request.method=="POST":
        name=request.form["name"].strip(); username=request.form.get("username","").strip(); user_id=None
        if username:
            if one("SELECT id FROM users WHERE username=?",(username,)): flash("Username ইতোমধ্যে আছে।","danger"); return redirect(request.url)
            user_id=q("INSERT INTO users(username,password_hash,role,display_name) VALUES(?,?, 'client',?)",(username,generate_password_hash(request.form.get("password") or "ChangeMe123!"),name)).lastrowid
        q("INSERT INTO clients(user_id,name,phone,address,status) VALUES(?,?,?,?, 'active')",(user_id,name,request.form.get("phone"),request.form.get("address")))
        flash("Client তৈরি হয়েছে।","success"); return redirect(url_for("clients"))
    return render_template("client_new.html")

@app.route("/contracts", methods=["GET","POST"])
@login_required("admin")
def contracts():
    if request.method=="POST":
        client_id=int(request.form["client_id"]); cost=money(request.form["product_cost"]); rate=Decimal(request.form["profit_rate"])/Decimal(100)
        months=int(request.form["months"])
        profit=money(Decimal(str(cost))*rate); sale=money(cost+profit)
        cid=q("""INSERT INTO client_contracts(client_id,product_name,product_cost,profit_rate,total_profit,total_sale_price,months,start_date,status)
                 VALUES(?,?,?,?,?,?,?,?, 'active')""",(client_id,request.form["product_name"],cost,float(rate*100),profit,sale,months,request.form.get("start_date") or date.today().isoformat())).lastrowid
        # Equal allocation by default; last installment absorbs rounding.
        for n in range(1,months+1):
            principal=money(cost/months if n<months else cost-money((cost/months)*(months-1)))
            pft=money(profit/months if n<months else profit-money((profit/months)*(months-1)))
            amt=money(principal+pft)
            q("INSERT INTO installments(contract_id,installment_no,due_date,amount,principal_due,profit_due,status) VALUES(?,?,?,?,?,?, 'due')",
              (cid,n,date.today().isoformat(),amt,principal,pft))
        flash("Client contract ও installment schedule তৈরি হয়েছে।","success"); return redirect(url_for("contracts"))
    return render_template("contracts.html", contracts=all_("SELECT cc.*,c.name client_name FROM client_contracts cc JOIN clients c ON c.id=cc.client_id ORDER BY cc.id DESC"), clients=all_("SELECT id,name FROM clients WHERE status='active' ORDER BY name"))

@app.route("/contracts/<int:cid>")
@login_required()
def contract_detail(cid):
    c=one("SELECT cc.*,cl.name client_name FROM client_contracts cc JOIN clients cl ON cl.id=cc.client_id WHERE cc.id=?",(cid,))
    if not c: abort(404)
    u=current_user()
    if u["role"]=="client":
        cl=one("SELECT * FROM clients WHERE user_id=?",(u["id"],))
        if not cl or cl["id"]!=c["client_id"]: abort(403)
    inst=all_("SELECT i.*, COALESCE(SUM(p.amount),0) paid FROM installments i LEFT JOIN installment_payments p ON p.installment_id=i.id WHERE i.contract_id=? GROUP BY i.id ORDER BY i.installment_no",(cid,))
    return render_template("contract_detail.html", c=c, installments=inst)

@app.route("/installments/<int:iid>/pay", methods=["POST"])
@login_required("admin")
def installment_pay(iid):
    inst=one("SELECT * FROM installments WHERE id=?",(iid,))
    if not inst: abort(404)
    already=one("SELECT COALESCE(SUM(amount),0) v FROM installment_payments WHERE installment_id=?",(iid,))["v"]
    remaining=money(inst["amount"]-already)
    amount=money(request.form.get("amount") or remaining)
    if amount<=0 or amount>remaining+0.01:
        flash("Payment amount সঠিক নয়।","danger"); return redirect(url_for("contract_detail",cid=inst["contract_id"]))
    ratio_principal=Decimal(str(inst["principal_due"])) / Decimal(str(inst["amount"])) if inst["amount"] else Decimal(0)
    principal=money(Decimal(str(amount))*ratio_principal); profit=money(amount-principal)
    q("INSERT INTO installment_payments(installment_id,amount,principal_component,profit_component,paid_date,note) VALUES(?,?,?,?,?,?)",
      (iid,amount,principal,profit,request.form.get("paid_date") or date.today().isoformat(),request.form.get("note")))
    newpaid=already+amount
    q("UPDATE installments SET status=? WHERE id=?",("paid" if newpaid>=inst["amount"]-0.01 else "partial",iid))
    flash("Installment payment recorded; profit automatically recognized হয়েছে।","success")
    return redirect(url_for("contract_detail",cid=inst["contract_id"]))

@app.route("/recovery")
@login_required("admin")
def recovery():
    return render_template("recovery.html", summary=recovery_summary(), contracts=all_("SELECT cc.*,c.name client_name FROM client_contracts cc JOIN clients c ON c.id=cc.client_id ORDER BY cc.id DESC"))

@app.route("/settings", methods=["GET","POST"])
@login_required("admin")
def settings():
    if request.method=="POST":
        for k in ["monthly_per_share","increment_per_share","increment_interval_months"]:
            set_setting(k, request.form[k])
        flash("Settings updated.","success"); return redirect(url_for("settings"))
    return render_template("settings.html", monthly=setting("monthly_per_share"), increment=setting("increment_per_share"), interval=setting("increment_interval_months"))

if __name__ == "__main__":
    with app.app_context(): init_db()
    app.run(debug=True)
