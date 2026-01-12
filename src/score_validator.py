"""
Score validator to ensure audit results are valid and consistent.
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationError:
    """Single validation error."""
    field: str
    message: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class ValidationResult:
    """Result of score validation."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)
    corrected_data: Optional[Dict[str, Any]] = None

    def add_error(self, field: str, message: str):
        self.errors.append(ValidationError(field, message, "error"))
        self.is_valid = False

    def add_warning(self, field: str, message: str):
        self.warnings.append(ValidationError(field, message, "warning"))


# Category max points
CATEGORY_MAX_POINTS = {
    "websiteTechnicalSEO": 25,
    "brandClarity": 12,
    "localSEO": 18,
    "socialPresence": 16,
    "trustAuthority": 15,
    "performanceUX": 8,
    "growthReadiness": 6,
}

# Sub-score max points
SUB_SCORE_MAX = {
    "websiteTechnicalSEO": {
        "domainQuality": 6,
        "onPageSEO": 8,
        "technicalInfrastructure": 6,
        "contentPresence": 5,
    },
    "brandClarity": {
        "nameQuality": 5,
        "brandConsistency": 4,
        "marketPositioning": 3,
    },
    "localSEO": {
        "gbpLikelihood": 8,
        "napConsistency": 4,
        "localKeywords": 3,
        "directoryPresence": 3,
    },
    "socialPresence": {
        "platformCoverage": 5,
        "handleConsistency": 5,
        "profileCompleteness": 3,
        "engagementIndicators": 3,
    },
    "trustAuthority": {
        "securityLegitimacy": 4,
        "reviewReputation": 6,
        "socialProof": 3,
        "backlinkAuthority": 2,
    },
}

# Grade ranges
GRADE_RANGES = {
    "A": (90, 100),
    "A-": (85, 89),
    "B+": (80, 84),
    "B": (75, 79),
    "B-": (70, 74),
    "C+": (65, 69),
    "C": (60, 64),
    "C-": (55, 59),
    "D": (50, 54),
    "F": (0, 49),
}

VALID_CONFIDENCE_LEVELS = {"high", "medium", "low"}
VALID_GRADES = set(GRADE_RANGES.keys())


def validate_audit_result(audit_data: dict) -> ValidationResult:
    """
    Validate an audit result from Groq API.
    
    Args:
        audit_data: The parsed JSON audit result
        
    Returns:
        ValidationResult with errors, warnings, and optionally corrected data
    """
    result = ValidationResult(is_valid=True)
    
    # Check required top-level fields
    required_fields = ['overallScore', 'grade', 'categoryBreakdown']
    for field in required_fields:
        if field not in audit_data:
            result.add_error(field, f"Missing required field: {field}")
    
    if not result.is_valid:
        return result
    
    # Validate overall score range
    overall_score = audit_data.get('overallScore', 0)
    if not isinstance(overall_score, (int, float)):
        result.add_error('overallScore', f"Score must be a number, got {type(overall_score)}")
    elif overall_score < 0 or overall_score > 100:
        result.add_error('overallScore', f"Score must be 0-100, got {overall_score}")
    
    # Validate grade
    grade = audit_data.get('grade', '')
    if grade not in VALID_GRADES:
        result.add_error('grade', f"Invalid grade '{grade}', must be one of {VALID_GRADES}")
    
    # Validate grade matches score
    if isinstance(overall_score, (int, float)) and grade in GRADE_RANGES:
        min_score, max_score = GRADE_RANGES[grade]
        if not (min_score <= overall_score <= max_score):
            result.add_warning(
                'grade',
                f"Grade '{grade}' expects score {min_score}-{max_score}, but score is {overall_score}"
            )
    
    # Validate category breakdown
    breakdown = audit_data.get('categoryBreakdown', {})
    category_total = 0
    
    for category, max_points in CATEGORY_MAX_POINTS.items():
        if category not in breakdown:
            result.add_error(f'categoryBreakdown.{category}', f"Missing category: {category}")
            continue
        
        cat_data = breakdown[category]
        
        # Check score exists and is valid
        cat_score = cat_data.get('score', 0)
        if not isinstance(cat_score, (int, float)):
            result.add_error(
                f'categoryBreakdown.{category}.score',
                f"Score must be a number, got {type(cat_score)}"
            )
            cat_score = 0
        elif cat_score < 0:
            result.add_error(
                f'categoryBreakdown.{category}.score',
                f"Score cannot be negative: {cat_score}"
            )
        elif cat_score > max_points:
            result.add_error(
                f'categoryBreakdown.{category}.score',
                f"Score {cat_score} exceeds max points {max_points}"
            )
        
        category_total += cat_score
        
        # Check maxPoints is correct
        stated_max = cat_data.get('maxPoints', 0)
        if stated_max != max_points:
            result.add_warning(
                f'categoryBreakdown.{category}.maxPoints',
                f"maxPoints should be {max_points}, got {stated_max}"
            )
        
        # Validate confidence level
        confidence = cat_data.get('confidenceLevel', '')
        if confidence not in VALID_CONFIDENCE_LEVELS:
            result.add_warning(
                f'categoryBreakdown.{category}.confidenceLevel',
                f"Invalid confidence '{confidence}', should be high/medium/low"
            )
        
        # Validate sub-scores if applicable
        if category in SUB_SCORE_MAX and 'subScores' in cat_data:
            sub_scores = cat_data['subScores']
            sub_total = 0
            
            for sub_name, sub_max in SUB_SCORE_MAX[category].items():
                if sub_name not in sub_scores:
                    result.add_warning(
                        f'categoryBreakdown.{category}.subScores.{sub_name}',
                        f"Missing sub-score: {sub_name}"
                    )
                    continue
                
                sub_value = sub_scores[sub_name]
                if not isinstance(sub_value, (int, float)):
                    result.add_error(
                        f'categoryBreakdown.{category}.subScores.{sub_name}',
                        f"Sub-score must be a number"
                    )
                elif sub_value < 0 or sub_value > sub_max:
                    result.add_warning(
                        f'categoryBreakdown.{category}.subScores.{sub_name}',
                        f"Sub-score {sub_value} should be 0-{sub_max}"
                    )
                else:
                    sub_total += sub_value
            
            # Check sub-scores sum to category score (with tolerance)
            if abs(sub_total - cat_score) > 1:
                result.add_warning(
                    f'categoryBreakdown.{category}',
                    f"Sub-scores sum ({sub_total}) doesn't match category score ({cat_score})"
                )
    
    # Check total equals overall score (with small tolerance for rounding)
    if abs(category_total - overall_score) > 2:
        result.add_warning(
            'overallScore',
            f"Category total ({category_total}) doesn't match overall score ({overall_score})"
        )
    
    # Validate other sections exist
    optional_sections = [
        'industryBenchmark', 'socialAudit', 'executiveSummary',
        'topStrengths', 'criticalWeaknesses', 'quickWins', 'priorityRoadmap',
        'freeReport', 'paidReportPreview'
    ]
    for section in optional_sections:
        if section not in audit_data:
            result.add_warning(section, f"Missing optional section: {section}")
    
    return result


