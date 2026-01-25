from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, BigInteger, Enum, Float, func, Text, Date
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from database.db_connector import Base
from datetime import datetime
from enum import Enum
from sqlalchemy.types import Enum as SQLAlchemyEnum

from subjects.models.models import Subject

class PaymentStatus(str, Enum):
    pending_payment = "pending_payment"
    paid = "paid"
    failed = "failed"
    refunded = "refunded"

class ReconciliationStatus(str, Enum):
    matched = "matched"
    verified = "verified"
    approved = "approved"
    rejected = "rejected"

class PaymentMethod(str, Enum):
    mpesa = "M-Pesa"
    mixx = "Mixx by Yas"
    airtel = "Airtel Money"
    bank = "Bank"
    card = "Card"
    cash = "Cash"
    other = "Other"

class ApplicationStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    waitlisted = "waitlisted"
    withdrawn = "withdrawn"
    verified = "verified"

class Application(Base):
    __tablename__ = "applications"
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    payment_status = Column(SQLAlchemyEnum(PaymentStatus), default=PaymentStatus.pending_payment)
    total_fee = Column(Float, default=0.0)
    status = Column(SQLAlchemyEnum(ApplicationStatus), default=ApplicationStatus.pending)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"))
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"))
    deleted_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], backref="applications")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
    details = relationship("ApplicationDetail", back_populates="application", cascade="all, delete-orphan")
    payment_details = relationship("PaymentDetail", back_populates="application")
    payments = relationship("Payment", secondary="payment_details", back_populates="application")
    
    def __repr__(self):
        return f"<Application(id={self.id}, user_id={self.user_id}, status={self.status})>"

class ApplicationDetail(Base):
    __tablename__ = "application_details"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    application_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("applications.id"), nullable=False)
    subject_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("subjects.id"), nullable=False)
    fee = Column(Float, default=0.0)
    status = Column(SQLAlchemyEnum(ApplicationStatus), default=ApplicationStatus.pending)
    is_active = Column(Boolean, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"))
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"))
    deleted_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relationships
    application = relationship("Application", back_populates="details")
    subject = relationship("Subject")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
    
    def __repr__(self):
        return f"<ApplicationDetail(id={self.id}, application_id={self.application_id}, subject_id={self.subject_id})>"

class Payment(Base):
    """Payment model to store payment information"""
    __tablename__ = 'payments'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    transaction_id = Column(String(100), unique=True, nullable=False, index=True)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50), nullable=False)
    payment_status = Column(SQLAlchemyEnum(PaymentStatus), nullable=False, default=PaymentStatus.pending_payment)
    payment_date = Column(DateTime, nullable=True)
    bank_reference = Column(String(100), nullable=True, index=True)
    mobile_number = Column(String(20), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    deleted_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Define relationships
    payment_details = relationship("PaymentDetail", back_populates="payment", cascade="all, delete-orphan")
    reconciliations = relationship("BankReconciliation", back_populates="payment")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
    application = relationship("Application", secondary="payment_details", back_populates="payments")
    
    def __repr__(self):
        return f"<Payment(id={self.id}, transaction_id={self.transaction_id}, amount={self.amount}, payment_status={self.payment_status})>"

class PaymentDetail(Base):
    """Payment Detail model to store additional payment details"""
    __tablename__ = 'payment_details'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    payment_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('payments.id'), nullable=False)
    application_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('applications.id'), nullable=False)
    amount = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    deleted_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Define relationships
    payment = relationship("Payment", back_populates="payment_details")
    application = relationship("Application", back_populates="payment_details")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    deleter = relationship("User", foreign_keys=[deleted_by])
    
    def __repr__(self):
        return f"<PaymentDetail(id={self.id}, payment_id={self.payment_id}, application_id={self.application_id}, amount={self.amount})>"

class PaymentTransaction(Base):
    """Payment Transaction model to store payment information for applications"""
    __tablename__ = 'payment_transactions'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    transaction_id = Column(String(50), unique=True, nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(20), nullable=False)
    payment_status = Column(SQLAlchemyEnum(PaymentStatus), nullable=False, default=PaymentStatus.pending_payment)
    payment_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    mobile_number = Column(String(20), nullable=True)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), nullable=True)
    deleted_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Define relationship with payment details
    transaction_details = relationship("TransactionDetail", back_populates="transaction", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<PaymentTransaction(id={self.id}, transaction_id={self.transaction_id}, amount={self.amount})>"

class TransactionDetail(Base):
    """Transaction Detail model to store additional payment details"""
    __tablename__ = 'transaction_details'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    transaction_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('payment_transactions.id'), nullable=False)
    provider_reference = Column(String(50), nullable=True)
    confirmation_code = Column(String(50), nullable=True)
    payment_data = Column(Text, nullable=True)  # For storing JSON response from payment provider
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    
    # Define relationship with payment
    transaction = relationship("PaymentTransaction", back_populates="transaction_details")
    
    def __repr__(self):
        return f"<TransactionDetail(id={self.id}, transaction_id={self.transaction_id})>"

