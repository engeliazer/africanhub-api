"""
Book purchase workflow: orders, payment submission, approval, entitlements, LMS access.
"""

import random
import string
import secrets
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session

from applications.models.models import Payment, PaymentStatus, PaymentMethod, PaymentMethodModel
from books.models.sales_models import (
    BookOrder,
    BookOrderItem,
    BookOrderStatus,
    UserPaidBookEdition,
)
from books.services.price_resolution_service import resolve_customer_price, PriceResolutionError
from services.lms_client import LMSClient


class BookPurchaseError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def customer_profile_from_order(order: BookOrder) -> Optional[Dict[str, Any]]:
    user = getattr(order, "user", None)
    if not user:
        return None
    parts = [user.first_name, user.middle_name, user.last_name]
    name = " ".join(p for p in parts if p).strip()
    return {
        "user_id": user.id,
        "customer_name": name or None,
        "phone": user.phone,
        "email": user.email,
    }


def user_owns_edition(db: Session, user_id: int, edition_reference_id: str) -> bool:
    return (
        db.query(UserPaidBookEdition.id)
        .filter(
            UserPaidBookEdition.user_id == user_id,
            UserPaidBookEdition.edition_reference_id == edition_reference_id,
        )
        .first()
        is not None
    )


def _generate_order_number() -> str:
    suffix = secrets.token_hex(3).upper()
    return f"BOOK-ORD-{datetime.utcnow().strftime('%Y%m%d')}-{suffix}"


def _generate_transaction_id() -> str:
    return "BOOK-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8)) + "-" + datetime.utcnow().strftime("%Y%m%d%H%M%S")


def _payment_method_enum_from_string(payment_method: str) -> Optional[PaymentMethod]:
    for method in PaymentMethod:
        if method.value == payment_method or method.name.lower() == payment_method.lower():
            return method
    return None


def resolve_book_payment_method(
    db: Session,
    payment_method: Optional[str],
    service_provider_id: Optional[int],
) -> str:
    """
    Resolve payment method string the same way application payments do:
    prefer active row from payment_methods (service provider id), else enum string.
    """
    if service_provider_id is not None:
        provider = (
            db.query(PaymentMethodModel)
            .filter(
                PaymentMethodModel.id == service_provider_id,
                PaymentMethodModel.is_active.is_(True),
            )
            .first()
        )
        if not provider:
            raise BookPurchaseError("Invalid or inactive payment service provider", 400)

        for candidate in (provider.name, provider.code):
            if not candidate:
                continue
            matched = _payment_method_enum_from_string(candidate)
            if matched:
                return matched.value
        return provider.name

    if not payment_method or not str(payment_method).strip():
        raise BookPurchaseError("service_provider_id or payment_method is required", 400)

    method_enum = _payment_method_enum_from_string(str(payment_method).strip())
    if not method_enum:
        raise BookPurchaseError(
            f"Invalid payment method. Valid options: {[m.value for m in PaymentMethod]}",
            400,
        )
    return method_enum.value


def create_book_order(
    db: Session,
    lms_client: LMSClient,
    user_id: int,
    edition_reference_ids: List[str],
) -> BookOrder:
    if not edition_reference_ids:
        raise BookPurchaseError("At least one edition is required")

    unique_editions = list(dict.fromkeys(edition_reference_ids))
    skipped_owned: List[str] = []
    to_buy: List[str] = []

    for edition_ref in unique_editions:
        if user_owns_edition(db, user_id, edition_ref):
            skipped_owned.append(edition_ref)
        else:
            to_buy.append(edition_ref)

    if not to_buy:
        raise BookPurchaseError(
            "You already own all selected editions",
            status_code=409,
        )

    order = BookOrder(
        user_id=user_id,
        order_number=_generate_order_number(),
        status=BookOrderStatus.pending_payment.value,
        currency="TZS",
        total_amount=Decimal("0"),
    )
    db.add(order)
    db.flush()

    total = Decimal("0")
    currency = "TZS"

    for edition_ref in to_buy:
        try:
            resolved = resolve_customer_price(db, lms_client, user_id, edition_ref)
        except PriceResolutionError as exc:
            raise BookPurchaseError(str(exc), exc.status_code) from exc

        unit_price = resolved["unit_price_decimal"]
        qty = 1
        line_total = unit_price * qty
        currency = resolved["currency"]

        db.add(
            BookOrderItem(
                order_id=order.id,
                book_reference_id=resolved["book_reference_id"],
                edition_reference_id=edition_ref,
                quantity=qty,
                unit_price=unit_price,
                total_price=line_total,
            )
        )
        total += line_total

    order.total_amount = total
    order.currency = currency
    db.commit()
    db.refresh(order)

    order._skipped_owned_editions = skipped_owned  # type: ignore[attr-defined]
    return order


