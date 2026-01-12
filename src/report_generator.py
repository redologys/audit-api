"""
PDF Report Generator - Using ReportLab for production stability.
Removes dependency on heavy system libraries (GTK/WeasyPrint).
Enforces strict Unicode sanitization to prevent emoji crashes.
"""
import os
import re
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Directories
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "reports"

# ----------------------------------------------------------------------------
# 1. Unicode / Emoji Sanitization
# ----------------------------------------------------------------------------
def sanitize_text(text: Any) -> str:
    """
    Aggressively strip emojis and unsupported characters.
    ReportLab standard fonts only support Latin-1/ASCII efficiently.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    
    # Method 1: ASCII encode/decode (Aggressive but safe)
    # This removes all emojis (U+1Fxxx) and non-latin chars
    sanitized = text.encode("ascii", "ignore").decode("ascii")
    
    # Method 2: Regex cleanup (double check)
    # Remove control characters but keep newlines
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
    
    return sanitized.strip()

# ----------------------------------------------------------------------------
# 2. PDF Generation Logic
# ----------------------------------------------------------------------------
async def generate_pdf_report(
    audit_id: str,
    audit_data: Dict[str, Any],
    business_name: str,
    report_type: str = "free"
) -> str:
    """
    Generate a PDF report using ReportLab.
    Path: /reports/audit-{id}-{type}.pdf
    """
    ensure_directories()
    
    output_filename = f"audit-{audit_id}-{report_type}.pdf"
    output_path = OUTPUT_DIR / output_filename
    
    try:
        # Build the PDF document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=LETTER,
            rightMargin=72, leftMargin=72,
            topMargin=72, bottomMargin=72,
            title=sanitize_text(f"Audit Report - {business_name}")
        )
        
        # Styles
        styles = getSampleStyleSheet()
        
        # Custom Styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        h2_style = ParagraphStyle(
            'CustomH2',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#111827'),
            spaceBefore=20,
            spaceAfter=10,
            borderPadding=5,
            borderColor=colors.HexColor('#FBBF24'),
            borderWidth=0,
            borderBottomWidth=2
        )
        
        summary_style = ParagraphStyle(
            'Summary',
            parent=styles['BodyText'],
            backColor=colors.HexColor('#FFFBEB'),
            borderColor=colors.HexColor('#FBBF24'),
            borderWidth=1,
            borderPadding=10,
            borderRadius=5,
            spaceAfter=20
        )
        
        category_name_style = ParagraphStyle(
            'CatName',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12
        )
        
        # Story Container
        story = []
        
        # --- HEADER ---
        story.append(Paragraph("Digital Presence Audit", styles['Title']))
        story.append(Paragraph(f"Business: {sanitize_text(business_name)}", styles['Normal']))
        story.append(Paragraph(f"Date: {datetime.now().strftime('%B %d, %Y')}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # --- SCORE SECTION ---
        overall_score = audit_data.get("overallScore", 0)
        grade = sanitize_text(audit_data.get("grade", "F"))
        
        # Color logic
        score_color = colors.green if overall_score >= 75 else colors.orange if overall_score >= 50 else colors.red
        
        story.append(Paragraph(f"Overall Score: {overall_score}/100", title_style))
        story.append(Paragraph(f"Grade: {grade}", styles['Heading2']))
        story.append(Spacer(1, 20))
        
        # --- EXECUTIVE SUMMARY ---
        story.append(Paragraph("Executive Summary", h2_style))
        exec_summary = sanitize_text(audit_data.get("executiveSummary", "Analysis completed."))
        story.append(Paragraph(exec_summary, summary_style))
        
        # --- CATEGORY BREAKDOWN ---
        story.append(Paragraph("Category Breakdown", h2_style))
        
        categories = audit_data.get("categoryBreakdown", {})
        # Map friendly names
        cat_map = {
            "websiteTechnicalSEO": "Website & Technical SEO",
            "brandClarity": "Brand Clarity",
            "localSEO": "Local SEO",
            "socialPresence": "Social Media",
            "trustAuthority": "Trust & Authority",
            "performanceUX": "Performance",
            "growthReadiness": "Growth Ready",
        }
        
        table_data = [['Category', 'Score', 'Max']]
        
        for key, data in categories.items():
            name = cat_map.get(key, key)
            score = data.get("score", 0)
            max_pts = data.get("maxPoints", 1)
            # Sanitize name just in case
            table_data.append([sanitize_text(name), str(score), str(max_pts)])
            
        cat_table = Table(table_data, colWidths=[300, 60, 60])
        cat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 25))

        # --- QUICK WINS ---
        story.append(Paragraph("Quick Wins", h2_style))
        
        quick_wins = audit_data.get("quickWins", [])
        if report_type == "free":
            quick_wins = quick_wins[:3]
            
        if not quick_wins:
            story.append(Paragraph("No immediate actions found.", styles['Normal']))
        else:
            for win in quick_wins:
                action = sanitize_text(win.get("action", "Action"))
                impact = sanitize_text(win.get("expectedImpact", ""))
                points = win.get("pointsGain", 0)
                
                win_text = f"<b>{action}</b> (+{points} pts)<br/>{impact}"
                story.append(Paragraph(win_text, styles['BodyText']))
                story.append(Spacer(1, 10))

        # --- CTA / PAYWALL ---
        if report_type == "free":
            story.append(Spacer(1, 30))
            # Box style for upgrade
            cta_style = ParagraphStyle(
                'CTA',
                parent=styles['BodyText'],
                backColor=colors.HexColor('#1E3A8A'),
                textColor=colors.white,
                alignment=TA_CENTER,
                borderPadding=20,
                borderRadius=10
            )
            story.append(Paragraph("<b>Unlock Full Report</b>", cta_style))
            story.append(Paragraph("Get specific platform strategies and roadmap.", cta_style))
            
        # Build
        doc.build(story)
        
        return str(output_path)
        
    except Exception as e:
        print(f"PDF Generation Error: {e}")
        # Make a dummy text file if PDF fails to fallback gracefully
        error_path = output_path.with_suffix(".txt")
        with open(error_path, "w") as f:
            f.write(f"Error generating PDF: {sanitize_text(str(e))}\n\n")
            f.write(f"Summary: {sanitize_text(audit_data.get('executiveSummary', ''))}")
        return str(error_path)


def ensure_directories():
    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMPLATE_DIR.mkdir(exist_ok=True)

# ----------------------------------------------------------------------------
# 3. HTML Generator (Legacy/Email support)
# ----------------------------------------------------------------------------
def generate_html_report(
    audit_id: str,
    audit_data: Dict[str, Any],
    business_name: str,
    report_type: str = "free"
) -> str:
    """
    Generate clean HTML report (sanitized).
    """
    # ... Simplified HTML generation relying on sanitization ...
    # (Kept briefly for backward compatibility if needed, but sanitized)
    s = sanitize_text
    
    overall_score = audit_data.get("overallScore", 0)
    grade = s(audit_data.get("grade", "F"))
    summary = s(audit_data.get("executiveSummary", ""))
    
    html = f"""
    <html>
    <body>
        <h1>Audit for {s(business_name)}</h1>
        <h2>Score: {overall_score} - Grade: {grade}</h2>
        <p>{summary}</p>
    </body>
    </html>
    """
    return html
