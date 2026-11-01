# Al Haya Initiative

## Run locally
1. Install Python 3.10+
2. Open terminal in this folder
3. `pip install -r requirements.txt`
4. `python app.py`
5. Open `http://127.0.0.1:5000`
6. Use **Initial Setup** to create the first Admin.

The database starts empty. No demo members, clients, products, or transactions are included.

## Core rules implemented
- Initial, monthly and increment contributions are tracked.
- Total Capital = Initial + Monthly + Increment + Recognized Profit - Necessary Expenses.
- Product expenses are tracked separately and do not permanently reduce Capital.
- Client principal recovery is tracked separately from Capital.
- Profit is recognized proportionally when installment payments are received.
- Share Value = Total Capital / Total Active Shares.
- Admin, Member and Client roles are supported.
