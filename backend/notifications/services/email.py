"""Envoi des emails transactionnels.

Le service ne connaît aucun fournisseur : il passe par le backend email de
Django, configurable par variable d'environnement (console en local, SMTP
avec Mailpit sous Docker, fournisseur réel en production).

Aucun mot de passe et aucun token n'est journalisé (spec 05 §15).
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from notifications.models import EmailLog, EmailStatus, EmailType

logger = logging.getLogger(__name__)


def _send(
    *,
    email_type: str,
    recipient: str | None,
    subject: str,
    template: str,
    context: dict,
    user=None,
) -> EmailLog | None:
    """Rend, envoie et journalise un email.

    Renvoie `None` si aucun destinataire n'est connu : l'email est facultatif
    dans ce projet (spec 01 §1), son absence n'est pas une erreur.
    """
    if not recipient:
        return None

    text_body = render_to_string(f"notifications/emails/{template}.txt", context)
    html_body = render_to_string(f"notifications/emails/{template}.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    message.attach_alternative(html_body, "text/html")

    try:
        message.send(fail_silently=False)
    # Un échec d'envoi est journalisé mais ne doit jamais faire échouer
    # l'action métier qui l'a déclenché (acceptation, reset...).
    except Exception as exc:
        logger.warning("Échec d'envoi de l'email %s (%s)", email_type, type(exc).__name__)
        return EmailLog.objects.create(
            user=user,
            email_type=email_type,
            recipient=recipient,
            status=EmailStatus.FAILED,
            # Type de l'exception uniquement : jamais le contenu du message.
            provider_response_summary=type(exc).__name__,
        )

    return EmailLog.objects.create(
        user=user,
        email_type=email_type,
        recipient=recipient,
        status=EmailStatus.SENT,
    )


def send_account_accepted_email(user) -> EmailLog | None:
    """Prévient l'utilisateur que sa demande de compte a été acceptée."""
    return _send(
        email_type=EmailType.ACCOUNT_ACCEPTED,
        recipient=user.email,
        subject="Votre compte MyFitnessPalworld a été activé",
        template="account_accepted",
        context={
            "first_name": user.first_name,
            "username": user.username,
            "login_url": f"{settings.FRONTEND_URL}/connexion",
        },
        user=user,
    )


def send_account_rejected_email(*, recipient: str | None, first_name: str) -> EmailLog | None:
    """Prévient le demandeur que sa demande de compte a été refusée.

    Aucun `User` n'existe à ce moment : la trace est enregistrée sans
    utilisateur associé.
    """
    return _send(
        email_type=EmailType.ACCOUNT_REJECTED,
        recipient=recipient,
        subject="Votre demande de compte MyFitnessPalworld",
        template="account_rejected",
        context={"first_name": first_name},
    )


def send_password_reset_email(user, reset_url: str) -> EmailLog | None:
    """Envoie le lien de réinitialisation.

    Le mot de passe n'est jamais envoyé par email et l'URL n'est pas
    journalisée puisqu'elle contient le token.
    """
    return _send(
        email_type=EmailType.PASSWORD_RESET,
        recipient=user.email,
        subject="Réinitialisation de votre mot de passe MyFitnessPalworld",
        template="password_reset",
        context={
            "first_name": user.first_name,
            "username": user.username,
            "reset_url": reset_url,
            "validity_minutes": settings.PASSWORD_RESET_TIMEOUT // 60,
        },
        user=user,
    )
