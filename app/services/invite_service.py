import secrets
from datetime import UTC, datetime
from typing import Optional, Tuple

from app.extensions import db
from app.models.invite_code import InviteCode, InviteCodeStatus


class InviteService:
    def list_codes(self) -> list[InviteCode]:
        return InviteCode.query.order_by(InviteCode.created_at.desc()).all()

    def create_code(
        self,
        created_by_user_id: int,
        label: Optional[str] = None,
        max_uses: int = 1,
    ) -> InviteCode:
        try:
            max_uses_value = int(max_uses or 1)
        except (TypeError, ValueError):
            max_uses_value = 1
        max_uses = max(1, min(max_uses_value, 25))
        code = self._generate_unique_code()
        invite = InviteCode(
            code=code,
            label=(label or "").strip() or None,
            max_uses=max_uses,
            created_by_user_id=created_by_user_id,
        )
        db.session.add(invite)
        db.session.commit()
        return invite

    def deny_code(self, invite_id: int) -> Tuple[Optional[InviteCode], Optional[str]]:
        invite = db.session.get(InviteCode, invite_id)
        if not invite:
            return None, "Invite code not found."
        if invite.status == InviteCodeStatus.USED:
            return None, "Used invite codes cannot be denied."

        invite.status = InviteCodeStatus.DENIED
        db.session.commit()
        return invite, None

    def is_valid(
        self,
        code: str,
        fallback_code: str,
        bootstrap_invite_enabled: bool = True,
    ) -> bool:
        code = (code or "").strip()
        if bootstrap_invite_enabled and code and fallback_code and code == fallback_code:
            return True

        invite = InviteCode.query.filter_by(code=code).first()
        return bool(
            invite
            and invite.status == InviteCodeStatus.ACTIVE
            and invite.uses < invite.max_uses
        )

    def consume(
        self,
        code: str,
        user_id: int,
        fallback_code: str,
        bootstrap_invite_enabled: bool = True,
    ) -> None:
        if bootstrap_invite_enabled and code and fallback_code and code == fallback_code:
            return

        invite = InviteCode.query.filter_by(code=code).first()
        if not invite:
            return

        invite.uses += 1
        invite.used_by_user_id = user_id
        invite.used_at = datetime.now(UTC)
        if invite.uses >= invite.max_uses:
            invite.status = InviteCodeStatus.USED
        db.session.commit()

    def _generate_unique_code(self) -> str:
        while True:
            code = secrets.token_urlsafe(12)
            if not InviteCode.query.filter_by(code=code).first():
                return code
