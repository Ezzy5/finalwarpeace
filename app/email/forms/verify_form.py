# app/email/forms/verify_form.py
from flask_wtf import FlaskForm
from wtforms import BooleanField, SubmitField


class VerifyForm(FlaskForm):
    send_test_mail = BooleanField("Send a test email to myself on success")
    submit = SubmitField("Verify & Connect")
