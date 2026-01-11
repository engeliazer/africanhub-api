import random
import string
from datetime import datetime
import json

def generate_transaction_id(prefix="OCPA"):
    """Generate a unique transaction ID"""
    # Format: PREFIX-RANDOMSTRING-TIMESTAMP
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{random_str}-{timestamp}"

def process_mock_payment(application_ids, payment_method, mobile_number, amount=0):
    """Generate mock payment data"""
    transaction_id = generate_transaction_id()
    payment_date = datetime.now().isoformat()
    
    # Generate mock application data
    applications = []
    total_amount = 0
    
    for app_id in application_ids:
        app_fee = random.uniform(50, 200)
        total_amount += app_fee
        
        applications.append({
            "id": app_id,
            "fee": round(app_fee, 2),
            "status": "pending",
            "payment_status": "paid",
            "subjects": [
                {
                    "id": random.randint(1, 5),
                    "name": f"Subject {random.randint(1, 10)}",
                    "fee": round(app_fee / 2, 2)
                },
                {
                    "id": random.randint(6, 10),
                    "name": f"Subject {random.randint(11, 20)}",
                    "fee": round(app_fee / 2, 2)
                }
            ]
        })
    
    # Use provided amount or calculated total
    if amount <= 0:
        amount = round(total_amount, 2)
    
    # Generate mock payment response
    payment_data = {
        "payment": {
            "id": random.randint(1000, 9999),
            "transaction_id": transaction_id,
            "amount": amount,
            "payment_method": payment_method,
            "payment_status": "paid",
            "payment_date": payment_date,
            "mobile_number": mobile_number,
            "description": f"Payment for applications {application_ids}",
            "created_at": payment_date,
            "updated_at": payment_date
        },
        "transaction_details": {
            "transaction_id": transaction_id,
            "payment_date": payment_date,
            "payment_status": "paid",
            "provider_reference": ''.join(random.choices(string.digits, k=10)),
            "confirmation_code": ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        },
        "applications": applications
    }
    
    return payment_data

def test_payment():
    """Test payment function with mock data"""
    # Mock payment request data
    application_ids = [1]
    payment_method = "M-Pesa"
    mobile_number = "255755344162"
    amount = 0
    
    # Process mock payment
    payment_data = process_mock_payment(application_ids, payment_method, mobile_number, amount)
    
    # Print payment details
    print("Payment processed successfully!")
    print(f"Transaction ID: {payment_data['payment']['transaction_id']}")
    print(f"Amount: {payment_data['payment']['amount']}")
    print(f"Payment Status: {payment_data['payment']['payment_status']}")
    print(f"Payment Date: {payment_data['payment']['payment_date']}")
    print(f"Provider Reference: {payment_data['transaction_details']['provider_reference']}")
    print(f"Confirmation Code: {payment_data['transaction_details']['confirmation_code']}")
    
    # Print application details
    print("\nApplication Details:")
    for app in payment_data['applications']:
        print(f"  Application ID: {app['id']}")
        print(f"  Fee: {app['fee']}")
        print(f"  Payment Status: {app['payment_status']}")
        print(f"  Subjects:")
        for subject in app['subjects']:
            print(f"    - {subject['name']} (ID: {subject['id']}, Fee: {subject['fee']})")
        print()
    
    # Save payment data to JSON file
    with open("mock_payment_response.json", "w") as f:
        json.dump(payment_data, f, indent=2)
    
    print("\nMock payment data saved to 'mock_payment_response.json'")
    
    return payment_data

if __name__ == "__main__":
    test_payment() 