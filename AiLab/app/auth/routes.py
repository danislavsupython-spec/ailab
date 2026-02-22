from flask import (
    render_template,
    request,
    flash,
    redirect,
    url_for,
)
from flask_login import current_user
from app.auth import blueprint
from app.base.models import User, UserProfile
from app.base.forms import LoginForm, RegistrationForm
from app import db
from urllib.parse import urlsplit
from flask_login import login_user, logout_user
from werkzeug.utils import secure_filename
from app.base.funcs import generate_qr_code
import sqlalchemy as sa
import os
from app.base.config import USER_FILES_PATH


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("ide_blueprint.ide"))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.scalar(sa.select(User).where(User.email == form.email.data))
        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password")
            return redirect(url_for("auth_blueprint.login"))
        login_user(user)

        next_page = request.args.get("next")
        if not next_page or urlsplit(next_page).netloc != "":
            next_page = url_for("ide_blueprint.ide")
        return redirect(next_page)
    # Если запрос GET или форма не прошла валидацию, возвращаем страницу входа
    return render_template("login.html", title="Sign In", form=form)


@blueprint.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth_blueprint.login"))


def _get_fullname(last_name: str, first_name: str, middle_name: str) -> str:
    full_name = " ".join(filter(None, [last_name, first_name, middle_name]))
    return full_name


def _create_user_profile(user: User, form: RegistrationForm):
    full_name = _get_fullname(
        form.last_name.data, form.first_name.data, form.middle_name.data
    )

    user.profile = UserProfile(
        email=form.email.data, full_name=full_name, phone="", position=""
    )
    user.set_password(form.password.data)
    user.profile.profile_photo = "standart.png"


@blueprint.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("ide_blueprint.ide"))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            last_name=form.last_name.data,
            first_name=form.first_name.data,
            middle_name=form.middle_name.data,
            email=form.email.data,
        )

        _create_user_profile(user, form)

        qr_filename = generate_qr_code(user.id, user.email, False)
        user.profile.qr_photo = qr_filename

        db.session.add(user)
        db.session.commit()
        qr_filename = generate_qr_code(user.id, user.email, True)

        filename = secure_filename("main.py")
        save_path = os.path.join(USER_FILES_PATH, str(user.id), filename)

        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w") as f:
            f.write("# Your content here\n")  # Пример записи в файлё
            f.close

        flash("Congratulations, you are now a registered user!")
        return redirect(url_for("auth_blueprint.login"))
    return render_template("register.html", title="Register", form=form)
