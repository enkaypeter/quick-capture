from typing import Optional, Tuple

from werkzeug.security import generate_password_hash, check_password_hash

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.invite_service import InviteService


class AuthService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.invite_service = InviteService()

    def register_user(
        self,
        email: str,
        first_name: str,
        password: str,
        invite_code: str,
        expected_invite_code: str,
        bootstrap_invite_enabled: bool = True,
    ) -> Tuple[Optional[User], Optional[str]]:
        """Register a new user.

        Returns:
            Tuple of (user, error_message). On success error_message is None.
        """
        if not self.invite_service.is_valid(
            invite_code,
            expected_invite_code,
            bootstrap_invite_enabled,
        ):
            return None, "Invalid invite code."

        if self.user_repo.get_by_email(email):
            return None, "Email already exists."

        if len(email) < 4:
            return None, "Please enter a valid email."

        if len(first_name) < 2:
            return None, "Please enter a valid name."

        if len(password) < 8:
            return None, "Password must be at least 8 characters."

        user = self.user_repo.create(
            email=email,
            first_name=first_name,
            password=generate_password_hash(password, method="pbkdf2:sha256"),
        )
        self.invite_service.consume(
            invite_code,
            user.id,
            expected_invite_code,
            bootstrap_invite_enabled,
        )
        return user, None

    def authenticate(self, email: str, password: str) -> Tuple[Optional[User], Optional[str]]:
        """Authenticate a user by email and password.

        Returns:
            Tuple of (user, error_message). On success error_message is None.
        """
        user = self.user_repo.get_by_email(email)

        if not user or not check_password_hash(user.password, password):
            return None, "Incorrect email or password, try again."

        return user, None
