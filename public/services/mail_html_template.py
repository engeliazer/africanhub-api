"""
Branded HTML email wrapper for African Hub mail batches.
"""

import html
import os
import re

# African Hub brand palette (from product UI)
BRAND_GOLD = "#C9A227"
BRAND_GOLD_DARK = "#A8861E"
BRAND_TEXT = "#1F2937"
BRAND_MUTED = "#6B7280"
BRAND_BG = "#F3F4F6"
BRAND_WHITE = "#FFFFFF"
BRAND_BORDER = "#E5E7EB"

_DEFAULT_LOGO_URL = "https://africanhub.ac.tz/logo.png"
_DEFAULT_WEBSITE = "https://africanhub.ac.tz"
_DEFAULT_TAGLINE = "Building Accounting Skills for the Real World"


def _logo_url() -> str:
    return (os.getenv("MAIL_LOGO_URL") or _DEFAULT_LOGO_URL).strip()


def _website_url() -> str:
    return (os.getenv("MAIL_WEBSITE_URL") or _DEFAULT_WEBSITE).strip()


def _brand_tagline() -> str:
    return (os.getenv("MAIL_BRAND_TAGLINE") or _DEFAULT_TAGLINE).strip()


def _brand_name() -> str:
    return (os.getenv("MAIL_FROM_NAME") or "The African Hub").strip()


def _message_to_html_blocks(message: str) -> str:
    """Escape user content and preserve paragraphs / line breaks."""
    text = html.escape(message or "")
    paragraphs = re.split(r"\n\s*\n", text)
    blocks = []
    for para in paragraphs:
        lines = para.split("\n")
        inner = "<br />".join(lines)
        blocks.append(
            f'<p style="margin:0 0 16px;font-size:16px;line-height:1.65;color:{BRAND_TEXT};">'
            f"{inner}</p>"
        )
    return "".join(blocks) or (
        f'<p style="margin:0;font-size:16px;line-height:1.65;color:{BRAND_TEXT};">&nbsp;</p>'
    )


def render_batch_email_html(*, message_body: str, subject: str) -> str:
    """
    Wrap a personalized plain-text batch message in a branded HTML layout.
    message_body should already have [NAME] replaced.
    """
    brand = html.escape(_brand_name().upper())
    tagline = html.escape(_brand_tagline())
    website = html.escape(_website_url(), quote=True)
    website_label = html.escape(_website_url().replace("https://", "").replace("http://", ""))
    safe_subject = html.escape(subject or "")
    body_html = _message_to_html_blocks(message_body)
    logo = _logo_url()
    logo_block = ""
    if logo:
        safe_logo = html.escape(logo, quote=True)
        logo_block = f"""
          <img src="{safe_logo}" alt="{brand}" width="56" height="56"
               style="display:block;width:56px;height:56px;border-radius:12px;" />
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{safe_subject}</title>
</head>
<body style="margin:0;padding:0;background-color:{BRAND_BG};font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
         style="background-color:{BRAND_BG};padding:32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"
               style="max-width:600px;background-color:{BRAND_WHITE};border-radius:16px;overflow:hidden;border:1px solid {BRAND_BORDER};">
          <!-- Gold accent bar -->
          <tr>
            <td style="height:5px;background:linear-gradient(90deg,{BRAND_GOLD_DARK},{BRAND_GOLD});font-size:0;line-height:0;">&nbsp;</td>
          </tr>
          <!-- Header -->
          <tr>
            <td style="padding:28px 32px 20px;background-color:{BRAND_WHITE};">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td width="68" valign="middle" style="padding-right:14px;">
                    {logo_block}
                  </td>
                  <td valign="middle">
                    <div style="font-size:18px;font-weight:700;letter-spacing:0.04em;color:{BRAND_TEXT};">
                      {brand}
                    </div>
                    <div style="font-size:13px;line-height:1.4;color:{BRAND_MUTED};margin-top:4px;">
                      {tagline}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding:8px 32px 28px;background-color:{BRAND_WHITE};">
              <div style="border-top:1px solid {BRAND_BORDER};padding-top:24px;">
                {body_html}
              </div>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding:20px 32px 28px;background-color:#FAFAFA;border-top:1px solid {BRAND_BORDER};">
              <p style="margin:0 0 8px;font-size:13px;line-height:1.5;color:{BRAND_MUTED};">
                You are receiving this email from <strong style="color:{BRAND_TEXT};">{brand}</strong>.
              </p>
              <p style="margin:0 0 12px;font-size:13px;line-height:1.5;color:{BRAND_MUTED};">
                Reply to this message if you have any questions — we are happy to help.
              </p>
              <p style="margin:0;font-size:13px;">
                <a href="{website}" style="color:{BRAND_GOLD_DARK};text-decoration:none;font-weight:600;">
                  {website_label}
                </a>
              </p>
            </td>
          </tr>
        </table>
        <p style="margin:16px 0 0;font-size:12px;color:{BRAND_MUTED};text-align:center;">
          &copy; {brand}. All rights reserved.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""