def correct_audit_scores(audit_data: dict) -> dict:
    """
    Attempt to correct minor scoring issues in audit data.
    
    Args:
        audit_data: The audit result to correct
        
    Returns:
        Corrected audit data
    """
    corrected = audit_data.copy()
    
    # Recalculate overall score from categories
    breakdown = corrected.get('categoryBreakdown', {})
    total = 0
    
    for category in CATEGORY_MAX_POINTS:
        if category in breakdown:
            cat_score = breakdown[category].get('score', 0)
            max_pts = CATEGORY_MAX_POINTS[category]
            # Clamp to max
            clamped = min(max(0, cat_score), max_pts)
            if clamped != cat_score:
                breakdown[category]['score'] = clamped
            total += clamped
    
    corrected['overallScore'] = total
    
    # Fix grade based on corrected score
    corrected['grade'] = get_grade_for_score(total)
    
    return corrected


def get_grade_for_score(score: float) -> str:
    """Get the correct grade for a given score."""
    for grade, (min_score, max_score) in GRADE_RANGES.items():
        if min_score <= score <= max_score:
            return grade
    return "F"


def generate_validation_report(result: ValidationResult) -> str:
    """
    Generate a human-readable validation report.
    
    Args:
        result: ValidationResult to format
        
    Returns:
        Formatted report string
    """
    lines = []
    lines.append("=" * 50)
    lines.append("AUDIT VALIDATION REPORT")
    lines.append("=" * 50)
    lines.append("")
    
    if result.is_valid:
        lines.append("✓ Audit passed validation")
    else:
        lines.append("✗ Audit FAILED validation")
    
    if result.errors:
        lines.append("")
        lines.append(f"ERRORS ({len(result.errors)}):")
        lines.append("-" * 30)
        for err in result.errors:
            lines.append(f"  ✗ [{err.field}] {err.message}")
    
    if result.warnings:
        lines.append("")
        lines.append(f"WARNINGS ({len(result.warnings)}):")
        lines.append("-" * 30)
        for warn in result.warnings:
            lines.append(f"  ⚠ [{warn.field}] {warn.message}")
    
    if not result.errors and not result.warnings:
        lines.append("")
        lines.append("No issues found.")
    
    lines.append("")
    lines.append("=" * 50)
    
    return "\n".join(lines)
