"""
AWS Lambda handler for Order Sync System
Executes one sync cycle per Lambda invocation
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from service import OrderSyncService
import config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    AWS Lambda handler function
    Executes one complete sync cycle
    
    Returns:
        dict: Status and results of the sync cycle
    """
    
    request_id = context.request_id if context else 'local'
    logger.info(f"Lambda invocation started (request_id: {request_id})")
    
    service = OrderSyncService()
    results = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'request_id': request_id,
        'status': 'success',
        'results': {}
    }
    
    try:
        # Step 1: Poll source for orders (since yesterday, excluding tagged orders)
        since = datetime.now(timezone.utc) - timedelta(days=2)
        logger.info(f"Step 1: Polling source store (since {since.strftime('%Y-%m-%d %H:%M:%S')})")
        synced = service.poll_source_orders(since)
        results['results']['orders_synced'] = synced
        logger.info(f"Step 1 complete: {synced} new orders synced")
        
        # Step 2: Route pending orders to destinations
        logger.info("Step 2: Routing pending orders to destinations")
        sent = service.route_pending_orders()
        results['results']['orders_routed'] = sent
        logger.info(f"Step 2 complete: {sent} orders routed")
        
        # Step 3: Check for cancellations in destination
        logger.info("Step 3: Checking for cancellations in destination stores")
        cancelled = service.poll_cancellations()
        results['results']['orders_cancelled'] = cancelled
        logger.info(f"Step 3 complete: {cancelled} orders cancelled")
        
        # Step 4: Poll for tracking and sync back
        logger.info("Step 4: Syncing tracking information")
        tracked = service.poll_tracking()
        results['results']['tracking_updates'] = tracked
        logger.info(f"Step 4 complete: {tracked} tracking updates synced")
        
        logger.info(f"Lambda cycle complete successfully: {json.dumps(results['results'])}")
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {str(e)}", exc_info=True)
        results['status'] = 'error'
        results['error'] = str(e)
        results['error_type'] = type(e).__name__
        
        return {
            'statusCode': 500,
            'body': json.dumps(results)
        }
    finally:
        service.close()
        logger.info("Database connection closed")
    
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
