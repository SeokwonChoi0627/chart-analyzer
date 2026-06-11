"""포트폴리오 페이지 비밀번호 검증."""
import hmac


def verify_password(raw: str, expected: str | None) -> bool:
    """입력 비밀번호 검증. expected 미설정 시 항상 실패 (잠금 기본값)."""
    if not expected:
        return False
    candidate = (raw or "").strip()
    if not candidate:
        return False
    return hmac.compare_digest(candidate, expected)