def submit_book_order_payment(
    db: Session,
    user_id: int,
    order_id: int,
    payment_method: str,
    amount: Optional[float],
    mobile_number: Optional[str],
    bank_reference: Optional[str],
    description: Optional[str],
) -> Payment:
    order = (
        db.query(BookOrder)
        .filter(BookOrder.id == order_id, BookOrder.user_id == user_id)
        .first()
    )
    if not order:
        raise BookPurchaseError("Book order not found", 404)

    if order.status not in (
        BookOrderStatus.pending_payment.value,
        BookOrderStatus.payment_submitted.value,
        BookOrderStatus.pending.value,
    ):
        raise BookPurchaseError(f"Order cannot accept payment in status {order.status}", 409)

    expected = float(order.total_amount)
    pay_amount = float(amount) if amount is not None else expected
    if abs(pay_amount - expected) > 0.01:
        raise BookPurchaseError(
            f"Payment amount must match order total ({expected} {order.currency})",
            400,
        )

    method_enum = _payment_method_enum_from_string(payment_method)
    is_cash = method_enum == PaymentMethod.cash if method_enum else payment_method.lower() == "cash"

    if not is_cash:
        ref = (bank_reference or "").strip()
        if not ref:
            raise BookPurchaseError(
                "payment_reference (or bank_reference) is required for this payment method",
                400,
            )
        bank_reference = ref

    if not mobile_number or not str(mobile_number).strip():
        raise BookPurchaseError("mobile_number is required", 400)

    payment = Payment(
        transaction_id=_generate_transaction_id(),
        amount=pay_amount,
        payment_method=payment_method,
        payment_status=PaymentStatus.pending_payment,
        payment_date=datetime.utcnow(),
        mobile_number=str(mobile_number).strip(),
        bank_reference=bank_reference,
        description=description or f"BOOK_ORDER|{order.order_number}",
        created_by=user_id,
        updated_by=user_id,
    )
    db.add(payment)
    db.flush()

    order.payment_id = payment.id
    order.status = BookOrderStatus.payment_submitted.value
    order.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(payment)
    db.refresh(order)
    return payment


def approve_book_payment(db: Session, payment_id: int, approved_by: int) -> Dict[str, Any]:
    order = db.query(BookOrder).filter(BookOrder.payment_id == payment_id).first()
    if not order:
        raise BookPurchaseError("No book order linked to this payment", 404)

    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.is_active.is_(True)).first()
    if not payment:
        raise BookPurchaseError("Payment not found", 404)

    if payment.payment_status == PaymentStatus.paid:
        raise BookPurchaseError("Payment is already approved", 409)

    try:
        now = datetime.utcnow()
        payment.payment_status = PaymentStatus.paid
        payment.payment_date = payment.payment_date or now
        payment.updated_by = approved_by
        payment.updated_at = now

        order.status = BookOrderStatus.paid.value
        order.completed_at = now
        order.updated_at = now

        entitlements = []
        for item in order.items:
            existing = (
                db.query(UserPaidBookEdition)
                .filter(
                    UserPaidBookEdition.user_id == order.user_id,
                    UserPaidBookEdition.edition_reference_id == item.edition_reference_id,
                )
                .first()
            )
            if existing:
                continue
            ent = UserPaidBookEdition(
                user_id=order.user_id,
                book_reference_id=item.book_reference_id,
                edition_reference_id=item.edition_reference_id,
                order_id=order.id,
                payment_id=payment.id,
                paid_amount=item.unit_price,
                currency=order.currency,
                paid_at=now,
            )
            db.add(ent)
            entitlements.append(item.edition_reference_id)

        db.commit()
        return {
            "payment_id": payment.id,
            "order_id": order.id,
            "order_number": order.order_number,
            "editions_granted": entitlements,
        }
    except Exception:
        db.rollback()
        raise


