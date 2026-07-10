from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from database import get_db
from history import record_history
from models import EmailVerificationToken, PasswordResetToken, RefreshToken, User
from schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
    Token,
    TokenData,
    UserCreate,
    UserLogin,
    UserResponse,
    VerifyEmailRequest,
)
from security import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    create_verification_token,
    decode_token,
    get_current_user,
    get_password_hash,
    hash_token,
    normalize_email,
    revoke_token,
    token_is_blacklisted,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _serialize_user(user: User) -> UserResponse:
    return UserResponse.model_validate(user)


def _issue_tokens(db: Session, user: User) -> dict:
    access_token = create_access_token(user.email)
    refresh_token = create_refresh_token(user.email)
    refresh_payload = decode_token(refresh_token)
    db.add(
        RefreshToken(
            user_id=user.id,
            jti=refresh_payload["jti"],
            token_hash=hash_token(refresh_token),
            expires_at=datetime.fromtimestamp(refresh_payload["exp"], tz=timezone.utc),
        )
    )
    db.commit()
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}


@router.post("/signup", response_model=AuthResponse)
def signup(payload: UserCreate, db: Session = Depends(get_db)):
    full_name = payload.full_name.strip()
    email = normalize_email(payload.email)
    if not full_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Full name is required")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is required")
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    user = User(
        full_name=full_name,
        email=email,
        password_hash=get_password_hash(payload.password),
        role="user",
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    verification_token = create_verification_token(user.email)
    verification_payload = decode_token(verification_token)
    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(verification_token),
            expires_at=datetime.fromtimestamp(verification_payload["exp"], tz=timezone.utc),
        )
    )
    db.commit()
    tokens = _issue_tokens(db, user)
    return AuthResponse(
        **tokens,
        user=_serialize_user(user),
        verification_token=verification_token,
    )


@router.post("/login", response_model=AuthResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    tokens = _issue_tokens(db, user)
    return AuthResponse(**tokens, user=_serialize_user(user))


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return _serialize_user(current_user)


@router.post("/logout")
def logout(
    request: Request,
    payload: RefreshTokenRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_header = request.headers.get("Authorization") if request else None
    if auth_header and auth_header.lower().startswith("bearer "):
        revoke_token(db, auth_header.split(" ", 1)[1], "access")
    if payload and payload.refresh_token:
        revoke_token(db, payload.refresh_token, "refresh")
    return {"status": "logged_out"}


@router.post("/refresh", response_model=AuthResponse)
def refresh_token(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    token_payload = decode_token(payload.refresh_token)
    if token_payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if token_is_blacklisted(db, token_payload.get("jti")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    user = db.query(User).filter(User.email == token_payload.get("sub")).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    tokens = _issue_tokens(db, user)
    return AuthResponse(**tokens, user=_serialize_user(user))


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    token_payload = decode_token(payload.token)
    if token_payload.get("type") != "email_verification":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification token")
    email = token_payload.get("sub")
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    token_record = db.query(EmailVerificationToken).filter(EmailVerificationToken.token_hash == hash_token(payload.token)).first()
    if token_record is None or token_record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is invalid or already used")
    token_record.used_at = datetime.utcnow()
    user.is_verified = True
    db.commit()
    return {"status": "verified"}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return {"status": "ok"}
    token = create_reset_token(user.email)
    token_payload = decode_token(token)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.fromtimestamp(token_payload["exp"], tz=timezone.utc),
        )
    )
    db.commit()
    return {"status": "ok", "reset_token": token}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_payload = decode_token(payload.token)
    if token_payload.get("type") != "password_reset":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")
    user = db.query(User).filter(User.email == token_payload.get("sub")).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    token_record = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == hash_token(payload.token)).first()
    if token_record is None or token_record.used_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is invalid or already used")
    user.password_hash = get_password_hash(payload.new_password)
    token_record.used_at = datetime.utcnow()
    db.commit()
    return {"status": "password_reset"}
