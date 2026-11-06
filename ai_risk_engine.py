
"""
Coaching Institute Fee Tracking System
File: ai_risk_engine.py

Responsibilities:
- Assess potential student dropout risk.
- Identify contributing risk factors.
- Generate explainable risk scores.
- Create counsellor follow-up tasks.
- Allow counsellors to mark false-positive flags.

SAFETY:
This is a rule-based decision-support tool, not a trained
machine-learning prediction model.

A risk flag must NEVER:
- Change a student's fee ledger.
- Automatically send a parent message.
- Block a student from attending classes.
- Apply a penalty or initiate a refund.

All flagged cases require human review.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional


# -------------------------------------------------------------------
# Risk thresholds
# -------------------------------------------------------------------

LOW_RISK_LIMIT = 0.30
MEDIUM_RISK_LIMIT = 0.60

MAX_RISK_SCORE = 1.0


# -------------------------------------------------------------------
# Sample student data
# -------------------------------------------------------------------

SAMPLE_STUDENTS = [
    {
        "student_id": "STU-0412",
        "student_name": "Aarav Meena",
        "batch": "JEE 2027 Morning",
        "overdue_days": 0,
        "missed_instalments": 0,
        "attendance_percentage": 92.4,
        "test_trend": "Improving",
        "test_score_change": 4.0,
    },
    {
        "student_id": "STU-0587",
        "student_name": "Ishita Sharma",
        "batch": "JEE 2027 Evening",
        "overdue_days": 23,
        "missed_instalments": 1,
        "attendance_percentage": 68.5,
        "test_trend": "Declining",
        "test_score_change": -15.0,
    },
    {
        "student_id": "STU-0219",
        "student_name": "Mohit Gurjar",
        "batch": "NEET 2027 Morning",
        "overdue_days": 0,
        "missed_instalments": 0,
        "attendance_percentage": 88.0,
        "test_trend": "Stable",
        "test_score_change": 0.0,
    },
]


# -------------------------------------------------------------------
# Counsellor task queue
# -------------------------------------------------------------------

counsellor_task_queue: List[Dict[str, Any]] = []

risk_assessments: Dict[str, Dict[str, Any]] = {}


# -------------------------------------------------------------------
# Risk engine
# -------------------------------------------------------------------

class AIDropoutRiskEngine:
    """
    Explainable rule-based dropout risk assessment.

    Risk factors and weights are configurable assumptions.
    They are not statistically trained or validated weights.
    """

    def __init__(
        self,
        overdue_weight: float = 0.30,
        missed_instalment_weight: float = 0.20,
        attendance_weight: float = 0.25,
        test_decline_weight: float = 0.25,
    ):

        weights = [
            overdue_weight,
            missed_instalment_weight,
            attendance_weight,
            test_decline_weight,
        ]

        if any(weight < 0 for weight in weights):
            raise ValueError("Risk weights cannot be negative.")

        if sum(weights) <= 0:
            raise ValueError("At least one risk weight must be positive.")

        self.weights = {
            "overdue": overdue_weight,
            "missed_instalment": missed_instalment_weight,
            "attendance": attendance_weight,
            "test_decline": test_decline_weight,
        }

        total_weight = sum(self.weights.values())

        # Normalize weights so their total equals 1.
        self.weights = {
            key: value / total_weight
            for key, value in self.weights.items()
        }

    # ----------------------------------------------------------------
    # Input validation
    # ----------------------------------------------------------------

    @staticmethod
    def validate_student(student: Dict[str, Any]) -> None:

        required = [
            "student_id",
            "student_name",
            "overdue_days",
            "missed_instalments",
            "attendance_percentage",
            "test_trend",
        ]

        for field in required:
            if field not in student:
                raise ValueError(f"Missing student field: {field}")

        if not str(student["student_id"]).strip():
            raise ValueError("Student ID cannot be empty.")

        if int(student["overdue_days"]) < 0:
            raise ValueError("Overdue days cannot be negative.")

        if int(student["missed_instalments"]) < 0:
            raise ValueError("Missed instalments cannot be negative.")

        attendance = float(student["attendance_percentage"])

        if not 0 <= attendance <= 100:
            raise ValueError(
                "Attendance must be between 0 and 100."
            )

        trend = str(student["test_trend"]).strip().lower()

        if trend not in ("improving", "stable", "declining", "unknown"):
            raise ValueError(
                "Test trend must be Improving, Stable, Declining or Unknown."
            )

        if "test_score_change" in student:
            change = float(student["test_score_change"])

            if not -100 <= change <= 100:
                raise ValueError(
                    "Test score change must be between -100 and 100."
                )

    # ----------------------------------------------------------------
    # Risk assessment
    # ----------------------------------------------------------------

    def assess_student(
        self,
        student: Dict[str, Any]
    ) -> Dict[str, Any]:

        self.validate_student(student)

        score = 0.0
        reasons = []
        factor_scores = {}

        # Factor 1: Overdue fee instalments.
        overdue_days = int(student["overdue_days"])

        if overdue_days > 15:
            factor_scores["overdue"] = 1.0
            reasons.append(
                f"Fee instalment is overdue by {overdue_days} days."
            )
        elif overdue_days > 0:
            factor_scores["overdue"] = 0.5
            reasons.append(
                f"Fee instalment is overdue by {overdue_days} days."
            )
        else:
            factor_scores["overdue"] = 0.0

        score += (
            factor_scores["overdue"]
            * self.weights["overdue"]
        )

        # Factor 2: Missed instalments.
        missed = int(student["missed_instalments"])

        if missed >= 2:
            factor_scores["missed_instalment"] = 1.0
            reasons.append(
                f"{missed} fee instalments have been missed."
            )
        elif missed == 1:
            factor_scores["missed_instalment"] = 0.5
            reasons.append(
                "One fee instalment has been missed."
            )
        else:
            factor_scores["missed_instalment"] = 0.0

        score += (
            factor_scores["missed_instalment"]
            * self.weights["missed_instalment"]
        )

        # Factor 3: Attendance.
        attendance = float(
            student["attendance_percentage"]
        )

        if attendance < 60:
            factor_scores["attendance"] = 1.0
            reasons.append(
                f"Attendance is critically low at {attendance:.1f}%."
            )
        elif attendance < 75:
            factor_scores["attendance"] = 0.7
            reasons.append(
                f"Attendance is below 75% at {attendance:.1f}%."
            )
        elif attendance < 85:
            factor_scores["attendance"] = 0.3
            reasons.append(
                f"Attendance needs monitoring at {attendance:.1f}%."
            )
        else:
            factor_scores["attendance"] = 0.0

        score += (
            factor_scores["attendance"]
            * self.weights["attendance"]
        )

        # Factor 4: Test performance trend.
        trend = str(student["test_trend"]).strip().lower()

        if trend == "declining":
            factor_scores["test_decline"] = 1.0
            reasons.append(
                "Recent test performance is declining."
            )
        else:
            factor_scores["test_decline"] = 0.0

        score += (
            factor_scores["test_decline"]
            * self.weights["test_decline"]
        )

        # Final score.
        score = min(max(score, 0.0), MAX_RISK_SCORE)
        score = round(score, 3)

        if score < LOW_RISK_LIMIT:
            risk_level = "LOW"

        elif score < MEDIUM_RISK_LIMIT:
            risk_level = "MEDIUM"

        else:
            risk_level = "HIGH"

        if not reasons:
            reasons.append(
                "No significant risk indicators detected."
            )

        return {
            "student_id": student["student_id"],
            "student_name": student["student_name"],
            "batch": student.get("batch", "Unknown"),
            "risk_score": score,
            "risk_percentage": round(score * 100, 1),
            "risk_level": risk_level,
            "risk_factors": factor_scores,
            "reasons": reasons,
            "requires_counsellor_review": (
                risk_level in ("MEDIUM", "HIGH")
            ),
            "assessment_type": "RULE_BASED",
        }

    # ----------------------------------------------------------------
    # Assess all students
    # ----------------------------------------------------------------

    def assess_all(
        self,
        students: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:

        results = []

        for student in students:
            result = self.assess_student(student)
            results.append(result)

        return results


# -------------------------------------------------------------------
# Counsellor task creation
# -------------------------------------------------------------------

def create_counsellor_task(
    assessment: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Create a follow-up task for medium/high risk students.

    This function does not contact parents or change fee records.
    """

    if not assessment["requires_counsellor_review"]:
        return None

    student_id = assessment["student_id"]

    # Prevent duplicate open tasks for the same student.
    for task in counsellor_task_queue:

        if (
            task["student_id"] == student_id
            and task["status"] == "OPEN"
        ):
            return task

    task = {
        "task_id": f"RISK-{student_id}",
        "student_id": student_id,
        "student_name": assessment["student_name"],
        "risk_level": assessment["risk_level"],
        "risk_score": assessment["risk_score"],
        "reasons": assessment["reasons"],
        "recommended_action": (
            "Counsellor should review the student's situation "
            "and contact the appropriate person if necessary."
        ),
        "status": "OPEN",
        "false_positive": False,
        "created_date": date.today().isoformat(),
    }

    counsellor_task_queue.append(task)

    return task


