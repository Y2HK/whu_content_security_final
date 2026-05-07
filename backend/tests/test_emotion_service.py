from app.services.emotion_service import EMOTIONS, analyze_image_emotion


def test_emotion_service_falls_back_for_invalid_image_bytes():
    result = analyze_image_emotion(b"not-an-image", fallback_seed="student-001")

    assert result.emotion in EMOTIONS
    assert 0 <= result.confidence <= 1
    assert result.source in {"deepface", "fallback"}
