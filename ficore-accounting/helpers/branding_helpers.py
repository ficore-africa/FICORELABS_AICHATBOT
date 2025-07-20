from flask import current_app
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors

# Colors from your CSS
FICORE_PRIMARY_COLOR = "#b88a44"
FICORE_HEADER_BG = "#F2EFEA"
FICORE_TEXT_COLOR = "#1e293b"
FICORE_LOGO_PATH = "img/ficore_logo.png"  # relative to static folder

FICORE_MARKETING = "Empowering Africa's businesses. Contact: ficorelabs@gmail.com | +234-xxx-xxxx"
FICORE_BRAND = "Ficore Labs"

def draw_ficore_pdf_header(canvas, user, y_start=11.5):
    """
    Draw Ficore Labs branding and user info at the top of a PDF page.
    - canvas: reportlab.pdfgen.canvas.Canvas
    - user: Flask-Login user object (current_user)
    - y_start: vertical start position in inches (default is top of page)
    """
    inch = 72  # 1 inch in points
    static_folder = current_app.static_folder
    logo_path = f"{static_folder}/{FICORE_LOGO_PATH}"
    try:
        logo = ImageReader(logo_path)
        canvas.drawImage(logo, 1*inch, y_start*inch, width=0.9*inch, height=0.9*inch, mask='auto')
    except Exception:
        # Don't break PDF if logo fails
        pass

    # Brand name
    canvas.setFont("Helvetica-Bold", 18)
    canvas.setFillColor(FICORE_PRIMARY_COLOR)
    canvas.drawString(2.1*inch, (y_start+0.4)*inch, FICORE_BRAND)
    # Marketing
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(colors.black)
    canvas.drawString(2.1*inch, (y_start+0.15)*inch, FICORE_MARKETING)

    # User info
    user_name = getattr(user, "name", "") or getattr(user, "username", "User")
    user_email = getattr(user, "email", "")
    canvas.setFont("Helvetica", 10)
    canvas.setFillColor(FICORE_TEXT_COLOR)
    canvas.drawString(1*inch, (y_start-0.15)*inch, f"User: {user_name} | Email: {user_email}")

def ficore_csv_header(user):
    """
    Return a list of rows (each is a list of str) for branding/user info for CSV.
    """
    user_name = getattr(user, "name", "") or getattr(user, "username", "User")
    user_email = getattr(user, "email", "")
    return [
        [FICORE_BRAND],
        [FICORE_MARKETING],
        [f"User: {user_name} | Email: {user_email}"],
        []
    ]