# -------------------------------------------------------------------
# False-positive handling
# -------------------------------------------------------------------

def mark_false_positive(
    task_id: str,
    counsellor_note: str
) -> Dict[str, Any]:
    """
    Allow a counsellor to dismiss an incorrect risk flag.

    A production version must record the authenticated
    counsellor's user ID and audit history.
    """

    if not counsellor_note or not counsellor_note.strip():
        raise ValueError(
            "A counsellor note is required."
        )

    for task in counsellor_task_queue:

        if task["task_id"] == task_id:

            if task["status"] != "OPEN":
                raise ValueError(
                    "Only open tasks can be marked as false positives."
                )

            task["false_positive"] = True
            task["status"] = "DISMISSED"
            task["counsellor_note"] = counsellor_note.strip()

            return task

    raise ValueError("Counsellor task not found.")


# -------------------------------------------------------------------
# Task completion
# -------------------------------------------------------------------

def complete_counsellor_task(
    task_id: str,
    counsellor_note: str
) -> Dict[str, Any]:

    if not counsellor_note or not counsellor_note.strip():
        raise ValueError(
            "A completion note is required."
        )

    for task in counsellor_task_queue:

        if task["task_id"] == task_id:

            if task["status"] != "OPEN":
                raise ValueError(
                    "Only open tasks can be completed."
                )

            task["status"] = "COMPLETED"
            task["counsellor_note"] = counsellor_note.strip()

            return task

    raise ValueError("Counsellor task not found.")


