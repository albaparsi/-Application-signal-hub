from app.classifier import classify_email
from app.enums import EmailSignalType


def test_classifies_confirmation():
    result = classify_email(
        "Thank you for applying to Acme",
        "We have received your application and will be in touch soon.",
    )
    assert result.signal_type == EmailSignalType.CONFIRMATION
    assert result.confidence > 0


def test_classifies_interview_invite():
    result = classify_email(
        "Next steps",
        "We would like to invite you to interview for the Software Engineer role.",
    )
    assert result.signal_type == EmailSignalType.INTERVIEW


def test_classifies_rejection():
    result = classify_email(
        "Update on your application",
        "Unfortunately, we have decided to move forward with other candidates.",
    )
    assert result.signal_type == EmailSignalType.REJECTION


def test_classifies_offer():
    result = classify_email(
        "Congratulations!",
        "We are pleased to offer you the position of Software Engineer at Acme.",
    )
    assert result.signal_type == EmailSignalType.OFFER


def test_classifies_unknown_for_unrelated_email():
    result = classify_email(
        "Your weekly newsletter",
        "Here are this week's top articles on software engineering.",
    )
    assert result.signal_type == EmailSignalType.UNKNOWN
    assert result.confidence == 0.0


def test_rejection_takes_priority_over_interview_keyword_collision():
    # Contains the word "interview" but is clearly a rejection.
    result = classify_email(
        "Regarding your interview",
        "Unfortunately, we will not be moving forward with your application at this time.",
    )
    assert result.signal_type == EmailSignalType.REJECTION


def test_confidence_scales_with_multiple_matched_phrases():
    single = classify_email("Update", "We regret to inform you of our decision.")
    multiple = classify_email(
        "Update",
        "We regret to inform you that we will not be moving forward with your application.",
    )
    assert multiple.confidence >= single.confidence
