# app/email/forms/config_form.py
from flask_wtf import FlaskForm
from wtforms import (
    StringField, PasswordField, BooleanField, IntegerField,
    SelectField, SubmitField
)
from wtforms.validators import DataRequired, Email, Optional, NumberRange


SECURITY_CHOICES = [
    ("ssl", "SSL/TLS"),
    ("starttls", "STARTTLS"),
    ("none", "None (Not Secure)"),
]


class ConfigForm(FlaskForm):
    # Account
    email_address = StringField("Email Address", validators=[DataRequired(), Email()])
    password = PasswordField("Password / App Password", validators=[Optional()])
    display_name = StringField("Display Name", validators=[Optional()])
    reply_to = StringField("Reply-To Address", validators=[Optional(), Email()])

    # Incoming server
    incoming_host = StringField("Incoming Host", validators=[Optional()])
    incoming_port = IntegerField("Incoming Port", validators=[Optional(), NumberRange(min=1, max=65535)])
    incoming_security = SelectField("Incoming Security", choices=SECURITY_CHOICES)

    # Outgoing server
    outgoing_host = StringField("Outgoing Host", validators=[Optional()])
    outgoing_port = IntegerField("Outgoing Port", validators=[Optional(), NumberRange(min=1, max=65535)])
    outgoing_security = SelectField("Outgoing Security", choices=SECURITY_CHOICES)
    outgoing_auth_custom = BooleanField("Use separate authentication for outgoing")

    # Advanced
    use_idle = BooleanField("Enable IMAP IDLE (push notifications)")
    sync_window_days = IntegerField("Sync window (days)", default=30, validators=[Optional()])
    allow_self_signed = BooleanField("Allow self-signed certificates")

    submit = SubmitField("Test & Continue")
