# app/email/forms/protocol_form.py
from flask_wtf import FlaskForm
from wtforms import RadioField, SubmitField
from wtforms.validators import DataRequired


class ProtocolForm(FlaskForm):
    protocol = RadioField(
        "Select Protocol",
        choices=[
            ("imap", "IMAP (recommended) — Full mailbox sync"),
            ("pop3", "POP3 — Simple inbox fetch"),
            ("oauth", "OAuth (Gmail/Outlook/Yahoo only)"),
        ],
        validators=[DataRequired()],
        render_kw={"class": "form-check-input"},
    )

    submit = SubmitField("Continue")
