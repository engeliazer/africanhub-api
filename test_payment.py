from database.db_connector import db_session
from applications.controllers.payments_controller import PaymentsController
from applications.models.schemas import PaymentCreate

# Test payment function
def test_payment():
    # Create payment data
    payment_data = PaymentCreate(
        application_ids=[1],
        amount=0,
        payment_method="M-Pesa",
        mobile_number="255755344162",
        description="Test payment",
        created_by=1,
        updated_by=1
    )
    
    # Process payment
    controller = PaymentsController(db_session)
    
    try:
        payment = controller.create_payment(payment_data)
        print("Payment successful!")
        print("Transaction ID:", payment.get("transaction_id"))
        print("Amount:", payment.get("amount"))
        print("Payment status:", payment.get("payment_status"))
        print("Payment date:", payment.get("payment_date"))
        
        # Print payment details
        print("\nPayment details:")
        for detail in payment.get("payment_details", []):
            print(f"  Application ID: {detail.get('application_id')}")
            print(f"  Amount: {detail.get('amount')}")
            
        return payment
    except Exception as e:
        print(f"Error processing payment: {str(e)}")
        return None
    finally:
        db_session.remove()

if __name__ == "__main__":
    test_payment() 