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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, ListFlowable, ListItem
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
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
    "white": HexColor("#FFFFFF"),
    "danger": HexColor("#DC2626")        # Red
}

# ----------------------------------------------------------------------------
# 2. SANITIZATION UTILS
# ----------------------------------------------------------------------------
def sanitize_text(text: Any) -> str:
    """
    Aggressively strip emojis and unsupported characters.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    
    # ASCII encode/decode (Aggressive but safe)
    sanitized = text.encode("ascii", "ignore").decode("ascii")
    # Regex cleanup
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
        _register_custom_styles(styles)

        # --- BUILD STORY ---
        story = []
        
        if report_type == "paid":
            # --- PAID REPORT STRUCTURE ---
            _add_cover_page(story, business_name, styles)
            _add_expanded_executive_summary(story, audit_data, styles)
            _add_deep_category_analysis(story, audit_data, styles)
            _add_checklists(story, audit_data, styles)
            _add_benchmarks(story, audit_data, styles)
            _add_90_day_roadmap_detailed(story, audit_data, styles)
            _add_tool_recommendations(story, styles)
            _add_risk_analysis(story, audit_data, styles)
            _add_final_summary(story, styles)
            
        else:
            # --- FREE REPORT STRUCTURE ---
            # Header
            story.append(Paragraph("DIGITAL PRESENCE AUDIT", styles["BrandTitle"]))
            story.append(Paragraph(f"Prepared for: {sanitize_text(business_name)}", styles["BrandSubtitle"]))
            story.append(Spacer(1, 10))
            
            # Score
            _add_score_section(story, audit_data, styles)
            
            # Summary
            story.append(Paragraph("EXECUTIVE SUMMARY", styles["SectionHeader"]))
            summary_text = sanitize_text(audit_data.get("executiveSummary", "Analysis completed."))
            story.append(Paragraph(summary_text, styles["SummaryBox"]))
            
            # Categories
            story.append(Paragraph("CATEGORY PERFORMANCE", styles["SectionHeader"]))
            _add_category_table(story, audit_data)
            
            # Top 3 Wins
            story.append(Paragraph("QUICK WINS (Top 3)", styles["SectionHeader"]))
            _add_quick_wins(story, audit_data, "free", styles)
            
            # CTA
            story.append(Spacer(1, 30))
            _add_upgrade_cta(story, styles)

        # Footer
        story.append(Spacer(1, 40))
        footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d')} | ID: {audit_id}"
        story.append(Paragraph(footer_text, ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.gray, alignment=TA_CENTER)))

        doc.build(story)
        return str(output_path)
        
    except Exception as e:
        print(f"PDF Error: {e}")
        error_path = output_path.with_suffix(".txt")
        with open(error_path, "w") as f:
            f.write(f"Error: {e}\nSummary: {sanitize_text(str(audit_data))}")
        return str(error_path)

# ----------------------------------------------------------------------------
# 4. SECTION HELPERS (PAID & FREE)
# ----------------------------------------------------------------------------

def _register_custom_styles(styles):
    # Brand Title
    styles.add(ParagraphStyle(
        name='BrandTitle', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=28,
        textColor=BRAND_CONFIG["primary"], spaceAfter=10, alignment=TA_CENTER
    ))
    # Brand Subtitle
    styles.add(ParagraphStyle(
        name='BrandSubtitle', parent=styles['Heading2'],
        fontName='Helvetica', fontSize=16,
        textColor=BRAND_CONFIG["text_light"], spaceAfter=30, alignment=TA_CENTER
    ))
    # Section Header
    styles.add(ParagraphStyle(
        name='SectionHeader', parent=styles['Heading2'],
        fontName='Helvetica-Bold', fontSize=18,
        textColor=BRAND_CONFIG["primary"], spaceBefore=20, spaceAfter=12,
        borderPadding=6, borderColor=BRAND_CONFIG["accent"],
        borderWidth=0, borderBottomWidth=2
    ))
    # H3
    styles.add(ParagraphStyle(
        name='Heading3Bold', parent=styles['Heading3'],
        fontName='Helvetica-Bold', fontSize=14,
        textColor=BRAND_CONFIG["secondary"], spaceBefore=12, spaceAfter=6
    ))
    # Summary Box
    styles.add(ParagraphStyle(
        name='SummaryBox', parent=styles['BodyText'],
        backColor=HexColor("#FFFBEB"), borderColor=BRAND_CONFIG["accent"],
        borderWidth=1, borderPadding=12, borderRadius=6,
        spaceAfter=20, fontSize=11, leading=16
    ))
    # Action Item
    styles.add(ParagraphStyle(
        name='ActionItem', parent=styles['BodyText'],
        fontSize=11, leading=14, spaceAfter=8
    ))
    # Cover Page Text
    styles.add(ParagraphStyle(
        name='CoverText', parent=styles['Normal'],
        fontSize=12, textColor=colors.gray, alignment=TA_CENTER
    ))

def _add_cover_page(story, business_name, styles):
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("DIGITAL GROWTH BLUEPRINT", styles["BrandTitle"]))
    story.append(Paragraph("CONSULTING GRADE AUDIT & ROADMAP", styles["BrandSubtitle"]))
    story.append(Spacer(1, 1*inch))
    
    story.append(Paragraph(f"Prepared Exclusively For:", styles["CoverText"]))
    story.append(Paragraph(sanitize_text(business_name), 
        ParagraphStyle('BusinessBig', parent=styles['BrandTitle'], fontSize=22, spaceBefore=10, spaceAfter=10)))
    
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%B %d, %Y')}", styles["CoverText"]))
    story.append(Paragraph("CONFIDENTIAL", styles["CoverText"]))
    story.append(PageBreak())

def _add_expanded_executive_summary(story, data, styles):
    story.append(Paragraph("EXECUTIVE STRATEGY", styles["SectionHeader"]))
    
    score = data.get("overallScore", 0)
    grade = sanitize_text(data.get("grade", "F"))
    summary = sanitize_text(data.get("executiveSummary", "Analysis completed."))
    
    story.append(Paragraph("<b>Current Status Diagnostic</b>", styles["Heading3Bold"]))
    story.append(Paragraph(summary, styles["BodyText"]))
    story.append(Spacer(1, 10))

    # Diagnosis Logic
    diagnosis = "Your digital foundation is strong." 
    if score < 50: diagnosis = "Your digital presence is currently limiting your growth potential. Significant gaps in SEO and trust factors are likely causing lost revenue."
    elif score < 75: diagnosis = "You have a solid foundation but are missing key optimizations that could double your inbound leads."
    
    story.append(Paragraph("<b>Strategic Outlook</b>", styles["Heading3Bold"]))
    story.append(Paragraph(diagnosis, styles["BodyText"]))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("<b>The Cost of Inaction vs. Action</b>", styles["Heading3Bold"]))
    
    t_data = [
        ["If You Do Nothing", "If You Act Now"],
        ["Continued loss of organic traffic to competitors.", "Capture high-intent search traffic within 60 days."],
        ["Lower trust from potential customers.", "Establish market authority and review dominance."],
        ["Wasted ad spend on unoptimized pages.", "Higher conversion rates and better ROI."]
    ]
    t = Table(t_data, colWidths=[250, 250])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (1,0), BRAND_CONFIG["bg_light"]),
        ('FONTNAME', (0,0), (1,0), 'Helvetica-Bold'),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('PADDING', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,0), BRAND_CONFIG["danger"]),
        ('TEXTCOLOR', (1,0), (1,0), BRAND_CONFIG["success"]),
    ]))
    story.append(t)
    story.append(PageBreak())

def _add_deep_category_analysis(story, data, styles):
    # Mapping for categories
    categories = data.get("categoryBreakdown", {})
    cat_defs = {
        "websiteTechnicalSEO": {
            "title": "Website & Technical SEO",
            "why": "Technical SEO determines if Google can read your site and if users stay on it.",
            "impact": "Low scores here mean you are invisible to search engines."
        },
        "brandClarity": {
            "title": "Brand Clarity & Messaging",
            "why": "Clear messaging converts visitors into buyers.",
            "impact": "Confusing copy kills conversion rates immediately."
        },
        "localSEO": {
            "title": "Local SEO & Visibility",
            "why": "This governs showing up in Google Maps and 'Near Me' searches.",
            "impact": "Critical for capturing local market share."
        },
        "socialPresence": {
            "title": "Social Media Presence",
            "why": "Social proof builds trust and brand awareness.",
            "impact": "Lack of activity signals a 'dead' business to customers."
        },
        "trustAuthority": {
            "title": "Trust & Authority",
            "why": "Reviews and citations prove you are legitimate.",
            "impact": "Customers buy from who they trust. Low trust = no sales."
        },
        "performanceUX": {
            "title": "Performance & User Experience",
            "why": "Speed and mobile usability are ranking factors.",
            "impact": "Slow sites have high bounce rates."
        }
    }

    for key, val in categories.items():
        if key not in cat_defs: continue
        
        info = cat_defs[key]
        score = val.get("score", 0)
        max_pts = val.get("maxPoints", 1)
        pct = (score / max_pts) * 100
        
        story.append(Paragraph(info["title"].upper(), styles["SectionHeader"]))
        
        # Intro Box
        story.append(Paragraph(f"<b>Score: {score}/{max_pts}</b> ({'Critical' if pct < 50 else 'Good'})", styles["Heading3Bold"]))
        story.append(Paragraph(f"<b>Why it matters:</b> {info['why']}", styles["BodyText"]))
        story.append(Paragraph(f"<b>Business Impact:</b> {info['impact']}", styles["BodyText"]))
        story.append(Spacer(1, 10))
        
        # Detailed Subscores
        subscores = val.get("subScores", {})
        if subscores:
            story.append(Paragraph("<b>Detailed Diagnostics:</b>", styles["Heading3Bold"]))
            for k, v in subscores.items():
                k_clean = sanitize_text(k.replace("([A-Z])", " \\1").title())
                status = "REQUIRES ATTENTION" if v < 3 else "OPTIMIZED"
                color = "red" if v < 3 else "green"
                story.append(Paragraph(f"- {k_clean}: <font color='{color}'>{status}</font>", styles["BodyText"]))
        
        # Improvement Plan (Generic but customized by category)
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Step-by-Step Improvement Plan:</b>", styles["Heading3Bold"]))
        
        plans = _get_category_plans(key)
        for step in plans:
            story.append(Paragraph(f"<b>{step['phase']}:</b> {step['action']}", styles["BodyText"]))
            story.append(Paragraph(f"<i>Payoff: {step['payoff']}</i>", styles["BodyText"]))
            story.append(Spacer(1, 4))

        story.append(PageBreak())

def _get_category_plans(cat_key):
    # Static expert content mapped to categories
    # In a real app, this would be more dynamic depending on the specific error
    defaults = [
        {"phase": "Immediate (Day 1-7)", "action": "Fix urgent issues.", "payoff": "Stop bleeding leads."}
    ]
    
    if cat_key == "websiteTechnicalSEO":
        return [
            {"phase": "Immediate", "action": "Install Google Search Console and fix 404 errors.", "payoff": "Indexing health."},
            {"phase": "Short Term", "action": "Compress all images >100KB and enable browser caching.", "payoff": "Faster load times."},
            {"phase": "Long Term", "action": "Implement Schema markup for rich snippets.", "payoff": "Higher CTR."}
        ]
    elif cat_key == "localSEO":
        return [
            {"phase": "Immediate", "action": "Fully claim and verify Google Business Profile.", "payoff": "Appear in Maps."},
            {"phase": "Short Term", "action": "Get 5 new reviews from past happy clients.", "payoff": "Social proof boost."},
            {"phase": "Long Term", "action": "Build local citations in YP, Yelp, and industry directories.", "payoff": "Domain Authority."}
        ]
    # ... Add others as needed, falling back to generic if needed ...
    return [
        {"phase": "Immediate", "action": "Audit current state and identify low-hanging fruit.", "payoff": "Clarity."},
        {"phase": "Short Term", "action": "Optimize core assets and messaging.", "payoff": "Conversion rate."},
        {"phase": "Long Term", "action": "Scale content and outreach.", "payoff": "Traffic growth."}
    ]

def _add_checklists(story, data, styles):
    story.append(Paragraph("ACTIONABLE CHECKLISTS", styles["SectionHeader"]))
    
    checklists = [
        ("Website Optimization", [
            "Ensure SSL (HTTPS) is active",
            "Make phone number clickable on mobile",
            "Add contact form above the fold",
            "Compress images to WebP format",
            "Fix broken links (Check Google Search Console)"
        ]),
        ("Local Authority", [
            "Reply to last 5 Google Reviews",
            "Add 'Products/Services' to GBP",
            "Upload 10 new photos to GBP",
            "Ensure Name/Address/Phone match exactly everywhere"
        ])
    ]
    
    for title, items in checklists:
        story.append(Paragraph(f"<b>{title} Checklist</b>", styles["Heading3Bold"]))
        for item in items:
            story.append(Paragraph(f"[ ] {item}", styles["BodyText"]))
        story.append(Spacer(1, 10))
    story.append(PageBreak())

def _add_90_day_roadmap_detailed(story, data, styles):
    story.append(Paragraph("90-DAY GROWTH ROADMAP", styles["SectionHeader"]))
    
    roadmap = data.get("priorityRoadmap", {})
    
    phases = [
        ("Phase 1: Foundation (Days 1-30)", "immediate", "Fix broken technicals and claim assets."),
        ("Phase 2: Optimization (Days 31-60)", "shortTerm", "Improve content and conversion rates."),
        ("Phase 3: Scale (Days 61-90)", "longTerm", "Expand reach and authority.")
    ]
    
    for title, key, desc in phases:
        story.append(Paragraph(title, styles["Heading3Bold"]))
        story.append(Paragraph(f"<i>Focus: {desc}</i>", styles["BodyText"]))
        
        items = roadmap.get(key, [])
        if items:
            for item in items:
                story.append(Paragraph(f"• {sanitize_text(item)}", styles["BodyText"]))
        else:
            story.append(Paragraph("• Complete audit actionable items first.", styles["BodyText"]))
        story.append(Spacer(1, 15))
    
    story.append(PageBreak())

def _add_benchmarks(story, data, styles):
    story.append(Paragraph("COMPETITIVE BENCHMARKS", styles["SectionHeader"]))
    
    bench = data.get("industryBenchmark", {})
    industry = sanitize_text(bench.get("industry", "General Business"))
    
    story.append(Paragraph(f"We compared your digital footprint against top performers in the <b>{industry}</b> sector.", styles["BodyText"]))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph(f"<b>Your Rank:</b> {sanitize_text(bench.get('yourRank', 'N/A'))}", styles["Heading3Bold"]))
    story.append(Paragraph("<b>Top Competitors Typically Have:</b>", styles["BodyText"]))
    story.append(Paragraph("• 50+ Google Reviews (4.8+ Star Avg)", styles["BodyText"]))
    story.append(Paragraph("• Mobile load speed under 2.5 seconds", styles["BodyText"]))
    story.append(Paragraph("• Active social posting (2-3x per week)", styles["BodyText"]))
    story.append(Spacer(1, 20))

def _add_tool_recommendations(story, styles):
    story.append(Paragraph("RECOMMENDED TOOLS", styles["SectionHeader"]))
    story.append(Paragraph("Use these tools to execute your roadmap faster:", styles["BodyText"]))
    story.append(Spacer(1, 10))
    
    tools = [
        ("Google Search Console", "Free. Monitor site health and broken links."),
        ("Google Business Profile", "Free. Manage local listings and reviews."),
        ("Canva", "Design. Create social media posts easily."),
        ("AnswerThePublic", "Content. Find what your customers are asking."),
        ("PageSpeed Insights", "Tech. Test website speed.")
    ]
    
    for name, desc in tools:
        story.append(Paragraph(f"<b>{name}:</b> {desc}", styles["BodyText"]))
        story.append(Spacer(1, 5))
    story.append(PageBreak())

def _add_risk_analysis(story, data, styles):
    story.append(Paragraph("RISK & OPPORTUNITY ANALYSIS", styles["SectionHeader"]))
    story.append(Paragraph("<b>Hidden Risks:</b>", styles["Heading3Bold"]))
    story.append(Paragraph("• Ignoring mobile speed increases ad costs by up to 50%.", styles["BodyText"]))
    story.append(Paragraph("• Lack of recent reviews signals 'closed' to new algorithms.", styles["BodyText"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Compounding Opportunities:</b>", styles["Heading3Bold"]))
    story.append(Paragraph("• Every new review creates permanent SEO value.", styles["BodyText"]))
    story.append(Paragraph("• Improving conversion rate from 1% to 2% doubles revenue without new traffic.", styles["BodyText"]))

def _add_final_summary(story, styles):
    story.append(Spacer(1, 20))
    story.append(Paragraph("YOUR NEXT STEPS", styles["SectionHeader"]))
    story.append(Paragraph("1. Print this roadmap.", styles["BodyText"]))
    story.append(Paragraph("2. Assign the 'Immediate' tasks to your team or developer.", styles["BodyText"]))
    story.append(Paragraph("3. Schedule a review in 30 days to measure progress.", styles["BodyText"]))
    story.append(Paragraph("<b>Success favors action. Start today.</b>", styles["Heading3Bold"]))

# --- FREE HELPERS ---
def _add_score_section(story, data, styles):
    score = data.get("overallScore", 0)
    grade = sanitize_text(data.get("grade", "F"))
    # Determine color
    if score >= 75: color = BRAND_CONFIG["success"]
    elif score >= 50: color = BRAND_CONFIG["accent"]
    else: color = colors.red
    story.append(Paragraph(f"OVERALL SCORE: <font color='{color}'>{score}/100</font>", 
                 ParagraphStyle('Score', parent=styles['Heading1'], fontSize=20, alignment=TA_CENTER)))
    story.append(Paragraph(f"GRADE: {grade}", 
                 ParagraphStyle('Grade', parent=styles['Heading2'], fontSize=16, alignment=TA_CENTER)))
    story.append(Spacer(1, 20))

def _add_category_table(story, data):
    categories = data.get("categoryBreakdown", {})
    cat_map = {
        "websiteTechnicalSEO": "Tech SEO", "brandClarity": "Brand", "localSEO": "Local SEO",
        "socialPresence": "Social", "trustAuthority": "Trust", "performanceUX": "UX/Speed", "growthReadiness": "Growth"
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
        wins = wins[:3] 
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
        'CTA_Box', parent=styles['Normal'],
        backColor=BRAND_CONFIG["primary"], textColor=colors.white,
        alignment=TA_CENTER, fontSize=14, fontName='Helvetica-Bold',
        borderPadding=20, borderRadius=8, spaceBefore=20
    )
    story.append(Paragraph("UNLOCK FULL REPORT & ROADMAP", cta_style))
    story.append(Paragraph("<font size=10>Get detailed strategies, checklist, and 90-day plan.</font>", 
                 ParagraphStyle('CTA_Sub', parent=cta_style, backColor=None, fontSize=10)))

def ensure_directories():
    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMPLATE_DIR.mkdir(exist_ok=True)
    
async def generate_html_file(*args, **kwargs):
    return "" 

