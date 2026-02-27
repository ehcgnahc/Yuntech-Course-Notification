import os
import aiomysql
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()
db_pool = None

async def lifespan(app: FastAPI):
    global db_pool
    print("伺服器啟動")
    db_pool = await aiomysql.create_pool(
        host=os.getenv('DB_HOST'),
        db=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        autocommit=True,
        minsize=1,
        maxsize=10
    )
    yield
    print("伺服器關閉")
    db_pool.close()
    await db_pool.wait_closed()

app = FastAPI(lifespan=lifespan)

class SubscribeRequest(BaseModel):
    email: str
    semester: str
    course: list[str]

@app.get("/subscriptions")
async def get_subscriptions(email):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                sql = """
                    SELECT c.semester, c.course_id, c.course_name, cs.is_notified, cs.created_at
                    FROM subscribers s
                    JOIN course_subscriptions cs ON s.id = cs.user_id
                    JOIN course c ON cs.course_pk_id = c.id
                    WHERE s.email = %s
                    ORDER BY cs.created_at DESC
                    """
                await cursor.execute(sql, (email,))
                results = await cursor.fetchall()
                
                if not results:
                    return {
                        "status": "success",
                        "message": "查無訂閱紀錄",
                        "subscriptions": []
                    }
                
                subscriptions = []
                for row in results:
                    subscriptions.append({
                        "semester": row[0],
                        "course_id": row[1],
                        "course_name": row[2],
                        "is_notified": bool(row[3]),
                        "subscribed_at": str(row[4])
                    })
                
                return {
                    "status": "success",
                    "message": f"找到{len(subscriptions)}筆訂閱紀錄",
                    "subscriptions": subscriptions
                }
            except Exception as e:
                print(f"Database error: {e}")
                raise HTTPException(status_code=500, detail="伺服器內部錯誤")

@app.post("/subscribe")
async def subscribe_course(request: SubscribeRequest):
    async with db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                await cursor.execute(
                    "INSERT IGNORE INTO subscribers (email, is_active) VALUES (%s, 1)", 
                    (request.email,)
                )
                await cursor.execute(
                    "SELECT id FROM subscribers WHERE email = %s", 
                    (request.email,)
                )
                user_row = await cursor.fetchone()
                user_id = user_row[0]

                added_count = 0
                already_count = 0
                not_found = []
                
                for course_id in request.course:
                    await cursor.execute(
                        "SELECT id FROM course WHERE semester = %s AND course_id = %s",
                        (request.semester, course_id)
                    )
                    course_row = await cursor.fetchone()
                    
                    if not course_row:
                        not_found.append(course_id)
                        continue

                    await cursor.execute(
                        """
                        INSERT IGNORE INTO course_subscriptions 
                        (user_id, course_pk_id, is_notified) 
                        VALUES (%s, %s, 0)
                        """,
                        (user_id, course_row[0])
                    )
                    
                    if cursor.rowcount == 1:
                        added_count += 1
                    else:
                        already_count += 1
                        
                return{
                    "status": "success", 
                    "message": f"成功訂閱課程 {request.course}",
                    "added_count": added_count,
                    "already_count": already_count,
                    "not_found": not_found
                }

            except HTTPException:
                raise
            except Exception as e:
                print(f"Database error: {e}")
                raise HTTPException(status_code=500, detail="伺服器內部錯誤")