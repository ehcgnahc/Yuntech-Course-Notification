import os
import math
import asyncio
import aiomysql
from dotenv import load_dotenv
from send_email import send_email

async def notification(queue: asyncio.Queue):
    load_dotenv()
    pool = await aiomysql.create_pool(
        host=os.getenv('DB_HOST'),
        db=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    
    while True:
        info = await queue.get()
        targetSemester, course_ID, course_name, course_type, current_students, max_limit = info
        
        try:
            if current_students is None:
                continue
            
            current_students = int(current_students)
            max_limit = math.inf if max_limit is None else int(max_limit)
            
            if current_students >= max_limit:
                continue
            
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    sql = """
                        SELECT sub.email, cs.id AS sub_id
                        FROM subscribers sub
                        JOIN course_subscriptions cs ON sub.id = cs.user_id
                        JOIN course c ON c.id = cs.course_pk_id
                        WHERE c.course_id = %s 
                            AND c.semester = %s 
                            AND cs.is_notified = 0 
                            AND sub.is_active = 1
                    """
                    await cursor.execute(sql, (course_ID, targetSemester))
                    results = await cursor.fetchall()
                    
                    if not results:
                        continue
                    
                    notified_ids = []
                    for email, sub_id in results:
                        await send_email(email, info)
                        notified_ids.append(sub_id)
                    
                    if notified_ids:
                        format_strings = ','.join(['%s'] * len(notified_ids))
                        update_sql = f"UPDATE course_subscriptions SET is_notified = 1 WHERE id IN ({format_strings})"
                        await cursor.execute(update_sql, tuple(notified_ids))
                        await conn.commit()
        except Exception as e:
            print(f"Error processing notification for {course_ID}: {e}")
        finally:
            queue.task_done()