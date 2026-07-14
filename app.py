from flask import (
    Flask,
    render_template,
    request,
    url_for,
    flash,
    redirect,
)
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from sqlalchemy import func


app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expenses.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.secret_key = "my-secret-key"
db = SQLAlchemy(app)

with app.app_context():
    db.create_all()


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(
        db.String(120), nullable=False
    )  # Need description of the expense
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today())


with app.app_context():
    db.create_all()

CATEGORIES = ["Food", "Transport", "Rent", "Utilities", "Health"]


def parse_date_or_none(date_str: str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


@app.route("/")
def index():
    # Read query string parameters
    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    selected_category = request.args.get("category", "").strip() or None

    # Parse dates
    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)

    if start_date and end_date and end_date < start_date:
        flash("End date must be greater than start date", "error")
        start_date = end_date = None
        start_str = end_str = ""

        # Query expenses
    query = Expense.query
    if start_date:
        query = query.filter(Expense.date >= start_date)
    if end_date:
        query = query.filter(Expense.date <= end_date)

    if selected_category:
        query = query.filter(Expense.category == selected_category)
    else:
        query = query.filter(Expense.category.in_(CATEGORIES))

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total = sum(expense.amount for expense in expenses)

    # Get category data for the pie chart
    category_query = db.session.query(Expense.category, func.sum(Expense.amount))

    if start_date:
        category_query = category_query.filter(Expense.date >= start_date)

    if end_date:
        category_query = category_query.filter(Expense.date <= end_date)

    if selected_category:
        category_query = category_query.filter(Expense.category == selected_category)

    category_rows = category_query.group_by(Expense.category).all()
    category_labels = [category for category, _ in category_rows]
    category_values = [round(float(amount or 0), 2) for _, amount in category_rows]

    # Get day data for the day chart

    day_query = db.session.query(func.date(Expense.date), func.sum(Expense.amount))

    if start_date:
        day_query = day_query.filter(Expense.date >= start_date)
    if end_date:
        day_query = day_query.filter(Expense.date <= end_date)
    if selected_category:
        day_query = day_query.filter(Expense.category == selected_category)
    
    day_expr = func.date(Expense.date)
    day_rows = day_query.group_by(day_expr).order_by(day_expr).all()
    day_labels = [day for day, _ in day_rows]
    day_values = [round(float(amount or 0), 2) for _, amount in day_rows]

    return render_template(
        "index.html",
        categories=CATEGORIES,
        today=date.today().isoformat(),
        expenses=expenses,
        total=total,
        start_str=start_str,
        end_str=end_str,
        selected_category=selected_category,
        category_labels=category_labels,
        category_values=category_values,
        day_labels=day_labels,
        day_values=day_values,
    )


@app.route("/add", methods=["POST"])
def add():

    description = (request.form.get("description") or "").strip()
    amount_str = (request.form.get("amount") or "").strip()
    category = (request.form.get("category") or "").strip()
    date_str = (request.form.get("date") or "").strip()

    if not description or not amount_str or not category or not date_str:
        flash("Please fill in all fields", "error")
        return redirect(url_for("index"))

    if category not in CATEGORIES:
        flash("Please choose a valid category", "error")
        return redirect(url_for("index"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        flash("Amount must be a positive number", "error")
        return redirect(url_for("index"))

    try:
        expense_date = (
            datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        )  # Parse the date string into a date object
    except ValueError:
        expense_date = date.today()

    new_expense = Expense(
        description=description, amount=amount, category=category, date=expense_date
    )
    db.session.add(new_expense)
    db.session.commit()

    flash("Expense added", "success")
    return redirect(url_for("index"))


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash("Expense deleted", "success")
    return redirect(url_for("index"))

    print("Form received:", dict(request.form))
    return make_response("Form received check the console", 200)


if __name__ == "__main__":
    app.run(debug=True, port=4848)
