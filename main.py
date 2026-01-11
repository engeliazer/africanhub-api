from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from auth.routes import auth_routes
from public.routes import public_routes
from public.routes.sms_routes import router as sms_routes
from applications.routes.bank_statement_batch import router as bank_statement_batch_routes
from api.routes import accounting_routes

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_routes.router)
app.include_router(public_routes.router)
app.include_router(sms_routes)
app.include_router(bank_statement_batch_routes)
app.include_router(accounting_routes.router) 