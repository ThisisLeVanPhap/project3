UPDATE purchase_requests
SET status = 'PROCESSING'
WHERE status = 'CONTACTED';
