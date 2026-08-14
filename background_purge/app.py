import os
import psycopg2

def lambda_handler(event, context):
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        return {"statusCode": 500, "body": "DATABASE_URL not configured"}
    db_url = db_url.replace("sslmode=verify-full", "sslmode=require").replace("&sslrootcert=system", "").replace("?sslrootcert=system&", "?")
        
    try:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                # Delete memories that have been in the recycle bin for > 30 days
                cur.execute("""
                    DELETE FROM hive_context 
                    WHERE status = 'deleted' 
                      AND deleted_at < NOW() - INTERVAL '30 days';
                """)
                deleted_count = cur.rowcount
                conn.commit()
            
        return {
            "statusCode": 200,
            "body": f"Successfully purged {deleted_count} expired memories."
        }
    except Exception as e:
        print(f"Error purging memories: {e}")
        return {"statusCode": 500, "body": str(e)}
