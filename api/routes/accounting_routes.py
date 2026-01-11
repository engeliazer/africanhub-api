from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from database.db_connector import DBConnector
from applications.controllers.accounting_controller import AccountingController
from datetime import datetime
from typing import Optional

router = APIRouter(
    prefix="/api/accounting",
    tags=["accounting"]
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.get("/reconciliation-summary")
async def get_reconciliation_summary(
    start_date: str,
    end_date: str,
    token: str = Depends(oauth2_scheme)
):
    """Get reconciliation summary for a specific date range"""
    try:
        # Parse dates
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
            
        # Get summary from controller
        db = DBConnector().get_session()
        controller = AccountingController(db)
        summary = controller.get_reconciliation_summary(start_date, end_date)
        
        return {
            "status": "success",
            "data": summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    finally:
        db.close()

@router.get("/reconciliation-summary-details/{summary_id}")
async def get_reconciliation_summary_details(
    summary_id: str,
    start_date: str,
    end_date: str,
    token: str = Depends(oauth2_scheme)
):
    """Get detailed information for a specific reconciliation summary category"""
    try:
        # Parse dates
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
            
        # Get details from controller
        db = DBConnector().get_session()
        controller = AccountingController(db)
        details = controller.get_reconciliation_summary_details(summary_id, start_date, end_date)
        
        return {
            "status": "success",
            "data": details
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    finally:
        db.close() 