"""
PDF Report Generator - Using ReportLab for production stability.
Removes dependency on heavy system libraries (GTK/WeasyPrint).
Enforces strict Unicode sanitization to prevent emoji crashes.
"""
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.colors import HexColor

# Directories
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "reports"

# ----------------------------------------------------------------------------
# 1. BRAND CONFIGURATION
# ----------------------------------------------------------------------------
BRAND_CONFIG = {
    "primary": HexColor("#1E3A8A"),      # Navy Blue
    "secondary": HexColor("#1E40AF"),    # Lighter Navy
    "accent": HexColor("#FBBF24"),       # Gold/Amber
    "text_dark": HexColor("#111827"),    # Gray 900
    "text_light": HexColor("#6B7280"),   # Gray 500
    "bg_light": HexColor("#F9FAFB"),     # Gray 50
    "success": HexColor("#059669"),      # Green 600
    "white": HexColor("#FFFFFF")
}

# ----------------------------------------------------------------------------
# 2. SANITIZATION UTILS
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
    
    # Method: ASCII encode/decode (Aggressive but safe)
    # This removes all emojis (U+1Fxxx) and non-latin chars
    sanitized = text.encode("ascii", "ignore").decode("ascii")
    
    # Regex cleanup for control chars
    sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
    
    return sanitized.strip()

# ----------------------------------------------------------------------------
# 3. PDF GENERATOR
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
        # Document Setup
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=LETTER,
            rightMargin=50, leftMargin=50,
            topMargin=50, bottomMargin=50,
            title=sanitize_text(f"Audit - {business_name}")
        )
        
        # Styles
        styles = getSampleStyleSheet()
        
        # --- CUSTOM STYLES ---
        styles.add(ParagraphStyle(
            name='BrandTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=26,
            textColor=BRAND_CONFIG["primary"],
            spaceAfter=10,
            alignment=TA_CENTER
        ))
        
        styles.add(ParagraphStyle(
            name='BrandSubtitle',
            parent=styles['Heading2'],
            fontName='Helvetica',
            fontSize=14,
            textColor=BRAND_CONFIG["text_light"],
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=BRAND_CONFIG["primary"],
            spaceBefore=20,
            spaceAfter=12,
            borderPadding=6,
            borderColor=BRAND_CONFIG["accent"],
            borderWidth=0,
            borderBottomWidth=2
        ))
        
        styles.add(ParagraphStyle(
            name='SummaryBox',
            parent=styles['BodyText'],
            backColor=HexColor("#FFFBEB"),
            borderColor=BRAND_CONFIG["accent"],
            borderWidth=1,
            borderPadding=12,
            borderRadius=6,
            spaceAfter=20,
            fontSize=11,
            leading=14
        ))
        
        styles.add(ParagraphStyle(
            name='ActionItem',
            parent=styles['BodyText'],
            fontSize=11,
            leading=14,
            spaceAfter=8
        ))

        # --- BUILD STORY ---
        story = []
        
        # 1. Header Section
        story.append(Paragraph("DIGITAL PRESENCE AUDIT", styles["BrandTitle"]))
        story.append(Paragraph(f"Prepared for: {sanitize_text(business_name)}", styles["BrandSubtitle"]))
        story.append(Spacer(1, 10))
        
        # 2. Score & Grade
        _add_score_section(story, audit_data, styles)
        
        # 3. Executive Summary
        story.append(Paragraph("EXECUTIVE SUMMARY", styles["SectionHeader"]))
        summary_text = sanitize_text(audit_data.get("executiveSummary", "Analysis completed."))
        story.append(Paragraph(summary_text, styles["SummaryBox"]))
        
        # 4. Category Breakdown
        story.append(Paragraph("CATEGORY PERFORMANCE", styles["SectionHeader"]))
        _add_category_table(story, audit_data)
        
        # 5. Quick Wins (Top 3 for Free, All for Paid)
        story.append(Paragraph("QUICK WINS & OPPORTUNITIES", styles["SectionHeader"]))
        _add_quick_wins(story, audit_data, report_type, styles)
        
        # --- PAID CONTENT ---
        if report_type == "paid":
            story.append(PageBreak())
            story.append(Paragraph("DETAILED ANALYSIS & ROADMAP", styles["BrandTitle"]))
            story.append(Spacer(1, 20))
            
            # Deep Dive
            _add_detailed_breakdown(story, audit_data, styles)
            
            # Roadmap
            story.append(PageBreak())
            story.append(Paragraph("GROWTH ROADMAP (30-60-90 DAYS)", styles["SectionHeader"]))
            _add_roadmap(story, audit_data, styles)
            
            # Benchmarks
            story.append(Paragraph("INDUSTRY BENCHMARKS", styles["SectionHeader"]))
            _add_benchmarks(story, audit_data, styles)

        # --- CTA (Free Only) ---
        else:
            story.append(Spacer(1, 30))
            _add_upgrade_cta(story, styles)

        # Footer
        story.append(Spacer(1, 40))
        footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d')} | ID: {audit_id}"
        story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.gray, alignment=TA_CENTER)))

        doc.build(story)
        return str(output_path)
        
    except Exception as e:
        # Fail safe
        print(f"PDF Error: {e}")
        error_path = output_path.with_suffix(".txt")
        with open(error_path, "w") as f:
            f.write(f"Error: {e}\nSummary: {sanitize_text(str(audit_data))}")
        return str(error_path)

