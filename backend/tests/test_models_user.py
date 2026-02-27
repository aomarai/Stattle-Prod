"""
Tests for the User SQLAlchemy model.

Covers:
- Creating and persisting a User.
- All nullable / optional fields.
- Unique constraints (authentik_sub, email, github_username).
- __repr__ output.
- github_access_token and token-expiry fields.
"""

from datetime import datetime, timezone

import pytest
from app.models.user import User
from sqlalchemy.exc import IntegrityError
from tests.conftest import make_user


class TestUserCreation:
    """Tests for basic User creation and field persistence."""

    def test_create_user_minimal(self, db_session):
        """User can be created with only required fields."""
        user = User(authentik_sub="sub-minimal", email="minimal@example.com")
        db_session.add(user)
        db_session.flush()

        assert user.id is not None
        assert user.authentik_sub == "sub-minimal"
        assert user.email == "minimal@example.com"
        assert user.username is None
        assert user.github_username is None
        assert user.github_access_token is None
        assert user.github_token_expiry is None
        assert user.last_github_sync is None

    def test_create_user_all_fields(self, db_session):
        """User can be created with all fields populated."""
        expiry = datetime(2025, 12, 31, tzinfo=timezone.utc)
        sync = datetime(2024, 6, 1, tzinfo=timezone.utc)
        user = User(
            authentik_sub="sub-full",
            email="full@example.com",
            username="fulluser",
            github_username="gh-fulluser",
            github_access_token="gha_token123",
            github_token_expiry=expiry,
            last_github_sync=sync,
        )
        db_session.add(user)
        db_session.flush()

        assert user.id is not None
        assert user.username == "fulluser"
        assert user.github_username == "gh-fulluser"
        assert user.github_access_token == "gha_token123"
        assert user.github_token_expiry == expiry
        assert user.last_github_sync == sync

    def test_user_id_autoincrement(self, db_session):
        """Each User gets a unique auto-incremented id."""
        u1 = make_user(
            authentik_sub="sub-a", email="a@example.com", github_username="gh-a"
        )
        u2 = make_user(
            authentik_sub="sub-b", email="b@example.com", github_username="gh-b"
        )
        db_session.add_all([u1, u2])
        db_session.flush()

        assert u1.id != u2.id


class TestUserUniqueConstraints:
    """Tests for unique constraints on the User model."""

    def test_duplicate_authentik_sub_raises(self, db_session):
        """Creating two users with the same authentik_sub raises IntegrityError."""
        db_session.add(
            make_user(
                authentik_sub="dup-sub",
                email="first@example.com",
                github_username="gh-first",
            )
        )
        db_session.flush()

        db_session.add(
            make_user(
                authentik_sub="dup-sub",
                email="second@example.com",
                github_username="gh-second",
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_duplicate_email_raises(self, db_session):
        """Creating two users with the same email raises IntegrityError."""
        db_session.add(
            make_user(
                authentik_sub="sub-e1", email="dup@example.com", github_username="gh-e1"
            )
        )
        db_session.flush()

        db_session.add(
            make_user(
                authentik_sub="sub-e2", email="dup@example.com", github_username="gh-e2"
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_duplicate_github_username_raises(self, db_session):
        """Creating two users with the same github_username raises IntegrityError."""
        db_session.add(
            make_user(
                authentik_sub="sub-g1",
                email="g1@example.com",
                github_username="same-gh",
            )
        )
        db_session.flush()

        db_session.add(
            make_user(
                authentik_sub="sub-g2",
                email="g2@example.com",
                github_username="same-gh",
            )
        )
        with pytest.raises(IntegrityError):
            db_session.flush()

    def test_null_github_username_allowed_multiple(self, db_session):
        """Multiple users may have github_username=None (null is not unique-constrained)."""
        u1 = User(authentik_sub="sub-n1", email="n1@example.com", github_username=None)
        u2 = User(authentik_sub="sub-n2", email="n2@example.com", github_username=None)
        db_session.add_all([u1, u2])
        db_session.flush()  # Should not raise

        assert u1.id is not None
        assert u2.id is not None


class TestUserRepr:
    """Tests for User.__repr__."""

    def test_repr_contains_id_email_username(self, db_session):
        """__repr__ includes id, email, and username."""
        user = make_user(email="repr@example.com", username="repruser")
        db_session.add(user)
        db_session.flush()

        r = repr(user)
        assert str(user.id) in r
        assert "repr@example.com" in r
        assert "repruser" in r

    def test_repr_with_none_username(self, db_session):
        """__repr__ handles None username without raising."""
        user = User(authentik_sub="sub-repr-none", email="reprnone@example.com")
        db_session.add(user)
        db_session.flush()

        r = repr(user)
        assert "None" in r
