"""
Daily Market Index Performance — fetch & email agent.
Fetches S&P 500 TR, NASDAQ, DJIA, and Russell 2000 via yfinance,
then sends a formatted HTML email via Gmail SMTP.

Required environment variables (set as GitHub Actions secrets):
  GMAIL_USER     — your Gmail address (sender)
  GMAIL_APP_PASS — Gmail App Password (not your regular password)
  EMAIL_TO       — recipient address (can be the same as GMAIL_USER)
"""

import os
import smtplib
import sys
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import yfinance as yf

# ---------------------------------------------------------------------------
# Index definitions
# ---------------------------------------------------------------------------
INDICES = [
    {"ticker": "^SP500TR", "label": "S&P 500 Total Return"},
    {"ticker": "^IXIC",    "label": "NASDAQ Composite"},
    {"ticker": "^DJI",     "label": "Dow Jones Industrial Average"},
    {"ticker": "^RUT",     "label": "Russell 2000"},
]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def fetch_performance() -> list[dict]:
    """Return today's close, previous close, change $ and change % for each index."""
    results = []
    # Pull 5 days so we always have a prior close even after a holiday
    for idx in INDICES:
        ticker = yf.Ticker(idx["ticker"])
        hist = ticker.history(period="5d")
        if len(hist) < 2:
            results.append({**idx, "error": "Insufficient data"})
            continue

        prev_close = hist["Close"].iloc[-2]
        last_close = hist["Close"].iloc[-1]
        change     = last_close - prev_close
        pct_change = (change / prev_close) * 100
        last_date  = hist.index[-1].date()

        results.append({
            **idx,
            "date":       last_date,
            "close":      last_close,
            "prev_close": prev_close,
            "change":     change,
            "pct_change": pct_change,
        })
    return results


# ---------------------------------------------------------------------------
# Email building
# ---------------------------------------------------------------------------
def arrow(pct: float) -> str:
    return "▲" if pct >= 0 else "▼"


def color(pct: float) -> str:
    return "#16a34a" if pct >= 0 else "#dc2626"   # green / red


def build_html(data: list[dict]) -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    rows = ""
    for d in data:
        if "error" in d:
            rows += f"""
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;">{d['label']}</td>
              <td colspan="3" style="padding:12px 16px;border-bottom:1px solid #e5e7eb;color:#6b7280;">
                {d['error']}
              </td>
            </tr>"""
            continue

        sign   = "+" if d["pct_change"] >= 0 else ""
        ar     = arrow(d["pct_change"])
        clr    = color(d["pct_change"])
        rows += f"""
            <tr>
              <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;font-weight:500;">
                {d['label']}
              </td>
              <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;text-align:right;">
                {d['close']:,.2f}
              </td>
              <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;text-align:right;color:{clr};">
                {ar} {sign}{d['change']:,.2f}
              </td>
              <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;text-align:right;
                         font-weight:600;color:{clr};">
                {sign}{d['pct_change']:.2f}%
              </td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 0;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:12px;overflow:hidden;
                    box-shadow:0 1px 3px rgba(0,0,0,.1);">

        <!-- Header -->
        <tr>
          <td style="background:#1e3a5f;padding:24px 32px;">
            <p style="margin:0;color:#93c5fd;font-size:12px;text-transform:uppercase;
                      letter-spacing:.08em;">Daily Market Digest</p>
            <h1 style="margin:4px 0 0;color:#ffffff;font-size:22px;font-weight:700;">
              Index Performance
            </h1>
            <p style="margin:4px 0 0;color:#94a3b8;font-size:13px;">{today}</p>
          </td>
        </tr>

        <!-- Table -->
        <tr>
          <td style="padding:0 0 8px;">
            <table width="100%" cellpadding="0" cellspacing="0">
              <thead>
                <tr style="background:#f8fafc;">
                  <th style="padding:10px 16px;text-align:left;font-size:11px;
                             text-transform:uppercase;letter-spacing:.06em;color:#6b7280;">
                    Index
                  </th>
                  <th style="padding:10px 16px;text-align:right;font-size:11px;
                             text-transform:uppercase;letter-spacing:.06em;color:#6b7280;">
                    Close
                  </th>
                  <th style="padding:10px 16px;text-align:right;font-size:11px;
                             text-transform:uppercase;letter-spacing:.06em;color:#6b7280;">
                    Change
                  </th>
                  <th style="padding:10px 16px;text-align:right;font-size:11px;
                             text-transform:uppercase;letter-spacing:.06em;color:#6b7280;">
                    % Change
                  </th>
                </tr>
              </thead>
              <tbody>{rows}
              </tbody>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px 24px;border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:11px;color:#9ca3af;">
              Data sourced via Yahoo Finance. Prices reflect the most recent
              market close. This email is generated automatically.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return html


def build_plain(data: list[dict]) -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    lines = [f"Daily Market Digest — {today}", "=" * 50]
    for d in data:
        if "error" in d:
            lines.append(f"{d['label']}: {d['error']}")
            continue
        sign = "+" if d["pct_change"] >= 0 else ""
        lines.append(
            f"{d['label']}: {d['close']:,.2f}  "
            f"({sign}{d['change']:,.2f} / {sign}{d['pct_change']:.2f}%)"
        )
    lines.append("\nData via Yahoo Finance.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------
def send_email(html: str, plain: str, subject: str) -> None:
    gmail_user = os.environ["GMAIL_USER"]
    gmail_pass = os.environ["GMAIL_APP_PASS"]
    recipient  = os.environ["EMAIL_TO"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = gmail_user
    msg["To"]      = recipient

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, recipient, msg.as_string())
    print(f"Email sent to {recipient}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("Fetching market data…")
    data = fetch_performance()
    for d in data:
        if "error" in d:
            print(f"  {d['label']}: {d['error']}")
        else:
            sign = "+" if d["pct_change"] >= 0 else ""
            print(f"  {d['label']}: {d['close']:,.2f} ({sign}{d['pct_change']:.2f}%)")

    today   = date.today().strftime("%b %d, %Y")
    subject = f"📈 Daily Market Digest — {today}"

    html  = build_html(data)
    plain = build_plain(data)

    send_email(html, plain, subject)


if __name__ == "__main__":
    main()