# ----------------------------------------------------------------------------
# 4. SECTION HELPERS
# ----------------------------------------------------------------------------
def _add_score_section(story, data, styles):
    score = data.get("overallScore", 0)
    grade = sanitize_text(data.get("grade", "F"))
    
    # Determine color
    if score >= 75: color = BRAND_CONFIG["success"]
    elif score >= 50: color = BRAND_CONFIG["accent"]
    else: color = colors.red
    
    # Simulating a big centered score
    story.append(Paragraph(f"OVERALL SCORE: <font color='{color}'>{score}/100</font>", 
                 ParagraphStyle('Score', parent=styles['Heading1'], fontSize=20, alignment=TA_CENTER)))
    story.append(Paragraph(f"GRADE: {grade}", 
                 ParagraphStyle('Grade', parent=styles['Heading2'], fontSize=16, alignment=TA_CENTER)))
    story.append(Spacer(1, 20))

def _add_category_table(story, data):
    categories = data.get("categoryBreakdown", {})
    cat_map = {
        "websiteTechnicalSEO": "Tech SEO",
        "brandClarity": "Brand",
        "localSEO": "Local SEO",
        "socialPresence": "Social",
        "trustAuthority": "Trust",
        "performanceUX": "UX/Speed",
        "growthReadiness": "Growth"
    }
    
    table_data = [['Category', 'Score', 'Status']]
    
    for key, val in categories.items():
        name = cat_map.get(key, key)
        score = val.get("score", 0)
        max_pts = val.get("maxPoints", 1)
        pct = (score / max_pts) * 100
        
        status = "Good" if pct >= 70 else "Fair" if pct >= 50 else "Critical"
        table_data.append([sanitize_text(name), f"{score}/{max_pts}", status])

    t = Table(table_data, colWidths=[300, 80, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BRAND_CONFIG["primary"]),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#E5E7EB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, BRAND_CONFIG["bg_light"]])
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

def _add_quick_wins(story, data, report_type, styles):
    wins = data.get("quickWins", [])
    if report_type == "free":
        wins = wins[:3] # Limit to 3
        
    if not wins:
        story.append(Paragraph("No immediate actions found.", styles['Normal']))
        return

    for i, win in enumerate(wins, 1):
        action = sanitize_text(win.get("action", ""))
        impact = sanitize_text(win.get("expectedImpact", ""))
        pts = win.get("pointsGain", 0)
        
        text = f"<b>{i}. {action}</b> <font color='#059669'>(+{pts} pts)</font><br/><i>Impact: {impact}</i>"
        story.append(Paragraph(text, styles["ActionItem"]))

def _add_upgrade_cta(story, styles):
    cta_style = ParagraphStyle(
        'CTA_Box',
        parent=styles['Normal'],
        backColor=BRAND_CONFIG["primary"],
        textColor=colors.white,
        alignment=TA_CENTER,
        fontSize=14,
        fontName='Helvetica-Bold',
        borderPadding=20,
        borderRadius=8,
        spaceBefore=20
    )
    story.append(Paragraph("UNLOCK FULL REPORT & ROADMAP", cta_style))
    story.append(Paragraph("<font size=10>Get detailed strategies, checklist, and 90-day plan.</font>", 
                 ParagraphStyle('CTA_Sub', parent=cta_style, backColor=None, fontSize=10)))

def _add_detailed_breakdown(story, data, styles):
    # This section expands on categories
    categories = data.get("categoryBreakdown", {})
    for key, val in categories.items():
        name = sanitize_text(key.replace("TechnicalSEO", " Technical SEO").title())
        subscores = val.get("subScores", {})
        
        story.append(Paragraph(f"Analysis: {name}", styles["Heading3"]))
        if subscores:
            sub_text = ", ".join([f"{k}: {v}" for k,v in subscores.items()])
            story.append(Paragraph(f"Diagnostics: {sanitize_text(sub_text)}", styles["BodyText"]))
        else:
             story.append(Paragraph("No sub-metrics available.", styles["BodyText"]))
        story.append(Spacer(1, 10))

def _add_roadmap(story, data, styles):
    roadmap = data.get("priorityRoadmap", {})
    phases = [("30 Days (Immediate)", "immediate"), ("60 Days (Short Term)", "shortTerm"), ("90 Days (Long Term)", "longTerm")]
    
    for label, key in phases:
        items = roadmap.get(key, [])
        story.append(Paragraph(f"<b>{label}</b>", styles["Heading4"]))
        if items:
            for item in items:
                story.append(Paragraph(f"- {sanitize_text(item)}", styles["BodyText"]))
        else:
            story.append(Paragraph("- Assessment pending full audit.", styles["BodyText"]))
        story.append(Spacer(1, 10))

def _add_benchmarks(story, data, styles):
    bench = data.get("industryBenchmark", {})
    industry = sanitize_text(bench.get("industry", "Unknown"))
    rank = sanitize_text(bench.get("yourRank", "N/A"))
    
    story.append(Paragraph(f"<b>Industry:</b> {industry}", styles["BodyText"]))
    story.append(Paragraph(f"<b>Competitive Rank:</b> {rank}", styles["BodyText"]))

def ensure_directories():
    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMPLATE_DIR.mkdir(exist_ok=True)
    
# Fallback for old code if referenced (returns path to new PDF)
async def generate_html_file(*args, **kwargs):
    return "" 

