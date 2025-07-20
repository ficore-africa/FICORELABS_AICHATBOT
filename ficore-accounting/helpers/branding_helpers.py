from flask import current_app
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors

# Colors from your CSS
FICORE_PRIMARY_COLOR = "#b88a44"
FICORE_HEADER_BG = "#F2EFEA"
FICORE_TEXT_COLOR = "#1e293b"
FICORE_LOGO_PATH = "img/ficore_logo.png"  # relative to static folder
TOP_MARGIN = 10.5  # in inches, adjusted to match new y_start

FICORE_MARKETING = "Empowering Africa's businesses. Contact: ficorelabs@gmail.com | +234-xxx-xxxx"
FICORE_BRAND = "Ficore Labs"

def draw_ficore_pdf_header(canvas, user, y_start=10.5):
    """
    Draw Ficore Labs branding and user info at the top of a PDF page.
    - canvas: reportlab.pdfgen.canvas.Canvas
    - user: Flask-Login user object (current_user)
    - y_start: vertical start position in inches (default is 10.5 inches from bottom)
    """
    inch = 72  # 1 inch in points
    static_folder = current_app.static_folder
    logo_path = f"{static_folder}/{FICORE_LOGO_PATH}"
    
    # Debug line to visualize y_start position
    canvas.setStrokeColor(colors.red)
    canvas.line(0, y_start * inch, 500, y_start * inch)
    
    try:
        logo = ImageReader(logo_path)
        # Constrain logo size to prevent overflow
        canvas.drawImage(logo, 1 * inch, (y_start - 0.6) * inch, width=0.6 * inch, height=0.6 * inch, mask='auto')
    except Exception:
        # Don't break PDF if logo fails
        pass

    # Brand name
    canvas.setFont("Helvetica-Bold", 16)
    canvas.setFillColor(FICORE_PRIMARY_COLOR)
    canvas.drawString(1.8 * inch, (y_start - 0.1) * inch, FICORE_BRAND)
    
    # Marketing
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.black)
    canvas.drawString(1.8 * inch, (y_start - 0.3) * inch, FICORE_MARKETING)
    
    # User info
    user_name = getattr(user, "name", "") or getattr(user, "username", "User")
    user_email = getattr(user, "email", "")
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(FICORE_TEXT_COLOR)
    canvas.drawString(1 * inch, (y_start - 0.5) * inch, f"User: {user_name} | Email: {user_email}")
    
    # Reset stroke color for subsequent content
    canvas.setStrokeColor(colors.black)

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
