#!/bin/bash

# Set B2 environment variables
export B2_BUCKET_NAME='dcrc-ocpac'
export B2_APPLICATION_KEY_ID='005f40fe139a1a50000000002'
export B2_APPLICATION_KEY='K005ZGmxoF1rcPS7DN6KX/HCQSAuEtU'

# Start Flask application with Gunicorn
python3 -m gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
