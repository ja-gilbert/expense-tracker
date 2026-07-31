from flask import (
    Flask,
    render_template,
    request,
    url_for,
    flash,
    redirect,
    Response,
)
from flask_sqlalchemy import SQLAlchemy
from datetime import date, datetime
from sqlalchemy import func
import csv
import io
import math


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


def apply_expense_filters(
    query, start_date, end_date, selected_category, exclude_unknown_categories=False
):
    """Apply the shared start/end/category filters to `query`.

    `exclude_unknown_categories` falls back to `Expense.category.in_(CATEGORIES)`
    when no category was chosen, so rows with legacy/invalid categories drop out.
    Only the dashboard's expense table currently does this — the two chart
    queries and the CSV export do not, and that difference is preserved here
    rather than quietly changed. See PLAN.md; making all four consistent is a
    one-line change to this default.
    """
    if start_date:
        query = query.filter(Expense.date >= start_date)
    if end_date:
        query = query.filter(Expense.date <= end_date)

    if selected_category:
        query = query.filter(Expense.category == selected_category)
    elif exclude_unknown_categories:
        query = query.filter(Expense.category.in_(CATEGORIES))

    return query


def parse_expense_form(form, strict_date):
    """Read and validate the expense form fields shared by /add and /edit.

    Returns `(values, amount, expense_date, error)`. `values` holds the raw
    trimmed strings (so a caller can echo them back into the form) and `error`
    is None when everything validated.

    `strict_date` is the one place the two callers legitimately differ: /add
    falls back to today on an unparseable date, while /edit treats it as an
    error rather than silently rewriting a date the expense already has.
    """
    values = {
        "description": (form.get("description") or "").strip(),
        "amount": (form.get("amount") or "").strip(),
        "category": (form.get("category") or "").strip(),
        "date": (form.get("date") or "").strip(),
    }

    if not all(values.values()):
        return values, None, None, "Please fill in all fields"

    if values["category"] not in CATEGORIES:
        return values, None, None, "Please choose a valid category"

    try:
        amount = float(values["amount"])
        # float() happily accepts "nan"/"inf"/"1e999", and both compare False
        # against `<= 0`, so they slip past a bare positivity check: "inf" used
        # to save and turn `total` and the chart values into inf, and "nan"
        # blew up with an IntegrityError at commit time.
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError
    except ValueError:
        return values, None, None, "Amount must be a positive number"

    expense_date = parse_date_or_none(values["date"])
    if expense_date is None:
        if strict_date:
            return values, None, None, "Please enter a valid date"
        expense_date = date.today()

    return values, amount, expense_date, None


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
    query = apply_expense_filters(
        Expense.query,
        start_date,
        end_date,
        selected_category,
        exclude_unknown_categories=True,
    )

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total = sum(expense.amount for expense in expenses)

    # Get category data for the pie chart
    category_query = apply_expense_filters(
        db.session.query(Expense.category, func.sum(Expense.amount)),
        start_date,
        end_date,
        selected_category,
    )

    category_rows = category_query.group_by(Expense.category).all()
    category_labels = [category for category, _ in category_rows]
    category_values = [round(float(amount or 0), 2) for _, amount in category_rows]

    # Get day data for the day chart

    day_query = apply_expense_filters(
        db.session.query(func.date(Expense.date), func.sum(Expense.amount)),
        start_date,
        end_date,
        selected_category,
    )

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

    values, amount, expense_date, error = parse_expense_form(
        request.form, strict_date=False
    )

    if error:
        flash(error, "error")
        return redirect(url_for("index"))

    new_expense = Expense(
        description=values["description"],
        amount=amount,
        category=values["category"],
        date=expense_date,
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

def render_edit_form(expense, form):
    """Render the edit form for `expense` with `form` supplying the field values."""
    return render_template(
        "edit.html",
        expense=expense,
        categories=CATEGORIES,
        today=date.today().isoformat(),
        form=form,
    )


@app.route("/edit/<int:expense_id>", methods=["GET"])
def edit(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    form = {
        "description": expense.description,
        "amount": f"{expense.amount:.2f}",
        "category": expense.category,
        "date": expense.date.isoformat() if expense.date else date.today().isoformat(),
    }
    return render_edit_form(expense, form)


@app.route("/edit/<int:expense_id>", methods=["POST"])
def edit_post(expense_id):
    expense = Expense.query.get_or_404(expense_id)

    # strict_date=True: a bad date is an error here rather than a silent
    # fallback to today, which would lose the date the expense already has.
    values, amount, expense_date, error = parse_expense_form(
        request.form, strict_date=True
    )

    if error:
        # Re-render with what was submitted so the user doesn't lose their edits.
        flash(error, "error")
        return render_edit_form(expense, values)

    expense.description = values["description"]
    expense.amount = amount
    expense.category = values["category"]
    expense.date = expense_date
    db.session.commit()

    flash("Expense updated", "success")
    return redirect(url_for("index"))

@app.route("/export.csv")
def export_csv():

    start_str = (request.args.get("start") or "").strip()
    end_str = (request.args.get("end") or "").strip()
    selected_category = request.args.get("category", "").strip() or None

    start_date = parse_date_or_none(start_str)
    end_date = parse_date_or_none(end_str)

    query = apply_expense_filters(
        Expense.query, start_date, end_date, selected_category
    )

    expenses = query.order_by(Expense.date, Expense.id).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "description", "amount", "category"])

    for expense in expenses:
        writer.writerow([
            expense.date.isoformat(),
            expense.description,
            f"{expense.amount:.2f}",
            expense.category,
        ])

    file_start = start_str or "all"
    file_end = end_str or "all"
    filname = f"expenses_{file_start}_{file_end}.csv"

    return Response(
        output.getvalue(),
        headers={
            "Content-Type": "text/csv",
            "Content-Disposition": f"attachment; filename={filname}"
        },
        mimetype="text/csv"
    )


if __name__ == "__main__":
    app.run(debug=True, port=4848)
