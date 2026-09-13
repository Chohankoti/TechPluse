import smtplib
from .models import PostMetadata
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MailManager:
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 465

    def __init__(self, from_email: str, to_email: str, app_password: str):
        self.from_email = from_email
        self.to_email = to_email
        self.app_password = app_password
        if not self.from_email or not self.to_email or not self.app_password:
            logger.warning("MailManager initialized with incomplete email credentials.")

    def sendRelevantPosts(self, posts: list[PostMetadata]):
        if not posts:
            logger.info("No relevant posts to send.")
            return
        now = datetime.now()
        current_time = now.strftime("%B %d, %Y") + " | " + now.strftime("%I:%M %p %Z")
        user_name = self.to_email.split('@')[0].replace('_', ' ').replace('.', ' ').title()

        read_first_posts = sorted(
            (post for post in posts if post.read_first),
            key=lambda post: post.relevance_score,
            reverse=True
        )

        read_later_posts = sorted(
            (post for post in posts if not post.read_first),
            key=lambda post: post.relevance_score,
            reverse=True
        )

        logger.info(
            "Preparing digest email with %d relevant posts (%d Read First, %d Read Later)...",
            len(posts),
            len(read_first_posts),
            len(read_later_posts)
        )

        html = self._buildRelevantPostsHtml(
            read_first_posts,
            read_later_posts,
            user_name
        )

        self._sendMail(
            subject=f"TechPulse - {current_time}",
            html=html
        )

    def sendPipelinefail(self, message: str):
        logger.error("Preparing pipeline failure alert email: %s", message)
        now = datetime.now()
        current_time = now.strftime("%B %d, %Y") + " | " + now.strftime("%I:%M %p %Z")

        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="
            margin: 0;
            padding: 40px 16px;
            background-color: #F5EBDD;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            color: #413333;
        ">
            <div style="
                max-width: 600px;
                margin: auto;
                background: #ffffff;
                border-radius: 16px;
                padding: 32px;
                border: 1px solid #e2d9cd;
                box-shadow: 0 4px 12px rgba(65, 51, 51, 0.05);
            ">
                <h2 style="margin-top: 0; color: #F2765E; font-size: 22px; font-weight: 700;">
                    TechPulse Pipeline Failed
                </h2>

                <p style="line-height: 1.6; color: #413333; font-size: 15px;">
                    {message}
                </p>
            </div>
        </body>
        </html>
        """

        self._sendMail(
            subject=f"TechPulse - Pipeline Failed - {current_time}",
            html=html
        )

    def _sendMail(self, subject: str, html: str):
        if not self.from_email or not self.to_email or not self.app_password:
            logger.error("Cannot send email: missing configuration (from_email, to_email, or app_password).")
            return

        mail = MIMEMultipart("alternative")
        mail["From"] = self.from_email
        mail["To"] = self.to_email
        mail["Subject"] = subject

        mail.attach(MIMEText(html, "html", "utf-8"))

        try:
            logger.info("Connecting to SMTP server %s:%d to send email...", self.SMTP_HOST, self.SMTP_PORT)
            with smtplib.SMTP_SSL(self.SMTP_HOST, self.SMTP_PORT) as server:
                server.login(self.from_email, self.app_password)
                server.sendmail(
                    self.from_email,
                    self.to_email,
                    mail.as_string()
                )
            logger.info("Successfully sent email to %s with subject: '%s'", self.to_email, subject)
        except Exception as e:
            logger.error("Failed to send email with subject '%s' to %s: %s", subject, self.to_email, e)

    def _buildRelevantPostsHtml(
        self,
        read_first_posts: list[PostMetadata],
        read_later_posts: list[PostMetadata],
        user_name: str
    ) -> str:
        current_time = datetime.now()
        greeting_time = "Good morning" if 5 <= current_time.hour < 12 else "Good afternoon" if 12 <= current_time.hour < 17 else "Good evening"
        

        read_first_html = self._buildPostSection(
            "Read First",
            read_first_posts
        )

        read_later_html = self._buildPostSection(
            "Read Later",
            read_later_posts
        )

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <style>
        body {{
            margin: 0;
            padding: 40px 16px;
            background-color: #F5EBDD;
            font-family: -apple-system, BlinkMacSystemFont,
                         "Segoe UI", Roboto, Arial, sans-serif;
            color: #413333;
        }}

        .container {{
            max-width: 680px;
            margin: auto;
            background: #ffffff;
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid #e2d9cd;
            box-shadow: 0 4px 12px rgba(65, 51, 51, 0.05);
        }}

        .header {{
            padding: 32px 36px 28px;
            background: #315B8C;
            color: #ffffff;
        }}

        .brand {{
            margin: 0 0 8px;
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
        }}

        .brand span {{
            color: #F2765E;
        }}

        .date {{
            margin: 0;
            font-size: 14px;
            color: #F5EBDD;
            opacity: 0.9;
        }}

        .greeting {{
            margin: 0;
            font-size: 14px;
            color: #F5EBDD;
            opacity: 0.95;
        }}

        .intro {{
            padding: 28px 36px 8px;
        }}

        .intro h1 {{
            margin: 0;
            font-size: 22px;
            color: #413333;
            font-weight: 700;
        }}

        .section {{
            padding: 24px 36px 8px;
        }}

        .section-title {{
            margin: 0 0 16px;
            font-size: 18px;
            font-weight: 700;
            color: #315B8C;
        }}

        .section-title .bullet {{
            color: #F2765E;
            margin-right: 6px;
        }}

        .article {{
            margin-bottom: 16px;
            padding: 20px;
            background-color: #ffffff;
            border: 1px solid #e5dec9;
            border-left: 4px solid #F2765E;
            border-radius: 8px;
        }}

        .article-title {{
            margin: 0 0 10px;
            font-size: 17px;
            line-height: 1.45;
            font-weight: 600;
        }}

        .article-title a {{
            color: #315B8C;
            text-decoration: none;
        }}

        .article-title a:hover {{
            color: #F2765E;
            text-decoration: underline;
        }}

        .reason-label {{
            margin: 0 0 4px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #F2765E;
        }}

        .reason {{
            margin: 0;
            font-size: 14px;
            line-height: 1.6;
            color: #413333;
        }}

        /* Footer */

        .footer {{
            margin-top: 24px;
            padding: 26px 36px;
            border-top: 1px solid #e2d9cd;
            background-color: #faf6f0;
            text-align: center;
        }}

        .footer-brand {{
            margin: 0;
            font-size: 15px;
            line-height: 1.4;
            font-weight: 700;
            color: #315B8C;
        }}

        .footer-text {{
            margin: 6px 0 16px;
            font-size: 13px;
            line-height: 1.5;
            color: #413333;
            opacity: 0.85;
        }}

        .footer-links {{
            text-align: center;
        }}

        .footer-link {{
            display: inline-block;
            margin: 0 8px;
            text-decoration: none;
            vertical-align: middle;
        }}

        .footer-link img {{
            width: 24px;
            height: 24px;
            display: inline-block;
            vertical-align: middle;
            border: 0;
        }}

        /* Mobile */

        @media only screen and (max-width: 600px) {{

            body {{
                padding: 16px 8px;
            }}

            .header,
            .intro,
            .section,
            .footer {{
                padding-left: 20px;
                padding-right: 20px;
            }}

            .brand {{
                font-size: 24px;
            }}

            .intro h1 {{
                font-size: 20px;
            }}

            .article {{
                padding: 16px;
            }}
        }}


    </style>
</head>

<body>

<div class="container">

    <div class="header">
        <p class="brand">Tech<span>Pulse</span></p>
        <p class="greeting">{greeting_time}, {user_name}</p>
    </div>

    <div class="intro">
        <h1>What's worth reading today</h1>
    </div>

    {read_first_html}

    {read_later_html}

    <div class="footer">

    <p class="footer-brand">TechPulse</p>

    <p class="footer-text">
        Built by Koti Chohan
    </p>

    <div class="footer-links">

        <!-- LinkedIn -->
        <a
            class="footer-link"
            href="https://www.linkedin.com/in/chohankoti/"
            target="_blank"
            title="LinkedIn"
            aria-label="LinkedIn"
        >
            <img
                src="https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/linkedin.svg"
                width="24"
                height="24"
                alt="LinkedIn"
            />
        </a>

        <!-- GitHub -->
        <a
            class="footer-link"
            href="https://github.com/Chohankoti"
            target="_blank"
            title="GitHub"
            aria-label="GitHub"
        >
            <img
                src="https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/github.svg"
                width="24"
                height="24"
                alt="GitHub"
            />
        </a>

    </div>

</div>

</div>

</body>
</html>
"""

    def _buildPostSection(
        self,
        title: str,
        posts: list[PostMetadata]
    ) -> str:

        if not posts:
            return ""

        articles = ""

        for post in posts:
            articles += f"""
            <div class="article">
                <h3 class="article-title">
                    <a href="{post.url}" target="_blank">
                        {post.title}
                    </a>
                </h3>

                <p class="reason-label">
                    Reason to read
                </p>

                <p class="reason">
                    {post.reason}
                </p>
            </div>
            """

        return f"""
        <div class="section">
            <h2 class="section-title">
                <span class="bullet">●</span> {title}
            </h2>

            {articles}
        </div>
        """