# -------------------------------------------------------------------
# Full risk assessment workflow
# -------------------------------------------------------------------

def run_risk_assessment(
    students: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:

    students = students if students is not None else SAMPLE_STUDENTS

    engine = AIDropoutRiskEngine()

    assessments = engine.assess_all(students)

    for assessment in assessments:

        risk_assessments[assessment["student_id"]] = assessment

        create_counsellor_task(assessment)

    return assessments


# -------------------------------------------------------------------
# Reporting
# -------------------------------------------------------------------

def print_risk_report(
    assessments: List[Dict[str, Any]]
) -> None:

    print("\nSTUDENT DROPOUT RISK REPORT")
    print("=" * 75)

    for assessment in assessments:

        print(f"\nStudent      : {assessment['student_name']}")
        print(f"Student ID   : {assessment['student_id']}")
        print(f"Batch        : {assessment['batch']}")
        print(f"Risk score   : {assessment['risk_percentage']}%")
        print(f"Risk level   : {assessment['risk_level']}")

        print("Risk factors:")

        for reason in assessment["reasons"]:
            print(f"  - {reason}")

        print(
            "Counsellor review:",
            "Required"
            if assessment["requires_counsellor_review"]
            else "Not currently required"
        )

    print("\n" + "=" * 75)


def print_counsellor_queue() -> None:

    print("\nCOUNSELLOR FOLLOW-UP QUEUE")
    print("=" * 75)

    if not counsellor_task_queue:
        print("No counsellor tasks available.")

    for task in counsellor_task_queue:

        print(f"\nTask ID     : {task['task_id']}")
        print(f"Student     : {task['student_name']}")
        print(f"Risk level  : {task['risk_level']}")
        print(f"Risk score  : {task['risk_score']}")
        print(f"Status      : {task['status']}")

        for reason in task["reasons"]:
            print(f"  - {reason}")

    print("\n" + "=" * 75)


# -------------------------------------------------------------------
# Main execution
# -------------------------------------------------------------------

if __name__ == "__main__":

    assessments = run_risk_assessment()

    print_risk_report(assessments)

    print_counsellor_queue()
