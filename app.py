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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/add", methods=["POST"])
def add():

    description = (request.form.get("description") or "").strip()
    amount_str = (request.form.get("amount") or "").strip()
    category = (request.form.get("category") or "").strip()
    date_str = (request.form.get("date") or "").strip()

    if not description or not amount_str or not category or not date_str:
        flash("Please fill in all fields", "error")
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

    print("Form received:", dict(request.form)) 
    return make_response("Form received check the console", 200)
    
if __name__ == "__main__":
    app.run(debug=True, port=4848)
