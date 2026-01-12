"""
Mock/Test Data Generator for Logic Testing Mode.
Returns deterministic audit results without calling Groq.
"""
from datetime import datetime
import random


def generate_mock_audit(business_name: str, industry: str = "other") -> dict:
    """
    Generate a deterministic mock audit result for testing.
    Uses business_name hash for consistent but varied scores.
    """
    # Create deterministic seed from business name
    seed = sum(ord(c) for c in business_name) % 100
    
    # Generate scores based on seed (deterministic)
    base_score = 45 + (seed % 40)  # Range: 45-84
    
    # Category breakdown
    categories = {
        "websiteTechnicalSEO": {
            "score": min(25, 10 + (seed % 16)),
            "maxPoints": 25,
            "subScores": {
                "siteSpeed": 6 + (seed % 4),
                "mobileFriendly": 4 + (seed % 4),
                "metaTags": 3 + (seed % 3),
                "structuredData": 2 + (seed % 3)
            },
            "confidenceLevel": "high" if seed > 50 else "medium"
        },
        "brandClarity": {
            "score": min(12, 5 + (seed % 8)),
            "maxPoints": 12,
            "subScores": {
                "messaging": 3 + (seed % 3),
                "visualIdentity": 2 + (seed % 3),
                "valueProposition": 2 + (seed % 2)
            },
            "confidenceLevel": "high"
        },
        "localSEO": {
            "score": min(15, 6 + (seed % 10)),
            "maxPoints": 15,
            "subScores": {
                "googleBusiness": 4 + (seed % 4),
                "localListings": 3 + (seed % 3),
                "reviewManagement": 2 + (seed % 3)
            },
            "confidenceLevel": "medium"
        },
        "socialPresence": {
            "score": min(18, 7 + (seed % 12)),
            "maxPoints": 18,
            "subScores": {
                "platformPresence": 4 + (seed % 4),
                "engagementRate": 3 + (seed % 4),
                "contentConsistency": 3 + (seed % 3)
            },
            "confidenceLevel": "medium"
        },
        "trustAuthority": {
            "score": min(12, 4 + (seed % 9)),
            "maxPoints": 12,
            "subScores": {
                "reviews": 3 + (seed % 3),
                "testimonials": 2 + (seed % 2),
                "certifications": 2 + (seed % 2)
            },
            "confidenceLevel": "low" if seed < 30 else "medium"
        },
        "performanceUX": {
            "score": min(10, 4 + (seed % 7)),
            "maxPoints": 10,
            "subScores": {
                "loadTime": 3 + (seed % 3),
                "navigation": 2 + (seed % 2),
                "accessibility": 2 + (seed % 2)
            },
            "confidenceLevel": "high"
        },
        "growthReadiness": {
            "score": min(8, 3 + (seed % 6)),
            "maxPoints": 8,
            "subScores": {
                "analytics": 2 + (seed % 2),
                "cta": 2 + (seed % 2),
                "leadCapture": 1 + (seed % 2)
            },
            "confidenceLevel": "medium"
        }
    }
    
    # Calculate actual overall score from categories
    overall_score = sum(cat["score"] for cat in categories.values())
    
    # Determine grade
    if overall_score >= 90:
        grade = "A"
    elif overall_score >= 80:
        grade = "B+"
    elif overall_score >= 70:
        grade = "B"
    elif overall_score >= 60:
        grade = "C+"
    elif overall_score >= 50:
        grade = "C"
    elif overall_score >= 40:
        grade = "D"
    else:
        grade = "F"
    
    # Quick wins
    quick_wins = [
        {
            "action": "Optimize Google Business Profile with complete info and photos",
            "expectedImpact": "Increase local visibility by 40%",
            "timeToImplement": "2 hours",
            "difficulty": "easy",
            "pointsGain": 5
        },
        {
            "action": "Add structured data markup to homepage",
            "expectedImpact": "Improve rich snippet appearance in search",
            "timeToImplement": "1 hour",
            "difficulty": "medium",
            "pointsGain": 4
        },
        {
            "action": "Set up automated review request emails",
            "expectedImpact": "Increase review count by 200%",
            "timeToImplement": "3 hours",
            "difficulty": "easy",
            "pointsGain": 6
        },
        {
            "action": "Compress images and enable lazy loading",
            "expectedImpact": "Reduce page load time by 50%",
            "timeToImplement": "2 hours",
            "difficulty": "medium",
            "pointsGain": 4
        },
        {
            "action": "Create consistent posting schedule across social platforms",
            "expectedImpact": "Boost engagement by 80%",
            "timeToImplement": "Ongoing",
            "difficulty": "medium",
            "pointsGain": 5
        }
    ]
    
    return {
        "overallScore": overall_score,
        "grade": grade,
        "executiveSummary": f"{business_name} shows {'strong' if overall_score >= 70 else 'moderate' if overall_score >= 50 else 'developing'} digital presence with opportunities for growth in {'local SEO and social engagement' if seed % 2 == 0 else 'website optimization and brand clarity'}.",
        "categoryBreakdown": categories,
        "quickWins": quick_wins,
        "topStrengths": [
            "Consistent brand messaging across platforms",
            "Active social media presence"
        ],
        "criticalWeaknesses": [
            "Missing structured data on website",
            "Low Google review count"
        ],
        "socialAudit": {
            "platforms": {
                "instagram": {"score": 6 + (seed % 4), "followers": 500 + (seed * 10)},
                "facebook": {"score": 5 + (seed % 4), "followers": 300 + (seed * 8)},
                "tiktok": {"score": 3 + (seed % 3), "followers": 100 + (seed * 5)}
            },
            "overallEngagement": "medium",
            "recommendedPlatforms": ["Instagram", "TikTok"]
        },
        "priorityRoadmap": {
            "immediate": ["Claim Google Business Profile", "Add basic schema markup"],
            "shortTerm": ["Launch review campaign", "Optimize page speed"],
            "longTerm": ["Build comprehensive content strategy", "Develop email marketing funnel"]
        },
        "industryBenchmark": {
            "industry": industry,
            "averageScore": 55,
            "yourRank": "top 35%" if overall_score >= 65 else "average" if overall_score >= 45 else "needs improvement",
            "competitorRange": "45-78"
        },
        "confidenceNote": "TEST MODE: This is mock data for logic testing. Scores are deterministic based on business name.",
        "freeReport": {
            "includedSections": ["Executive Summary", "Category Overview", "Top 3 Quick Wins"],
            "callToAction": "Unlock your complete growth roadmap with 30+ recommendations"
        },
        "paidReportPreview": {
            "additionalSections": [
                "Deep Category Analysis",
                "Full Recommendations List",
                "90-Day Priority Roadmap",
                "Industry Benchmarks",
                "Competitor Gap Analysis"
            ]
        },
        "_metadata": {
            "generatedAt": datetime.utcnow().isoformat(),
            "isTest": True,
            "version": "2.0-test"
        }
    }
