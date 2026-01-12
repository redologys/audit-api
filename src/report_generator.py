"""
PDF Report Generator - Simple fallback without WeasyPrint.
Uses basic HTML generation and browser print for PDF creation.
For production, consider pdfkit or reportlab as alternatives.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "reports"

# Try WeasyPrint, fallback to simple HTML if not available
WEASYPRINT_AVAILABLE = False
try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except ImportError:
    print("WeasyPrint not available, using HTML fallback")
except OSError as e:
    print(f"WeasyPrint OS error (missing GTK?): {e}")


def ensure_directories():
    """Ensure template and output directories exist."""
    TEMPLATE_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


async def generate_pdf_report(
    audit_id: str,
    audit_data: Dict[str, Any],
    business_name: str,
    report_type: str = "free"
) -> str:
    """
    Generate a PDF report from audit data.
    Falls back to HTML if WeasyPrint is unavailable.
    """
    ensure_directories()
    
    # Generate the HTML content
    html_content = generate_html_report(audit_id, audit_data, business_name, report_type)
    
    if WEASYPRINT_AVAILABLE:
        return await generate_weasyprint_pdf(audit_id, html_content, report_type)
    else:
        # Fallback: generate HTML file (can be opened in browser and printed to PDF)
        return await generate_html_file(audit_id, html_content, report_type)


async def generate_weasyprint_pdf(audit_id: str, html_content: str, report_type: str) -> str:
    """Generate PDF using WeasyPrint."""
    output_path = OUTPUT_DIR / f"audit-{audit_id}-{report_type}.pdf"
    
    css_path = TEMPLATE_DIR / "report_styles.css"
    css = CSS(filename=str(css_path)) if css_path.exists() else None
    
    HTML(string=html_content).write_pdf(
        str(output_path),
        stylesheets=[css] if css else None
    )
    
    return str(output_path)


async def generate_html_file(audit_id: str, html_content: str, report_type: str) -> str:
    """Generate HTML file as PDF fallback."""
    # For now, save as HTML - the API will need to handle this differently
    output_path = OUTPUT_DIR / f"audit-{audit_id}-{report_type}.html"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return str(output_path)


def generate_html_report(
    audit_id: str,
    audit_data: Dict[str, Any],
    business_name: str,
    report_type: str = "free"
) -> str:
    """Generate standalone HTML report with embedded styles."""
    
    overall_score = audit_data.get("overallScore", 0)
    grade = audit_data.get("grade", "F")
    executive_summary = audit_data.get("executiveSummary", "")
    categories = audit_data.get("categoryBreakdown", {})
    quick_wins = audit_data.get("quickWins", [])[:3] if report_type == "free" else audit_data.get("quickWins", [])
    
    # Color based on score
    score_color = "#22c55e" if overall_score >= 75 else "#f59e0b" if overall_score >= 50 else "#ef4444"
    grade_color = "#22c55e" if grade.startswith("A") else "#3b82f6" if grade.startswith("B") else "#f59e0b" if grade.startswith("C") else "#ef4444"
    
    # Category names
    category_names = {
        "websiteTechnicalSEO": "Website & Technical SEO",
        "brandClarity": "Brand Clarity",
        "localSEO": "Local SEO",
        "socialPresence": "Social Media",
        "trustAuthority": "Trust & Authority",
        "performanceUX": "Performance",
        "growthReadiness": "Growth Ready",
    }
    
    # Build category HTML
    categories_html = ""
    for key, data in categories.items():
        score = data.get("score", 0)
        max_pts = data.get("maxPoints", 1)
        pct = round((score / max_pts) * 100)
        bar_color = "#22c55e" if pct >= 75 else "#f59e0b" if pct >= 50 else "#ef4444"
        
        categories_html += f'''
        <div style="background: #f9fafb; padding: 12px; border-radius: 8px; border: 1px solid #e5e7eb;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="font-weight: 600; font-size: 13px;">{category_names.get(key, key)}</span>
                <span style="font-weight: 700;">{score}/{max_pts}</span>
            </div>
            <div style="height: 8px; background: #e5e7eb; border-radius: 4px; overflow: hidden;">
                <div style="width: {pct}%; height: 100%; background: {bar_color}; border-radius: 4px;"></div>
            </div>
        </div>
        '''
    
    # Build quick wins HTML
    wins_html = ""
    for win in quick_wins:
        wins_html += f'''
        <div style="background: #f0fdf4; padding: 12px; border-radius: 8px; border-left: 4px solid #22c55e; margin-bottom: 8px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                <strong style="font-size: 13px;">{win.get("action", "")}</strong>
                <span style="background: #22c55e; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px;">+{win.get("pointsGain", 0)} pts</span>
            </div>
            <p style="font-size: 12px; color: #666; margin: 0;">{win.get("expectedImpact", "")}</p>
        </div>
        '''
    
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Digital Presence Audit - {business_name}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #1f2937; background: #fff; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; padding-bottom: 20px; border-bottom: 2px solid #e5e7eb; margin-bottom: 30px; }}
        .hero {{ text-align: center; padding: 30px 0; background: linear-gradient(135deg, #f9fafb 0%, #f3f4f6 100%); border-radius: 12px; margin-bottom: 30px; }}
        .score-circle {{ width: 120px; height: 120px; border-radius: 50%; background: white; border: 6px solid {score_color}; display: inline-flex; flex-direction: column; justify-content: center; align-items: center; margin: 20px; }}
        .score-number {{ font-size: 42px; font-weight: 800; color: #111827; }}
        .grade-badge {{ display: inline-block; background: {grade_color}; color: white; font-size: 28px; font-weight: 800; padding: 8px 16px; border-radius: 8px; }}
        section {{ margin-bottom: 30px; }}
        h2 {{ font-size: 18px; color: #111827; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 2px solid #fbbf24; }}
        .summary {{ background: #fffbeb; padding: 15px; border-radius: 8px; border-left: 4px solid #fbbf24; font-size: 14px; }}
        .category-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; font-size: 11px; color: #6b7280; }}
        @media print {{ body {{ padding: 0; }} .container {{ max-width: 100%; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <span style="font-size: 20px;">📊</span>
                <span style="font-size: 18px; font-weight: 700; margin-left: 8px;">Digital Presence Audit</span>
            </div>
            <div style="text-align: right; font-size: 12px; color: #6b7280;">
                <p>Report ID: {audit_id}</p>
                <p>Generated: {datetime.now().strftime("%B %d, %Y")}</p>
            </div>
        </div>

        <div class="hero">
            <h1 style="font-size: 24px; margin-bottom: 20px;">{business_name}</h1>
            <div class="score-circle">
                <span class="score-number">{overall_score}</span>
                <span style="font-size: 12px; color: #6b7280;">/100</span>
            </div>
            <div class="grade-badge">{grade}</div>
        </div>

        <section>
            <h2>📋 Executive Summary</h2>
            <div class="summary">{executive_summary or "Your business digital presence has been analyzed across 7 key categories."}</div>
        </section>

        <section>
            <h2>📊 Category Breakdown</h2>
            <div class="category-grid">
                {categories_html}
            </div>
        </section>

        <section>
            <h2>🚀 Quick Wins</h2>
            {wins_html or "<p style='color: #666; font-size: 13px;'>Complete the audit to see recommended improvements.</p>"}
        </section>

        {"" if report_type == "paid" else '''
        <section style="background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); color: white; padding: 30px; border-radius: 12px; text-align: center;">
            <h2 style="color: white; border: none; margin-bottom: 15px;">🔓 Unlock Full Report</h2>
            <p style="margin-bottom: 20px;">Get detailed sub-scores, platform strategies, and a 30-60-90 day growth roadmap.</p>
            <a href="#" style="display: inline-block; background: #fbbf24; color: #111827; padding: 12px 30px; border-radius: 8px; font-weight: 700; text-decoration: none;">Get Full Report - $29</a>
        </section>
        '''}

        <div class="footer">
            <p style="font-style: italic; margin-bottom: 10px;">This report is an AI-generated analysis based on provided inputs and industry heuristics.</p>
            <p>© {datetime.now().year} Digital Presence Audit. All rights reserved.</p>
        </div>
    </div>
</body>
</html>'''
    
    return html
