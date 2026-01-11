"""
Test script to directly check application statuses
"""
from applications.controllers.applications_controller import ApplicationsController
from database.db_connector import db_session

def test_get_applications():
    """Test retrieving applications with different statuses"""
    try:
        controller = ApplicationsController(db_session)
        
        # Get all applications
        applications = controller.get_applications()
        
        print(f"Found {len(applications)} applications")
        for app in applications:
            print(f"Application ID: {app['id']}")
            print(f"  Status: {app['status']}")
            print(f"  Payment Status: {app['payment_status']}")
            print("")
            
        # Count applications by status
        statuses = {}
        for app in applications:
            status = app['status']
            if status not in statuses:
                statuses[status] = 0
            statuses[status] += 1
            
        print("Applications by status:")
        for status, count in statuses.items():
            print(f"  {status}: {count}")
            
        # Count applications by payment status
        payment_statuses = {}
        for app in applications:
            status = app['payment_status']
            if status not in payment_statuses:
                payment_statuses[status] = 0
            payment_statuses[status] += 1
            
        print("Applications by payment status:")
        for status, count in payment_statuses.items():
            print(f"  {status}: {count}")
    finally:
        db_session.remove()

if __name__ == "__main__":
    test_get_applications() 