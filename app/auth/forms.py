# app/auth/forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField("Корисничко име", validators=[DataRequired()])
    password = PasswordField("Лозинка", validators=[DataRequired()])
    submit = SubmitField("Најави се")
