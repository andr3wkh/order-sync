import json
from service import OrderSyncService
from datetime import datetime, timedelta, timezone
import config
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    logger.info("Lambda invocation started")
    service = OrderSyncService()
    results = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'status': 'success',
        'results': {}
    }
    try:
        since = datetime.now(timezone.utc) - timedelta(days=2)
        logger.info(f"Polling source store (since {since})")
        synced = service.poll_source_orders(since)
        results['results']['orders_synced'] = synced
        sent = service.route_pending_orders()
        results['results']['orders_routed'] = sent
        cancelled = service.poll_cancellations()
        results['results']['orders_cancelled'] = cancelled
        tracked = service.poll_tracking()
        results['results']['tracking_updates'] = tracked
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        results['status'] = 'error'
        results['error'] = str(e)
        return {'statusCode': 500, 'body': json.dumps(results)}
    finally:
        service.close()
    return {'statusCode': 200, 'body': json.dumps(results)}
