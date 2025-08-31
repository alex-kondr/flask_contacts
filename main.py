from uuid import uuid4
import pickle

from flask import Flask, render_template, request, url_for, flash, redirect
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.utils import secure_filename
from flask_caching import Cache

from models import db, User, Contact
from config import settings
from forms import SignInForm, SignUpForm, ContactForm


config = {
    "CACHE_TYPE": "SimpleCache",  # Flask-Caching related configs
    "CACHE_DEFAULT_TIMEOUT": 300
}

app = Flask(__name__)
app.secret_key = settings.secret_key
app.config["SQLALCHEMY_DATABASE_URI"] = settings.sqlalchemy_uri
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['MAX_FORM_MEMORY_SIZE'] = 1024 * 1024  # 1MB
app.config['MAX_FORM_PARTS'] = 500
db.init_app(app)
csrf_protect = CSRFProtect(app)
app.config.from_mapping(config)
cache = Cache(app)

login_manager = LoginManager()
login_manager.login_message = "Спочатку увійдіть у систему"
login_manager.login_view = "sign_in"
login_manager.init_app(app)


with app.app_context():
    db.drop_all()
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    user = cache.get(user_id)
    if user:
        user = pickle.loads(user)
        print("Дані з кешу")
    else:
        user = User.query.filter_by(id=user_id).first_or_404()
        cache.set(user_id, pickle.dumps(user))
        print("Пішов запит до бази даних")
    return user


@app.route("/signUp/", methods=["GET", "POST"])
def sign_up():
    sign_up_form = SignUpForm()

    if sign_up_form.validate_on_submit():
        username = sign_up_form.username.data
        password = sign_up_form.password.data
        fullname = sign_up_form.fullname.data
        phone_number = sign_up_form.phone_number.data

        user = User(
            username=username,
            password=password,
            fullname=fullname,
            phone_number=phone_number
        )
        db.session.add(user)
        db.session.commit()
        flash("Ви успішно зареєструвались")
        return redirect(url_for("sign_in"))

    return render_template("sign_up.html", form=sign_up_form)


@app.route("/signIn/", methods=["GET", "POST"])
def sign_in():
    form = SignInForm()

    if not form.validate_on_submit():
        return render_template("sign_in.html", form=form)

    user: User = User.query.filter_by(username=form.username.data).first()
    if not user or not user.is_verify_password(pwd=form.password.data):
        flash("Логін або пароль невірні!")
        return redirect(url_for("sign_in"))

    login_user(user)
    return redirect(url_for("cabinet"))


@app.get("/")
@login_required
def cabinet():
    contacts = cache.get(f"contacts_{current_user.id}")
    if contacts:
        contacts = pickle.loads(contacts)
        print("Контакти з кешу")
    else:
        contacts = current_user.contacts
        cache.set(f"contacts_{current_user.id}", pickle.dumps(contacts))
        print("Контакти з бази даних")
    return render_template("cabinet.html", contacts=contacts)


@app.get("/logout/")
@login_required
def logout():
    logout_user()
    return redirect(url_for("sign_in"))





@app.route("/contact/", methods=["GET", "POST"])
@login_required
def add_contact():
    form = ContactForm()
    if form.validate_on_submit():
        file = form.file.data
        if file and secure_filename(file.filename):
            file_name = secure_filename(file.filename)
            file_path = f"static/img/{uuid4().hex}_{file_name}"
            file.save(file_path)
        else:
            file_path = None

        contact = Contact(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            phone_number=form.phone_number.data,
            bio=form.bio.data,
            city=form.city.data,
            img=file_path,
            user_id=current_user.id
        )
        db.session.add(contact)
        db.session.commit()
        cache.clear()
        return redirect(url_for("cabinet"))

    return render_template("add_contact.html", form=form)


if __name__ == "__main__":
    app.run(debug=True)