def reject_book_payment(
    db: Session,
    payment_id: int,
    rejected_by: int,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    order = db.query(BookOrder).filter(BookOrder.payment_id == payment_id).first()
    if not order:
        raise BookPurchaseError("No book order linked to this payment", 404)

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise BookPurchaseError("Payment not found", 404)

    payment.payment_status = PaymentStatus.failed
    payment.updated_by = rejected_by
    payment.updated_at = datetime.utcnow()
    if reason:
        payment.description = (payment.description or "") + f" | REJECTED: {reason}"

    order.status = BookOrderStatus.pending_payment.value
    order.payment_id = None
    order.updated_at = datetime.utcnow()

    db.commit()
    return {"payment_id": payment.id, "order_id": order.id, "status": "REJECTED"}


def order_to_response(order: BookOrder, include_skipped: Optional[List[str]] = None) -> dict:
    customer = customer_profile_from_order(order)
    data = {
        "id": order.id,
        "user_id": order.user_id,
        "order_number": order.order_number,
        "status": order.status,
        "total_amount": float(order.total_amount),
        "currency": order.currency,
        "customer_name": customer["customer_name"] if customer else None,
        "customer_phone": customer["phone"] if customer else None,
        "customer_email": customer["email"] if customer else None,
        "customer": customer,
        "payment_id": order.payment_id,
        "payment_reference": order.payment.bank_reference if order.payment else None,
        "payment_method": order.payment.payment_method if order.payment else None,
        "payment_status": order.payment.payment_status.value if order.payment else None,
        "mobile_number": order.payment.mobile_number if order.payment else None,
        "attachment_filename": order.attachment_filename,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "completed_at": order.completed_at.isoformat() if order.completed_at else None,
        "items": [
            {
                "book_reference_id": item.book_reference_id,
                "edition_reference_id": item.edition_reference_id,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "total_price": float(item.total_price),
            }
            for item in order.items
        ],
    }
    if include_skipped:
        data["skipped_already_owned"] = include_skipped
    return data


def list_paid_editions_for_user(db: Session, user_id: int) -> List[UserPaidBookEdition]:
    return (
        db.query(UserPaidBookEdition)
        .filter(UserPaidBookEdition.user_id == user_id)
        .order_by(UserPaidBookEdition.paid_at.desc())
        .all()
    )


def get_paid_edition_for_user(
    db: Session,
    user_id: int,
    edition_reference_id: str,
) -> Optional[UserPaidBookEdition]:
    return (
        db.query(UserPaidBookEdition)
        .filter(
            UserPaidBookEdition.user_id == user_id,
            UserPaidBookEdition.edition_reference_id == edition_reference_id,
        )
        .first()
    )


def enrich_access_grant_with_lms_metadata(
    grant_data: Dict[str, Any],
    lms_client: Optional[LMSClient],
    edition_reference_id: str,
    entitlement: Optional[UserPaidBookEdition] = None,
) -> Dict[str, Any]:
    """Attach LMS book/edition metadata to a reading access grant response."""
    from books.services.lms_edition_helpers import attach_store_catalog_metadata
    from config import apply_per_edition_cover_urls

    out = dict(grant_data)
    if entitlement:
        out["paid_amount"] = float(entitlement.paid_amount)
        out["currency"] = entitlement.currency
        out["paid_at"] = entitlement.paid_at.isoformat() if entitlement.paid_at else None

    if not lms_client:
        return apply_per_edition_cover_urls(out, edition_reference_id)

    hint = entitlement.book_reference_id if entitlement else out.get("parent_book_reference_id")
    try:
        edition = lms_client.get_edition(
            edition_reference_id,
            book_reference_id_hint=hint,
        )
    except Exception:
        out.setdefault("book", None)
        out.setdefault("edition", None)
        return apply_per_edition_cover_urls(out, edition_reference_id)

    catalog = attach_store_catalog_metadata(
        {"edition_reference_id": edition_reference_id},
        edition,
        lms_client,
    )
    for key in (
        "title",
        "author",
        "edition_label",
        "description",
        "book_reference_id",
    ):
        if catalog.get(key) is not None:
            out[key] = catalog[key]
    out["book"] = catalog.get("book")
    out["edition"] = catalog.get("edition")
    return apply_per_edition_cover_urls(out, edition_reference_id)


def enrich_paid_edition(
    entitlement: UserPaidBookEdition,
    lms_client: Optional[LMSClient],
) -> dict:
    payload = {
        "book_reference_id": entitlement.book_reference_id,
        "edition_reference_id": entitlement.edition_reference_id,
        "paid_amount": float(entitlement.paid_amount),
        "currency": entitlement.currency,
        "paid_at": entitlement.paid_at.isoformat() if entitlement.paid_at else None,
        "order_id": entitlement.order_id,
        "payment_id": entitlement.payment_id,
    }
    from config import hub_edition_cover_url

    payload["cover_url"] = hub_edition_cover_url(entitlement.edition_reference_id)
    if lms_client:
        try:
            edition = lms_client.get_edition(entitlement.edition_reference_id)
            payload["edition"] = edition
            if isinstance(edition, dict) and isinstance(edition.get("book"), dict):
                payload["book"] = edition["book"]
        except Exception:
            payload["book"] = None
            payload["edition"] = None
    return payload
