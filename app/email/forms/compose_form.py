# app/email/forms/compose_form.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email

class ComposeForm(FlaskForm):
    to = StringField("To", validators=[DataRequired()])
    subject = StringField("Subject", validators=[DataRequired()])
    body = TextAreaField("Body")
    is_html = BooleanField("Send as HTML")
    submit = SubmitField("Send")
