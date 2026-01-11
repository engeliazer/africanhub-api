import os
import logging
from celery import Celery
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')

# Build Redis URL with optional password authentication
if REDIS_PASSWORD:
    REDIS_URL = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0'
else:
    REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'

# Create Celery instance
celery = Celery('ocpac',
                broker=REDIS_URL,
                backend=REDIS_URL)

# Celery configuration
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour (3600 seconds) for large video processing
    task_soft_time_limit=3500,  # 58 minutes (soft limit before hard timeout)
    worker_prefetch_multiplier=1,
    worker_max_memory_per_child=1500000,  # 1.5GB to handle 1200MB videos
    worker_max_tasks_per_child=5,  # Reduced to prevent memory issues
    task_routes={
        'tasks.convert_video_to_hls': {'queue': 'video_processing'},
        'tasks.migrate_hls_to_b2': {'queue': 'video_processing'},
    },
    task_queues={
        'video_processing': {
            'exchange': 'video_processing',
            'routing_key': 'video_processing',
            'queue_arguments': {
                'x-max-length': 50,  # Reduced queue length for larger videos
                'x-overflow': 'reject-publish'  # Reject new tasks when queue is full
            }
        }
    },
    task_default_queue='video_processing',
    task_default_exchange='video_processing',
    task_default_routing_key='video_processing',
    worker_send_task_events=True,
    task_send_sent_event=True,
    event_queue_ttl=5.0,
    event_queue_expires=60.0,
    worker_pool_restarts=True,
    worker_pool='prefork',  # Use prefork pool for better task isolation
    worker_concurrency=2,  # Allow 2 concurrent tasks
    task_acks_late=True,  # Only acknowledge task after completion
    task_reject_on_worker_lost=True,  # Requeue task if worker dies
    task_default_retry_delay=60,  # Wait 60 seconds before retrying
    task_max_retries=3,  # Maximum number of retries
    worker_enable_remote_control=True,  # Enable remote control for better monitoring
    worker_state_db='worker_state.db',  # Persist worker state
    task_compression='gzip',  # Compress task messages
    task_default_rate_limit='10/m',  # Rate limit tasks per minute
    task_default_priority=5,  # Default task priority (0-9, 0 being highest)
    task_queue_max_priority=10,  # Enable priority queue
    task_ignore_result=False,  # Store task results
    task_store_errors_even_if_ignored=True,  # Store errors even if result is ignored
    task_publish_retry=True,  # Retry publishing tasks
    task_publish_retry_policy={
        'max_retries': 3,
        'interval_start': 0,
        'interval_step': 0.2,
        'interval_max': 0.5,
    }
)

# Import tasks module to ensure tasks are registered
logger.info("Registering tasks...")
import tasks_streamlined
import tasks_migration
logger.info("Tasks registered successfully")

# Export the Celery instance as the default export of the module
__all__ = ['celery'] 