class BankDetails(Base):
    """Bank Details model to store bank information for payments"""
    __tablename__ = 'bank_details'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    bank_name = Column(String(100), nullable=False)
    account_name = Column(String(100), nullable=False)
    account_number = Column(String(50), nullable=False)
    branch_code = Column(String(20), nullable=False)
    swift_code = Column(String(20), nullable=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    
    # Define relationships
    transactions = relationship("BankTransaction", back_populates="account")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self):
        return f"<BankDetails(id={self.id}, bank_name={self.bank_name}, account_name={self.account_name}, account_number={self.account_number})>"

class BankTransaction(Base):
    """Bank Transaction model to store bank statement transactions"""
    __tablename__ = 'bank_transactions'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    account_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('bank_details.id'), nullable=False)
    batch_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('bank_statement_batches.id'), nullable=True)
    transaction_id = Column(String(100), unique=True, nullable=False, index=True)
    payment_date = Column(Date, nullable=False)
    reference_number = Column(String(100), nullable=True, index=True)
    account_number = Column(String(50), nullable=True)
    amount = Column(Float, nullable=False)
    is_reconciled = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define relationships
    account = relationship("BankDetails", back_populates="transactions")
    batch = relationship("BankStatementBatch", back_populates="transactions")
    reconciliations = relationship("BankReconciliation", back_populates="bank_transaction")
    
    def __repr__(self):
        return f"<BankTransaction(id={self.id}, transaction_id={self.transaction_id}, amount={self.amount})>"

class BankStatementBatch(Base):
    """Bank Statement Batch model to store batch information for bank statements"""
    __tablename__ = 'bank_statement_batches'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    account_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('bank_details.id'), nullable=False)
    batch_reference = Column(String(50), nullable=False, unique=True)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    number_of_transactions = Column(Integer, nullable=False)
    total_batch_amount = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    
    # Relationship with BankDetails
    bank_account = relationship("BankDetails", backref="statement_batches")
    # Relationship with BankTransaction
    transactions = relationship("BankTransaction", back_populates="batch", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<BankStatementBatch(id={self.id}, batch_reference={self.batch_reference}, total_amount={self.total_batch_amount})>"

class BankReconciliation(Base):
    """Bank Reconciliation model to store reconciliation records"""
    __tablename__ = 'bank_reconciliation'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    bank_transaction_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('bank_transactions.id'), nullable=False)
    payment_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('payments.id'), nullable=False)
    status = Column(SQLAlchemyEnum(ReconciliationStatus), nullable=False, default=ReconciliationStatus.matched)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    
    # Define relationships
    bank_transaction = relationship("BankTransaction", back_populates="reconciliations")
    payment = relationship("Payment", back_populates="reconciliations")
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self):
        return f"<BankReconciliation(id={self.id}, bank_transaction_id={self.bank_transaction_id}, payment_id={self.payment_id}, status={self.status})>"

class PaymentApproval(Base):
    __tablename__ = 'payment_approvals'

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    reconciliation_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('bank_reconciliation.id'), nullable=False)
    user_id = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey('users.id'), nullable=False)
    previous_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    comments = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reconciliation = relationship('BankReconciliation', backref='approvals')
    user = relationship('User', backref='payment_approvals')

    def __repr__(self):
        return f'<PaymentApproval {self.id}>'

class PaymentMethodModel(Base):
    """Payment Method model to store payment method information"""
    __tablename__ = 'payment_methods'
    
    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    icon = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    instructions = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    updated_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    
    # Define relationships
    creator = relationship("User", foreign_keys=[created_by])
    updater = relationship("User", foreign_keys=[updated_by])
    
    def __repr__(self):
        return f"<PaymentMethodModel(id={self.id}, name={self.name}, code={self.code}, is_active={self.is_active})>"


# GSM-7 segment size (chars per SMS). Multi-part: 161–320 → 2, 321–480 → 3, etc.
SMS_CHARS_PER_SEGMENT = 160


class SmsLog(Base):
    """Audit log for all SMS sent. Used for reconciliation and compliance."""

    __tablename__ = "sms_logs"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, index=True)
    sender_id = Column(String(100), nullable=False)
    recipient = Column(String(20), nullable=False, index=True)
    message = Column(Text, nullable=False)
    message_length = Column(Integer, nullable=False)
    sms_count = Column(Integer, nullable=False)  # segments used (1 per 160 chars; for billing reconciliation)
    process_name = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False)  # 'sent' | 'failed'
    provider = Column(String(50), nullable=False, default="mshastra")
    external_id = Column(String(100), nullable=True)  # e.g. msg_id from provider
    api_response_raw = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(BigInteger().with_variant(Integer, "sqlite"), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return f"<SmsLog(id={self.id}, recipient={self.recipient}, process={self.process_name}, status={self.status})>" 