from allauth.account.models import EmailAddress
from django.conf import settings
from django.core.mail import send_mail
from django.template import loader

from radiofeed.html import strip_html
from radiofeed.podcasts.models import Podcast


def send_recommendations_email(
    email_address: EmailAddress, num_podcasts: int = 6, **email_settings
) -> None:
    """Sends email to user with a list of recommended podcasts.

    Recommendations based on their subscriptions or latest promoted podcasts.

    Recommended podcasts are saved to the database, so the user is not recommended the same podcasts more than once.

    If no matching podcasts are found, no email is sent.
    """

    user = email_address.user

    # include recommended + promoted

    podcasts = (
        Podcast.objects.published()
        .recommended(user)
        .order_by("-relevance", "-pub_date")
    )[:num_podcasts]

    if podcasts:
        user.recommended_podcasts.add(*podcasts)

        html_message = loader.render_to_string(
            "podcasts/emails/recommendations.html",
            {
                "podcasts": podcasts,
                "recipient": user,
            },
        )

        send_mail(
            f"Hi {user.first_name or user.username}, here are some new podcasts you might like!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_address.email],
            message=strip_html(html_message),
            html_message=html_message,
            **email_settings,
        )
