import os
import aiomysql
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, EmailStr
from contextlib import asynccontextmanager
from dotenv import load_dotenv


load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("伺服器啟動")
    app.state.db_pool = await aiomysql.create_pool(
        host=os.getenv('DB_HOST'),
        db=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        cursorclass=aiomysql.DictCursor,
        autocommit=True,
        minsize=1,
        maxsize=10
    )
    yield
    print("伺服器關閉")
    app.state.db_pool.close()
    await app.state.db_pool.wait_closed()

app = FastAPI(lifespan=lifespan)

class SubscribeRequest(BaseModel):
    email: EmailStr
    semester: str
    course_ids: list[str]

@app.get("/subscriptions")
async def get_subscriptions(email: EmailStr, request: Request):
    async with request.app.state.db_pool.acquire() as conn:
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
                    return{
                        "status": "success",
                        "message": "查無訂閱紀錄",
                        "subscriptions": []
                    }
                
                subscriptions = []
                for row in results:
                    subscriptions.append({
                        "semester": row["semester"],
                        "course_id": row["course_id"],
                        "course_name": row["course_name"],
                        "is_notified": bool(row["is_notified"]),
                        "subscribed_at": str(row["created_at"])
                    })
                
                return{
                    "status": "success",
                    "message": f"找到{len(subscriptions)}筆訂閱紀錄",
                    "subscriptions": subscriptions
                }
            except Exception as e:
                print(f"Database error: {e}")
                raise HTTPException(status_code=500, detail="伺服器內部錯誤")

@app.post("/subscribe")
async def subscribe_course(body: SubscribeRequest, request: Request):
    async with request.app.state.db_pool.acquire() as conn:
        async with conn.cursor() as cursor:
            try:
                insert_sql = "INSERT IGNORE INTO subscribers (email, is_active) VALUES (%s, 1)"
                await cursor.execute(insert_sql, (body.email,))
                
                select_sql = "SELECT id FROM subscribers WHERE email = %s"
                await cursor.execute(select_sql, (body.email,))
                
                user_row = await cursor.fetchone()
                user_id = user_row["id"]

                if not body.course_ids:
                    clear_sql = """
                        DELETE cs FROM course_subscriptions cs
                        JOIN course c ON cs.course_pk_id = c.id
                        WHERE cs.user_id = %s AND c.semester = %s
                    """
                    await cursor.execute(clear_sql, (user_id, body.semester))
                    
                    return{
                        "status": "success",
                        "message": "已取消所有課程訂閱",
                        "added_count": 0,
                        "delete_count": cursor.rowcount,
                        "not_found": []
                    }

                format_strings = ','.join(['%s'] * len(body.course_ids))
                
                courses_sql = f"""
                    SELECT id, course_id 
                    FROM course 
                    WHERE semester = %s AND course_id IN ({format_strings})
                """
                await cursor.execute(courses_sql, [body.semester] + body.course_ids)
                
                valid_courses = await cursor.fetchall()
                course_id_to_pk = {row["course_id"]: row["id"] for row in valid_courses}
                target_pk = set(course_id_to_pk.values())
                not_found = [cid for cid in body.course_ids if cid not in course_id_to_pk]
                
                current_subscriptions_sql = """
                    SELECT cs.course_pk_id 
                    FROM course_subscriptions cs
                    JOIN course c ON cs.course_pk_id = c.id
                    WHERE cs.user_id = %s AND c.semester = %s
                """
                await cursor.execute(current_subscriptions_sql, (user_id, body.semester))
                
                current_pk = set(row["course_pk_id"] for row in await cursor.fetchall())
                add_pk = target_pk - current_pk
                delete_pk = current_pk - target_pk
                
                added_count = 0
                delete_count = 0
                
                if delete_pk:
                    delete_format = ','.join(['%s'] * len(delete_pk))
                    delete_subscriptions_sql = f"""
                        DELETE cs FROM course_subscriptions cs
                        WHERE cs.user_id = %s AND cs.course_pk_id IN ({delete_format})
                    """
                    await cursor.execute(delete_subscriptions_sql, [user_id] + list(delete_pk))
                    delete_count = cursor.rowcount
                
                if add_pk:
                    insert_subscriptions_sql = """
                        INSERT IGNORE INTO course_subscriptions (user_id, course_pk_id, is_notified) 
                        VALUES (%s, %s, 0)
                    """
                    await cursor.executemany(insert_subscriptions_sql, [(user_id, pk) for pk in add_pk])
                    added_count = cursor.rowcount
                        
                return{
                    "status": "success", 
                    "message": f"成功訂閱課程 {body.course_ids}",
                    "added_count": added_count,
                    "delete_count": delete_count,
                    "not_found": not_found
                }

            except HTTPException:
                raise
            except Exception as e:
                print(f"Database error: {e}")
                raise HTTPException(status_code=500, detail="伺服器內部錯誤")